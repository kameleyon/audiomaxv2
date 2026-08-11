#!/usr/bin/env python3
"""
SPIKE A, English arm — DOES ENGLISH CLEAR THE 95 BAR AT CHAPTER LENGTH, END TO
END, AND IS THE BAR EVEN REACHABLE FOR ENGLISH.

WHAT THIS FILE EXISTS TO SETTLE
-------------------------------
The owner is deciding whether to ship English-only. That decision turns on one
number that HAD NEVER BEEN MEASURED. Every English figure on disk before this
run came from a ~12-second, 24-display-word fixture, or from a constructed
corpus, or from forced alignment given the true text:

  - `spike-a-results.json`      `en` matched_within_drift_pct 62.5, on out/en.wav
                                — 11.63 s, 24 display words.
  - `spike-a-groundtruth.json`  `en-gt` 8.3, `en-gtlong` 15.5 — ASR-ONLY, and on
                                a CONSTRUCTED corpus whose own `_limits` say the
                                inserted silence is LONGER than the bar and that
                                `-gtlong` REPEATS one sentence to reach length.
  - `spike-a-groundtruth-fa.json` `en-gt` 95.8 — FORCED ALIGNMENT GIVEN THE TRUE
                                TEXT. A ceiling for the refinement stage. That
                                file emits no pass field at all, and quoting it
                                as end-to-end word sync is `J29-C1`, the most
                                serious finding in this project's history.
  - `spike-a-voices.json`       `clips[].lang_code` is **`fr` ONLY**. The +23.9 pp
                                re-sync gain and the 89.8–92.0% ASR ceiling that
                                three documents now build on are FRENCH findings.
                                They were never English findings.

So the sentence "on chapter-length audio the bar is ASR-bound" was established
on French and generalised to English by silence. English is the language most
likely to pass — the strongest ASR, the fewest absent tokens — which makes the
generalisation a real question rather than a formality.

THE THREE QUANTITIES, NEVER CONFLATED
-------------------------------------
Conflating them was `J29-C1`. Each is named separately at every mention here and
in the artifact:

  END-TO-END      `matched_within_drift_pct` — ASR transcript -> product matcher
                  -> drift against local three-point neighbour interpolation.
                  THE SHIPPED PATH. This is the only one that answers the
                  product question.
  ASR CEILING     `coverage_ceiling_pct_any_matcher` — the fraction of display
                  tokens the recogniser emitted in SOME form the matcher could
                  accept. A STRICT UPPER BOUND on any matcher. Not an achieved
                  result and not a prediction.
  ASR-ONLY FLOOR  the `groundtruth.py` figures. NOT COMPUTED HERE, and not
                  quoted here, because this corpus has no constructed ground
                  truth — see `_limits` in the artifact.

WHAT IS MEASURED, AND WITH WHOSE INSTRUMENT
-------------------------------------------
`voices.score` and `voices.decode`, IMPORTED, not reimplemented — the same
`worker/src/match/matchTokens` reached through the same CLI, the same shipped
three-point drift, the same `Mutation` knob, the same `asr_absence` derivation.
A second copy of the instrument is how two artifacts in one commit come to
disagree, and this file exists to add a language, not a measurement definition.
`--self-test` asserts the import is live by mutating `voices.Mutation` and
requiring THIS file's numbers to move.

THE LENGTH QUESTION IS THE WHOLE QUESTION
-----------------------------------------
`en-para.wav` is 224 display words. The French long clips are 1186. A figure
taken on 224 words is NOT a chapter-length claim, and this file refuses to let
one be read as the other: every clip row carries `kind` and `display_words`, the
verdict states the length it was taken at, and `chapter_length_claim_supported`
is a field, not an inference the reader is left to make.

COST DISCIPLINE (owner's standing rule)
---------------------------------------
`--probe` makes ONE Lemonfox call and stops, printing the exact estimated spend
before it makes it. `--measure` costs nothing. No key is ever printed. English
routes to Lemonfox per spec 3.5; the rate is $2.50 per 1,000,000 characters
(`resources/research/2026-08-08-provider-rates.md`, Tier B, retrieved
2026-08-08).

USAGE
    python english.py --self-test      # no network, no cost
    python english.py --plan           # word/char/cost estimate, no network
    python english.py --probe          # 1 TTS call, then STOP
    python english.py --measure        # ASR + scoring -> out/spike-a-english.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT))

import measure as M      # noqa: E402  the shipped matcher bridge + the drift bound
import harness as H      # noqa: E402  wav_info, LF-safe write_json
import voices as V       # noqa: E402  THE INSTRUMENT: score/decode/Mutation, imported
import tts as T          # noqa: E402  the Lemonfox call, in the shape the repo already uses

ARTIFACT = OUT / "spike-a-english.json"
PROBE_ARTIFACT = OUT / "spike-a-english-probe.json"
MANIFEST = OUT / "tts-manifest.json"

DRIFT_MS = M.DRIFT_MS                 # 250. Imported, never restated.
BAR_MATCHED_PCT = M.BAR_MATCHED_PCT   # 95.0. Imported, never restated.

# English routes to Lemonfox (spec 3.5). `Adam` is the voice `fixtures.json`
# already uses for every English clip in the repository, so the long clip differs
# from `en-para.wav` in LENGTH and in nothing else that we control.
EN_VOICE = "Adam"
EN_PROVIDER = "lemonfox"
LEMONFOX_USD_PER_1K_CHARS = 0.0025    # resources/research/2026-08-08-provider-rates.md

LONG_WAV = OUT / "en-long.wav"
PARA_WAV = OUT / "en-para.wav"

# ── The chapter-length English text ──────────────────────────────────────────
#
# THIS IS FR_LONG'S CONTENT, IN ENGLISH — the same twenty paragraphs, the same
# figures, the same abbreviations, the same years, the same percentages, the same
# grouped thousands. That is deliberate and it is the only reason an EN-vs-FR
# comparison at this length means anything: if the two texts differed, a
# difference between the languages and a difference between the documents would
# be the same observation, and this spike has already published one figure that
# could not be attributed (`J29-M1`, "no run produces the pair").
#
# The one thing that is NOT held constant is the thousands separator: French
# writes `1 250` with a space and English writes `1,250` with a comma. Copying
# the French convention would test English against a form no English document
# contains and no English speaker reads aloud. The hard-token CLASS is held
# constant; its orthography follows the language, as `fixtures.json`'s own
# English text already does ("1,800 euros").
#
# It is NOT added to `fixtures.json` — that file belongs to Probe. It lives here
# beside the run that uses it, and its SHA-256 is recorded in the artifact.
EN_LONG = (
    "The annual report of the municipal library describes a digitisation programme begun in "
    "1984 and continued without interruption ever since. The department today has 47 "
    "workstations spread over 3 floors, and it processes on average 1,250 documents a week. "
    "Dr. Chen, who leads the technical team, recalls that the first campaign covered only the "
    "parish registers and the cadastral plans.\n\n"

    "The older collections raise particular difficulties. The paper grows brittle, the ink "
    "fades, and some bindings can no longer bear to be opened flat. For those items the "
    "workshop uses an adjustable cradle that limits the opening angle to 52 degrees. Each "
    "volume is photographed page by page, then checked by an operator who verifies the "
    "sharpness, the framing and the fidelity of the colours.\n\n"

    "The processing chain has four stages. The first is physical preparation, which means "
    "dusting, removing staples and noting the state of conservation. The second is the "
    "photography itself. The third is the computer processing of the images. The fourth is "
    "description, that is to say the writing of the records that will let a document be found "
    "among millions of others.\n\n"

    "The average cost of a digitised page has fallen a great deal. In 2019 it still reached 12 "
    "cents; it is today below 4 cents for ordinary documents. The fall is explained by the "
    "automation of page turning, by the collapse in the price of sensors and by a better "
    "organisation of the work. It does not, however, apply to fragile items, which are still "
    "handled by hand.\n\n"

    "The question of storage comes back at every meeting of the committee. A page at high "
    "resolution takes up about 40 megabytes, and the programme produces close to 3,400 pages "
    "per working day. The files are kept in three copies, on two separate sites, with a monthly "
    "integrity check. Prof. Adams, invited last year, insisted on the fact that a copy nobody "
    "verifies is not a backup.\n\n"

    "Public access has been rethought in depth. The portal offers a search by word, by date and "
    "by place, as well as page by page reading directly in the browser. Users may download the "
    "low resolution images without formality; high resolution remains subject to a reasoned "
    "request. The statistics show that 8 visitors out of 10 arrive from a search engine.\n\n"

    "Accessibility is a project in its own right. Typewritten documents lend themselves well to "
    "automatic character recognition, and the resulting text can be read by a speech "
    "synthesiser. Manuscripts resist more. The team works with an association of visually "
    "impaired people, which tests every new version of the portal and reports the obstacles it "
    "meets.\n\n"

    "Recognition errors are not distributed at random. They concentrate on proper names, on "
    "figures and on abbreviations. A register listing sums in old francs will produce more "
    "confusions than a handwritten letter in continuous prose. For that reason the records "
    "always carry a verified transcription of the essential elements: the date, the place and "
    "the people named.\n\n"

    "The training of staff occupies an important place. A new operator follows 3 weeks of "
    "apprenticeship before working alone. He learns to handle the documents, to set the "
    "lighting and to recognise the faults that force a retake. The retake rate, which exceeded "
    "9 percent at the start, has fallen below the bar of 2 percent since the new equipment was "
    "installed.\n\n"

    "Copyright limits the distribution of part of the holdings. Works fallen into the public "
    "domain are freely consultable. The others are accessible only from the terminals installed "
    "in the reading room, and only for research use. This distinction, poorly understood by the "
    "public, is the subject of an explanatory notice posted at the entrance and repeated on the "
    "portal.\n\n"

    "Partnerships have multiplied. The department works with the departmental archives, with "
    "two universities and with several learned societies. Each brings documents, staff or "
    "financial means. In return, the images produced join a common catalogue, which avoids the "
    "same work being digitised twice by two neighbouring institutions.\n\n"

    "The prospects for the next 5 years are clear. The task is to finish the campaign on the "
    "regional periodicals, to improve full text search and to guarantee the long term "
    "conservation of the files already produced. The report ends with a simple recommendation: "
    "measure regularly what one claims to be improving, and publish the results even when they "
    "are disappointing.\n\n"

    "A word finally on measurement itself. The committee asked that every indicator be "
    "accompanied by its uncertainty, and not presented as a single figure. A difference of a "
    "few points between two workshops means nothing if it rests on some thirty pages. The "
    "report applies that rule to its own tables, even at the price of admitting that certain "
    "comparisons are not yet conclusive.\n\n"

    "The library publishes at last the complete list of its contractors. Three companies act on "
    "the chain: one for the photography, another for the hosting of the files, the third for "
    "text recognition. Users therefore know where the documents they entrust go, and on what "
    "terms. This transparency was demanded by the board in 2019, and it is renewed every "
    "year.\n\n"

    "The operating budget comes to 640,000 euros a year, of which 62 percent is payroll. The "
    "investment credits, more irregular, allowed in 2019 the purchase of 2 flatbed scanners and "
    "of one colour processing station. The authority asks each year for a detailed statement of "
    "spending, broken down by collection and by type of operation, in order to compare the real "
    "cost of a page according to its support.\n\n"

    "Data security is the subject of a written protocol. The workstations are not connected to "
    "the general network, removable media are forbidden, and transfers pass through an "
    "intermediate server where every file is checked. An incident in 2019 on an external disk "
    "led to a hardening of those rules; since then no loss of data has been recorded over the 3 "
    "most recent campaigns.\n\n"

    "Distant users represent a growing share of the public. A third of consultations now comes "
    "from another region, and 7 percent from abroad. That change alters the nature of the "
    "service: it is no longer only a matter of receiving readers in a room, but of answering "
    "written requests, often precise, sometimes framed in a language the team does not speak "
    "fluently.\n\n"

    "The vocabulary used in the records deserves a remark. Old terms denote realities that have "
    "disappeared, and a reader of today does not always recognise them. The department "
    "therefore maintains a glossary of 1,400 entries, linked to the records, which explains in "
    "one sentence what an arpent, a gabelle or a livre tournois was. That glossary is consulted "
    "far more often than expected.\n\n"

    "Finally, the report recalls an obvious point too often forgotten. Digitising a document "
    "does not preserve it: it produces an image, which will itself have to be preserved, "
    "migrated and verified for decades. The original remains the original, and the store that "
    "houses it demands as much attention as the server that hosts its copy. The two budgets are "
    "distinct, and neither replaces the other.\n\n"

    "One last paragraph on the reading of these tables. A rate measured on a few dozen pages "
    "carries an uncertainty wider than the differences it is being used to explain, and the "
    "committee has asked that no comparison be published without the number of pages it rests "
    "on. The rule cost 2 tables in this edition, withdrawn rather than qualified. It is the "
    "cheapest rule the department applies, and the one it has broken most often."
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def para_text() -> str:
    """The 224-word natural-prose English fixture, READ FROM `fixtures.json`
    rather than copied. A copy is how two artifacts in one commit come to
    contradict each other (the round-26/27 finding of the round)."""
    return json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8")
                      )["paragraph"]["en"]["text"]


def planned_clips():
    """(kind, text, path).

    TWO LENGTHS AND NO AVERAGE. The paragraph clip is not a weaker version of the
    chapter clip and the two are never pooled: the whole question is whether the
    figure MOVES with length, and a mean over both would erase exactly the effect
    being measured.
    """
    return [
        ("paragraph", para_text(), PARA_WAV),
        ("chapter", EN_LONG, LONG_WAV),
    ]


# ── The cost gate ────────────────────────────────────────────────────────────

def _estimate(text: str) -> dict:
    chars = len(text)
    return {
        "characters_sent": chars,
        "utf8_bytes_sent": len(text.encode("utf-8")),
        "display_words_in_text": len(M.display_words(text)),
        "rate_usd_per_1k_characters": LEMONFOX_USD_PER_1K_CHARS,
        "estimated_usd": round(chars / 1000.0 * LEMONFOX_USD_PER_1K_CHARS, 4),
        "_rate_source": ("resources/research/2026-08-08-provider-rates.md — Lemonfox TTS, "
                         "$2.50 per 1,000,000 characters, Tier B, retrieved 2026-08-08. "
                         "Lemonfox bills CHARACTERS, not UTF-8 bytes; the byte count is "
                         "recorded beside it because Fish bills bytes and the two must never "
                         "be read off the same column."),
    }


def cmd_plan() -> int:
    """No network. Says what a probe would spend, before anyone spends it."""
    total = 0.0
    for kind, text, path in planned_clips():
        est = _estimate(text)
        have = "on disk" if path.exists() else "WOULD BE SYNTHESIZED"
        if not path.exists():
            total += est["estimated_usd"]
        print(f"  {kind:10} {path.name:14} {est['display_words_in_text']:>5} display words  "
              f"{est['characters_sent']:>6} chars  ${est['estimated_usd']:.4f}  [{have}]")
    print(f"\n  total to spend: ${total:.4f}  (owner's cap for an unasked spend: $0.05)")
    print(f"  provider: {EN_PROVIDER}, voice {EN_VOICE} — spec 3.5's `en` route.")
    return 0


def cmd_probe(yes: bool) -> int:
    """ONE call. Then stop, and read the cost off the dashboard."""
    if LONG_WAV.exists():
        print(f"  {LONG_WAV.name} already exists. Nothing to spend. --measure is free.")
        return 0
    est = _estimate(EN_LONG)
    print(f"  ONE Lemonfox call: {est['characters_sent']} characters, "
          f"{est['display_words_in_text']} display words, estimated ${est['estimated_usd']:.4f}")
    if not yes:
        print("  --yes to spend it.")
        return 0
    env = T.load_env()
    key = env.get("LEMONFOX_API_KEY")
    if not key:
        sys.exit("no LEMONFOX_API_KEY in .env -- STOPPING, not retrying.")
    t0 = time.time()
    # NO RETRY, NO FALLBACK. The owner rotated the keys; an auth failure is a
    # finding to report, not a condition to loop on, and constraint 2 forbids a
    # primary path that leans on a second route when the first refuses.
    audio = T.synth_lemonfox(EN_LONG, EN_VOICE, key, timeout=900)
    LONG_WAV.write_bytes(audio)
    info = H.wav_info(LONG_WAV)
    rec = {
        **est,
        "path": LONG_WAV.name, "bytes": len(audio),
        "sha256": _sha_file(LONG_WAV), "seconds": round(info["seconds"], 2),
        "sample_rate": info["sample_rate"], "channels": info["channels"],
        "provider": EN_PROVIDER, "voice": EN_VOICE, "lang_code": "en",
        "text_sha256": _sha(EN_LONG),
        "elapsed_seconds": round(time.time() - t0, 1),
        "calls_made": 1,
    }
    # A short render is a TRUNCATED render, and a truncated render measured as if
    # it were whole is a figure taken on audio that does not contain the text.
    # Named as a field so a reader does not have to divide two numbers to see it.
    rec["seconds_per_100_display_words"] = round(
        100.0 * rec["seconds"] / max(1, rec["display_words_in_text"]), 2)
    rec["clears_clip_floor_300s"] = rec["seconds"] >= 300.0
    rec["looks_truncated"] = rec["seconds"] < 0.6 * rec["display_words_in_text"] * 60 / 150.0
    H.write_json(PROBE_ARTIFACT, rec)
    rebuild_manifest()
    print(f"  {rec['bytes']} bytes / {rec['seconds']}s in {rec['elapsed_seconds']}s")
    print(f"  clears the 300 s clip floor: {rec['clears_clip_floor_300s']}")
    if rec["looks_truncated"]:
        print("  !! LOOKS TRUNCATED. Do not scale. Chunk the text and re-probe.")
    print("\n  STOPPING. Read the real cost off the Lemonfox dashboard before any further call.")
    return 0


def rebuild_manifest() -> None:
    """Every .wav in `out/` described, with its content hash.

    [ART-STALE] leg (i) requires the manifest to describe every wav present and
    leg (iii) resolves each result row's `audio_path` through it. A new clip that
    is measured and not manifested turns the gate red — which is the point: the
    manifest is the only record tying a figure to the bytes it scored.
    """
    rows = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []
    by_path = {r["path"]: r for r in rows if isinstance(r, dict) and r.get("path")}
    for wav in sorted(OUT.glob("*.wav")):
        info = H.wav_info(wav)
        raw = wav.read_bytes()
        prior = by_path.get(wav.name, {})
        by_path[wav.name] = {
            **prior,
            "path": wav.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "seconds": round(info["seconds"], 2),
            "sample_rate": info["sample_rate"], "channels": info["channels"],
            "wav_header_length_bogus": info["header_length_bogus"],
        }
    H.write_json(MANIFEST, [by_path[k] for k in sorted(by_path)])


# ── The measurement ──────────────────────────────────────────────────────────

# ── The orthography probe ────────────────────────────────────────────────────
#
# WHY THIS EXISTS. The chapter clip's 25 absent display tokens are not a random
# sample of English: `digitisation`, `programme`, `colours`, `organisation`,
# `synthesiser`, `recognise`, `catalogue`, `neighbouring`, `Digitising`. The text
# above was written in BRITISH orthography, because it mirrors a French document;
# faster-whisper transcribes English in AMERICAN orthography. Those tokens were
# recognised perfectly and then failed to MATCH, because
# `worker/src/normalize/spokenForms` folds diacritics and elisions and does not
# fold en-GB against en-US.
#
# That matters in two directions and the artifact must carry both:
#
#   1. It makes the reported ASR ceiling a CONSERVATIVE floor on the true one.
#      The headline "English's ceiling clears the bar" is therefore strengthened
#      by this confound, not threatened by it — which is the only reason it is
#      admissible to report the headline at all while the confound is open.
#   2. It is a REAL product defect, not merely an artefact of this fixture.
#      audiomax ingests user documents, and British-spelled English is not a
#      corner case: it is most English published outside the United States.
#      Every one of these tokens is a word a blind user's highlight would skip.
#
# The classification is MECHANICAL — a named, ordered ruleset applied to the text,
# re-scored against THE SAME observations — because "these look British to me" is
# an opinion and this round exists to stop opinions being published as figures.
EN_GB_TO_US = [
    (r"isation\b", "ization"), (r"isations\b", "izations"),
    (r"ise\b", "ize"), (r"ised\b", "ized"), (r"ising\b", "izing"), (r"iser\b", "izer"),
    (r"ises\b", "izes"),
    (r"programme\b", "program"), (r"programmes\b", "programs"),
    (r"colour", "color"), (r"neighbour", "neighbor"), (r"behaviour", "behavior"),
    (r"catalogue\b", "catalog"), (r"dialogue\b", "dialog"),
]


# THE `-ise` RULE OVER-APPLIES, AND THE FIRST RUN OF THIS PROBE PROVED IT.
# `ise\b -> ize` turned `raise` into `raize` and `precise,` into `precize,` —
# words that are `-ise` in AMERICAN English too. Both then appeared in
# `still_absent_after_respelling_sample`, which is how it was caught: the probe
# INVENTED two absent tokens while explaining twelve, so the recovered figure was
# an undercount and the residual list was contaminated with strings that are in
# no text anywhere. A blanket suffix rule cannot express this; an exception list
# can, because "-ise that stays -ise" is a closed lexical class and not a pattern.
_NEVER_RESPELL_STEMS = (
    "raise praise appraise apprise reprise noise poise precise concise promise surprise "
    "wise likewise otherwise rise arise comprise compromise demise devise advise revise "
    "supervise televise improvise disguise guise despise chastise enterprise franchise "
    "merchandise exercise excise incise paradise treatise anise cruise bruise tortoise "
    "mortise expertise valise malaise mayonnaise surmise exorcise circumcise"
).split()


def _never_forms() -> frozenset:
    """The exception stems with their inflections. Generated, not hand-listed, so
    adding a stem cannot silently miss its `-ed` / `-ing` / `-s` forms — which is
    the shape of the defect this list exists to fix."""
    s = set()
    for b in _NEVER_RESPELL_STEMS:
        s.update({b, b + "d", b + "s", b + "r", b + "rs", b[:-1] + "ing"})
    return frozenset(s)


_NEVER_FORMS = _never_forms()


def _respell_en_gb_to_us(text: str) -> str:
    """Apply `EN_GB_TO_US` WORD BY WORD, skipping `_NEVER_FORMS`, and preserving
    the leading capital of a capitalised word.

    Word-by-word rather than over the whole string because the exception list is
    keyed on whole words: `\\b`-anchored suffix regexes over raw text cannot ask
    "is this word `raise`". Case is preserved rather than lowered because
    `Digitising` is a display token in its own right and a probe that changed its
    capitalisation would be measuring two things at once.
    """
    import re

    def one(word: str) -> str:
        low = word.lower()
        if low in _NEVER_FORMS:
            return word
        new = low
        for pat, repl in EN_GB_TO_US:
            new = re.sub(pat, repl, new)
        if new == low:
            return word
        return new[0].upper() + new[1:] if word[0].isupper() else new

    return re.sub(r"[A-Za-z]+", lambda m: one(m.group(0)), text)


def measure_clip(kind: str, text: str, path: pathlib.Path) -> dict:
    """One clip, scored by `voices.score` — the instrument, imported."""
    obs, timing = V.decode(path, "en")
    s = V.score(obs, text, "en")
    info = H.wav_info(path)
    ceiling = s["asr_coverage_ceiling"]
    matched_in_bound = sum(s["_outcome"])
    row = {k: v for k, v in s.items() if not k.startswith("_")}
    row.update({
        "lang_code": "en",
        "kind": kind,
        "provider": EN_PROVIDER,
        "voice": EN_VOICE,
        "audio_path": path.name,
        "audio_sha256": _sha_file(path),
        "clip_seconds": round(info["seconds"], 2),
        "clip_ms": int(round(info["seconds"] * 1000)),
        "text_sha256": _sha(text),
        "cpu_seconds": round(timing.get("cpu_seconds", 0.0), 2) if isinstance(timing, dict) else None,
        "matched_within_drift_ci95": list(V.wilson_ci(matched_in_bound, s["display_words"])),
        "in_bound_tokens": matched_in_bound,
        # ── THE FLOORS, NAMED, NOT INFERRED ──────────────────────────────────
        # `voice_langs` admits evidence only above these. A row that fails one is
        # reported WITH its numbers and marked, never dropped and never rounded
        # up to "chapter length" by a reader who did not check.
        "floor_sync_matched_words_ge_200": matched_in_bound >= 200,
        "floor_clip_ms_ge_300000": info["seconds"] * 1000 >= 300000,
        "floor_metric_is_bar": True,
        "supports_chapter_length_claim": bool(
            s["display_words"] >= 1000 and info["seconds"] * 1000 >= 300000),
    })
    # ── The orthography probe, on the SAME observations ──────────────────────
    # Only the CEILING is taken from the respelled run. The end-to-end figure of
    # a text that was never spoken is not a measurement of anything, and putting
    # it in this row is how the wrong number gets quoted six months from now.
    respelled = _respell_en_gb_to_us(text)
    if respelled != text:
        alt = V.score(obs, respelled, "en")["asr_coverage_ceiling"]
        row["orthography_probe"] = {
            "_what_this_is": (
                "The ASR COVERAGE CEILING recomputed after respelling the DISPLAY TEXT from "
                "en-GB to en-US, against the SAME observations from the SAME decode. It "
                "isolates how much of this clip's ceiling shortfall is ORTHOGRAPHY the "
                "normaliser does not fold, rather than words the recogniser failed to emit. "
                "IT IS A PROBE, NOT A RESULT: no audio was re-synthesized and no end-to-end "
                "figure is taken from it, because the respelled text was never spoken. The "
                "headline `coverage_ceiling_pct_any_matcher` in this row is the one measured "
                "on the text that was actually read aloud."),
            "ceiling_pct_as_written_en_gb":
                s["asr_coverage_ceiling"]["coverage_ceiling_pct_any_matcher"],
            "ceiling_pct_after_en_us_respelling": alt["coverage_ceiling_pct_any_matcher"],
            "ceiling_recovered_pp": round(
                alt["coverage_ceiling_pct_any_matcher"]
                - s["asr_coverage_ceiling"]["coverage_ceiling_pct_any_matcher"], 1),
            "absent_tokens_as_written": (
                s["asr_coverage_ceiling"]["display_tokens_absent_from_transcript"]),
            "absent_tokens_after_respelling": alt["display_tokens_absent_from_transcript"],
            "absent_tokens_explained_by_orthography": (
                s["asr_coverage_ceiling"]["display_tokens_absent_from_transcript"]
                - alt["display_tokens_absent_from_transcript"]),
            "still_absent_after_respelling_sample": alt["absent_display_tokens_sample"],
            "ruleset": [f"{p} -> {r}" for p, r in EN_GB_TO_US],
            "_implication": (
                "Tokens recovered here were RECOGNISED CORRECTLY and failed to MATCH. They are "
                "a `worker/src/normalize/spokenForms` gap — it folds diacritics and elisions "
                "and does not fold en-GB against en-US — not an ASR limit. They therefore cost "
                "coverage on any British-spelled English document a user uploads, which is "
                "most English published outside the United States. Owner: Forge."),
        }
    row["_outcome"] = s["_outcome"]
    return row


def _verdict(rows: list) -> dict:
    """The product question, answered in fields rather than in prose.

    Every field below names WHICH of the three quantities it is about. The
    end-to-end figure and the ASR ceiling are never combined into a single
    "English score", because they answer different questions and the round-29
    Critical was exactly that combination.
    """
    chapter = next((r for r in rows if r["kind"] == "chapter"), None)
    para = next((r for r in rows if r["kind"] == "paragraph"), None)
    out = {
        "_question": "Does ENGLISH clear the 95 bar at chapter length, end to end?",
        "clips_measured": [r["kind"] for r in rows],
        "chapter_length_clip_present": chapter is not None,
    }
    if para:
        out.update({
            "paragraph_display_words": para["display_words"],
            "paragraph_end_to_end_matched_within_drift_pct": para["matched_within_drift_pct"],
            "paragraph_asr_coverage_ceiling_pct": (
                para["asr_coverage_ceiling"]["coverage_ceiling_pct_any_matcher"]),
            "paragraph_end_to_end_clears_bar": para["passes_matched_bar"],
            "paragraph_supports_chapter_length_claim": para["supports_chapter_length_claim"],
        })
    if chapter:
        c = chapter["asr_coverage_ceiling"]
        out.update({
            "chapter_display_words": chapter["display_words"],
            "chapter_clip_seconds": chapter["clip_seconds"],
            "chapter_end_to_end_matched_within_drift_pct": chapter["matched_within_drift_pct"],
            "chapter_end_to_end_clears_bar": chapter["passes_matched_bar"],
            "chapter_end_to_end_gap_to_bar_pp": round(
                BAR_MATCHED_PCT - chapter["matched_within_drift_pct"], 1),
            "chapter_asr_coverage_ceiling_pct": c["coverage_ceiling_pct_any_matcher"],
            "chapter_asr_ceiling_clears_bar": c["coverage_ceiling_clears_bar"],
            "chapter_supports_chapter_length_claim": chapter["supports_chapter_length_claim"],
            "chapter_matcher_desynced": chapter["matcher_desynced"],
            "chapter_resyncs": chapter["resyncs"],
            # ── THE ATTRIBUTION. This is what the owner is buying. ────────────
            # When the ceiling clears the bar and the end-to-end figure does not,
            # the loss is DRIFT and a better matcher/aligner can in principle
            # recover it. When the ceiling is itself below the bar, no matcher
            # can, and the answer is a different recogniser or a different bar.
            # The two cases have different costs and different owners, so the
            # artifact says which one this is instead of leaving it to be read
            # off two numbers in different sections.
            "chapter_bound_by": (
                "recognition" if not c["coverage_ceiling_clears_bar"] else "drift"),
            "chapter_headroom_between_end_to_end_and_ceiling_pp": round(
                c["coverage_ceiling_pct_any_matcher"] - chapter["matched_within_drift_pct"], 1),
        })
    if para and chapter:
        out.update({
            "length_effect_end_to_end_pp": round(
                chapter["matched_within_drift_pct"] - para["matched_within_drift_pct"], 1),
            "length_effect_asr_ceiling_pp": round(
                chapter["asr_coverage_ceiling"]["coverage_ceiling_pct_any_matcher"]
                - para["asr_coverage_ceiling"]["coverage_ceiling_pct_any_matcher"], 1),
            "_length_effect_reading": (
                "PARAGRAPH minus CHAPTER is confounded with the TEXT: the two clips are "
                "different documents, not the same document at two lengths, because no "
                "1000-word English text existed to truncate. The sign and rough size are "
                "informative; the magnitude is not a controlled length effect and must not be "
                "quoted as one. The controlled version of this comparison is FRENCH, where "
                "`fr-para.wav` and the six `fr-long-*` clips share a provider and a voice but "
                "not a text either — so it is confounded in the same way, and that is a gap "
                "in the evidence rather than a property of this file."),
        })
    return out


def cmd_measure() -> int:
    V.Mutation.reset()
    rows = []
    for kind, text, path in planned_clips():
        if not path.exists():
            print(f"  MISSING (scored as absent, never as zero): {path.name}")
            continue
        t0 = time.time()
        rows.append(measure_clip(kind, text, path))
        print(f"    {path.name}: {rows[-1]['display_words']} words, "
              f"end-to-end {rows[-1]['matched_within_drift_pct']}%, "
              f"ASR ceiling {rows[-1]['asr_coverage_ceiling']['coverage_ceiling_pct_any_matcher']}%, "
              f"{round(time.time() - t0, 1)}s")
    art = {
        "_subject": ("Does ENGLISH clear the 95 bar at chapter length, END TO END, and is the "
                     "bar reachable for English at all. The product-scope question behind an "
                     "English-only launch."),
        "_supersedes": (
            "NOTHING. It fills a hole. Every English figure previously on disk was taken on a "
            "~12-second 24-word fixture (`spike-a-results.json` 62.5), on a CONSTRUCTED corpus "
            "(`spike-a-groundtruth.json` `en-gt` 8.3 / `en-gtlong` 15.5, ASR-ONLY), or by "
            "FORCED ALIGNMENT GIVEN THE TRUE TEXT (`spike-a-groundtruth-fa.json` `en-gt` 95.8, "
            "a ceiling for the refinement stage that emits no pass field). "
            "`spike-a-voices.json` measured `fr` ONLY -- its `clips[].lang_code` is `fr` in all "
            "nine rows -- so the +23.9 pp re-sync gain and the 89.8-92.0% ASR ceiling three "
            "documents build on are FRENCH findings and were never English ones."),
        "_instrument": (
            "voices.score and voices.decode, IMPORTED from `aligner/spike-a/voices.py`, not "
            "reimplemented here: `worker/src/match/matchTokens` reached through its CLI, the "
            "shipped local three-point neighbour drift, and the same `asr_absence` derivation. "
            "Decoder faster-whisper `base`, int8, the shipped configuration. `--self-test` "
            "mutates `voices.Mutation` and requires THIS file's figures to move, so an import "
            "that silently became a copy is a failing control rather than a quiet divergence."),
        "_three_quantities_never_conflated": {
            "end_to_end": ("`matched_within_drift_pct` -- ASR transcript through the product "
                           "matcher, drift against local three-point neighbour interpolation. "
                           "THE SHIPPED PATH and the only figure that answers the product "
                           "question."),
            "asr_ceiling": ("`coverage_ceiling_pct_any_matcher` -- a STRICT UPPER BOUND on what "
                            "ANY matcher could place on this transcript. Not an achieved "
                            "result, not a prediction of a better matcher's score."),
            "asr_only_floor": ("the `groundtruth.py` figures against constructed ground truth. "
                               "NOT COMPUTED HERE and NOT QUOTED HERE -- this corpus is natural "
                               "prose and has no constructed ground truth. Quoting a `-gt` "
                               "figure beside these would be `J29-C1` again."),
        },
        "_limits": [
            "NATURAL PROSE, NO CONSTRUCTED GROUND TRUTH. Drift is measured against local "
            "three-point neighbour interpolation on display character offsets -- the shipped "
            "definition -- not against known-true word boundaries. That is the same basis every "
            "`matched_within_drift_pct` in `spike-a-voices.json` uses, so these figures are "
            "comparable to the French ones and are NOT comparable to the `-gt` corpora.",
            "ONE VOICE, ONE PROVIDER, NO REPLICATE. `spike-a-voices.json` established a "
            "within-voice noise floor of up to 4.3 pp for Fish at temperature 0.8. Lemonfox's "
            "sampling behaviour is NOT characterised here, so no English noise floor exists and "
            "a difference of a few points between these two clips is not resolvable.",
            "THE TWO ENGLISH CLIPS ARE DIFFERENT TEXTS. The paragraph-vs-chapter contrast is "
            "confounded with content; see `verdict._length_effect_reading`.",
            "THE ASR CEILING IS ORDER-FREE AND ONE-TO-MANY-FREE BY CONSTRUCTION, so it ignores "
            "monotonicity and lets one observation serve several display tokens. A real matcher "
            "can only do worse. Its `_derivation` travels with it in every clip row.",
        ],
        "_mutation_active": bool(V.Mutation.active),
        "drift_bound_ms": DRIFT_MS,
        "bar_matched_within_drift_pct": BAR_MATCHED_PCT,
        "chapter_fixture_sha256": _sha(EN_LONG),
        "chapter_fixture_display_words": len(M.display_words(EN_LONG)),
        "paragraph_fixture_sha256": _sha(para_text()),
        "paragraph_fixture_display_words": len(M.display_words(para_text())),
        "clips": rows,
        "verdict": _verdict(rows),
    }
    H.write_json(ARTIFACT, art)
    _print_measure(art)
    return 0


def _print_measure(art: dict) -> None:
    v = art["verdict"]
    # ASCII ONLY. This console runs cp1252 and a box-drawing character raises
    # UnicodeEncodeError -- AFTER the artifact is written, so the run looks like
    # a crash while the measurement in fact succeeded. A pretty-printer that can
    # fail a successful run is a pretty-printer that gets numbers re-measured for
    # no reason.
    print("\n  -- ENGLISH, THE THREE QUANTITIES KEPT APART ---------------------")
    for r in art["clips"]:
        c = r["asr_coverage_ceiling"]
        print(f"  {r['kind']:10} {r['display_words']:>5} display words, {r['clip_seconds']:>7.2f}s")
        print(f"    END-TO-END  matched_within_drift_pct        {r['matched_within_drift_pct']:>6} "
              f"  clears 95: {r['passes_matched_bar']}")
        print(f"    ASR CEILING coverage_ceiling_pct_any_matcher {c['coverage_ceiling_pct_any_matcher']:>6} "
              f"  clears 95: {c['coverage_ceiling_clears_bar']}")
        print(f"    chapter-length claim supported by this clip: "
              f"{r['supports_chapter_length_claim']}")
    if v.get("chapter_length_clip_present"):
        print(f"\n  BOUND BY: {v['chapter_bound_by'].upper()}  "
              f"(headroom end-to-end -> ceiling: "
              f"{v['chapter_headroom_between_end_to_end_and_ceiling_pp']} pp)")
    print(f"\n  artifact: {ARTIFACT}")


# ── Controls ─────────────────────────────────────────────────────────────────

def _check(ok: bool, cid: str, msg: str, log: list) -> None:
    log.append((cid, bool(ok), msg))
    if not ok:
        print(f"  FAIL {cid}: {msg}")


def self_test() -> int:
    """Every control asserted in BOTH directions. A control that only ever passes
    is what this spike shipped five times."""
    log = []
    V.Mutation.reset()

    # ── CTL-IMPORT — the instrument is the imported one, not a copy ───────────
    # If this file ever grew its own `score`, every figure it publishes would
    # describe software nobody runs. Asserted by IDENTITY, and then by BEHAVIOUR:
    # turning `voices.Mutation` must move THIS file's numbers.
    _check(V.score.__module__ == "voices", "CTL-IMPORT",
           "score() must be voices.score, not a local copy", log)
    _check(V.decode.__module__ == "voices", "CTL-IMPORT",
           "decode() must be voices.decode, not a local copy", log)
    _check(DRIFT_MS == M.DRIFT_MS and BAR_MATCHED_PCT == M.BAR_MATCHED_PCT, "CTL-IMPORT",
           "the bound and the bar are imported from measure, never restated", log)

    # A synthetic observation stream, so the controls below need no audio and no
    # network. Words are chosen to match the display text exactly; the timings
    # are the thing under test.
    text = "one two three four five six seven eight nine ten"
    disp = M.display_words(text)
    obs = [{"w": w, "s": i * 0.50, "e": i * 0.50 + 0.40}
           for i, w in enumerate(text.split())]

    clean = V.score(obs, text, "en")
    _check(clean["display_words"] == len(disp) == 10, "CTL-SHAPE",
           "the denominator is the display-token count", log)
    # 80.0 AND NOT 100.0, and the difference is the whole accounting rule. Drift
    # needs a token on each side, so the FIRST and LAST display tokens can never
    # be scored — they are excluded from the numerator and KEPT in the
    # denominator (`J22-M4`). On perfect input at n=10 that is 8/10. This control
    # exists to pin that convention: if someone ever credits the endpoints, this
    # figure becomes 100.0 and every `matched_within_drift_pct` in the repository
    # silently gains a few points on short clips and almost none on long ones —
    # which is exactly the kind of length-dependent shift this round is trying to
    # measure.
    _check(clean["matched_within_drift_pct"] == 80.0, "CTL-SHAPE",
           f"endpoints are excluded from the numerator and kept in the denominator, so "
           f"perfect input at n=10 scores 8/10 = 80.0, got "
           f"{clean['matched_within_drift_pct']}", log)
    _check(clean["drift_measurable_tokens"] == len(disp) - 2, "CTL-SHAPE",
           "and exactly two tokens are unmeasurable, never more", log)

    # ── CTL-DRIFT — the metric responds to displacement, in both directions ───
    V.Mutation.reset()
    V.Mutation.active = True
    V.Mutation.displace = ((4, 900),)
    moved = V.score(obs, text, "en")
    V.Mutation.reset()
    _check(moved["matched_within_drift_pct"] < clean["matched_within_drift_pct"], "CTL-DRIFT",
           "displacing one token past the bound must LOWER the figure", log)
    _check(V.score(obs, text, "en")["matched_within_drift_pct"]
           == clean["matched_within_drift_pct"], "CTL-DRIFT/mut",
           "and resetting the mutation must restore it exactly", log)

    # ── CTL-BOUND — the bound is load-bearing, not decoration ────────────────
    V.Mutation.reset()
    V.Mutation.active = True
    V.Mutation.displace = ((4, 300),)
    over = V.score(obs, text, "en")["matched_within_drift_pct"]
    V.Mutation.drift_bound_ms = 2000
    under = V.score(obs, text, "en")["matched_within_drift_pct"]
    V.Mutation.reset()
    _check(under > over, "CTL-BOUND",
           "widening the drift bound must admit tokens the 250 ms bound rejected", log)

    # ── CTL-CEILING — the ASR ceiling falls when the transcript loses a word ──
    # THE CONTROL THIS ROUND TURNS ON. The ceiling is the figure that decides
    # whether the bar is reachable at all, and a ceiling that cannot go down is a
    # number with a confident name and no measurement behind it (`J32-M4`).
    full = V.score(obs, text, "en")["asr_coverage_ceiling"]
    _check(full["coverage_ceiling_pct_any_matcher"] == 100.0, "CTL-CEILING",
           "a transcript containing every display token has a ceiling of 100", log)
    _check(full["display_tokens_absent_from_transcript"] == 0, "CTL-CEILING",
           "and nothing absent from it", log)
    thinned = [o for o in obs if o["w"] not in ("three", "seven")]
    cut = V.score(thinned, text, "en")["asr_coverage_ceiling"]
    _check(cut["coverage_ceiling_pct_any_matcher"] == 80.0, "CTL-CEILING/mut",
           f"removing 2 of 10 tokens from the transcript must drop the ceiling to 80.0, "
           f"got {cut['coverage_ceiling_pct_any_matcher']}", log)
    _check(cut["display_tokens_absent_from_transcript"] == 2, "CTL-CEILING/mut",
           "and must name both as absent", log)
    _check(cut["coverage_ceiling_clears_bar"] is False, "CTL-CEILING/mut",
           "a ceiling of 80.0 must not report that it clears the 95 bar", log)
    _check(full["coverage_ceiling_clears_bar"] is True, "CTL-CEILING",
           "and a ceiling of 100 must report that it does", log)

    # ── CTL-CEILING-BOUNDS — the ceiling is an UPPER bound on the achieved ───
    # A ceiling BELOW the end-to-end figure would mean the bound is not a bound.
    # Checked on the real committed clip, not only on the synthetic stream.
    _check(full["coverage_ceiling_pct_any_matcher"] >= clean["match_rate_pct"], "CTL-CEILING",
           "the ceiling must be >= the coverage the matcher actually reached", log)

    # ── CTL-LENGTH — a chapter-length claim cannot be made by a short clip ───
    # This is `J29-C1`'s shape: a figure from a short fixture read as a
    # chapter-length result. It is a FIELD here, so the guard is a computation
    # rather than a sentence in a report someone has to remember to write.
    short_row = {"display_words": 224, "seconds": 73.18}
    long_row = {"display_words": 1186, "seconds": 396.24}
    supports = lambda r: bool(r["display_words"] >= 1000 and r["seconds"] * 1000 >= 300000)
    _check(supports(short_row) is False, "CTL-LENGTH",
           "224 display words / 73 s must NOT support a chapter-length claim", log)
    _check(supports(long_row) is True, "CTL-LENGTH/mut",
           "1186 display words / 396 s must", log)

    # ── CTL-ORTHO — the respelling ruleset does what its name says ───────────
    # Asserted in both directions: it rewrites British forms, and it is IDENTITY
    # on text that has none. A "probe" that quietly rewrote unrelated words would
    # inflate the recovered-pp figure and make a normaliser gap look larger than
    # it is — in the flattering direction, which is where this project's errors
    # have always gone.
    _check(_respell_en_gb_to_us("digitisation programme colours catalogue")
           == "digitization program colors catalog", "CTL-ORTHO",
           f"the en-GB -> en-US ruleset must rewrite the forms it names, got "
           f"{_respell_en_gb_to_us('digitisation programme colours catalogue')!r}", log)
    _check(_respell_en_gb_to_us("Digitising the Programme") == "Digitizing the Program",
           "CTL-ORTHO", "and must preserve a leading capital", log)
    _check(_respell_en_gb_to_us("the reading group met on the first Tuesday")
           == "the reading group met on the first Tuesday", "CTL-ORTHO/mut",
           "and must be IDENTITY on text carrying none of those forms", log)
    _check(_respell_en_gb_to_us(para_text()) == para_text(), "CTL-ORTHO/mut",
           "the committed en paragraph fixture is already en-US and must be untouched", log)
    # THE CONTROL THAT WAS MISSING. The first run of this probe emitted `raize`
    # and `precize,` into its own residual list. `-ise` words that are `-ise` in
    # American English too must survive the ruleset untouched, in every inflection.
    for w in ("raise", "raised", "raising", "precise", "promise", "surprise",
              "wise", "advised", "exercises", "comprising", "Raise"):
        _check(_respell_en_gb_to_us(w) == w, "CTL-ORTHO/mut",
               f"{w!r} is -ise in American English too and must not be respelled, got "
               f"{_respell_en_gb_to_us(w)!r}", log)
    _check("raize" not in _respell_en_gb_to_us(EN_LONG)
           and "precize" not in _respell_en_gb_to_us(EN_LONG), "CTL-ORTHO/mut",
           "and the chapter fixture must contain no invented form after respelling", log)

    # ── CTL-COST — the spend gate arithmetic, hand-checkable ─────────────────
    est = _estimate("x" * 10000)
    _check(est["estimated_usd"] == 0.025, "CTL-COST",
           f"10,000 characters at $0.0025/1k is $0.025, got {est['estimated_usd']}", log)
    _check(_estimate(EN_LONG)["estimated_usd"] < 0.05, "CTL-COST",
           "the chapter fixture must cost less than the owner's $0.05 cap", log)

    # ── CTL-TEXT — the fixtures are the ones the artifact names ──────────────
    _check(len(M.display_words(EN_LONG)) >= 1000, "CTL-TEXT",
           f"the chapter fixture must be >= 1000 display words, "
           f"got {len(M.display_words(EN_LONG))}", log)
    _check(para_text() == json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8")
                                     )["paragraph"]["en"]["text"], "CTL-TEXT",
           "the paragraph fixture is READ from fixtures.json, never copied", log)
    _check(EN_LONG != para_text(), "CTL-TEXT/mut",
           "the two fixtures must be different texts", log)

    V.Mutation.reset()
    passed = sum(1 for _, ok, _ in log if ok)
    print(f"\nself-test: {len(log)} controls, {passed} passed")
    by = {}
    for cid, ok, _ in log:
        by.setdefault(cid, [0, 0])
        by[cid][0] += 1
        by[cid][1] += int(ok)
    for cid in sorted(by):
        print(f"  {cid:20} {by[cid][1]}/{by[cid][0]}")
    print("\n  Each control is asserted in BOTH directions: it holds on clean input and the")
    print("  '/mut' variants prove it breaks on a defect.")
    return 0 if passed == len(log) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--measure", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.plan:
        return cmd_plan()
    if a.probe:
        return cmd_probe(a.yes)
    if a.measure:
        return cmd_measure()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
