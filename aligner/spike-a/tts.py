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
  en     -> Lemonfox
  es, fr -> Fish Audio `s2-pro`

CORRECTED (J29-C3, in code). These four lines read *"es, fr -> Gemini via
OpenRouter (primary), direct Google (fallback) -- ADR-0003"* for four rounds
after every DOCUMENT was fixed. Gemini was only ever the Haitian Creole TTS
route; `ht` left scope on 2026-08-08 (ADR-0005) and the route left with it.
Rounds 29-31 corrected spec 3.5, CLAUDE.md constraint 7, the README, spec 11,
roadmap Phase 5 and the ADR-0003 banner, and nobody opened the script that makes
the calls -- the document-vs-implementation seam in its purest form.

TWO THINGS WERE WRONG HERE AND ONLY ONE OF THEM WAS THE COMMENT.

The dispatch below is DATA-DRIVEN off `fixtures.json:provider`, which has said
`fish` for `es` and `fr` since the owner's correction, so no wrong audio is
being generated today and no measurement on disk is affected. But the dispatch
ended in a bare `else` that sent ANY unrecognised provider string to Gemini via
OpenRouter. That is a live defect, not a stale comment: a retired route reachable
by DEFAULT, which is CLAUDE.md constraint 2 (no fallback launch) and constraint 7
(the user is told where their document goes) in executable form -- an unexpected
fixture would have sent document text to a vendor the subprocessor list does not
name. The route is deleted, not commented out, and the dispatch now REFUSES an
unknown provider.
"""
import argparse
import hashlib
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
sys.path.insert(0, str(ROOT))
import harness as H  # noqa: E402  (wav header repair + size-derived duration)


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


def synth_lemonfox(text: str, voice: str, key: str, timeout: int = 180) -> bytes:
    """The `en` route (spec 3.5).

    `timeout` is explicit because a CHAPTER-length payload renders for minutes,
    and the default 180 s was sized for the 10-second fixtures. A socket timeout
    on a TTS call is the worst failure shape available: the vendor has rendered
    the audio and BILLED for it, and the caller has nothing. Raising the ceiling
    for a long call is not a retry -- there is still exactly one call.
    """
    return post(
        "https://api.lemonfox.ai/v1/audio/speech",
        {"input": text, "voice": voice.lower(), "response_format": "wav"},
        {"Authorization": f"Bearer {key}"},
        timeout=timeout,
    )


def wav_wrap(pcm: bytes, rate: int = 24000, ch: int = 1, bits: int = 16) -> bytes:
    """Wrap headerless PCM in a minimal RIFF/WAVE container."""
    import struct
    ba = ch * bits // 8
    hdr = (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, ch, rate, rate * ba, ba, bits) + b"data" + struct.pack("<I", len(pcm)))
    return hdr + pcm


def synth_fish(text: str, ref_id: str, key: str) -> bytes:
    """
    Fish Audio s2-pro -- the `es`/`fr` path (spec 3.5). Header `model: s2-pro`,
    reference_id selects the voice. Mirrors the reference stack's call shape.
    """
    req = urllib.request.Request(
        "https://api.fish.audio/v1/tts",
        data=json.dumps({
            "text": text, "reference_id": ref_id, "format": "wav",
            "sample_rate": 44100, "normalize": True,
            "prosody": {"speed": 1, "normalize_loudness": True},
            "temperature": 0.8, "top_p": 0.8, "latency": "normal",
        }).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "model": "s2-pro"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


# THE GEMINI-VIA-OPENROUTER TTS ROUTE WAS HERE, AND IT IS DELETED.
#
# It was the Haitian Creole route and nothing else. `ht` left scope on
# 2026-08-08 and CLAUDE.md is explicit that it "is not deferred; it is out", so a
# live function that can reach that vendor is not dormant code -- it is an
# undisclosed subprocessor one dispatch mistake away, and the dispatch that could
# make the mistake was directly below it.
#
# Two findings are kept because deleting the code should not delete what it cost
# to learn:
#   - Gemini TTS via OpenRouter accepted ONLY `response_format="pcm"` and
#     returned HEADERLESS PCM (24 kHz mono s16le), so it had to be wrapped before
#     any tool that reads audio containers would touch it.
#   - The reference stack falls back to direct Google on failure with only a
#     console.warn. This file never copied that shape, on constraint 2. That
#     restraint is now moot for TTS and remains the rule for every other route.
#
# `wav_wrap` survives: `groundtruth.py` wraps headerless PCM from other sources.


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def manifest_row(path: pathlib.Path, **extra) -> dict:
    """
    One manifest row, always carrying the CONTENT HASH and the SIZE-DERIVED
    duration.

    Two gaps this closes. (1) The manifest recorded `bytes` and no hash, so the
    committed audio had no integrity anchor at all -- and the audio is the only
    route to independently re-check a measurement (J23-M5), which makes a hash
    the difference between evidence and a file that resembles evidence.
    (2) It recorded only the files the LAST invocation wrote, so after the
    holdout run it described three files while six were on disk.
    """
    raw = path.read_bytes()
    info = H.wav_info(path)
    return {
        "path": path.name, "bytes": len(raw), "sha256": sha256(raw),
        "seconds": round(info["seconds"], 2),
        "sample_rate": info["sample_rate"], "channels": info["channels"],
        "wav_header_length_bogus": info["header_length_bogus"],
        **extra,
    }


def write_manifest() -> list:
    """Describe EVERY wav in out/, not just the ones this invocation wrote."""
    rows = [manifest_row(p) for p in sorted(OUT.glob("*.wav"))]
    H.write_json(OUT / "tts-manifest.json", rows)
    return rows


def repair_headers() -> list:
    """
    H26-m1, applied to the audio already on disk. NO SYNTHESIS, NO API CALL.

    Fish `s2-pro` returns a streaming WAV whose data-chunk size is the sentinel
    0xFFFFFFFC -- 48,695 seconds for a ten-second clip. Fixing the writer helps
    the NEXT file; the six files already committed keep lying to every tool that
    reads a header until the eight bytes are rewritten. Samples are untouched,
    so this is a repair, not a re-render, and the audio stays the audio the
    published measurements were taken on.
    """
    changed = []
    for p in sorted(OUT.glob("*.wav")):
        raw = p.read_bytes()
        fixed = H.repair_wav_header(raw)
        if fixed != raw:
            before = H.wav_info(p)["header_declared_seconds"]
            p.write_bytes(fixed)
            changed.append({"path": p.name, "declared_seconds_before": round(before, 1),
                            "declared_seconds_after": round(H.wav_info(p)["header_declared_seconds"], 2),
                            "bytes_changed": sum(1 for x, y in zip(raw, fixed) if x != y)})
    return changed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", metavar="LANG", help="synthesize ONE language and stop (cost probe)")
    ap.add_argument("--lang", action="append", help="restrict to these languages")
    ap.add_argument("--repair-headers", action="store_true",
                    help="rewrite bogus WAV chunk sizes on existing audio (H26-m1). No API calls.")
    ap.add_argument("--manifest", action="store_true",
                    help="rebuild tts-manifest.json from out/*.wav with SHA-256. No API calls.")
    a = ap.parse_args()

    if a.repair_headers or a.manifest:
        if a.repair_headers:
            for c in repair_headers():
                print(f"  {c['path']}: header said {c['declared_seconds_before']}s -> "
                      f"{c['declared_seconds_after']}s ({c['bytes_changed']} bytes rewritten)")
        rows = write_manifest()
        print(f"\nwrote out/tts-manifest.json — {len(rows)} file(s), SHA-256 recorded")
        for r in rows:
            print(f"  {r['path']:20} {r['seconds']:>6.2f}s  {r['sha256'][:16]}…"
                  f"{'  HEADER STILL BOGUS' if r['wav_header_length_bogus'] else ''}")
        return

    env = load_env()
    ALL = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))
    fx = ALL["holdout"] if os.environ.get("HOLDOUT") else ALL["languages"]
    langs = [a.one] if a.one else (a.lang or list(fx))

    manifest = []
    for lang in langs:
        if lang not in fx:
            sys.exit(f"no fixture for {lang!r} -- supported: {list(fx)}")
        spec = fx[lang]
        dest = OUT / (f"{lang}-holdout.wav" if os.environ.get("HOLDOUT") else f"{lang}.wav")
        t0 = time.time()
        try:
            # EXHAUSTIVE, and it REFUSES rather than falling through. The bare
            # `else` that stood here routed every unrecognised provider string to
            # the retired Gemini/OpenRouter path -- a vendor the subprocessor
            # list does not name, reached by default, on document text. Refusing
            # is the only safe answer: the two providers below are the two spec
            # 3.5 routes, and a third value in `fixtures.json` is a typo or an
            # unreviewed decision, neither of which should reach a network call.
            if spec["provider"] == "lemonfox":
                audio = synth_lemonfox(spec["text"], spec["voice"], env["LEMONFOX_API_KEY"])
            elif spec["provider"] == "fish":
                audio = synth_fish(spec["text"], spec["reference_id"], env["FISH_AUDIO_API_KEY"])
            else:
                sys.exit(f"{lang}: fixtures.json names provider {spec['provider']!r}, which is "
                         f"not a spec 3.5 TTS route. The routes are 'lemonfox' (en) and 'fish' "
                         f"(es, fr). Nothing is synthesized and no text leaves this machine.")
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            print(f"  {lang}: HTTP {e.code} from {spec['provider']} -- {body}")
            continue
        except Exception as e:
            print(f"  {lang}: {type(e).__name__}: {str(e)[:200]}")
            continue
        # H26-m1 -- THE HEADER IS REPAIRED AT THE WRITER. Fish s2-pro streams its
        # response, so the data-chunk size it emits is the sentinel 0xFFFFFFFC:
        # 48,695 seconds declared for a ten-second clip. Every tool downstream
        # that reads a duration from the header -- realtime factor, cost per
        # audio-hour, drift per second -- was off by ~4,600x, and in the
        # flattering direction. Fixing it here means it is fixed once, for every
        # provider, before anything else touches the file.
        audio = H.repair_wav_header(audio)
        dest.write_bytes(audio)
        rec = manifest_row(dest, lang=lang, provider=spec["provider"], voice=spec["voice"],
                           chars=len(spec["text"]), seconds_elapsed=round(time.time() - t0, 1))
        manifest.append(rec)
        print(f"  {lang}: {rec['bytes']} bytes / {rec['seconds']}s via {spec['provider']} "
              f"in {rec['seconds_elapsed']}s -> {dest.name}  sha {rec['sha256'][:12]}…")
        if a.one:
            print("\n  --one: STOPPING. Read the real cost off the provider dashboard")
            print("  before scaling. This is the owner's standing rule on paid APIs.")
            break

    # Rebuild from disk, not from this invocation: the manifest describes the
    # corpus, and a run that synthesizes three files must not silently retire
    # the three it did not touch.
    rows = write_manifest()
    print(f"\nsynthesized {len(manifest)} file(s); manifest covers {len(rows)} at out/tts-manifest.json")


if __name__ == "__main__":
    main()
