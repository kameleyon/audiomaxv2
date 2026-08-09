#!/usr/bin/env python3
"""
SPIKE A, step 1 — generate TTS audio for the fixtures.

This is the input to the measurement, not the measurement. It exists as its own
step because the audio must be generated ONCE and reused: re-synthesizing between
transcription runs would mean comparing two engines against two different audio
files, which measures nothing.

COST DISCIPLINE (owner's standing rule): `--one` synthesizes a SINGLE fixture and
stops, so the real per-call cost can be read off the provider dashboard before
anything is scaled. Do not remove that flag.

Providers per spec 3.5:
  en  -> Lemonfox
  es, fr -> Gemini via OpenRouter (primary), direct Google (fallback) -- ADR-0003
"""
import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)


def load_env() -> dict:
    """Read repo-root .env. Never printed, never logged."""
    env = {}
    p = ROOT.parent.parent / ".env"
    if not p.exists():
        sys.exit("no .env at repo root -- SPIKE A needs provider credentials")
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def post(url: str, body: dict, headers: dict, timeout: int = 180) -> bytes:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def synth_lemonfox(text: str, voice: str, key: str) -> bytes:
    return post(
        "https://api.lemonfox.ai/v1/audio/speech",
        {"input": text, "voice": voice.lower(), "response_format": "wav"},
        {"Authorization": f"Bearer {key}"},
    )


def wav_wrap(pcm: bytes, rate: int = 24000, ch: int = 1, bits: int = 16) -> bytes:
    """Wrap headerless PCM in a minimal RIFF/WAVE container."""
    import struct
    ba = ch * bits // 8
    hdr = (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, ch, rate, rate * ba, ba, bits) + b"data" + struct.pack("<I", len(pcm)))
    return hdr + pcm


def synth_openrouter(text: str, voice: str, key: str) -> bytes:
    """
    Gemini TTS via OpenRouter -- the PRIMARY path per ADR-0003.

    NOTE the constraint-2 problem this makes concrete: motionmax falls back to
    direct Google on failure with only a console.warn. audiomax may not copy that
    shape (CLAUDE.md constraint 2 -- no fallback launch). So this function does
    NOT fall back. It fails loudly and the spike records which path answered.
    """
    raw = post(
        "https://openrouter.ai/api/v1/audio/speech",
        {"model": "google/gemini-3.1-flash-tts-preview", "input": text, "voice": voice, "response_format": "pcm"},
        {"Authorization": f"Bearer {key}", "HTTP-Referer": "https://audiomax.ai"},
    )
    # SPIKE A finding: Gemini TTS via OpenRouter accepts ONLY response_format="pcm".
    # It returns HEADERLESS PCM, so it must be wrapped before any tool that reads
    # audio containers will touch it. 24 kHz mono s16le is Gemini's documented
    # output and matches what the reference stack assumes.
    if raw[:4] == b"RIFF" or raw[:3] == b"ID3":
        return raw
    if raw[:1] not in (b"{", b"["):
        return wav_wrap(raw)
    try:
        j = json.loads(raw)
    except Exception:
        return raw
    import base64
    for k in ("audio", "data", "b64_json"):
        if k in j:
            return base64.b64decode(j[k])
    raise RuntimeError(f"unrecognised OpenRouter TTS response: {list(j)[:6]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", metavar="LANG", help="synthesize ONE language and stop (cost probe)")
    ap.add_argument("--lang", action="append", help="restrict to these languages")
    a = ap.parse_args()

    env = load_env()
    fx = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))["languages"]
    langs = [a.one] if a.one else (a.lang or list(fx))

    manifest = []
    for lang in langs:
        if lang not in fx:
            sys.exit(f"no fixture for {lang!r} -- supported: {list(fx)}")
        spec = fx[lang]
        dest = OUT / (f"{lang}.wav" if spec["provider"] == "lemonfox" else f"{lang}.wav")
        t0 = time.time()
        try:
            if spec["provider"] == "lemonfox":
                audio = synth_lemonfox(spec["text"], spec["voice"], env["LEMONFOX_API_KEY"])
            else:
                audio = synth_openrouter(spec["text"], spec["voice"], env["OPENROUTER_API_KEY"])
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            print(f"  {lang}: HTTP {e.code} from {spec['provider']} -- {body}")
            continue
        except Exception as e:
            print(f"  {lang}: {type(e).__name__}: {str(e)[:200]}")
            continue
        dest.write_bytes(audio)
        rec = {
            "lang": lang,
            "provider": spec["provider"],
            "voice": spec["voice"],
            "chars": len(spec["text"]),
            "bytes": len(audio),
            "seconds_elapsed": round(time.time() - t0, 1),
            "path": str(dest.name),
        }
        manifest.append(rec)
        print(f"  {lang}: {len(audio)} bytes via {spec['provider']} in {rec['seconds_elapsed']}s -> {dest.name}")
        if a.one:
            print("\n  --one: STOPPING. Read the real cost off the provider dashboard")
            print("  before scaling. This is the owner's standing rule on paid APIs.")
            break

    (OUT / "tts-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nwrote {len(manifest)} file(s); manifest at out/tts-manifest.json")


if __name__ == "__main__":
    main()
