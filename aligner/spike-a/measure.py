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
import subprocess
import sys
import time
import unicodedata

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
DRIFT_MS = 250          # fixed before the run -- H17-C3. Do not tune to pass.
BAR_MATCHED_PCT = 95.0
BAR_P95_MS = 300.0
BAR_HALLUCINATION_PCT = 2.0   # roadmap:159 -- H20-M6. Was set in prose and computed nowhere.

# THE SPLIT (roadmap "Not closed", third item). `hallucination_rate` conflated
# two failures with OPPOSITE symptoms for a reader, and the conflation reaches
# the pre-payment disclosure -- so a blind user was told the wrong thing about
# the wrong risk before paying. See `split_unmatched` for the classification.
#
#   engine_hallucination_rate  the audio contains a word the page does not, so
#                              it has NO display address and the highlight
#                              FREEZES while it is spoken. Inherits the
#                              roadmap's `hallucination_rate <= 2` bar whole,
#                              because that bar was written about this failure:
#                              "a fluently hallucinated token can be timed to
#                              50 ms and mapped to the wrong word."
#   matcher_miss_rate          the word is on the page AND in the audio and we
#                              failed to join them, so the page word is SKIPPED.
#                              The bar is ZERO. This is our defect, not a
#                              provider property: it is fixed by adding a
#                              normalisation rule, which is now a code change
#                              with a test in `worker/src/normalize/`. Any
#                              budget above zero is a budget for our own bugs.
BAR_ENGINE_HALLUCINATION_PCT = 2.0
BAR_MATCHER_MISS_PCT = 0.0

# ── The normaliser lives in the PRODUCT, and this file delegates to it ────
#
# It used to live here, as four module-level fixture tables. It is what took the
# match rate from 91.7% to 100%, so it is not a measurement detail -- it is the
# thing that makes word sync work. A normaliser that exists only in the
# instrument means the shipped matcher is a DIFFERENT matcher from the measured
# one, and every figure on disk describes software nobody runs. Jury and Halo
# both said so repeatedly; this is that finding closed.
#
# There is NO Python copy left and no fallback to one. If node or the module is
# unreachable this raises. A normaliser that silently degrades to identity
# returns a plausible, wrong match rate -- CLAUDE.md constraint 2 applies to
# instruments as much as to providers.
NORMALIZER_CLI = ROOT.parents[1] / "worker" / "src" / "normalize" / "cli.ts"

_NORM_CACHE = {}


class NormalizerError(RuntimeError):
    """The product normaliser could not be reached or refused the request."""


def normalizer(lang: str, display_tokens, observed_tokens) -> dict:
    """
    One subprocess per (lang, token set), memoised -- not one per token.

    Returns the response of `worker/src/normalize/cli.ts`: folded forms, digits
    and spoken-form sequences for every display and observed token, plus the
    grouped-digit map that answers the many-to-one case.
    """
    key = (lang, tuple(display_tokens), tuple(observed_tokens))
    if key in _NORM_CACHE:
        return _NORM_CACHE[key]
    if not NORMALIZER_CLI.exists():
        raise NormalizerError(f"the product normaliser is missing: {NORMALIZER_CLI}")
    payload = json.dumps({"lang": lang, "display": list(display_tokens),
                          "observed": list(observed_tokens)})
    try:
        proc = subprocess.run([node_binary(), str(NORMALIZER_CLI)],
                              input=payload.encode("utf-8"), capture_output=True)
    except OSError as exc:                                    # node not on PATH
        raise NormalizerError(f"cannot run node for {NORMALIZER_CLI}: {exc}") from exc
    if proc.returncode != 0:
        raise NormalizerError(
            f"{NORMALIZER_CLI} exited {proc.returncode}: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    table = json.loads(proc.stdout.decode("utf-8"))
    # CROSS-IMPLEMENTATION CHECK. `norm` below still exists because harness.py
    # and groundtruth.py fold arbitrary tokens through it. Two implementations
    # of one fold is the drift this move was made to end, so every token that
    # passes through here is checked against the product fold and a disagreement
    # RAISES. The check is what makes keeping the Python copy safe.
    for side in ("display", "observed"):
        for row in table[side]:
            if norm(row["token"]) != row["fold"]:
                raise NormalizerError(
                    f"fold disagreement on {row['token']!r}: this file folds to "
                    f"{norm(row['token'])!r}, {NORMALIZER_CLI.name} folds to {row['fold']!r}. "
                    f"Two implementations of one rule have drifted; fix the product one.")
    _NORM_CACHE[key] = table
    return table


def node_binary() -> str:
    return "node"


def norm(tok: str) -> str:
    """
    Fold to a comparable form: NFC, lowercase, strip punctuation.

    Kept in Python because harness.py and groundtruth.py fold arbitrary tokens
    with it, and checked against `worker/src/normalize/foldToken` on every token
    this file processes (see `normalizer`). It is a mirror with an alarm on it,
    not a second source of truth.
    """
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


# The four fixture tables that used to stand here -- NUM, TENS, ABBREV and
# `spoken_forms` -- are gone. They are `worker/src/normalize/numerals.ts`,
# `abbreviations.ts` and `index.ts` now, with tests, and this file reaches them
# through `normalizer()` above. Nothing imports `spoken_forms` from here; the
# only consumers of this module are harness.py and groundtruth.py, which use
# `display_words`, `match` and `norm`.


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
    table = normalizer(lang, [d[0] for d in display], [o["w"] for o in observed])
    forms = [row["forms"] for row in table["display"]]
    # Zipped, never looked up by value: two observed tokens can be identical
    # dicts and `list.index` would return the first of them.
    obs_rows = [(o, row) for o, row in zip(observed, table["observed"]) if row["fold"]]
    obs = [o for o, _ in obs_rows]
    obs_fold = [row["fold"] for _, row in obs_rows]
    obs_digits = [row["digits"] for _, row in obs_rows]
    disp_fold = [row["fold"] for row in table["display"]]
    grouped = table["grouped"]

    matched, unmatched, di, oi = [], [], 0, 0
    while oi < len(obs) and di < len(display):
        placed = False
        # Try each display token in a bounded window, longest spoken form first.
        for j in range(di, min(di + 6, len(display))):
            for seq in sorted(forms[j], key=len, reverse=True):
                if not seq:
                    continue
                got = [obs_fold[oi + k] for k in range(len(seq)) if oi + k < len(obs)]
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
                        "via_normalizer": seq != [disp_fold[j]],
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
        #
        # The GROUP is decided by `worker/src/normalize/groupedDigitForm`, not
        # here: the rule that a run of display tokens is heard as one is part of
        # the normaliser, and the form this file used to compute joined the
        # digits of whatever tokens it was handed -- so `pages 47` joined to "47"
        # and could record the word "pages" as matched against an observation of
        # "47". The product rule requires every token in the run to carry a digit.
        if not placed and oi < len(obs):
            digits_heard = obs_digits[oi]
            for span in (3, 2):
                if di + span > len(display):
                    continue
                group = display[di:di + span]
                joined = grouped.get(str(di), {}).get(str(span))
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


def split_unmatched(unmatched, display, lang):
    """
    Split the unmatched observations into the TWO failures `hallucination_rate`
    conflated. They have opposite symptoms for a reader.

      ENGINE INVENTION -> the highlight FREEZES. The audio contains a word the
        page does not, so the token has no display address by definition (spec
        6.1) and there is nowhere for the caret to be while it is spoken.
      MATCHER MISS -> the highlight SKIPS. The word IS on the page and IS in the
        audio; we failed to join them. Some display word is therefore passed
        over, and the reader loses a word they can see.

    A blind user is told one number before paying. Told "the engine sometimes
    invents words" they hear an unfixable property of the provider; told "our
    matcher drops one word in twenty" they hear a defect with an owner. `fr`'s
    8.7% was reported entirely as the first and is half the second.

    CLASSIFICATION, and the direction of its residual error. An unmatched
    observation counts as a MATCHER MISS when it corresponds to some display
    token of the segment -- same fold, same digits, or one of that token's spoken
    forms. Correspondence is checked over the whole segment rather than at the
    cursor, because the `fr` case is exactly a token whose display word was
    placed by something else: a positional test would call `participants.` an
    invention, which is the conflation this function exists to end.

    The residual runs one way: a word the engine really did invent that happens
    to appear elsewhere on the page is counted as a matcher miss, so
    `engine_hallucination_rate` is a FLOOR. Closing it needs the hand-annotated
    ground truth the roadmap still lists as open -- it cannot be closed by
    choosing a different rule here, and pretending otherwise is how a metric
    stops meaning anything.
    """
    table = normalizer(lang, [d[0] for d in display], [o["w"] for o in unmatched])
    known = set()
    for row in table["display"]:
        if row["fold"]:
            known.add(row["fold"])
        if row["digits"]:
            known.add(row["digits"])
        for seq in row["forms"]:
            if len(seq) == 1:
                known.add(seq[0])
    engine, misses = [], []
    for o, row in zip(unmatched, table["observed"]):
        corresponds = row["fold"] in known or (row["digits"] and row["digits"] in known)
        (misses if corresponds else engine).append(o)
    return engine, misses


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
        # THE SPLIT. The two rates partition `hallucination_rate` exactly, so the
        # roadmap's required metric keeps its definition and its value and the
        # two components are additionally emitted. Nothing downstream loses a
        # number; a reader gains the one that says which failure they will hear.
        invented, missed_by_matcher = split_unmatched(halluc, disp, lang)
        engine_hall = 100.0 * len(invented) / len(obs) if obs else 0.0
        matcher_miss = 100.0 * len(missed_by_matcher) / len(obs) if obs else 0.0
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
            # ── THE SPLIT (roadmap "Not closed", third item). Two failures with
            # opposite symptoms for a reader, no longer one number.
            "engine_hallucination_rate": round(engine_hall, 1),
            "matcher_miss_rate": round(matcher_miss, 1),
            "passes_engine_hallucination_bar": bool(engine_hall <= BAR_ENGINE_HALLUCINATION_PCT),
            "passes_matcher_miss_bar": bool(matcher_miss <= BAR_MATCHER_MISS_PCT),
            "engine_invented_tokens": [h["w"] for h in invented][:20],
            "matcher_missed_tokens": [h["w"] for h in missed_by_matcher][:20],
            "_hallucination_split_note": (
                "engine_hallucination_rate + matcher_miss_rate == hallucination_rate. "
                "ENGINE INVENTION freezes the highlight: the audio holds a word the page "
                "does not, so it has no display address and the caret has nowhere to be. "
                "MATCHER MISS skips a word: it is on the page AND in the audio and we failed "
                "to join them. The first is a provider property disclosed before payment; the "
                "second is our defect, fixed by a rule in worker/src/normalize/. Bars: "
                f"engine <= {BAR_ENGINE_HALLUCINATION_PCT}% (the roadmap's hallucination bar, "
                f"which was written about this failure), matcher <= {BAR_MATCHER_MISS_PCT}% "
                "(any budget above zero is a budget for our own bugs). "
                "engine_hallucination_rate is a FLOOR: an invented word that also appears "
                "elsewhere on the page is counted as a matcher miss."),
            "unmatched_display": missed,
            "unmatched_display_pct": round(100.0 * len(missed) / len(disp), 1) if disp else 0.0,
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
        eflag = "PASS" if r["passes_engine_hallucination_bar"] else "OVER BAR"
        mflag = "PASS" if r["passes_matcher_miss_bar"] else "OVER BAR"
        print(f"     hallucination split: engine-invented {r['engine_hallucination_rate']}% "
              f"[{eflag}, bar {BAR_ENGINE_HALLUCINATION_PCT}%] -> highlight FREEZES  |  "
              f"matcher-missed {r['matcher_miss_rate']}% [{mflag}, bar "
              f"{BAR_MATCHER_MISS_PCT}%] -> highlight SKIPS a page word")
        if r["engine_invented_tokens"]:
            print(f"     engine invented (no page address): {r['engine_invented_tokens'][:12]}")
        if r["matcher_missed_tokens"]:
            print(f"     matcher missed (word IS on the page): {r['matcher_missed_tokens'][:12]}")

    H.write_json(OUT / (f"spike-a-results{a.tag}.json" if a.tag else "spike-a-results.json"), results)
    print(f"\nwrote out/spike-a-results.json  (bar: matched >= {BAR_MATCHED_PCT}%, p95 <= {BAR_P95_MS}ms)")


if __name__ == "__main__":
    main()
