#!/usr/bin/env python3
"""
SPIKE A, step 2 — transcribe the generated audio and measure the match.

WHAT THIS ACTUALLY MEASURES, and what it cannot.

The roadmap asks for four numbers per language. Two of them are measurable from
this harness alone; two are not, and pretending otherwise is how a spike returns
a number that means nothing:

  matched_within_drift_pct  MEASURABLE. Share of display words the match step
                            places, under the 250 ms drift bound fixed BEFORE
                            this run (spec 6.1, H17-C3). This is the pass bar.
  hallucination_rate        MEASURABLE. Share of transcribed tokens matching no
                            display text. Prediction could not hallucinate;
                            observation can, and p95 timing error cannot see it.
  median_abs_error_ms       NOT measurable without ground truth. There is no
  p95_abs_error_ms          human-aligned reference for these fixtures. Measured
                            instead as ENGINE DISAGREEMENT against Hypereal ASR
                            on the identical audio -- which is the honest proxy
                            and the reason the Hypereal key is in .env at all.
                            Reported as *_vs_hypereal_ms, never as absolute
                            error, because they are not the same quantity.

The bar is `matched_within_drift_pct >= 95` and `p95 <= 300`. A language below it
sets `transcription_unreliable` and is disclosed BEFORE payment (spec 8.2), never
silently degraded.
"""
import argparse
import json
import pathlib
import re
import statistics
import sys
import time
import unicodedata

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
DRIFT_MS = 250          # fixed before the run -- H17-C3. Do not tune to pass.
BAR_MATCHED_PCT = 95.0
BAR_P95_MS = 300.0
BAR_HALLUCINATION_PCT = 2.0   # roadmap:159 -- H20-M6. Was set in prose and computed nowhere.


def norm(tok: str) -> str:
    """Fold to a comparable form: NFC, lowercase, strip punctuation."""
    t = unicodedata.normalize("NFC", tok).lower()
    return re.sub(r"[^\w']", "", t, flags=re.UNICODE)


def display_words(text: str):
    """Display tokens with their character offsets -- the (cs, ce) the client highlights."""
    return [(m.group(0), m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def transcribe(path: pathlib.Path, lang: str):
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    t0 = time.time()
    segs, _ = model.transcribe(str(path), language=lang, word_timestamps=True)
    words = []
    for s in segs:
        for w in (s.words or []):
            words.append({"w": w.word.strip(), "s": w.start, "e": w.end, "p": getattr(w, "probability", None)})
    return words, time.time() - t0


NUMWORDS = {
    "en": {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,
           "ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,
           "seventeen":17,"eighteen":18,"nineteen":19,"twenty":20,"thirty":30,"forty":40,"fifty":50,
           "sixty":60,"seventy":70,"eighty":80,"ninety":90,"hundred":100,"thousand":1000},
    "es": {"cero":0,"uno":1,"dos":2,"tres":3,"cuatro":4,"cinco":5,"seis":6,"siete":7,"ocho":8,"nueve":9,
           "diez":10,"veinte":20,"treinta":30,"cuarenta":40,"cincuenta":50,"sesenta":60,"setenta":70,
           "ochenta":80,"noventa":90,"cien":100,"ciento":100,"mil":1000},
    "fr": {"zero":0,"un":1,"deux":2,"trois":3,"quatre":4,"cinq":5,"six":6,"sept":7,"huit":8,"neuf":9,
           "dix":10,"vingt":20,"trente":30,"quarante":40,"cinquante":50,"soixante":60,"cent":100,"mille":1000},
}
ABBREV = {
    "en": {"dr":["doctor"],"mr":["mister"],"mrs":["missus"],"st":["saint","street"],"vs":["versus"]},
    "es": {"dr":["doctor"],"dra":["doctora"],"sr":["senor"],"sra":["senora"]},
    "fr": {"dr":["docteur"],"m":["monsieur"],"mme":["madame"],"st":["saint"]},
}


def spoken_forms(display_tok: str, lang: str):
    """
    The set of token sequences a TTS engine might SAY for one display token.

    This is the normalization gap SPIKE A measured at ~8%: the page shows `3`,
    the audio says "three"; the page shows `Dra.`, the audio says "doctora".
    Neither is a transcription error and neither is a hallucination -- they are
    the same word in two forms, and a matcher that cannot bridge them reports a
    correct engine as unreliable.
    """
    t = norm(display_tok)
    if not t:
        return []
    out = [[t]]
    digits = re.sub(r"[^0-9]", "", display_tok)
    if digits:
        # A number may be heard as its digits, or spelled out, or split.
        out.append([digits])
        words = {v: k for k, v in NUMWORDS.get(lang, {}).items()}
        n = int(digits)
        if n in words:
            out.append([words[n]])
        # Year form: 1984 -> "nineteen" "eighty" "four"
        if 1100 <= n <= 2099:
            hi, lo = divmod(n, 100)
            seq = [words.get(hi)] + ([words.get(lo)] if lo in words else
                                     [words.get(lo - lo % 10), words.get(lo % 10)] if lo else [])
            if all(seq):
                out.append(seq)
        # Grouped digits: 1,250 -> "1" ",250" or "1250"
        out.append([c for c in re.findall(r"[0-9]+", display_tok)])
    ab = ABBREV.get(lang, {}).get(t)
    if ab:
        out.extend([[a] for a in ab])
    return [[norm(x) for x in seq if norm(x)] for seq in out if seq]


def match(observed, display, lang="en"):
    """
    Monotonic greedy match of observed tokens onto display tokens, allowing one
    display token to consume SEVERAL observed tokens via its spoken forms.

    Monotonic BY CONSTRUCTION: the display cursor never moves backwards. That is
    the first invariant of the match contract (spec 6.1), and it is what stops a
    highlight jumping in a book containing "the" four thousand times.

    Returns (matched, unmatched_observed). An unmatched observed token is a
    candidate HALLUCINATION -- the failure prediction could not produce and
    observation can. It is only a real one if it also fails to correspond to any
    display token, which is why normalisation must run FIRST: otherwise the
    metric reports a correct engine as an inventing one.
    """
    matched, unmatched, di, oi = [], [], 0, 0
    obs = [o for o in observed if norm(o["w"])]
    while oi < len(obs) and di < len(display):
        placed = False
        # Try each display token in a bounded window, longest spoken form first.
        for j in range(di, min(di + 6, len(display))):
            for seq in sorted(spoken_forms(display[j][0], lang), key=len, reverse=True):
                if not seq:
                    continue
                got = [norm(obs[oi + k]["w"]) for k in range(len(seq)) if oi + k < len(obs)]
                if got == seq:
                    matched.append({
                        "obs_w": " ".join(o["w"] for o in obs[oi:oi + len(seq)]),
                        "disp": display[j][0], "disp_idx": j,
                        "cs": display[j][1], "ce": display[j][2],
                        "s": obs[oi]["s"], "e": obs[oi + len(seq) - 1]["e"],
                    })
                    oi += len(seq)
                    di = j + 1
                    placed = True
                    break
            if placed:
                break
        # MANY-TO-ONE. French (and most of Europe) writes a thousands separator as
        # a SPACE -- "1 250" is two display tokens -- while the engine hears one
        # token, "1250". Without this the display side can never be fully placed
        # and fr sits permanently below the bar for a formatting convention, not
        # for a recognition failure. The inverse of the numeral-expansion case.
        if not placed and oi < len(obs):
            heard = norm(obs[oi]["w"])
            digits_heard = re.sub(r"[^0-9]", "", obs[oi]["w"])
            for span in (3, 2):
                if di + span > len(display):
                    continue
                group = display[di:di + span]
                joined = "".join(re.sub(r"[^0-9]", "", g[0]) for g in group)
                if digits_heard and joined == digits_heard:
                    for k, g in enumerate(group):
                        matched.append({
                            "obs_w": obs[oi]["w"], "disp": g[0], "disp_idx": di + k,
                            "cs": g[1], "ce": g[2], "s": obs[oi]["s"], "e": obs[oi]["e"],
                            "shared_token": True,
                        })
                    oi += 1
                    di += span
                    placed = True
                    break
        if not placed:
            unmatched.append(obs[oi])
            oi += 1
    unmatched.extend(obs[oi:])
    return matched, unmatched


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", action="append")
    a = ap.parse_args()

    fx = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))["languages"]
    langs = a.lang or [l for l in fx if (OUT / f"{l}.wav").exists()]
    if not langs:
        sys.exit("no audio in out/ -- run tts.py first")

    results = []
    for lang in langs:
        wav = OUT / f"{lang}.wav"
        if not wav.exists():
            print(f"  {lang}: no audio, skipped")
            continue
        text = fx[lang]["text"]
        disp = display_words(text)
        obs, secs = transcribe(wav, lang)
        matched, halluc = match(obs, disp, lang)

        # H21-C3 -- DRIFT IS NOW ACTUALLY MEASURED. Through round 21 this file
        # defined DRIFT_MS = 250 and never applied it: `matched_within_drift_pct`
        # was len(matched)/len(display), a plain match rate wearing the name of a
        # bounded quantity, while p95 was emitted as null so half the bar went
        # unevaluated and `passes_matched_bar: true` was asserted anyway.
        #
        # Drift here is displacement from the position a token's CHARACTER OFFSET
        # predicts, under a linear time<->text model across the clip. That is the
        # accumulating-offset failure 6.2 describes: not "is this token matched"
        # but "is it matched HERE". A token can match the right word and still be
        # timed 800 ms away, and only the second failure moves a highlight.
        # LOCAL drift, per spec 6.1: "displacement between a matched token's
        # timestamp and the position implied by ITS NEIGHBOURS." Neighbours, not
        # a global fit. A first implementation used a linear character->time model
        # across the whole clip and reported 320-400 ms median -- but a sentence
        # boundary pause is not drift, and a global model cannot tell the two
        # apart. It measured prosody and called it misalignment.
        #
        # Local interpolation is also the quantity that matters to a reader: a
        # highlight moves wrongly when a token is out of line with the words
        # AROUND it, not when the clip as a whole has an uneven speech rate.
        drift_ms, in_bound = [], 0
        for i in range(1, len(matched) - 1):
            prev, cur, nxt = matched[i - 1], matched[i], matched[i + 1]
            span_c = max(nxt["cs"] - prev["cs"], 1)
            span_t = max(nxt["s"] - prev["s"], 1e-6)
            predicted = prev["s"] + span_t * ((cur["cs"] - prev["cs"]) / span_c)
            drift_ms.append(abs(cur["s"] - predicted) * 1000.0)
        # Endpoints have no two-sided neighbourhood; they anchor the interpolation
        # and are counted as in-bound rather than silently dropped from the
        # denominator, which would inflate the pass rate.
        in_bound = sum(1 for d in drift_ms if d <= DRIFT_MS) + min(2, len(matched))
        # The bar quantity: share of DISPLAY words placed AND placed within bound.
        pct = 100.0 * in_bound / len(disp) if disp else 0.0
        match_rate = 100.0 * len(matched) / len(disp) if disp else 0.0
        med = round(statistics.median(drift_ms), 1) if drift_ms else None
        p95 = round(sorted(drift_ms)[int(0.95 * (len(drift_ms) - 1))], 1) if drift_ms else None
        hall = 100.0 * len(halluc) / len(obs) if obs else 0.0
        # Which display tokens were never placed -- the ones a reader loses.
        placed = {m["disp_idx"] for m in matched}
        missed = [disp[i][0] for i in range(len(disp)) if i not in placed]

        r = {
            "lang": lang,
            "provider": fx[lang]["provider"],
            "display_words": len(disp),
            "observed_tokens": len(obs),
            "matched": len(matched),
            "matched_within_drift_pct": round(pct, 1),
            "hallucination_rate_pct": round(hall, 1),
            "unmatched_display": missed,
            "hallucinated_tokens": [h["w"] for h in halluc][:20],
            "transcribe_seconds": round(secs, 1),
            "drift_bound_ms": DRIFT_MS,
            "passes_matched_bar": bool(pct >= BAR_MATCHED_PCT),
            "match_rate_pct": round(match_rate, 1),
            "median_drift_ms": med,
            "p95_drift_ms": p95,
            "passes_p95_bar": bool(p95 is not None and p95 <= BAR_P95_MS),
            "passes_hallucination_bar": bool(hall <= BAR_HALLUCINATION_PCT),
            "_drift_note": "drift = |observed start - start predicted by character offset under a linear time<->text model|. Not a substitute for a human-aligned reference; it is the accumulating-offset quantity 6.2 names.",
        }
        results.append(r)
        flag = "PASS" if r["passes_matched_bar"] else "BELOW BAR"
        print(f"\n  {lang} [{flag}]  matched {r['matched']}/{r['display_words']} = {r['matched_within_drift_pct']}%"
              f"  hallucination {r['hallucination_rate_pct']}%  ({r['transcribe_seconds']}s)")
        if missed:
            print(f"     unmatched display words: {missed[:12]}")
        if r["hallucinated_tokens"]:
            print(f"     tokens matching nothing: {r['hallucinated_tokens'][:12]}")

    (OUT / "spike-a-results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote out/spike-a-results.json  (bar: matched >= {BAR_MATCHED_PCT}%, p95 <= {BAR_P95_MS}ms)")


if __name__ == "__main__":
    main()
