#!/usr/bin/env python3
"""
SPIKE A, step 3 — measure timestamp accuracy against an INDEPENDENT engine.

WHY THIS EXISTS, and why the earlier number was wrong.

`measure.py` scored `matched_within_drift_pct` by predicting each word's start
from its neighbours' character offsets, under a constant-speech-rate assumption.
It reported 70.8% on English and did not move by a single point across `base`,
`small` and `medium` — a 10x parameter range. That flatness was the tell: a
recognition metric that ignores the recogniser is not measuring recognition.

The diagnosis, from per-word drift: every large value sits at a PAUSE.
"Section" scored 903 ms because it follows "1984." — the speaker stops, and a
character-offset predictor that knows nothing about prosody places the word
early and calls the engine wrong. The timestamps were right. The predictor was.

There is no human-annotated ground truth for these fixtures, so absolute
timestamp error is not measurable here and claiming it would be inventing a
number. What IS measurable is **agreement between two independent engines on the
same audio**: Hypereal ASR ($0.01/min, the vendor v14 rejected on price) against
self-hosted WhisperX. Where two engines that share no code agree on a word's
position, that position is probably right; where they disagree, something is.

This is the reference baseline the Hypereal key was provided for, and it is what
Jury's admissibility test calls leg (c) — an independent way to falsify our own
instrument.

COST: $0.01/min. The three fixtures total ~38 s = ~$0.006. `--one` still stops
after a single call so the real rate can be read off the dashboard first.
"""
import argparse
import base64
import json
import pathlib
import statistics
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
HYPEREAL_URL = "https://api.hypereal.cloud/v1/audio/generate"


def load_env() -> dict:
    env = {}
    p = ROOT.parent.parent / ".env"
    if not p.exists():
        sys.exit("no .env at repo root")
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def transcribe_hypereal(wav: pathlib.Path, key: str, language: str = "en") -> list:
    """Hypereal audio-asr — returns word-level timestamps."""
    b64 = base64.b64encode(wav.read_bytes()).decode()
    # Payload nests under `input` -- top-level `audio` returns 400 "audio is required".
    body = {"model": "audio-asr",
            "input": {"audio": f"data:audio/wav;base64,{b64}",
                      "language": language, "ignore_timestamps": False}}
    req = urllib.request.Request(
        HYPEREAL_URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        j = json.loads(r.read())
    # Words live inside `segments`, not at top level. Response keys are
    # status / outputUrl / jobId / creditsUsed / pollUrl / text / duration / segments.
    if isinstance(j.get("segments"), list):
        words = []
        for seg in j["segments"]:
            if isinstance(seg.get("words"), list):
                words.extend(seg["words"])
        if words:
            return words
        # HARD FAIL. This previously fell back to SEGMENT timings and returned
        # them as words -- so WhisperX word times were compared against Hypereal
        # segment times and reported as a word-sync measurement. Five different
        # Spanish voices scored an identical 82.4%, which is impossible if the
        # score depends on the voice, and the fallback is why. A reference that
        # cannot supply word timestamps is not a reference.
        raise RuntimeError(
            "Hypereal returned SEGMENT timings only (keys: "
            f"{list(j['segments'][0])}). It cannot serve as a word-level reference.")
    for path in (("words",), ("result", "words"), ("data", "words"), ("output", "words")):
        node = j
        for k in path:
            node = node.get(k) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, list) and node:
            return node
    raise RuntimeError(f"no word list; keys: {list(j)[:8]}; credits: {j.get('creditsUsed')}")


def norm(t: str) -> str:
    import re, unicodedata
    return re.sub(r"[^\w']", "", unicodedata.normalize("NFC", t).lower(), flags=__import__("re").UNICODE)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", metavar="LANG")
    ap.add_argument("--model", default="base")
    a = ap.parse_args()
    env = load_env()
    fx = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))["languages"]
    langs = [a.one] if a.one else list(fx)

    import measure as M
    import harness as H
    results, failures = [], []
    for lang in langs:
        wav = OUT / f"{lang}.wav"
        if not wav.exists():
            failures.append({"lang": lang, "stage": "audio", "error": "no wav"}); print(f"  {lang}: no audio"); continue
        t0 = time.time()
        try:
            hw = transcribe_hypereal(wav, env["HYPEREAL_API_KEY"], lang)
        except urllib.error.HTTPError as e:
            body = e.read()[:200].decode('utf-8','replace')
            failures.append({"lang": lang, "stage": "hypereal", "error": f"HTTP {e.code}: {body}"})
            print(f"  {lang}: HTTP {e.code} — {body}"); continue
        except Exception as e:
            failures.append({"lang": lang, "stage": "hypereal", "error": f"{type(e).__name__}: {str(e)[:300]}"})
            print(f"  {lang}: {type(e).__name__}: {str(e)[:180]}"); continue
        secs = time.time() - t0

        ww, _wall, _tm = M.transcribe(wav, lang, a.model, "int8", False)
        hi = [{"w": x.get("word", x.get("text", "")),
               "s": float(x.get("start", x.get("start_time", 0))),
               "e": float(x.get("end", x.get("end_time", x.get("start", 0))))} for x in hw]
        wi = [{"w": x["w"], "s": float(x["s"]), "e": float(x["e"])} for x in ww]
        # PAIRING (H26-M8). This block used to keep only tokens occurring exactly
        # once in BOTH streams. The reasoning was sound as far as it went -- a
        # greedy surface-form match will pair Whisper's first "en" with the
        # reference's second "en" and report an 840 ms disagreement between two
        # engines that agree -- but the cure had its own bias: it deletes every
        # short frequent function word, which are the hardest to place and the
        # ones a reader's eye is on most often, and keeps long content words
        # whose larger spans inflate overlap. Same defect, independently
        # implemented, in three files.
        #
        # Both streams are now mapped onto the DISPLAY TEXT and paired by display
        # index. That is positional, so it cannot mis-pair two occurrences of
        # "en", AND it keeps them both.
        display = H.display_units(fx[lang]["text"])
        w_units = H.units_from_asr(wi, display, lang)
        h_units = H.units_from_asr(hi, display, lang)
        deltas, overlaps, pairs = [], [], []
        for idx, a_, h in H.pair_by_display(w_units, h_units):
            deltas.append(abs(a_["s"] - h["s"]) * 1000.0)
            # SPAN OVERLAP -- the quantity that actually decides whether a
            # highlight is on the right word. A fixed 250 ms threshold is not
            # a word-sync measure: it ignores word DURATION and speech RATE,
            # so the same absolute error is harmless in slow speech and spans
            # two words in fast speech.
            lo, hiE = max(a_["s"], h["s"]), min(a_["e"], h["e"])
            dur = max(a_["e"] - a_["s"], 1e-6)
            overlaps.append(100.0 * max(0.0, hiE - lo) / dur)
            pairs.append((display[idx][0], round(a_["s"], 2), round(h["s"], 2)))
        if not deltas:
            failures.append({"lang": lang, "stage": "pair", "error": "no display token carried both streams"}); print(f"  {lang}: no common tokens between engines"); continue
        # DIAGNOSTIC (J-final): the largest disagreement has been the clip's LAST
        # word in every run, across 3 languages, 2 providers and 8 voices. If one
        # engine folds trailing silence into the final token's span, that single
        # token is a boundary artifact -- and on a 13-20 word fixture it is worth
        # 5-8 points, which is most of the spread being attributed to voices.
        # Report both so the claim is checkable rather than asserted.
        if len(deltas) > 2:
            last_w = pairs[-1][0]
            d_ex = deltas[:-1]
            within_ex = 100.0 * sum(1 for d in d_ex if d <= M.DRIFT_MS) / len(d_ex)
            p95_ex = sorted(d_ex)[int(0.95 * (len(d_ex) - 1))]
            print(f"     excl. final token '{last_w}': {within_ex:.1f}% within, p95 {p95_ex:.0f}ms"
                  f"   (final token delta {deltas[-1]:.0f}ms)")
        med = statistics.median(deltas)
        p95 = sorted(deltas)[int(0.95 * (len(deltas) - 1))]
        within = 100.0 * sum(1 for d in deltas if d <= M.DRIFT_MS) / len(deltas)
        ov_med = statistics.median(overlaps) if overlaps else 0.0
        ov_ok = 100.0 * sum(1 for o in overlaps if o >= 50.0) / len(overlaps) if overlaps else 0.0
        wps = len(wi) / max(wi[-1]["e"] - wi[0]["s"], 1e-6) if len(wi) > 1 else 0
        r = {"lang": lang, "words_per_sec": round(wps, 2),
             "median_span_overlap_pct": round(ov_med, 1),
             "words_overlapping_50pct": round(ov_ok, 1),
             "compared_words": len(deltas), "whisper_words": len(wi),
             "hypereal_words": len(hi), "median_delta_ms": round(med, 1),
             "p95_delta_ms": round(p95, 1), "agree_within_250ms_pct": round(within, 1),
             "hypereal_seconds": round(secs, 1), "whisper_model": a.model,
             "worst": sorted(pairs, key=lambda x: abs(x[1] - x[2]), reverse=True)[:3]}
        results.append(r)
        flag = "PASS" if ov_ok >= 95 else "BELOW BAR"
        print("")
        print(f"  {lang} [{flag}]  {len(deltas)} words | SPAN OVERLAP median {ov_med:.0f}%, {ov_ok:.0f}% of words overlap >=50% | rate {wps:.1f} w/s | (old abs-ms: {within:.1f}%)")
        if r["worst"]:
            print(f"     largest disagreements: {r['worst']}")
        if a.one:
            print("\n  --one: STOPPING. Check the Hypereal dashboard before scaling.")
            break

    # H26-m2, same lesson as wx.py. A run that produced nothing used to overwrite
    # the artifact with `[]`, which destroys the prior evidence AND is
    # indistinguishable from "measured nothing worth reporting". If this run
    # produced no rows, the previous ones are preserved verbatim and clearly
    # labelled as superseded-but-not-replaced, with the reason this run failed.
    dest = OUT / "spike-a-crossengine.json"
    if results:
        payload = {"ran": True, "results": results, "failures": failures}
    else:
        prior = json.loads(dest.read_text(encoding="utf-8")) if dest.exists() else None
        payload = {
            "ran": False, "results": [], "failures": failures,
            "preserved_prior_result": prior.get("results", prior) if isinstance(prior, dict) else prior,
            "_note": ("This run produced no rows. The prior result is PRESERVED, not "
                      "overwritten, and is NOT a measurement of the current audio -- the "
                      "audio has been corrected since it was written (H26-C1). It is also "
                      "not a WORD-LEVEL measurement: Hypereal returns SEGMENT timings only, "
                      "confirmed live on 2026-08-09 for all three languages, and the prior "
                      "rows were produced while this file still degraded to segment timings "
                      "and reported them as words. Any figure taken from `results` -- "
                      "including `agree_within_250ms_pct`, on which the fr voice lock rests "
                      "(fixtures.json:19) -- is a word-vs-SEGMENT comparison. Do not cite it "
                      "as word sync."),
        }
    H.write_json(dest, payload)
    print(f"\nwrote out/spike-a-crossengine.json  ran={payload['ran']}")


if __name__ == "__main__":
    main()
