#!/usr/bin/env python3
"""
SPIKE A follow-up — WHERE ARE ENGLISH'S MISSING POINTS, AND WHICH OF THEM CAN
ENGINEERING TAKE BACK.

WHAT THIS FILE EXISTS TO SETTLE
-------------------------------
`out/spike-a-english.json` measured English end to end at chapter length and
reported **90.0** against a 95 bar, with `verdict.chapter_bound_by: "drift"` and
**8.0 pp** of headroom under an ASR ceiling of **98.0** that clears the bar. That
is an attribution, not a diagnosis: it says the recogniser emitted enough and the
timing lost it, and it does not say WHY the timing lost it or what would get it
back. This file takes that apart into named causes and measures two candidate
fixes.

THE THREE HYPOTHESES, AND WHAT HAPPENED TO EACH
-----------------------------------------------
  1. A CONSTANT OFFSET. `calibrate.py` fits `en` at +90 ms and SPIKE A has
     measured faster-whisper's word starts running 80-120 ms early in every
     language. If the loss were a constant lead, correcting it would be a one-
     line fix with a large result.
     **FALSIFIED, and by construction rather than by luck.** `arm_b_offset_probe`
     shifts the WHOLE observation stream across +/-250 ms and the figure does not
     move by a single token, because §6.1's drift is LOCAL: it compares a token
     against an interpolation between ITS NEIGHBOURS, and a uniform shift moves
     the token and both neighbours together. `voices.py`'s `CTL-SHIFT` asserts
     exactly this property; the arm demonstrates it on the real clip. A
     calibration offset cannot buy one point of this metric, in any language.

  2. ORTHOGRAPHY. `clips[].orthography_probe` in the baseline artifact predicted
     that 14 of the chapter clip's 25 absent display tokens were British
     spellings the recogniser wrote in American form -- recognised correctly and
     never matched. **CONFIRMED AND FIXED IN THE PRODUCT**:
     `worker/src/normalize/orthographyForms` now enumerates the other spelling
     as a candidate form. The probe predicted 11 absent tokens and a 99.1%
     ceiling after respelling; the shipped fold delivers exactly those two
     numbers, which is the closest thing to a controlled confirmation this
     corpus allows.

  3. PROSODIC SILENCE. **This is the one that is left, and it is most of it.**
     `arm_c_cause_attribution` reports the causes with their BASE RATES among
     passing tokens, because a condition that is equally common in both
     populations explains nothing.

WHAT IS MEASURED, AND WITH WHOSE INSTRUMENT
-------------------------------------------
`voices.score` and `voices.decode`, IMPORTED -- the same `worker/src/match` and
`worker/src/normalize` reached through the same CLIs, the same shipped
three-point drift, the same `Mutation` knob. Nothing here recomputes a metric
`voices.py` already defines. `--self-test` asserts the import by identity AND by
behaviour, and asserts the orthography fold through the PRODUCT normaliser
rather than through a copy of its table (`J33-M2`'s lesson, one directory away).

WHAT THIS FILE DOES NOT DO
--------------------------
It does not move the bar and it does not touch the drift predicate. §6.1's
250 ms bound was fixed before SPIKE A ran (H17-C3) and
`worker/src/normalize/contract.ts` says moving it is a public act with a recorded
reason. `arm_e_sentence_interior` reports what the figure looks like on the
tokens whose neighbourhood carries no sentence end, and it is labelled a
DECOMPOSITION and not a result, in the artifact, in a field. The product bar is
over every display token and stays that way.

USAGE
    python drift.py --self-test    # no network, no model, no cost
    python drift.py --measure      # decode + forced alignment -> out/spike-a-english-drift.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import statistics
import sys
import time

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT))

import measure as M      # noqa: E402  the shipped matcher/normaliser bridge + the bound
import harness as H      # noqa: E402  wav_info, SENT_END, LF-safe write_json
import voices as V       # noqa: E402  THE INSTRUMENT: score/decode/Mutation, imported
import english as EN     # noqa: E402  the committed chapter fixture and its paragraph twin

ARTIFACT = OUT / "spike-a-english-drift.json"
BASELINE = OUT / "spike-a-english.json"

DRIFT_MS = M.DRIFT_MS                 # 250. Imported, never restated.
BAR_MATCHED_PCT = M.BAR_MATCHED_PCT   # 95.0. Imported, never restated.

# The window either side of a token below which the silence is ordinary
# inter-word spacing rather than a pause. 150 ms is not a tuning knob and nothing
# here is optimised over it: it is reported as a NAMED THRESHOLD beside its own
# base rate, so a reader can see whether it separates the two populations at all.
PAUSE_MS = 150.0

# Cause labels, in the order they are tried. ONE primary cause per token, so the
# buckets partition the failures and cannot double-count a token that carries two
# conditions -- a table whose columns sum to more than the total is a table that
# cannot be read.
CAUSES = (
    "neighbourhood_spans_paragraph_break",
    "neighbourhood_spans_sentence_end",
    "adjacent_silence_over_threshold",
    "display_token_skipped_in_neighbourhood",
    "no_named_cause",
)


def _sha_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _pct(k: int, n: int) -> float:
    return round(100.0 * k / n, 1) if n else 0.0


# ── The cause classifier ─────────────────────────────────────────────────────

def neighbourhoods(matched, disp, text: str, pause_ms: float = PAUSE_MS) -> list:
    """One row per DRIFT-MEASURABLE token: its drift, its sign, and the named
    conditions of its neighbourhood.

    The arithmetic for `drift` is `voices.score`'s, restated here for ONE reason
    and it is not a good one on its own: `score` returns the aggregate and the
    per-token outcome vector, and not the CONTEXT of each token. `--self-test`
    therefore asserts that this function's drift values equal `score`'s
    `_drift_by_disp` on the same input, so a divergence is a failing control
    rather than two numbers that quietly disagree.
    """
    rows = []
    for i in range(1, len(matched) - 1):
        prev, cur, nxt = matched[i - 1], matched[i], matched[i + 1]
        span_c = max(nxt["cs"] - prev["cs"], 1)
        span_t = max(nxt["s"] - prev["s"], 1e-6)
        predicted = prev["s"] + span_t * ((cur["cs"] - prev["cs"]) / span_c)
        signed = (cur["s"] - predicted) * 1000.0
        between = text[prev["cs"]:nxt["cs"]]
        rows.append({
            "disp_idx": cur["disp_idx"],
            "token": disp[cur["disp_idx"]][0],
            "drift_ms": abs(signed),
            "signed_drift_ms": signed,
            "neighbourhood_spans_paragraph_break": "\n\n" in between,
            "neighbourhood_spans_sentence_end": bool(H.SENT_END.search(between)),
            "adjacent_silence_over_threshold": bool(
                (cur["s"] - prev["e"]) * 1000.0 > pause_ms
                or (nxt["s"] - cur["e"]) * 1000.0 > pause_ms),
            "display_token_skipped_in_neighbourhood": bool(
                cur["disp_idx"] - prev["disp_idx"] > 1
                or nxt["disp_idx"] - cur["disp_idx"] > 1),
        })
    return rows


def primary_cause(row: dict) -> str:
    """The FIRST condition in `CAUSES` the row satisfies. One per token."""
    for c in CAUSES[:-1]:
        if row[c]:
            return c
    return CAUSES[-1]


def attribute(rows: list, bound_ms: float, n_display: int) -> dict:
    """Failures by cause, each beside its BASE RATE among the passing tokens.

    A cause quoted without its base rate is not evidence. If 79% of the failures
    sit next to a pause and 79% of the passes do too, the pause explains nothing
    -- and that is exactly the reading a bare count invites.
    """
    bad = [r for r in rows if r["drift_ms"] > bound_ms]
    good = [r for r in rows if r["drift_ms"] <= bound_ms]
    # `no_named_cause` is the absence of the four conditions, not a fifth
    # condition, so its "prevalence" is the share of rows carrying none of them.
    present = lambda r, c: (primary_cause(r) == c) if c == CAUSES[-1] else bool(r[c])  # noqa: E731
    by_cause = {}
    for c in CAUSES:
        n_bad = sum(1 for r in bad if primary_cause(r) == c)
        by_cause[c] = {
            "failures": n_bad,
            "failures_pct_of_out_of_bound": _pct(n_bad, len(bad)),
            "pp_of_all_display_tokens": round(100.0 * n_bad / n_display, 1) if n_display else 0.0,
            # The condition's PREVALENCE, not its primary-cause share, because a
            # base rate answers "how often does this happen at all", and a token
            # can carry the condition while being attributed to a stronger one.
            "condition_present_in_out_of_bound_pct":
                _pct(sum(1 for r in bad if present(r, c)), len(bad)),
            "condition_present_in_in_bound_pct":
                _pct(sum(1 for r in good if present(r, c)), len(good)),
        }
    return {
        "drift_measurable_tokens": len(rows),
        "out_of_bound_tokens": len(bad),
        "out_of_bound_pp_of_all_display_tokens":
            round(100.0 * len(bad) / n_display, 1) if n_display else 0.0,
        "by_primary_cause": by_cause,
        "worst_15": [
            {"token": r["token"], "signed_drift_ms": round(r["signed_drift_ms"]),
             "primary_cause": primary_cause(r)}
            for r in sorted(bad, key=lambda r: -r["drift_ms"])[:15]],
        "_reading": (
            "`by_primary_cause` PARTITIONS the out-of-bound tokens: each is attributed to the "
            "first condition it satisfies in a fixed order, so `failures` sums to "
            "`out_of_bound_tokens` and no token is counted twice. The two "
            "`condition_present_*` columns are PREVALENCES, not shares of the partition, and "
            "they are the load-bearing pair: a condition as common among the passing tokens as "
            "among the failing ones explains nothing, however large its count."),
    }


def sign_summary(rows: list, bound_ms: float) -> dict:
    """The SIGN of the failures, which is what tells a pause from a bias.

    A constant lead produces failures of one sign. A pause produces them in
    PAIRS of opposite sign -- the last word before the silence is predicted late
    and the first word after it is predicted early, because a character-linear
    model spreads the silence across the whole span.
    """
    bad = [r for r in rows if r["drift_ms"] > bound_ms]
    sg = [r["signed_drift_ms"] for r in rows]
    return {
        "median_signed_drift_ms_all": round(statistics.median(sg), 1) if sg else None,
        "mean_signed_drift_ms_all": round(statistics.mean(sg), 1) if sg else None,
        "out_of_bound_early": sum(1 for r in bad if r["signed_drift_ms"] < 0),
        "out_of_bound_late": sum(1 for r in bad if r["signed_drift_ms"] > 0),
        "_reading": (
            "A near-zero median with the failures split BOTH ways is the signature of a "
            "predictor that mismodels local timing, not of a decoder with a constant lead. "
            "One-signed failures with a large median would be the opposite finding and would "
            "make `arm_b_offset_probe` the fix."),
    }


# ── Arm B — the constant-offset probe ────────────────────────────────────────

def offset_probe(obs, text: str, step_ms: int = 25, span_ms: int = 250) -> dict:
    """Shift the WHOLE observation stream and re-score. The answer is expected to
    be a flat line, and the arm exists to put that on disk rather than in a
    sentence: `calibrate.py` fits `en` at +90 ms, three artifacts carry an 80-120
    ms lead, and nobody had checked whether this metric can see it."""
    curve = []
    for ms in range(-span_ms, span_ms + 1, step_ms):
        shifted = [dict(o, s=o["s"] + ms / 1000.0, e=o["e"] + ms / 1000.0) for o in obs]
        curve.append({"shift_ms": ms,
                      "matched_within_drift_pct":
                          V.score(shifted, text, "en")["matched_within_drift_pct"]})
    vals = [c["matched_within_drift_pct"] for c in curve]
    return {
        "curve": curve,
        "figure_range_over_all_shifts_pp": round(max(vals) - min(vals), 1),
        "best_shift_ms": max(curve, key=lambda c: c["matched_within_drift_pct"])["shift_ms"],
        "constant_offset_hypothesis_falsified": bool(max(vals) - min(vals) == 0.0),
        "calibrate_py_fitted_en_shift_ms": 90,
        "_derivation": (
            "Every observed token moved by the same amount, then re-scored by the same "
            "`voices.score`. §6.1 drift compares a token against an interpolation between ITS "
            "NEIGHBOURS, so a uniform shift moves all three together and cannot change the "
            "residual. `figure_range_over_all_shifts_pp = 0.0` is therefore the EXPECTED "
            "result and a non-zero value would mean the drift measure is not local. The "
            "consequence for the product is the load-bearing part: the per-language "
            "calibration in `spike-a-calibration.json` cannot recover one token of "
            "`matched_within_drift_pct`, in any language, and must not be quoted as if it "
            "could."),
    }


# ── Arm D — forced-alignment re-timing of the SAME observed words ────────────

def fa_refine(wav: pathlib.Path, obs: list, chunk_seconds: float = 25.0) -> tuple:
    """Re-time the observed words with torchaudio MMS_FA, leaving the SEQUENCE
    alone.

    ADR-0002 holds: forced alignment here receives the ASR TRANSCRIPT, never the
    display text, so it refines WHERE an observed word is and never decides WHAT
    was said. `match_rate_pct` and the ASR ceiling therefore CANNOT move, and
    `--measure` asserts they did not -- if they move, the arm changed the wrong
    thing and its drift figure means nothing.

    Chunked at inter-word gaps because wav2vec2 attention is quadratic in frames
    and a 454 s clip in one pass is not a thing this host can hold. Cuts land in
    silence, so a chunk boundary is not a word boundary.
    """
    import torch, torchaudio                                   # noqa: E401
    from torchaudio.pipelines import MMS_FA as B
    import fa as FA                                            # safe to import: no side effects

    model, tokenizer, aligner = FA._mms()
    wf, sr = torchaudio.load(str(wav))
    if wf.shape[0] > 1:
        wf = wf.mean(0, keepdim=True)
    if sr != B.sample_rate:
        wf = torchaudio.functional.resample(wf, sr, B.sample_rate)
    SR = B.sample_rate

    def alignable(w: str) -> list:
        import re
        digits = re.sub(r"[^0-9]", "", w)
        if digits and not FA.romanize(w):
            try:
                return FA.spell(int(digits), "en")
            except Exception:
                pass
        r = FA.romanize(w)
        return [r] if r else []

    chunks, cur = [], []
    for i, o in enumerate(obs):
        cur.append(i)
        dur = obs[cur[-1]]["e"] - obs[cur[0]]["s"]
        gap = (obs[i + 1]["s"] - o["e"]) if i + 1 < len(obs) else 9.9
        if dur >= chunk_seconds and gap >= 0.08:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)

    refined = [dict(o) for o in obs]
    retimed, failed = 0, []
    for ci, idxs in enumerate(chunks):
        t0 = max(0.0, obs[idxs[0]]["s"] - 0.25)
        t1 = min(wf.shape[1] / SR, obs[idxs[-1]]["e"] + 0.25)
        seg = wf[:, int(t0 * SR):int(t1 * SR)]
        words, owner = [], []
        for j in idxs:
            for part in alignable(obs[j]["w"]):
                words.append(part)
                owner.append(j)
        if not words or seg.shape[1] < SR // 10:
            failed.append({"chunk": ci, "why": "no alignable token in the chunk"})
            continue
        try:
            with torch.inference_mode():
                emission, _ = model(seg)
                spans = aligner(emission[0], tokenizer(words))
        except Exception as exc:                      # NOT retried and NOT hidden
            failed.append({"chunk": ci, "why": f"{type(exc).__name__}: {exc}"})
            continue
        ratio = seg.shape[1] / emission.shape[1] / SR
        by_owner = {}
        for sp, j in zip(spans, owner):
            s, e = t0 + sp[0].start * ratio, t0 + sp[-1].end * ratio
            by_owner[j] = (by_owner[j][0], e) if j in by_owner else (s, e)
        for j, (s, e) in by_owner.items():
            refined[j]["s"], refined[j]["e"] = s, e
            retimed += 1
    return refined, {"chunks": len(chunks), "chunks_failed": len(failed),
                     "failures": failed, "observed_tokens": len(obs),
                     "observed_tokens_retimed": retimed,
                     "chunk_seconds": chunk_seconds}


# ── Arm E — the decomposition that is NOT a result ───────────────────────────

def sentence_interior(rows: list, bound_ms: float) -> dict:
    inter = [r for r in rows if not r["neighbourhood_spans_sentence_end"]]
    bnd = [r for r in rows if r["neighbourhood_spans_sentence_end"]]
    ok = lambda rs: sum(1 for r in rs if r["drift_ms"] <= bound_ms)   # noqa: E731
    return {
        "interior_measurable_tokens": len(inter),
        "interior_in_bound_tokens": ok(inter),
        "interior_in_bound_pct": _pct(ok(inter), len(inter)),
        "boundary_measurable_tokens": len(bnd),
        "boundary_in_bound_tokens": ok(bnd),
        "boundary_in_bound_pct": _pct(ok(bnd), len(bnd)),
        "_this_is_not_a_product_figure": (
            "THE BAR IS OVER EVERY DISPLAY TOKEN AND STAYS THAT WAY. A reader follows a "
            "caret through sentence ends too, and a highlight that is reliable only mid-"
            "sentence is not a highlight that works. This pair is a DECOMPOSITION, published "
            "to locate the loss and to size what a pause-aware predictor could be worth if "
            "the owner ever decided to reopen §6.1's drift definition -- which this file does "
            "not propose and does not do. `matched_within_drift_pct` in `arm_a_as_shipped` is "
            "the only figure here that answers the product question. Note also that the "
            "denominators differ from the bar's: both exclude the unmatched tokens and the "
            "two endpoints, which the bar keeps (`J22-M4`)."),
    }


# ── The measurement ──────────────────────────────────────────────────────────

def measure_clip(kind: str, text: str, path: pathlib.Path, with_fa: bool) -> dict:
    obs, timing = V.decode(path, "en")
    disp = M.display_words(text)
    shipped = V.score(obs, text, "en")
    matched = M.match_full(obs, disp, "en")["matched"]
    rows = neighbourhoods(matched, disp, text)
    info = H.wav_info(path)

    keep = lambda s: {k: v for k, v in s.items() if not k.startswith("_")}   # noqa: E731
    row = {
        "kind": kind,
        "lang_code": "en",
        "audio_path": path.name,
        "audio_sha256": _sha_file(path),
        "clip_seconds": round(info["seconds"], 2),
        "display_words": len(disp),
        "cpu_seconds": round(timing.get("cpu_seconds", 0.0), 2) if isinstance(timing, dict) else None,
        "arm_a_as_shipped": keep(shipped),
        "arm_b_offset_probe": offset_probe(obs, text),
        "arm_c_cause_attribution": {
            **attribute(rows, DRIFT_MS, len(disp)),
            "sign": sign_summary(rows, DRIFT_MS),
            "pause_threshold_ms": PAUSE_MS,
        },
        "arm_e_sentence_interior": sentence_interior(rows, DRIFT_MS),
    }
    if with_fa:
        t0 = time.time()
        refined, meta = fa_refine(path, obs)
        fa_score = V.score(refined, text, "en")
        row["arm_d_fa_refined"] = {
            **meta,
            "elapsed_seconds": round(time.time() - t0, 1),
            "matched_within_drift_pct": fa_score["matched_within_drift_pct"],
            "median_drift_ms": fa_score["median_drift_ms"],
            "p95_drift_ms": fa_score["p95_drift_ms"],
            "match_rate_pct": fa_score["match_rate_pct"],
            "coverage_ceiling_pct_any_matcher":
                fa_score["asr_coverage_ceiling"]["coverage_ceiling_pct_any_matcher"],
            "delta_vs_as_shipped_pp": round(
                fa_score["matched_within_drift_pct"] - shipped["matched_within_drift_pct"], 1),
            "clears_bar": fa_score["passes_matched_bar"],
            "matched_within_drift_ci95": list(
                V.wilson_ci(sum(fa_score["_outcome"]), fa_score["display_words"])),
            # THE CONTROL ON THE ARM ITSELF. Re-timing must not change WHICH words
            # were heard; if it did, the arm changed two things and its delta is
            # uninterpretable.
            "word_sequence_unchanged": bool(
                fa_score["match_rate_pct"] == shipped["match_rate_pct"]
                and fa_score["asr_coverage_ceiling"]["coverage_ceiling_pct_any_matcher"]
                == shipped["asr_coverage_ceiling"]["coverage_ceiling_pct_any_matcher"]),
            "_what_this_is": (
                "torchaudio MMS_FA re-times the SAME observed words against the SAME audio. "
                "The transcript is the recogniser's, never the display text, so ADR-0002 "
                "holds and this is a REFINEMENT of the observation, not a prediction of it. "
                "It is a PROBE of a pipeline stage that is not built: shipping it means an FA "
                "sidecar in the worker, and SPIKE E measured that stage at 91.6% of the ASR "
                "stage's cost again."),
        }
    return row


def _baseline() -> dict:
    """The committed figure, READ from `spike-a-english.json`, never restated.

    A number retyped from another artifact is the defect this project files
    monthly; and the comparison this file publishes is only worth anything if the
    left-hand side comes off disk.
    """
    if not BASELINE.exists():
        return {"file": BASELINE.name, "present": False}
    d = json.loads(BASELINE.read_text(encoding="utf-8"))
    ch = next((c for c in d["clips"] if c["kind"] == "chapter"), {})
    pr = ch.get("orthography_probe", {})
    return {
        "file": BASELINE.name,
        "present": True,
        "chapter_matched_within_drift_pct": ch.get("matched_within_drift_pct"),
        "chapter_match_rate_pct": ch.get("match_rate_pct"),
        "chapter_coverage_ceiling_pct_any_matcher":
            ch.get("asr_coverage_ceiling", {}).get("coverage_ceiling_pct_any_matcher"),
        "chapter_display_tokens_absent_from_transcript":
            ch.get("asr_coverage_ceiling", {}).get("display_tokens_absent_from_transcript"),
        "orthography_probe_predicted_ceiling_pct": pr.get("ceiling_pct_after_en_us_respelling"),
        "orthography_probe_predicted_absent_tokens": pr.get("absent_tokens_after_respelling"),
        "_status": (
            "MEASURED BEFORE `worker/src/normalize/orthographyForms` EXISTED. Its chapter "
            "figures are therefore superseded by `arm_a_as_shipped` in this file and "
            "`english.py --measure` HAS NOT BEEN RE-RUN -- re-running it moves a committed "
            "artifact that README, ADR-0006 and the glossary quote by value, which is a "
            "document change and not this file's to make. Owner: Forge, with Scribe. "
            "Until that re-run lands, `spike-a-english.json`'s chapter row is the figure "
            "BEFORE the fold and must be quoted as such."),
    }


def cmd_measure(with_fa: bool = True) -> int:
    V.Mutation.reset()
    base = _baseline()
    clips = []
    for kind, text, path in EN.planned_clips():
        if not path.exists():
            print(f"  MISSING (scored as absent, never as zero): {path.name}")
            continue
        t0 = time.time()
        clips.append(measure_clip(kind, text, path, with_fa=with_fa))
        c = clips[-1]
        print(f"    {path.name}: as-shipped "
              f"{c['arm_a_as_shipped']['matched_within_drift_pct']}%, "
              f"FA-refined {c.get('arm_d_fa_refined', {}).get('matched_within_drift_pct', 'n/a')}%, "
              f"{round(time.time() - t0, 1)}s")

    chapter = next((c for c in clips if c["kind"] == "chapter"), None)
    art = {
        "_subject": ("Where the English chapter clip's shortfall against the 95 bar comes from, "
                     "and what two candidate fixes are worth. A follow-up to "
                     "`spike-a-english.json`, whose `verdict.chapter_bound_by` is `drift`."),
        "_supersedes": (
            "NOTHING is withdrawn. `spike-a-english.json` remains the end-to-end measurement; "
            "its CHAPTER figures predate `worker/src/normalize/orthographyForms` and are "
            "reproduced here under `baseline_artifact` FROM THAT FILE, not retyped."),
        "_instrument": (
            "voices.score and voices.decode, IMPORTED from `aligner/spike-a/voices.py`: "
            "`worker/src/match/matchTokens` and `worker/src/normalize` reached through their "
            "CLIs, the shipped local three-point drift, the same `Mutation` knob. Decoder "
            "faster-whisper `base`, int8, the shipped configuration. Arm D adds torchaudio "
            "MMS_FA over the ASR transcript. `--self-test` asserts the import by identity and "
            "by behaviour, and asserts the orthography fold through the PRODUCT normaliser."),
        "_limits": [
            "ONE VOICE, ONE PROVIDER, NO REPLICATE, and the same two clips as "
            "`spike-a-english.json`. No English noise floor exists, so a difference of a "
            "point or two between arms on ONE clip is not resolvable. The arms are PAIRED on "
            "the same decode of the same audio, which is why their DIFFERENCES are readable "
            "where their absolute values carry the same one-clip uncertainty as the baseline.",
            "ARM D IS A PROBE OF AN UNBUILT STAGE. No FA sidecar exists in `worker/`; SPIKE E "
            "priced that stage at 91.6% of the ASR stage again, so the +pp it reports is not "
            "free and the decision is the owner's, not this file's.",
            "THE CAUSE PARTITION IS AN ORDERING, NOT A MODEL. A token satisfying two "
            "conditions is charged to the first in `CAUSES`. The prevalence columns exist "
            "precisely so a reader can see what the ordering hid.",
            "ARM E IS NOT A PRODUCT FIGURE and its denominators are not the bar's. See the "
            "field `_this_is_not_a_product_figure`, which travels with it.",
        ],
        "_mutation_active": bool(V.Mutation.active),
        "drift_bound_ms": DRIFT_MS,
        "bar_matched_within_drift_pct": BAR_MATCHED_PCT,
        "pause_threshold_ms": PAUSE_MS,
        "baseline_artifact": base,
        "clips": clips,
    }
    if chapter and base.get("present"):
        a = chapter["arm_a_as_shipped"]
        d = chapter.get("arm_d_fa_refined", {})
        ceil_now = a["asr_coverage_ceiling"]["coverage_ceiling_pct_any_matcher"]
        absent_now = a["asr_coverage_ceiling"]["display_tokens_absent_from_transcript"]
        art["verdict"] = {
            "_question": ("How much of English's 5.0 pp shortfall is recoverable, by what, "
                          "and what is left?"),
            "chapter_before_pct": base["chapter_matched_within_drift_pct"],
            "chapter_after_orthography_fold_pct": a["matched_within_drift_pct"],
            "orthography_fold_delta_pp": round(
                a["matched_within_drift_pct"] - base["chapter_matched_within_drift_pct"], 1),
            # THE CONTROLLED PART OF THE COMPARISON. The end-to-end delta spans a
            # code change on one clip and is therefore an observation, not an
            # estimate. The CEILING is different: the baseline artifact recorded a
            # PREDICTION for it before the fold was written, so this is a
            # pre-registered check, and it is what makes the mechanism knowable.
            "orthography_fold_predicted_ceiling_pct":
                base["orthography_probe_predicted_ceiling_pct"],
            "orthography_fold_observed_ceiling_pct": ceil_now,
            "orthography_fold_predicted_absent_tokens":
                base["orthography_probe_predicted_absent_tokens"],
            "orthography_fold_observed_absent_tokens": absent_now,
            "orthography_fold_matches_its_prediction": bool(
                ceil_now == base["orthography_probe_predicted_ceiling_pct"]
                and absent_now == base["orthography_probe_predicted_absent_tokens"]),
            "chapter_after_fa_refinement_pct": d.get("matched_within_drift_pct"),
            "fa_refinement_delta_pp": d.get("delta_vs_as_shipped_pp"),
            "chapter_best_measured_pct": max(
                [a["matched_within_drift_pct"]]
                + ([d["matched_within_drift_pct"]] if d else [])),
            "clears_bar_as_shipped": a["passes_matched_bar"],
            "clears_bar_with_fa_refinement": d.get("clears_bar"),
            "remaining_gap_to_bar_pp": round(
                BAR_MATCHED_PCT - max([a["matched_within_drift_pct"]]
                                      + ([d["matched_within_drift_pct"]] if d else [])), 1),
            "constant_offset_recoverable_pp":
                0.0 if chapter["arm_b_offset_probe"]["constant_offset_hypothesis_falsified"] else None,
            "residual_dominant_primary_cause": max(
                chapter["arm_c_cause_attribution"]["by_primary_cause"].items(),
                key=lambda kv: kv[1]["failures"])[0],
            "residual_dominant_primary_cause_failures": max(
                v["failures"] for v in
                chapter["arm_c_cause_attribution"]["by_primary_cause"].values()),
            "_reading": (
                "ENGLISH DOES NOT CLEAR 95 AND IS NOT CLOSE TO IT. Both measured fixes are "
                "real and neither is large. The constant-offset hypothesis -- the cheap one, "
                "the one three artifacts pointed at -- is worth EXACTLY ZERO against this "
                "metric and is falsified on the clip, not argued away. What is left is "
                "prosodic: a character-linear predictor charges the silence at a sentence "
                "boundary to the words on either side of it, in opposite directions. That is "
                "a property of §6.1's drift DEFINITION, not of the decoder, and it is not "
                "this file's to change."),
        }
    H.write_json(ARTIFACT, art)
    print(f"\n  artifact: {ARTIFACT}")
    if "verdict" in art:
        v = art["verdict"]
        print(f"  chapter  before {v['chapter_before_pct']} -> orthography fold "
              f"{v['chapter_after_orthography_fold_pct']} -> FA refinement "
              f"{v['chapter_after_fa_refinement_pct']}   bar {BAR_MATCHED_PCT}, "
              f"gap {v['remaining_gap_to_bar_pp']} pp")
        print(f"  constant offset recoverable: {v['constant_offset_recoverable_pp']} pp")
    return 0


# ── Controls ─────────────────────────────────────────────────────────────────

def _check(ok: bool, cid: str, msg: str, log: list) -> None:
    log.append((cid, bool(ok), msg))
    if not ok:
        print(f"  FAIL {cid}: {msg}")


def self_test() -> int:
    log = []
    V.Mutation.reset()

    # ── CTL-IMPORT — the instrument is the imported one ──────────────────────
    _check(V.score.__module__ == "voices", "CTL-IMPORT",
           "score() must be voices.score, not a local copy", log)
    _check(V.decode.__module__ == "voices", "CTL-IMPORT",
           "decode() must be voices.decode, not a local copy", log)
    _check(DRIFT_MS == M.DRIFT_MS and BAR_MATCHED_PCT == M.BAR_MATCHED_PCT, "CTL-IMPORT",
           "the bound and the bar are imported from measure, never restated", log)

    # A synthetic clip with a real structure: ten words, a sentence end after the
    # fifth, and 600 ms of silence at that boundary.
    text = "one two three four five. six seven eight nine ten"
    disp = M.display_words(text)
    def stream(pause: float = 0.0):
        obs, t = [], 0.0
        for i, w in enumerate(text.replace(".", "").split()):
            obs.append({"w": w, "s": t, "e": t + 0.40})
            t += 0.50 + (pause if i == 4 else 0.0)
        return obs
    flat, paused = stream(), stream(0.60)

    # ── CTL-DRIFT-EQUIV — this file's drift equals `voices.score`'s ──────────
    # The one place a second copy of the arithmetic lives. It is here because
    # `score` returns no per-token CONTEXT; it is asserted equal because a copy
    # that is not asserted equal is `J33-M2`.
    s = V.score(paused, text, "en")
    rows = neighbourhoods(M.match_full(paused, disp, "en")["matched"], disp, text)
    mine = {r["disp_idx"]: round(r["drift_ms"], 6) for r in rows}
    theirs = {k: round(v, 6) for k, v in s["_drift_by_disp"].items()}
    _check(mine == theirs, "CTL-DRIFT-EQUIV",
           f"neighbourhoods() must reproduce voices.score's per-token drift exactly; "
           f"{len(set(mine.items()) ^ set(theirs.items()))} entries differ", log)
    bent = neighbourhoods(M.match_full(paused, disp, "en")["matched"], disp, text)
    bent[0]["drift_ms"] += 1.0
    _check({r["disp_idx"]: round(r["drift_ms"], 6) for r in bent} != theirs,
           "CTL-DRIFT-EQUIV/mut",
           "and the comparison must be able to FAIL — a perturbed copy must not compare equal",
           log)

    # ── CTL-OFFSET — a uniform shift cannot move the figure; one token can ───
    p0 = offset_probe(flat, text, step_ms=100, span_ms=200)
    _check(p0["constant_offset_hypothesis_falsified"] is True, "CTL-OFFSET",
           f"a uniform shift must not move a LOCAL drift measure, got range "
           f"{p0['figure_range_over_all_shifts_pp']} pp", log)
    V.Mutation.reset()
    V.Mutation.active = True
    V.Mutation.displace = ((4, 900),)
    moved = V.score(flat, text, "en")["matched_within_drift_pct"]
    V.Mutation.reset()
    _check(moved < V.score(flat, text, "en")["matched_within_drift_pct"], "CTL-OFFSET/mut",
           "while displacing ONE token past the bound must lower it — otherwise the arm is "
           "measuring a metric that responds to nothing", log)

    # ── CTL-CAUSE — the classifier names the condition that is there ─────────
    r_paused = neighbourhoods(M.match_full(paused, disp, "en")["matched"], disp, text)
    r_flat = neighbourhoods(M.match_full(flat, disp, "en")["matched"], disp, text)
    at = lambda rs, i: next(r for r in rs if r["disp_idx"] == i)      # noqa: E731
    _check(at(r_paused, 5)["adjacent_silence_over_threshold"] is True, "CTL-CAUSE",
           "600 ms of inserted silence before a token must be flagged as adjacent silence", log)
    _check(at(r_flat, 5)["adjacent_silence_over_threshold"] is False, "CTL-CAUSE/mut",
           "and the SAME token with the silence removed must not be", log)
    _check(at(r_paused, 5)["neighbourhood_spans_sentence_end"] is True, "CTL-CAUSE",
           "a neighbourhood straddling `five.` must be flagged as spanning a sentence end", log)
    _check(at(r_paused, 8)["neighbourhood_spans_sentence_end"] is False, "CTL-CAUSE/mut",
           "and one that does not must not be", log)
    _check(primary_cause({**at(r_paused, 5), "neighbourhood_spans_paragraph_break": True})
           == "neighbourhood_spans_paragraph_break", "CTL-CAUSE",
           "the paragraph break outranks the sentence end when both hold", log)
    _check(primary_cause({c: False for c in CAUSES[:-1]}) == "no_named_cause",
           "CTL-CAUSE/mut", "and a row with no condition is named as such, never dropped", log)

    # ── CTL-PARTITION — the buckets sum to the total, always ─────────────────
    a = attribute(r_paused, 250.0, len(disp))
    _check(sum(v["failures"] for v in a["by_primary_cause"].values()) == a["out_of_bound_tokens"],
           "CTL-PARTITION",
           f"the cause buckets must partition the failures: "
           f"{sum(v['failures'] for v in a['by_primary_cause'].values())} vs "
           f"{a['out_of_bound_tokens']}", log)
    wide = attribute(r_paused, 10.0, len(disp))
    _check(wide["out_of_bound_tokens"] > a["out_of_bound_tokens"]
           and sum(v["failures"] for v in wide["by_primary_cause"].values())
           == wide["out_of_bound_tokens"], "CTL-PARTITION/mut",
           "and it must still partition when the bound is tightened and MORE tokens fail", log)

    # ── CTL-SIGN — the sign summary can tell a bias from a pause ─────────────
    biased = [dict(o, s=o["s"] + (0.4 if i % 2 else 0.0)) for i, o in enumerate(flat)]
    sb = sign_summary(neighbourhoods(M.match_full(biased, disp, "en")["matched"], disp, text), 250.0)
    sf = sign_summary(r_flat, 250.0)
    _check(abs(sf["median_signed_drift_ms_all"]) < 1.0, "CTL-SIGN",
           f"an evenly spaced stream has no signed drift, got "
           f"{sf['median_signed_drift_ms_all']}", log)
    _check(sb["out_of_bound_early"] + sb["out_of_bound_late"] > 0, "CTL-SIGN/mut",
           "and a stream with alternating displacement must produce signed failures", log)

    # ── CTL-ORTHO-LIVE — the fold is the PRODUCT's, reached through its CLI ──
    # `J33-M2` is a control that guarded a COPY of the predicate it was about.
    # This one goes through `measure.normalizer`, which is the same subprocess
    # the measurement uses, so a table that exists only in a test cannot pass it.
    forms = {t["token"]: [tuple(f) for f in t["forms"]] for t in
             M.normalizer("en", ["digitisation", "raise", "colours", "cancelled"], [])["display"]}
    _check(("digitization",) in forms["digitisation"], "CTL-ORTHO-LIVE",
           f"the product normaliser must offer `digitization` for `digitisation`, got "
           f"{forms['digitisation']}", log)
    _check(("colors",) in forms["colours"], "CTL-ORTHO-LIVE",
           "and `colors` for `colours`", log)
    _check(("canceled",) in forms["cancelled"], "CTL-ORTHO-LIVE",
           "and `canceled` for `cancelled` — the paragraph clip's absent token", log)
    _check(("raize",) not in forms["raise"], "CTL-ORTHO-LIVE/mut",
           f"and must NOT offer `raize` for `raise`: the measured over-application, got "
           f"{forms['raise']}", log)
    fr = M.normalizer("fr", ["couleur"], [])["display"][0]["forms"]
    _check([tuple(f) for f in fr] == [("couleur",)], "CTL-ORTHO-LIVE/mut",
           f"and must add nothing in French, where no such split exists, got {fr}", log)

    # ── CTL-BASELINE — the left-hand side of the comparison comes off disk ───
    b = _baseline()
    _check(b.get("present") is True and isinstance(b.get("chapter_matched_within_drift_pct"), float),
           "CTL-BASELINE",
           f"the baseline must be READ from {BASELINE.name}, never restated; got {b}", log)
    _check(b.get("orthography_probe_predicted_absent_tokens") is not None, "CTL-BASELINE",
           "and it must carry the probe's PRE-REGISTERED prediction, which is the only "
           "controlled half of the orthography comparison", log)

    # ── CTL-INTERIOR — the decomposition is labelled, and it is a real split ─
    e = sentence_interior(r_paused, 250.0)
    _check(e["interior_measurable_tokens"] + e["boundary_measurable_tokens"] == len(r_paused),
           "CTL-INTERIOR", "interior and boundary tokens must partition the measurable set", log)
    _check("_this_is_not_a_product_figure" in e, "CTL-INTERIOR/mut",
           "and the decomposition must carry its own disclaimer as a FIELD, so it cannot be "
           "quoted without it", log)

    V.Mutation.reset()
    passed = sum(1 for _, ok, _ in log if ok)
    print(f"\nself-test: {len(log)} controls, {passed} passed")
    by = {}
    for cid, ok, _ in log:
        by.setdefault(cid, [0, 0])
        by[cid][0] += 1
        by[cid][1] += int(ok)
    for cid in sorted(by):
        print(f"  {cid:24} {by[cid][1]}/{by[cid][0]}")
    print(_coverage_footer(log))
    return 0 if passed == len(log) else 1


def _coverage_footer(log: list) -> str:
    """Say which controls are asserted in ONE direction only, BY NAME.

    `J33-m1`: both Python harnesses in this repository printed "asserted in BOTH
    directions" over assertion sets that were not. The honest form ships in the
    same repo -- `doc-check --self-test` names its unmutated IDs -- and it is
    COMPUTED, so a control added tomorrow without a `/mut` names itself here in
    the same run.
    """
    families = {cid.split("/")[0] for cid, _, _ in log}
    mutated = {cid.split("/")[0] for cid, _, _ in log if cid.endswith("/mut")}
    un = sorted(families - mutated)
    n_un = sum(1 for cid, _, _ in log if not cid.endswith("/mut")
               and cid.split("/")[0] in un)
    return (f"\n  {len(mutated)} of {len(families)} control families are asserted in BOTH "
            f"directions.\n  ONE DIRECTION ONLY ({len(un)} families, {n_un} assertions): "
            f"{', '.join(un) if un else 'none'}.\n"
            f"  Those hold on clean input and nothing here proves they would go red on a "
            f"defect.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--no-fa", action="store_true",
                    help="skip arm D (forced alignment) — it is the slow arm")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.measure:
        return cmd_measure(with_fa=not a.no_fa)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
