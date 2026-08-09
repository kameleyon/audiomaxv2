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


CPU_THREADS = 4          # pinned so cpu-seconds-per-audio-second is reproducible
_MODEL_CACHE = {}
_LOAD_SECONDS = {}


def load_asr(model_size: str = "base", ctype: str = "int8"):
    """
    Construct the model ONCE per process and record what construction cost.

    H26-M6. Model load is a fixed cost paid once per worker and amortised to
    nothing across a 9-hour book; charging it to an 11-second clip is how a
    0.9x-realtime decoder reports 1.3x. Every prior run rebuilt the model inside
    the timing loop, so every timing on disk includes it and none says so.
    """
    key = (model_size, ctype)
    if key not in _MODEL_CACHE:
        from faster_whisper import WhisperModel
        t0 = time.time()
        _MODEL_CACHE[key] = WhisperModel(model_size, device="cpu", compute_type=ctype,
                                         cpu_threads=CPU_THREADS)
        _LOAD_SECONDS[key] = time.time() - t0
    return _MODEL_CACHE[key], _LOAD_SECONDS[key]


def transcribe(path: pathlib.Path, lang: str, model_size: str = "base", ctype: str = "int8", vad: bool = False):
    """
    The FIRST run used base/int8/no-VAD -- the cheapest configuration there is.
    It failed the tail. That is not the same result as "the approach fails", and
    reporting it as though it were would be the same error as citing a 100% match
    rate: a number produced by the instrument rather than by the thing measured.
    Only the model, precision and VAD move here. The 250 ms bound, the fixtures
    and the language scope are fixed and untouched.

    Returns (words, wall_seconds, timing) where `timing` carries the amortised
    decode cost separately from the one-off model load, plus CPU-seconds -- which
    is the quantity a compute bill is denominated in, and the only one that
    survives a change of machine.
    """
    model, load_s = load_asr(model_size, ctype)
    t0, c0 = time.time(), time.process_time()
    segs, _ = model.transcribe(str(path), language=lang, word_timestamps=True, vad_filter=vad)
    words = []
    for s in segs:
        for w in (s.words or []):
            words.append({"w": w.word.strip(), "s": w.start, "e": w.end, "p": getattr(w, "probability", None)})
    wall, cpu = time.time() - t0, time.process_time() - c0
    return words, wall, {"wall_seconds": wall, "cpu_seconds": cpu, "model_load_seconds": load_s,
                         "cpu_threads": CPU_THREADS}


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
                        # J22-M2 -- which tokens needed the normalizer to be
                        # placed at all. `expect_hard` in fixtures.json is the
                        # falsification condition for a 100% match rate and was
                        # evaluated by nothing; it cannot be evaluated without
                        # this bit, because "matched" alone does not distinguish
                        # a numeral bridged by spoken_forms from one the ASR
                        # happened to write back as digits.
                        "via_normalizer": seq != [norm(display[j][0])],
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
                            "shared_token": True, "via_normalizer": True,
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
    # Imported HERE, not at module scope: harness.py imports this module for
    # display_words/match/norm, so a top-level import would be circular.
    global H
    import harness as H

    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", action="append")
    ap.add_argument("--model", default="base")
    ap.add_argument("--ctype", default="int8")
    ap.add_argument("--vad", action="store_true")
    ap.add_argument("--tag", default="")
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
        # H26-m1: duration from FILE SIZE. The Fish es/fr headers declare 48,695
        # seconds; a realtime factor computed from those is off by ~4,600x.
        info = H.wav_info(wav)
        audio_s = info["seconds"]
        obs, secs, tm = transcribe(wav, lang, a.model, a.ctype, a.vad)
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
        #
        # H26-m4 -- THE PAUSE CONFOUND, and what is and is not done about it.
        # Interpolating on CHARACTER offsets assumes characters are consumed at a
        # constant rate between the two neighbours. A full stop between them adds
        # time and no characters, so the residual it produces is prosody, not
        # misalignment. Going local narrowed the window; it did not remove the
        # confound. Every triple that spans sentence-final punctuation is
        # therefore marked INADMISSIBLE and reported separately, and the residual
        # confound in what remains (commas, clause breaks, breath) is stated in
        # the emitted record rather than left for a reader to infer:
        # 70-79% is a FLOOR on the true figure, not a verdict on it.
        drift_ms, drift_interior = [], []
        for i in range(1, len(matched) - 1):
            prev, cur, nxt = matched[i - 1], matched[i], matched[i + 1]
            span_c = max(nxt["cs"] - prev["cs"], 1)
            span_t = max(nxt["s"] - prev["s"], 1e-6)
            predicted = prev["s"] + span_t * ((cur["cs"] - prev["cs"]) / span_c)
            d = abs(cur["s"] - predicted) * 1000.0
            drift_ms.append(d)
            if not H.SENT_END.search(text[prev["cs"]:nxt["cs"]]):
                drift_interior.append(d)
        #
        # J22-M4 -- ENDPOINTS ARE NO LONGER CREDITED BY FIAT. The previous form
        # was `sum(...) + min(2, len(matched))`: the first and last matched token
        # have no two-sided neighbourhood, so their drift is unmeasured, and they
        # were added to the numerator as though measured and passing. On a
        # 24-word clip that is a free 8.3 points, always in the permissive
        # direction, and it is what carried 68.2/75.0/77.3 to 70.8/77.3/79.2.
        # The BAR is now the measured-only figure. The credited figure is kept as
        # a labelled UPPER bound so the two are never confused again.
        in_bound = sum(1 for d in drift_ms if d <= DRIFT_MS)
        pct = 100.0 * in_bound / len(disp) if disp else 0.0
        pct_credited = 100.0 * (in_bound + min(2, len(matched))) / len(disp) if disp else 0.0
        match_rate = 100.0 * len(matched) / len(disp) if disp else 0.0
        med = round(statistics.median(drift_ms), 1) if drift_ms else None
        p95 = round(sorted(drift_ms)[int(0.95 * (len(drift_ms) - 1))], 1) if drift_ms else None
        med_i = round(statistics.median(drift_interior), 1) if drift_interior else None
        p95_i = round(sorted(drift_interior)[int(0.95 * (len(drift_interior) - 1))], 1) if drift_interior else None
        hall = 100.0 * len(halluc) / len(obs) if obs else 0.0
        # Which display tokens were never placed -- the ones a reader loses.
        placed = {m["disp_idx"] for m in matched}
        missed = [disp[i][0] for i in range(len(disp)) if i not in placed]

        resolved = {m["disp_idx"]: m for m in matched}
        hard_rows = H.hard_token_report(fx[lang], disp, resolved, lang)

        r = {
            "lang": lang,
            "provider": fx[lang]["provider"],
            "display_words": len(disp),
            "observed_tokens": len(obs),
            "matched": len(matched),
            "matched_within_drift_pct": round(pct, 1),
            # The roadmap requires the metric `hallucination_rate` and this file
            # emitted `hallucination_rate_pct`. A near-miss on a required key is
            # indistinguishable, to anything mechanical, from not returning it at
            # all -- and the roadmap is the authority on the name.
            "hallucination_rate": round(hall, 1),
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
            # J22-M4 — the arithmetic, in the open.
            "drift_measurable_tokens": len(drift_ms),
            "endpoints_not_measurable": min(2, len(matched)),
            "matched_within_drift_pct_endpoints_credited": round(pct_credited, 1),
            # H26-m4 — the de-confounded instrument, beside the confounded one.
            "drift_admissible_tokens": len(drift_interior),
            "median_drift_ms_sentence_excluded": med_i,
            "p95_drift_ms_sentence_excluded": p95_i,
            # J22-M3 — this string described the REJECTED method ("linear
            # time<->text model") while the code computed local three-point
            # interpolation, and the results JSON is what gets cited downstream.
            # It now names what runs.
            "_drift_method": ("local three-point neighbour interpolation: for each matched token, "
                              "|observed start - the start its two IMMEDIATE NEIGHBOURS imply, "
                              "interpolated on display CHARACTER offsets|. Not a global fit; §6.1 "
                              "defines drift relative to neighbours."),
            "_drift_floor_note": ("Character-offset interpolation still charges pauses to drift. "
                                  "Triples spanning sentence-final punctuation are excluded and "
                                  "reported separately; commas, clause breaks and breath remain in "
                                  "the residual. Therefore matched_within_drift_pct is a FLOOR on "
                                  "the true figure, not a verdict on it."),
            "_endpoint_note": ("The first and last matched token have no two-sided neighbourhood, "
                               "so their drift is UNMEASURED. They are excluded from the numerator. "
                               "matched_within_drift_pct_endpoints_credited is the upper bound in "
                               "which they are assumed passing."),
            "expect_hard": hard_rows,
            **H.hard_falsification(hard_rows, match_rate),
            **H.cost_block(cpu_seconds=tm["cpu_seconds"], audio_seconds=audio_s,
                           load_seconds=tm["model_load_seconds"], wall_seconds=tm["wall_seconds"],
                           threads=tm["cpu_threads"]),
        }
        results.append(r)
        flag = "PASS" if r["passes_matched_bar"] else "BELOW BAR"
        print(f"\n  {lang} [{flag}]  within-drift {r['matched_within_drift_pct']}% "
              f"(endpoints credited {r['matched_within_drift_pct_endpoints_credited']}%)"
              f"  match {r['match_rate_pct']}%  hallucination {r['hallucination_rate']}%")
        print(f"     drift median {r['median_drift_ms']}ms p95 {r['p95_drift_ms']}ms over {r['drift_measurable_tokens']} tokens"
              f"  |  sentence-excluded median {r['median_drift_ms_sentence_excluded']}ms p95 "
              f"{r['p95_drift_ms_sentence_excluded']}ms over {r['drift_admissible_tokens']}")
        print(f"     audio {r['audio_seconds']}s  decode {r['decode_wall_seconds']}s "
              f"({r['realtime_factor_amortised']}x amortised, {r['realtime_factor_including_model_load']}x with load)"
              f"  ${r['compute_cost_per_audio_hour_usd']}/audio-hour")
        print(f"     expect_hard: " + ", ".join(f"{h['token']}={h['status']}" for h in r["expect_hard"]))
        if r["expect_hard_falsifies_match_rate"]:
            print(f"     !! FALSIFIED: 100% match claimed while {r['expect_hard_unresolved']} "
                  f"never went through the normalizer path (fixtures.json:13-15)")
        if info["header_length_bogus"]:
            print(f"     !! WAV header declares {info['header_declared_seconds']:.0f}s for a "
                  f"{info['seconds']:.1f}s file (H26-m1) -- duration taken from file size")
        if missed:
            print(f"     unmatched display words: {missed[:12]}")
        if r["hallucinated_tokens"]:
            print(f"     tokens matching nothing: {r['hallucinated_tokens'][:12]}")

    H.write_json(OUT / (f"spike-a-results{a.tag}.json" if a.tag else "spike-a-results.json"), results)
    print(f"\nwrote out/spike-a-results.json  (bar: matched >= {BAR_MATCHED_PCT}%, p95 <= {BAR_P95_MS}ms)")


if __name__ == "__main__":
    main()
