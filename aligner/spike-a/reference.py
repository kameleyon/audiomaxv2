#!/usr/bin/env python3
"""
SPIKE A, step 3 (rebuilt) — timestamp accuracy against Lemonfox ASR.

Hypereal returns segment-level timings only, so it cannot be a word-level
reference; hypereal.py now fails loudly rather than degrading to segments.
Lemonfox's OpenAI-compatible endpoint returns real word timestamps with
start, end and a confidence score, so it is the reference here.

METRIC. Span overlap AND absolute start delta, both reported. Overlap decides
whether a highlight covers the same audio; the start delta is the quantity §6.1
actually bounds, and reporting only the first is how the bar got called
unmeasurable when the second was sitting in this file (H26-B1).

PAIRING (H26-M8). This file used to compare only tokens occurring exactly once
in BOTH streams. That rule deletes every short frequent function word -- `the`,
`de`, `a`, `les`, the hardest words to place and the ones a reader's eye is on
most often -- and keeps long content words, whose larger spans inflate overlap.
It also deleted every numeral, because one stream says `1984` and the other says
nineteen eighty-four. n fell to 19 of 24 and the sample was biased toward easy
words. Both streams are now mapped onto the DISPLAY TEXT and paired by display
index, which is positional and keeps everything (see harness.py).
"""
import argparse, io, json, pathlib, statistics, sys, urllib.request, uuid, re, unicodedata

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"

def env():
    d = {}
    for line in (ROOT.parent.parent / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); d[k.strip()] = v.strip()
    return d

def norm(t):
    return re.sub(r"[^\w']", "", unicodedata.normalize("NFC", t).lower(), flags=re.UNICODE)

LANGNAME = {"en": "english", "es": "spanish", "fr": "french"}

def lemonfox_words(wav, key, lang):
    bd = "----" + uuid.uuid4().hex
    p = []
    def f(n, v): p.append(f"--{bd}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n".encode())
    f("language", LANGNAME[lang]); f("response_format", "verbose_json")
    p.append(f"--{bd}\r\nContent-Disposition: form-data; name=\"timestamp_granularities[]\"\r\n\r\nword\r\n".encode())
    p.append(f"--{bd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode()
             + wav.read_bytes() + b"\r\n")
    p.append(f"--{bd}--\r\n".encode())
    req = urllib.request.Request("https://api.lemonfox.ai/v1/audio/transcriptions", data=b"".join(p),
        headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={bd}"})
    j = json.loads(urllib.request.urlopen(req, timeout=300).read())
    w = j.get("words")
    # The assertion the last instrument lacked.
    if not w or "end" not in w[0]:
        raise RuntimeError(f"reference returned no word-level timestamps; keys={list(j)}")
    return w

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="base"); a = ap.parse_args()
    sys.path.insert(0, str(ROOT))
    import measure as M
    import harness as H
    fx = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))["languages"]
    E = env(); out = []
    for lang, spec in fx.items():
        wav = OUT / f"{lang}.wav"
        if not wav.exists(): continue
        try:
            ref = lemonfox_words(wav, E["LEMONFOX_API_KEY"], lang)
        except Exception as e:
            print(f"  {lang}: {type(e).__name__}: {str(e)[:150]}"); continue
        display = H.display_units(spec["text"])
        ww, _wall, tm = M.transcribe(wav, lang, a.model, "int8", False)
        w_units = H.units_from_asr(ww, display, lang)
        r_units = H.units_from_asr(
            [{"w": x["word"], "s": float(x["start"]), "e": float(x["end"])} for x in ref],
            display, lang)
        pairs = H.pair_by_display(w_units, r_units)
        if not pairs: print(f"  {lang}: no comparable tokens"); continue
        sc = H.score_pairs(pairs, display)
        audio_s = H.wav_seconds(wav)
        rate = len(ww) / audio_s
        cov = 100.0 * len(pairs) / len(display)
        unpaired = [display[i][0] for i in range(len(display))
                    if i not in w_units or i not in r_units]
        flag = "PASS" if sc["pct_overlap_50"] >= 95 else "BELOW BAR"
        print(f"  {lang} [{flag}] {sc['words']}w ({cov:.0f}% of display) | overlap median "
              f"{sc['median_overlap_pct']:.0f}% | {sc['pct_overlap_50']:.0f}% >=50% | abs start-delta "
              f"median {sc['median_abs_error_ms']:.0f}ms p95 {sc['p95_abs_error_ms']:.0f}ms | "
              f"signed {sc['median_signed_start_delta_ms']:+.0f}ms | {rate:.1f} w/s")
        print(f"      worst: {sc['worst_tokens']}  unpaired: {unpaired}")
        out.append({"lang": lang, "voice": spec.get("voice"), "provider": spec.get("provider"),
                    **sc,
                    "display_words": len(display),
                    "display_coverage_pct": round(cov, 1),
                    "unpaired_display": unpaired,
                    "words_per_sec": round(rate, 2),
                    "audio_seconds": round(audio_s, 2),
                    "reference": "lemonfox-asr",
                    "engine": f"faster-whisper {a.model}",
                    **H.cost_block(cpu_seconds=tm["cpu_seconds"], audio_seconds=audio_s,
                                   load_seconds=tm["model_load_seconds"],
                                   wall_seconds=tm["wall_seconds"], threads=tm["cpu_threads"]),
                    "_pairing": ("positional on DISPLAY TOKEN INDEX via measure.match on both "
                                 "streams. No surface-form uniqueness filter, so function words "
                                 "and numerals are retained (H26-M8, H26-B2)."),
                    "_error_basis": ("median_abs_error_ms / p95_abs_error_ms are ENGINE "
                                     "DISAGREEMENT between faster-whisper and Lemonfox ASR on "
                                     "identical audio, NOT error against human ground truth. "
                                     "Agreement bounds the common error; it does not measure it.")})
    H.write_json(OUT / "spike-a-reference.json", out)
    print("\nwrote out/spike-a-reference.json")

if __name__ == "__main__":
    main()
