#!/usr/bin/env python3
"""
SPIKE A, step 6 — CONSTRUCTED GROUND TRUTH, and the bar scored against it.

WHY THIS FILE EXISTS.

`matched_within_drift_pct >= 95` has never been evaluated against a reference
that knows where the words are. Every attempt compared two ASR engines to each
other, which measures AGREEMENT, and Jury named the consequence: "scoring forced
alignment against a Whisper reference penalises the precise method for being
precise." The figure on record — 62.5 / 68.2 / 75.0 — is explicitly a FLOOR, not
a verdict, because the drift instrument charges clause pauses to misalignment
(measure.py:378-382). Halo listed four cheaper falsifications; this is the third,
the one that needs no human:

  "Constructed ground truth, zero annotation. Synthesize each fixture word as its
   own TTS call and concatenate with known silence — boundaries are exact BY
   CONSTRUCTION. ~25 calls, cents, no human."

THE CORRECTNESS OF THE REFERENCE IS THE DELIVERABLE, not the audio. So the
construction states its own guarantee and then proves it against the bytes:

  1. Each display token is synthesized ALONE, by the same provider and voice the
     fixture names, and cached under out/gt/words/<lang>/. One call per word,
     once, forever.
  2. Each per-word file is trimmed to its SPEECH REGION: the first and last
     sample whose magnitude reaches `REL_THRESH` of that word's own peak, then
     widened by `PAD_MS` on each side so a low-energy onset (a fricative, an
     unstressed article) is never cut. What is discarded is therefore, by
     construction, below the threshold — and the peak of the discarded part is
     recorded per word so the claim is auditable rather than asserted.
  3. The regions are concatenated with exactly `GAP_MS` of DIGITAL SILENCE
     between them, and `GAP_MS` of lead-in before the first word. No resampling,
     no gain, no fade: the samples in the corpus are the samples the provider
     returned.
  4. Word k therefore occupies a byte range this file computed, not a range any
     model estimated. `--verify` re-reads the finished .wav and proves it:
     every word's samples are byte-identical to the trimmed source region, and
     every gap is exactly zero. That check is mutated in `--self-test` — a
     one-sample flip, a 50 ms insertion and a swapped pair of rows must all make
     it fail, or it is not a check.

WHAT THE TRUE BOUNDARY IS, EXACTLY. `start_s` / `end_s` are the threshold
crossings — the first and last audible sample. `region_start_s` / `region_end_s`
are the padded edges that bound the byte range. The scorer uses `start_s`, and
the difference between the two is the construction's own uncertainty band:
at most PAD_MS, in a known direction, recorded per word.

WHAT THIS CORPUS IS NOT — and this must travel with every number it produces.

  * It is NOT natural speech. Each word carries its own citation-form prosody:
    isolated stress, a phrase-final fall, no coarticulation across the boundary,
    and a uniform inter-word gap that no speaker produces. Word boundaries here
    are acoustically EASIER than in prose, where the end of one word and the
    start of the next are the same 30 ms of signal.
  * Therefore this is a LOWER BOUND ON DIFFICULTY. A method that fails here
    certainly fails on prose. A method that passes here has not been shown to
    pass on prose.
  * It cannot be quoted as "word sync measured on real audio". It measures the
    matcher and the timestamp source against a reference that is exactly right,
    on input that is exactly kind.

THE LONGER CORPORA. The whole spike is 62.5 seconds, 8-12 s per clip (H26-M7):
the failure the bar exists to catch — drift ACCUMULATING across a chapter —
cannot appear by construction. Two answers, because they fail differently:

  * `<lang>-gtlong.wav`: the same per-word audio, repeated to >=150 words and
    >=60 s. Ground truth is still exact, so accumulation is measured against
    TRUE boundaries. Confound: the text repeats, which is not what a chapter
    does, and a decoder may skip or loop on repetition. Costs nothing — the
    per-word audio already exists.
  * `<lang>-para.wav`: a ~150-word natural paragraph, one TTS call, added to
    fixtures.json under `paragraph`. No ground truth exists for it, so
    accumulation is probed against forced alignment, which is a Viterbi pass
    over the whole utterance and has no mechanism by which error can accumulate
    monotonically with position. A monotone trend in (ASR - FA) is therefore
    attributable to the ASR side; the absolute level of that difference is not
    an error measurement and is not reported as one.

COST DISCIPLINE (owner's standing rule). `--build --one` makes exactly ONE call
and stops. The full build is 70 word calls (en 24, es 22, fr 24) plus 3
paragraph calls = 73. Every call is cached on disk and skipped on re-run, so the
second build is free. No key is ever printed.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import pathlib
import re
import statistics
import sys
import time
import unicodedata
from array import array

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
WORDS = OUT / "gt" / "words"
sys.path.insert(0, str(ROOT))
import harness as H          # noqa: E402  wav_info / write_json / repair_wav_header / scoring
import measure as M          # noqa: E402  display_words / match / transcribe
import tts as T              # noqa: E402  load_env / synth_lemonfox / synth_fish / wav_wrap

FIXTURES = ROOT / "fixtures.json"
MANIFEST = OUT / "spike-a-groundtruth-manifest.json"
RESULTS = OUT / "spike-a-groundtruth.json"

# ── The construction's constants. Declared, not tuned. ───────────────────
GAP_MS = 300          # digital silence between words, and before the first
PAD_MS = 15           # kept on each side of the threshold crossing
REL_THRESH = 0.02     # of the word's OWN peak -- ~-34 dB relative
ABS_FLOOR = 0.002     # of full scale, so a near-silent file cannot self-normalise
LONG_WORDS_MIN = 150  # H26-M7: the corpus must be long enough for drift to accumulate
LONG_SECONDS_MIN = 60.0
# A single word is a degenerate prompt and a TTS engine can run away on it. Fish
# s2-pro returned TWELVE AND A HALF SECONDS of speech for the French token `3`
# on the first build. Nothing in a byte-level check can see that: the layout was
# arithmetically perfect and the corpus was still wrong, because the audio did
# not say the word. Duration is the cheapest observable that separates "one word
# spoken" from "the engine started talking", so it is a leg of --verify with its
# own mutation, not a thing the builder noticed once.
OUTLIER_FACTOR = 6.0
# MMS_FA is a wav2vec2 transformer with full self-attention over frames, so its
# cost grows with the SQUARE of the clip length: a 143 s corpus is not seven
# times a 20 s one, it is roughly fifty. Measured here at ~40 s for a 73 s clip
# and unbounded past that. The cap is declared rather than discovered, and a
# corpus over it records WHY forced alignment is missing instead of leaving a
# blank that reads like a result. The corpora over the cap are the `-gtlong`
# ones, and they need FA least: they have exact ground truth already.
FA_MAX_SECONDS = 90.0

# The bar, restated from measure.py so this file never invents its own.
DRIFT_MS = M.DRIFT_MS
BAR_MATCHED_PCT = M.BAR_MATCHED_PCT
BAR_P95_MS = M.BAR_P95_MS

LIMITS = [
    "CONSTRUCTED CORPUS. Every word was synthesized as its own TTS call and the "
    "clips were concatenated with a fixed digital silence. Boundaries are exact by "
    "construction; the SPEECH is not natural.",
    "No coarticulation: in prose the end of one word and the start of the next share "
    "the same signal, and that shared region is where boundary error actually lives. "
    "Here every boundary is surrounded by silence.",
    "No sentence prosody: each word carries citation-form stress and a phrase-final "
    "fall, because each was synthesized alone.",
    "Uniform inter-word silence: no speaker produces a constant gap, and a constant "
    "gap is an easier segmentation problem than a variable one.",
    "IT IS NOT UNIFORMLY EASIER, AND THE FIRST DRAFT OF THIS LIST SAID IT WAS. The "
    "corpus is easier for BOUNDARY placement — every boundary is surrounded by "
    "silence — and HARDER for RECOGNITION, because a word synthesized alone reaches "
    "the decoder with no language-model context. Measured: the French match rate is "
    "75.0% on the constructed corpus against 95.8% on the natural fixture, same voice, "
    "same words. So a low match rate here is partly the corpus and a low TIMING score "
    "here is not excused by it. The two halves of the bar have to be read separately, "
    "and a single sentence calling the whole thing a lower bound was wrong.",
    "THEREFORE, ON TIMING: failure here implies failure on prose. Success here does NOT "
    "imply success on prose, and no figure from this file may be quoted as word sync "
    "measured on natural audio.",
    "THE INSERTED SILENCE IS LONGER THAN THE BAR. 315-330 ms separates every pair of "
    "words; the drift bound is 250 ms. A decoder that assigns a word's start to the "
    "moment the previous word ended is therefore charged MORE than the whole bound here "
    "and ~30 ms on prose, for identical behaviour. `--analyse` decomposes exactly this "
    "and the strict figure must never be quoted without it.",
    "The `-gtlong` corpus repeats the fixture sentence to reach length. Repetition is "
    "not what a chapter does and a decoder may loop or skip on it; the timing question "
    "it answers is sound, the recognition figures on it are not comparable to prose.",
    "The `-para` corpus is natural prose and has NO ground truth. Its accumulation "
    "probe is against forced alignment, which cannot accumulate monotonically. The "
    "LEVEL of (ASR - FA) is engine disagreement, not error; only the SLOPE is read.",
]


# ── Audio primitives ─────────────────────────────────────────────────────

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _src_hashes() -> dict:
    """
    Hash the system under test AT IMPORT, not at write time.

    `measure.match` and `measure.transcribe` are the thing being measured and
    they were being rewritten by another agent while this ran — the matcher now
    shells out to `worker/src/normalize/`, so the product normaliser is part of
    the system too. Hashing when the artifact is written records whatever is on
    disk THEN, which on a long run is a different file from the one that
    produced the numbers. Hashing at import records what was loaded.
    """
    out = {}
    for p in [ROOT / "measure.py", ROOT / "harness.py", ROOT / "fa.py"] + \
             sorted((ROOT.parent.parent / "worker" / "src" / "normalize").glob("*.ts")):
        try:
            out[str(p.relative_to(ROOT.parent.parent)).replace("\\", "/")] = sha256(p.read_bytes())
        except OSError:
            pass
    return out


SRC_SHA = _src_hashes()


def wav_pcm(path: pathlib.Path):
    """(pcm_bytes, rate, channels, bits) with the data offset taken from the parsed chunk."""
    raw = path.read_bytes()
    info = H.wav_info(path)          # H26-m1: duration from file size, never the header
    if info["bits"] != 16:
        sys.exit(f"{path.name}: {info['bits']}-bit audio; this construction assumes s16le")
    if info["channels"] != 1:
        sys.exit(f"{path.name}: {info['channels']} channels; this construction assumes mono")
    off = len(raw) - info["actual_data_bytes"]
    return raw[off:off + info["actual_data_bytes"]], info["sample_rate"], info["channels"], info["bits"]


def speech_region(pcm: bytes):
    """
    (region_start, onset, end_excl, region_end, peak, discarded_peak) in SAMPLES.

    Threshold is relative to the word's own peak with an absolute floor, so a
    quiet rendition is not judged against a loud one. The returned region is
    widened by PAD_MS on each side: the padding is what keeps a low-energy onset
    from being cut, and it is the reason `start_s` (the crossing) and
    `region_start_s` (the byte edge) are reported separately rather than
    conflated into one number that would be wrong by an unstated amount.
    """
    a = array("h")
    a.frombytes(pcm[:len(pcm) - (len(pcm) % 2)])
    if not a:
        return None
    peak = max(max(a), -min(a))
    if peak == 0:
        return None
    thr = max(peak * REL_THRESH, 32767 * ABS_FLOOR)
    onset = end = None
    for i, v in enumerate(a):
        if v >= thr or -v >= thr:
            if onset is None:
                onset = i
            end = i
    if onset is None:
        return None
    return onset, end + 1, peak, a


def region_for(pcm: bytes, rate: int):
    r = speech_region(pcm)
    if r is None:
        return None
    onset, end_excl, peak, a = r
    pad = int(round(PAD_MS * rate / 1000.0))
    rs = max(0, onset - pad)
    re_ = min(len(a), end_excl + pad)
    discarded = list(a[:rs]) + list(a[re_:])
    dpeak = max((abs(v) for v in discarded), default=0)
    return {"region_start": rs, "onset": onset, "end_excl": end_excl, "region_end": re_,
            "peak": peak, "discarded_peak": dpeak, "samples": len(a)}


def silence(n_samples: int) -> bytes:
    return b"\x00" * (n_samples * 2)


# ── Reuse, not re-implementation ─────────────────────────────────────────

def borrow_from_fa():
    """
    Reuse `fa.py`'s numeral speller and tokenizer WITHOUT running `fa.py`.

    `fa.py` performs its whole measurement at module scope -- it loads MMS_FA and
    calls Lemonfox as a side effect of import -- so `import fa` would spend money
    and produce a second, conflicting artifact. Copying `spell()` and
    `tokens_for()` here is the failure class this repository has recorded seven
    times: one repair landing in two of three call sites. So the module is PARSED
    and only its function and constant definitions are executed. If `fa.py`'s
    tokenizer changes, this file changes with it; if the names disappear, this
    exits rather than silently falling back to a private copy.
    """
    tree = ast.parse((ROOT / "fa.py").read_text(encoding="utf-8"))
    keep = [n for n in tree.body
            if isinstance(n, ast.FunctionDef)
            or (isinstance(n, ast.Assign)
                and all(isinstance(t, ast.Name) and t.id in ("NUM", "TENS") for t in n.targets))]
    ns = {"re": re, "unicodedata": unicodedata, "__name__": "fa_defs"}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "fa.py<defs>", "exec"), ns)
    missing = [n for n in ("spell", "romanize", "tokens_for", "NUM", "TENS") if n not in ns]
    if missing:
        sys.exit(f"fa.py no longer defines {missing} -- refusing to substitute a private copy")
    return ns


# ── Build ────────────────────────────────────────────────────────────────

def slug(tok: str) -> str:
    s = unicodedata.normalize("NFKD", tok.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "x"


def synth_word(text: str, spec: dict, env: dict) -> bytes:
    """One call, one word, through tts.py's shipped provider functions."""
    if spec["provider"] == "lemonfox":
        audio = T.synth_lemonfox(text, spec["voice"], env["LEMONFOX_API_KEY"])
    elif spec["provider"] == "fish":
        audio = T.synth_fish(text, spec["reference_id"], env["FISH_AUDIO_API_KEY"])
    else:
        sys.exit(f"provider {spec['provider']!r} is not on the shipping routing table")
    return H.repair_wav_header(audio)


def build_words(lang: str, spec: dict, tokens: list, env: dict, one: bool, calls: list):
    """Synthesize any per-word clip not already cached. Returns [path per token]."""
    d = WORDS / lang
    d.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, tok in enumerate(tokens):
        p = d / f"{i:03d}-{slug(tok)}.wav"
        if not p.exists():
            t0 = time.time()
            audio = synth_word(tok, spec, env)
            p.write_bytes(audio)
            calls.append({"lang": lang, "index": i, "token": tok, "bytes": len(audio),
                          "seconds_elapsed": round(time.time() - t0, 1)})
            print(f"  {lang} [{i:>3}] {tok!r:<18} {len(audio):>7} bytes  "
                  f"{time.time() - t0:.1f}s -> {p.name}")
            if one:
                print("\n  --one: STOPPING after a single call. Read the real cost off the")
                print("  provider dashboard before scaling. Owner's standing rule on paid APIs.")
                return None
        paths.append(p)
    return paths


def concatenate(paths: list, tokens: list, repeats: int = 1):
    """
    Lay the trimmed regions out with fixed silence and record where each word IS.

    The layout is arithmetic on byte counts. Nothing here estimates anything, and
    that is the whole claim: `--verify` re-derives every row from the finished
    file and the sources.
    """
    rates = set()
    regions = []
    for p, tok in zip(paths, tokens):
        pcm, rate, ch, _ = wav_pcm(p)
        rates.add((rate, ch))
        r = region_for(pcm, rate)
        if r is None:
            sys.exit(f"{p.name}: no sample reaches the threshold -- the provider returned silence")
        regions.append((p, tok, pcm, r))
    if len(rates) != 1:
        sys.exit(f"per-word clips disagree on format: {sorted(rates)} -- refusing to resample")
    rate, ch = rates.pop()

    gap = int(round(GAP_MS * rate / 1000.0))
    buf = bytearray(silence(gap))            # lead-in, so word 1 does not start at t=0
    rows = []
    di = 0
    for _rep in range(repeats):
        for p, tok, pcm, r in regions:
            cur = len(buf) // 2              # sample cursor
            seg = pcm[r["region_start"] * 2:r["region_end"] * 2]
            buf += seg
            rows.append({
                "i": di,
                "token": tok,
                "src": p.name,
                "src_sha256": sha256(p.read_bytes()),
                "src_region_start_sample": r["region_start"],
                "src_region_end_sample": r["region_end"],
                "corpus_region_start_sample": cur,
                "corpus_region_end_sample": cur + len(seg) // 2,
                # THE GROUND TRUTH. Threshold crossings, in corpus time.
                "start_s": round((cur + (r["onset"] - r["region_start"])) / rate, 6),
                "end_s": round((cur + (r["end_excl"] - r["region_start"])) / rate, 6),
                # The padded byte edges. The gap between these and the crossings is
                # the construction's own uncertainty, stated rather than hidden.
                "region_start_s": round(cur / rate, 6),
                "region_end_s": round((cur + len(seg) // 2) / rate, 6),
                "speech_ms": round(1000.0 * (r["end_excl"] - r["onset"]) / rate, 2),
                "lead_pad_ms": round(1000.0 * (r["onset"] - r["region_start"]) / rate, 2),
                "tail_pad_ms": round(1000.0 * (r["region_end"] - r["end_excl"]) / rate, 2),
                "peak": r["peak"],
                "discarded_peak": r["discarded_peak"],
                "discarded_peak_ratio": round(r["discarded_peak"] / r["peak"], 4) if r["peak"] else 0.0,
            })
            buf += silence(gap)
            di += 1
    return T.wav_wrap(bytes(buf), rate=rate, ch=ch, bits=16), rows, rate, gap


def build(langs, one: bool, para: bool) -> None:
    env = T.load_env()
    fx = json.loads(FIXTURES.read_text(encoding="utf-8"))
    calls = []
    corpora = []

    for lang in langs:
        spec = fx["languages"][lang]
        tokens = [t for t, _, _ in M.display_words(spec["text"])]
        paths = build_words(lang, spec, tokens, env, one, calls)
        if paths is None:
            H.write_json(OUT / "spike-a-groundtruth-calls.json", calls)
            return

        for name, repeats in (("gt", 1), ("gtlong", math.ceil(LONG_WORDS_MIN / len(tokens)))):
            wav_bytes, rows, rate, gap = concatenate(paths, tokens, repeats)
            dest = OUT / f"{lang}-{name}.wav"
            dest.write_bytes(wav_bytes)
            info = H.wav_info(dest)
            if name == "gtlong" and (len(rows) < LONG_WORDS_MIN or info["seconds"] < LONG_SECONDS_MIN):
                sys.exit(f"{dest.name}: {len(rows)} words / {info['seconds']:.1f}s is below the "
                         f"H26-M7 floor of {LONG_WORDS_MIN} words and {LONG_SECONDS_MIN}s")
            corpora.append({
                "lang": f"{lang}-{name}",
                "language": lang,
                "kind": "constructed",
                "repeats": repeats,
                "text": " ".join(tokens * repeats),
                "provider": spec["provider"],
                "voice": spec["voice"],
                "audio": dest.name,
                "audio_seconds": round(info["seconds"], 2),
                "sha256": sha256(wav_bytes),
                "sample_rate": rate,
                "gap_ms": GAP_MS,
                "pad_ms": PAD_MS,
                "words": rows,
            })
            print(f"  {dest.name}: {len(rows)} words, {info['seconds']:.2f}s, "
                  f"{rate} Hz, gap {GAP_MS}ms  sha {sha256(wav_bytes)[:12]}…")

    if para:
        for lang in langs:
            pspec = fx.get("paragraph", {}).get(lang)
            if not pspec:
                sys.exit(f"fixtures.json has no `paragraph` fixture for {lang!r}")
            dest = OUT / f"{lang}-para.wav"
            if not dest.exists():
                t0 = time.time()
                audio = synth_word(pspec["text"], pspec, env)
                dest.write_bytes(audio)
                calls.append({"lang": lang, "kind": "paragraph", "bytes": len(audio),
                              "seconds_elapsed": round(time.time() - t0, 1)})
            info = H.wav_info(dest)
            n_words = len(M.display_words(pspec["text"]))
            if n_words < LONG_WORDS_MIN or info["seconds"] < LONG_SECONDS_MIN:
                print(f"  !! {dest.name}: {n_words} words / {info['seconds']:.1f}s is below the "
                      f"H26-M7 floor ({LONG_WORDS_MIN} words, {LONG_SECONDS_MIN}s)")
            corpora.append({
                "lang": f"{lang}-para",
                "language": lang,
                "kind": "natural_prose_NO_GROUND_TRUTH",
                "repeats": 1,
                "text": pspec["text"],
                "provider": pspec["provider"],
                "voice": pspec["voice"],
                "audio": dest.name,
                "audio_seconds": round(info["seconds"], 2),
                "sha256": sha256(dest.read_bytes()),
                "sample_rate": info["sample_rate"],
                "gap_ms": None,
                "pad_ms": None,
                "words": [],
            })
            print(f"  {dest.name}: {n_words} words, {info['seconds']:.2f}s (natural prose, no ground truth)")

    H.write_json(MANIFEST, {
        "_what_this_is": (
            "The reference SPIKE A never had. Word boundaries in the `constructed` corpora "
            "are byte arithmetic performed by groundtruth.py, not an estimate produced by "
            "any model. `--verify` re-derives every row from the finished .wav and the "
            "cached per-word sources; `--self-test` mutates that check and proves it fails."),
        "_construction": {
            "gap_ms": GAP_MS, "pad_ms": PAD_MS, "rel_threshold_of_word_peak": REL_THRESH,
            "abs_threshold_of_full_scale": ABS_FLOOR,
            "boundary_definition": (
                "start_s / end_s are the FIRST and LAST sample whose magnitude reaches the "
                "threshold, expressed in corpus time. region_start_s / region_end_s are the "
                "padded byte edges. The scorer uses start_s; the difference is the "
                "construction's own uncertainty, at most pad_ms, recorded per word as "
                "lead_pad_ms / tail_pad_ms."),
            "resampling": "none -- clips within a language share one rate by assertion",
        },
        "_limits": LIMITS,
        "corpora": corpora,
    })
    if calls:
        # CUMULATIVE. The first version overwrote, so the cost record described the
        # LAST invocation and the 74 calls before it vanished -- the same defect
        # tts.py fixed in its own manifest. A spend log that forgets is not a log.
        log = OUT / "spike-a-groundtruth-calls.json"
        rec = json.loads(log.read_text(encoding="utf-8")) if log.exists() else {}
        if not isinstance(rec, dict):
            rec = {"logged_rows": rec if isinstance(rec, list) else []}
        rec.setdefault("logged_rows", [])
        rec["logged_rows"] += [{"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **c} for c in calls]
        rec.setdefault("totals", {})["total_paid_calls"] = \
            rec["totals"].get("total_paid_calls", 0) + len(calls)
        H.write_json(log, rec)
    print(f"\nwrote {MANIFEST.name} — {len(corpora)} corpora, {len(calls)} paid call(s) this run")


# ── Verify: the boundaries, against the bytes ────────────────────────────

def verify(mutate=None) -> list:
    """
    Prove the manifest describes the file. No model, no network, no ASR.

    Three legs, and `--self-test` breaks each one on purpose:
      (i)   every word's corpus samples are byte-identical to its source region;
      (ii)  every inter-word gap is exactly zero;
      (iii) the file is exactly as long as the layout says it is.

    `mutate(pcm_bytearray, rate, rows)` is the injection point. A check that has
    never been made to fail is not a check -- this repository has recorded five
    instruments that passed while measuring the wrong thing.
    """
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    findings = []
    for c in man["corpora"]:
        if c["kind"] != "constructed":
            continue
        pcm, rate, _ch, _b = wav_pcm(OUT / c["audio"])
        pcm = bytearray(pcm)
        rows = [dict(r) for r in c["words"]]
        if mutate:
            mutate(pcm, rate, rows)
        gap = int(round(c["gap_ms"] * rate / 1000.0))
        src_cache = {}
        cursor = gap * 2                       # the lead-in silence
        if bytes(pcm[:cursor]) != silence(gap):
            findings.append(f"{c['audio']}: lead-in silence is not zero")
        for r in rows:
            a, b = r["corpus_region_start_sample"] * 2, r["corpus_region_end_sample"] * 2
            if a != cursor:
                findings.append(f"{c['audio']} word {r['i']} ({r['token']!r}): layout says sample "
                                f"{r['corpus_region_start_sample']}, the running cursor is {cursor // 2}")
            sp = WORDS / c["language"] / r["src"]
            if sp not in src_cache:
                src_cache[sp] = wav_pcm(sp)[0]
            src = src_cache[sp]
            want = src[r["src_region_start_sample"] * 2:r["src_region_end_sample"] * 2]
            if bytes(pcm[a:b]) != want:
                findings.append(f"{c['audio']} word {r['i']} ({r['token']!r}): corpus samples differ "
                                f"from the source region — the boundary is not where the manifest says")
            if bytes(pcm[b:b + gap * 2]) != silence(gap):
                findings.append(f"{c['audio']} word {r['i']} ({r['token']!r}): the gap after it is "
                                f"not digital silence")
            cursor = b + gap * 2
        if cursor != len(pcm):
            findings.append(f"{c['audio']}: layout ends at sample {cursor // 2}, file holds {len(pcm) // 2}")
        # The threshold claim, audited rather than asserted.
        for r in rows:
            if r["discarded_peak_ratio"] > REL_THRESH + 1e-9:
                findings.append(f"{c['audio']} word {r['i']}: discarded audio peaks at "
                                f"{r['discarded_peak_ratio']:.3f} of the word, above the "
                                f"{REL_THRESH} threshold — speech was trimmed")
        # (iv) RUNAWAY SYNTHESIS. Bytes can be laid out perfectly around audio
        # that does not say the word. A single token is a degenerate prompt and
        # Fish s2-pro answered the French `3` with 12.4 s of speech on the first
        # build — arithmetically sound, semantically worthless, and invisible to
        # every leg above.
        durs = [r["speech_ms"] for r in rows if "speech_ms" in r]
        if durs:
            med = statistics.median(durs)
            for r in rows:
                if r.get("speech_ms", 0) > OUTLIER_FACTOR * med:
                    findings.append(f"{c['audio']} word {r['i']} ({r['token']!r}): {r['speech_ms']:.0f} ms "
                                    f"of speech against a corpus median of {med:.0f} ms — the engine "
                                    f"ran away on a one-word prompt; re-synthesize it")
    return findings


# ── Score: the bar, against true boundaries ──────────────────────────────

def _fit(xs, ys):
    """OLS slope + Pearson r + a Fisher-z two-sided p. Stdlib only, and labelled."""
    n = len(xs)
    if n < 4:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0 or syy <= 0:
        return None
    r = sxy / math.sqrt(sxx * syy)
    r = max(-0.999999, min(0.999999, r))
    z = math.atanh(r) * math.sqrt(n - 3) if n > 3 else 0.0
    p = 2 * (1 - statistics.NormalDist().cdf(abs(z)))
    return {"n": n, "slope_ms_per_s": round(sxy / sxx, 3), "pearson_r": round(r, 3),
            "p_value_fisher_z": round(p, 4),
            "_stat_note": ("Fisher-z normal approximation, not an exact t test. Read as a "
                           "screen: |r| small and p large means no accumulation was detected, "
                           "which on this n is not the same as none existing.")}


def fa_starts(wav: pathlib.Path, display, lang: str, fa):
    """Forced alignment, mapped onto display token indices. Reuses fa.py's tokenizer."""
    import torch, torchaudio
    from torchaudio.pipelines import MMS_FA as B
    global _FA
    try:
        _FA
    except NameError:
        _FA = (B.get_model(), B.get_tokenizer(), B.get_aligner())
    model, tokenizer, aligner = _FA
    wf, sr = torchaudio.load(str(wav))
    if wf.shape[0] > 1:
        wf = wf.mean(0, keepdim=True)
    if sr != B.sample_rate:
        wf = torchaudio.functional.resample(wf, sr, B.sample_rate)
    toks, owner = fa["tokens_for"](display, lang)
    with torch.inference_mode():
        emission, _ = model(wf)
        spans = aligner(emission[0], tokenizer(toks))
    ratio = wf.shape[1] / emission.shape[1] / B.sample_rate
    units = H.units_from_expansion(
        [{"w": w, "s": sp[0].start * ratio, "e": sp[-1].end * ratio} for w, sp in zip(toks, spans)],
        owner)
    return {i: u["s"] for i, u in units.items()}


def _emit(rows) -> None:
    """
    Two files, because they are TWO ACCOUNTING BASES.

    J26-M2: a quoted figure set must be reproducible from one file and one basis,
    and `doc-check`'s `configurations()` reads values by key name at ANY depth.
    Leaving the forced-alignment scores nested inside the ASR rows put
    `matched_within_drift_pct` = {8.3, 15.5, …} and {95.8, 86.4, …} in the same
    bag, so a document could quote one number from each basis and the guard would
    wave it through — the exact defect J26-M2 named, rebuilt inside the artifact
    that exists to close it. The bases get separate files instead.
    """
    # IDEMPOTENT, because the first version was not and it destroyed real data.
    # `_emit` pops the FA blocks out of the rows it is given. Run it a second time
    # on rows it has already split — which is what happens when the artifact is
    # re-derived from disk — and there is nothing left to pop, so it rewrote the
    # FA file with three skip notices and deleted six measured results. The
    # measured FA numbers existed only in that file. Prior rows are now carried
    # forward for any corpus this call has no new FA data for.
    FA_FILE = OUT / "spike-a-groundtruth-fa.json"
    prior = {}
    if FA_FILE.exists():
        try:
            prior = {r["lang"]: r for r in json.loads(FA_FILE.read_text(encoding="utf-8"))["corpora"]}
        except (ValueError, KeyError, TypeError):
            prior = {}
    asr_rows, fa_rows = _split(rows, prior)
    if fa_rows:
        _emit_fa(fa_rows)
    rows = asr_rows
    H.write_json(RESULTS, {
        "_what_this_is": (
            "matched_within_drift_pct scored against CONSTRUCTED GROUND TRUTH, not against "
            "another engine. This is the number that converts 62.5 / 68.2 / 75.0 from a floor "
            "into a verdict — on audio that is easier than prose, which is the point of "
            "_limits below and is not optional context."),
        "_limits": LIMITS,
        "_bar": {"matched_within_drift_pct": BAR_MATCHED_PCT, "p95_drift_ms": BAR_P95_MS,
                 "drift_bound_ms": DRIFT_MS},
        "_scored_with": {
            "sha256": SRC_SHA,
            "_why": ("measure.match and measure.transcribe ARE the system under test, and they "
                     "were being rewritten by another agent while this ran — the matcher now "
                     "delegates to worker/src/normalize/, so the product normaliser is under "
                     "test too. Hashes are taken AT IMPORT, so they name what produced the "
                     "numbers rather than what happened to be on disk when the file was "
                     "written. A figure produced by an unnamed version of the matcher fails "
                     "leg (c) of admissibility."),
        },
        "corpora": rows,
    })


def _split(rows, prior):
    """Pure split of scored rows into (ASR basis, FA basis). Tested for idempotence."""
    fa_rows = []
    asr_rows = []
    for r in rows:
        r = dict(r)
        fa = r.pop("fa_vs_groundtruth", None)
        cross = r.pop("asr_minus_fa", None)
        skipped = r.get("fa_skipped")
        if fa or cross:
            fa_rows.append({k: r[k] for k in ("lang", "language", "kind", "audio_seconds",
                                              "audio_sha256", "display_words") if k in r}
                           | (fa or {}) | ({"asr_minus_fa": cross} if cross else {}))
            r["_forced_alignment"] = "reported separately in spike-a-groundtruth-fa.json"
        elif r["lang"] in prior:
            fa_rows.append(prior[r["lang"]])          # carried forward, not discarded
            r["_forced_alignment"] = "reported separately in spike-a-groundtruth-fa.json"
        elif skipped:
            fa_rows.append({k: r[k] for k in ("lang", "language", "kind", "audio_seconds",
                                              "audio_sha256", "display_words") if k in r}
                           | {"fa_skipped": skipped})
            r["_forced_alignment"] = "reported separately in spike-a-groundtruth-fa.json"
        asr_rows.append(r)
    return asr_rows, fa_rows


def _emit_fa(fa_rows) -> None:
    H.write_json(OUT / "spike-a-groundtruth-fa.json", {
            "_what_this_is": (
                "FORCED ALIGNMENT (torchaudio MMS_FA) scored against the SAME constructed ground "
                "truth, in its own file because it is a different accounting basis from the ASR "
                "timestamps in spike-a-groundtruth.json. Mixing the two inside one file lets a "
                "document quote one figure from each and call it a run (J26-M2)."),
            "_this_is_an_upper_bound_on_the_refinement_stage": (
                "FA HERE IS GIVEN THE TRUE TEXT. On the constructed corpus the display text is "
                "exactly what was spoken, so aligning the display text is legitimate — but it is "
                "NOT the shipped shape. §6.1 is `ASR -> FA -> match`, where FA receives the ASR "
                "TRANSCRIPT, and on this same corpus that transcript is 100% / 90.9% / 75.0% "
                "correct. So these figures answer 'how well can forced alignment place words "
                "when the words are known', which is the ceiling of the refinement stage and NOT "
                "an end-to-end result. Anything quoting them as end-to-end word sync is quoting "
                "the wrong number, which is the failure this whole spike keeps repeating."),
            "_limits": LIMITS,
            "_bar": {"matched_within_drift_pct": BAR_MATCHED_PCT, "p95_drift_ms": BAR_P95_MS,
                     "drift_bound_ms": DRIFT_MS},
            "corpora": fa_rows,
        })


def _fa_row(c, display, truth, asr_starts, fa) -> dict:
    """
    The forced-alignment basis for one corpus: FA against the constructed truth,
    and ASR-minus-FA as an accumulation probe. Factored out so `--fa-only` runs
    exactly the code `--score` runs, rather than a second implementation of it —
    the failure mode harness.py exists to prevent.
    """
    head = {k: c[k] for k in ("lang", "language", "kind", "audio_seconds") if k in c}
    head["audio_sha256"] = c["sha256"]
    head["display_words"] = len(display)
    if c["audio_seconds"] > FA_MAX_SECONDS:
        head["fa_skipped"] = (
            f"audio is {c['audio_seconds']}s, over the {FA_MAX_SECONDS}s cap. MMS_FA's cost is "
            f"quadratic in clip length. This corpus has EXACT ground truth, so forced alignment "
            f"adds nothing here that the truth does not already give.")
        return head
    try:
        fs = fa_starts(OUT / c["audio"], display, c["language"], fa)
    except Exception as e:                               # noqa: BLE001 — reported, never swallowed
        head["fa_error"] = f"{type(e).__name__}: {str(e)[:180]}"
        return head
    fd = [abs(fs[i] - truth[i]) * 1000.0 for i in sorted(set(fs) & set(truth))]
    if fd:
        fsrt = sorted(fd)
        head.update({
            "n": len(fd),
            "matched_within_drift_pct": round(
                100.0 * sum(1 for d in fd if d <= DRIFT_MS) / len(display), 1),
            "median_drift_ms": round(statistics.median(fd), 1),
            "p95_drift_ms": round(fsrt[int(0.95 * (len(fsrt) - 1))], 1),
            "engine": "torchaudio MMS_FA forced alignment",
        })
    both = sorted(set(fs) & set(asr_starts))
    if both:
        dd = [(asr_starts[i] - fs[i]) * 1000.0 for i in both]
        head["asr_minus_fa"] = {
            "n": len(both),
            "median_ms": round(statistics.median(dd), 1),
            "accumulation_vs_time": _fit([fs[i] for i in both], dd),
            "_basis": ("Engine disagreement, NOT error. Forced alignment is a Viterbi pass over "
                       "the whole utterance and has no mechanism by which error accumulates "
                       "monotonically with position, so a SLOPE here is attributable to the ASR "
                       "clock. The LEVEL is not an error measurement and must not be quoted as "
                       "one."),
        }
    return head


def fa_only() -> None:
    """
    Recompute the forced-alignment basis from the ASR starts already recorded in
    spike-a-groundtruth.json. No ASR, no API — the ~20 minutes of decoding is
    already on disk, so regenerating this basis costs only the alignment passes.
    """
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    asr = {c["lang"]: {w["i"]: w["obs_s"] for w in c.get("words", [])} for c in res["corpora"]}
    fa = borrow_from_fa()
    rows = []
    for c in man["corpora"]:
        if not (OUT / c["audio"]).exists():
            continue
        display = M.display_words(c["text"])
        truth = {r["i"]: r["start_s"] for r in c["words"]}
        row = _fa_row(c, display, truth, asr.get(c["lang"], {}), fa)
        rows.append(row)
        print(f"  {row['lang']:<12} within {row.get('matched_within_drift_pct', '—')}  "
              f"median {row.get('median_drift_ms', '—')}ms  p95 {row.get('p95_drift_ms', '—')}ms  "
              f"ASR-FA {(row.get('asr_minus_fa') or {}).get('median_ms', '—')}ms"
              f"{'  [skipped]' if 'fa_skipped' in row else ''}")
    _emit_fa(rows)
    print(f"\nwrote spike-a-groundtruth-fa.json — {len(rows)} corpora")


def score(model_size: str, ctype: str, want_fa: bool) -> None:
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    fx = json.loads(FIXTURES.read_text(encoding="utf-8"))
    fa = borrow_from_fa() if want_fa else None
    rows = []

    print(f"{'corpus':<12}{'n':>5}{'matched':>9}{'within':>9}{'median':>9}{'p95':>9}{'slope':>10}")
    for c in man["corpora"]:
        lang = c["language"]
        wav = OUT / c["audio"]
        if not wav.exists():
            print(f"{c['lang']:<12}  audio absent, skipped")
            continue
        display = M.display_words(c["text"])
        obs, _wall, tm = M.transcribe(wav, lang, model_size, ctype, False)
        matched, halluc = M.match(obs, display, lang)
        truth = {r["i"]: r["start_s"] for r in c["words"]}
        shared = sum(1 for m in matched if m.get("shared_token"))

        words, drift, signed, xs = [], [], [], []
        for m in matched:
            t = truth.get(m["disp_idx"])
            row = {"i": m["disp_idx"], "token": m["disp"], "obs_s": round(m["s"], 4),
                   "heard": m["obs_w"], "via_normalizer": bool(m.get("via_normalizer"))}
            if t is not None:
                d = (m["s"] - t) * 1000.0
                row.update({"true_s": round(t, 4), "signed_delta_ms": round(d, 1),
                            "abs_drift_ms": round(abs(d), 1)})
                drift.append(abs(d))
                signed.append(d)
                xs.append(t)
            words.append(row)

        r = {
            "lang": c["lang"],
            "language": lang,
            "kind": c["kind"],
            "audio_seconds": c["audio_seconds"],
            "audio_sha256": c["sha256"],
            "display_words": len(display),
            "observed_tokens": len(obs),
            "matched": len(matched),
            "match_rate_pct": round(100.0 * len(matched) / len(display), 1) if display else 0.0,
            "hallucination_rate": round(100.0 * len(halluc) / len(obs), 1) if obs else 0.0,
            "shared_token_matches": shared,
            "asr_model": f"faster-whisper {model_size}/{ctype}",
            "words": words,
        }

        if drift:
            srt = sorted(drift)
            in_bound = sum(1 for d in drift if d <= DRIFT_MS)
            r.update({
                "drift_reference": "constructed ground truth (exact by construction)",
                "drift_measurable_tokens": len(drift),
                "matched_within_drift_pct": round(100.0 * in_bound / len(display), 1),
                "median_drift_ms": round(statistics.median(drift), 1),
                "p95_drift_ms": round(srt[int(0.95 * (len(srt) - 1))], 1),
                "median_signed_delta_ms": round(statistics.median(signed), 1),
                "drift_bound_ms": DRIFT_MS,
                "passes_matched_bar": bool(100.0 * in_bound / len(display) >= BAR_MATCHED_PCT),
                "passes_p95_bar": bool(srt[int(0.95 * (len(srt) - 1))] <= BAR_P95_MS),
                "accumulation_signed_delta_vs_time": _fit(xs, signed),
                "accumulation_abs_drift_vs_time": _fit(xs, drift),
                "_basis": ("EVERY drift figure in this row is |ASR start - TRUE start|, where TRUE "
                           "is the threshold crossing this file placed by byte arithmetic. It is "
                           "NOT engine disagreement and NOT neighbour interpolation. It is also "
                           "not comparable to measure.py's figure, which is a different quantity "
                           "on different audio."),
            })
        else:
            r["drift_reference"] = "NONE — natural prose, no ground truth exists for this corpus"

        if fa and c["audio_seconds"] > FA_MAX_SECONDS:
            r["fa_skipped"] = (
                f"audio is {c['audio_seconds']}s, over the {FA_MAX_SECONDS}s cap. MMS_FA's cost "
                f"is quadratic in clip length. This corpus has EXACT ground truth, so forced "
                f"alignment adds nothing here that the truth does not already give.")
        elif fa:
            try:
                fs = fa_starts(wav, display, lang, fa)
                asr = {m["disp_idx"]: m["s"] for m in matched}
                both = sorted(set(fs) & set(asr))
                if drift:
                    fd = [abs(fs[i] - truth[i]) * 1000.0 for i in sorted(set(fs) & set(truth))]
                    if fd:
                        fsrt = sorted(fd)
                        r["fa_vs_groundtruth"] = {
                            "n": len(fd),
                            "matched_within_drift_pct": round(
                                100.0 * sum(1 for d in fd if d <= DRIFT_MS) / len(display), 1),
                            "median_drift_ms": round(statistics.median(fd), 1),
                            "p95_drift_ms": round(fsrt[int(0.95 * (len(fsrt) - 1))], 1),
                            "engine": "torchaudio MMS_FA forced alignment",
                        }
                if both:
                    dd = [(asr[i] - fs[i]) * 1000.0 for i in both]
                    tt = [fs[i] for i in both]
                    r["asr_minus_fa"] = {
                        "n": len(both),
                        "median_ms": round(statistics.median(dd), 1),
                        "accumulation_vs_time": _fit(tt, dd),
                        "_basis": ("Engine disagreement, NOT error. Forced alignment is a Viterbi "
                                   "pass over the whole utterance and has no mechanism by which "
                                   "error accumulates monotonically with position, so a SLOPE here "
                                   "is attributable to the ASR clock. The LEVEL is not an error "
                                   "measurement and must not be quoted as one."),
                    }
            except Exception as e:                       # noqa: BLE001 — reported, never swallowed
                r["fa_error"] = f"{type(e).__name__}: {str(e)[:180]}"

        spec = fx["languages"].get(lang, {})
        if c["kind"] == "constructed" and c["repeats"] == 1 and spec:
            resolved = {m["disp_idx"]: m for m in matched}
            hard = H.hard_token_report(spec, display, resolved, lang)
            r["expect_hard"] = hard
            r.update(H.hard_falsification(hard, r["match_rate_pct"]))

        rows.append(r)
        # Written after EVERY corpus, not once at the end. The first version held
        # nine results in memory for the length of the run and wrote them last, so
        # an out-of-memory kill in the ninth would have destroyed the first eight.
        _emit(rows)
        acc = (r.get("accumulation_signed_delta_vs_time") or {}).get("slope_ms_per_s")
        print(f"{c['lang']:<12}{len(display):>5}{r['match_rate_pct']:>8.1f}%"
              f"{r.get('matched_within_drift_pct', float('nan')):>8.1f}%"
              f"{r.get('median_drift_ms', float('nan')):>8.1f}ms"
              f"{r.get('p95_drift_ms', float('nan')):>8.1f}ms"
              f"{(f'{acc:+.2f}ms/s' if acc is not None else '—'):>10}")

    print(f"\nwrote {RESULTS.name}  (bar: matched >= {BAR_MATCHED_PCT}%, p95 <= {BAR_P95_MS}ms)")


# ── Decompose the drift the construction itself creates ──────────────────

def analyse(results=None, manifest=None, write=True):
    """
    Separate "the timestamp landed in the silence I inserted" from "the timestamp
    is in the wrong place". No ASR, no API — a derivation from what --score
    already recorded per word, so it is reproducible from the two artifacts.

    WHY THIS IS NOT AN EXCUSE. The corpus puts 315-330 ms of digital silence
    before every word, which is LONGER THAN THE 250 ms BOUND. Prose does not:
    between two words in a phrase there is typically 0-50 ms and often none at
    all. So a decoder that assigns a word's start to the moment the previous word
    stopped is charged up to 330 ms here and would be charged ~30 ms on prose,
    for identical behaviour. Reporting only the strict figure would blame the
    engine for the corpus — the fifth-instrument failure, arriving from the
    other direction.

    Reporting only the tolerant figure would be worse: it credits a highlight
    that switches on a third of a second before the word is audible, which for a
    screen-reader user tracking audio against text is a real defect, not a
    rounding artifact. Both are emitted. Neither is the headline alone.
    """
    res = results or json.loads(RESULTS.read_text(encoding="utf-8"))
    man = manifest or json.loads(MANIFEST.read_text(encoding="utf-8"))
    truth = {c["lang"]: c["words"] for c in man["corpora"]}
    for row in res["corpora"]:
        ws = [w for w in row.get("words", []) if "true_s" in w]
        rows = truth.get(row["lang"]) or []
        if not ws or not rows:
            continue
        end_by_i = {r["i"]: r["end_s"] for r in rows}
        prev_end = {r["i"]: end_by_i.get(r["i"] - 1, 0.0) for r in rows}
        tol, early, overlap, atafter, win = [], 0, 0, 0, []
        for w in ws:
            i, o, t = w["i"], w["obs_s"], w["true_s"]
            pe = prev_end.get(i, 0.0)
            win.append((t - pe) * 1000.0)
            if pe <= o < t:
                tol.append(0.0); early += 1
            elif o < pe:
                tol.append(abs(o - t) * 1000.0); overlap += 1
            else:
                tol.append(abs(o - t) * 1000.0); atafter += 1
        # A CONSTANT OFFSET IS A DIFFERENT DEFECT FROM SCATTER, and only one of
        # them is correctable. calibrate.py already fits a per-language offset in
        # this spike, so the question "how much of this failure is bias" is not
        # academic. The residual below is fitted and scored on THE SAME DATA --
        # in-sample, therefore optimistic, and labelled as such rather than
        # quoted as an achieved figure. Fitting and scoring on one clip is the
        # exact discipline failure fixtures.json:20 was written about.
        sd = [w["signed_delta_ms"] for w in ws]
        off = statistics.median(sd)
        resid = sorted(abs(x - off) for x in sd)
        srt = sorted(tol)
        row["constant_offset_decomposition"] = {
            "median_signed_offset_ms": round(off, 1),
            "matched_within_drift_pct_after_offset": round(
                100.0 * sum(1 for d in resid if d <= DRIFT_MS) / row["display_words"], 1),
            "median_residual_ms": round(statistics.median(resid), 1),
            "p95_residual_ms": round(resid[int(0.95 * (len(resid) - 1))], 1),
            "_basis": (
                "The per-corpus median signed delta removed, then scored. IN-SAMPLE: the offset "
                "is fitted on the very tokens it is scored against, so this is an upper bound and "
                "not an achieved result. It is here to answer one question — is the failure a "
                "correctable BIAS or irreducible SCATTER — because a bias is a calibration "
                "constant and scatter is not fixable at all."),
        }
        row["silence_decomposition"] = {
            "median_constructed_silence_before_word_ms": round(statistics.median(win), 1),
            "tokens_timestamped_inside_that_silence": early,
            "tokens_timestamped_before_the_previous_word_ended": overlap,
            "tokens_timestamped_at_or_after_the_true_onset": atafter,
            "matched_within_drift_pct_silence_tolerant": round(
                100.0 * sum(1 for d in tol if d <= DRIFT_MS) / row["display_words"], 1),
            "median_drift_ms_silence_tolerant": round(statistics.median(tol), 1),
            "p95_drift_ms_silence_tolerant": round(srt[int(0.95 * (len(srt) - 1))], 1),
            "_basis": (
                "A start landing anywhere in the silence THIS FILE INSERTED before the word "
                "is scored as zero drift; everything else is scored strictly. This is an "
                "UPPER bound and the strict figure beside it is a LOWER bound. The truth for "
                "prose is between them and nearer the strict one, because prose has 0-50 ms "
                "between words where this corpus has 315-330 — LONGER THAN THE BOUND ITSELF. "
                "Quoting the tolerant figure alone credits a highlight that switches on a "
                "third of a second early, which a blind user tracking audio against text "
                "experiences as the highlight running ahead of the voice."),
        }
    if write:
        H.write_json(RESULTS, res)
    return res


# ── Self-test: make the instrument fail on purpose ───────────────────────

def self_test() -> int:
    """
    Every trial breaks something the harness is supposed to catch. A trial that
    does not turn the check red is a trial that proves the check is decoration.
    """
    trials, failed = [], 0

    def trial(name, fn, expect_findings: bool):
        nonlocal failed
        try:
            found = fn()
        except SystemExit as e:
            found = [f"SystemExit: {e}"]
        ok = bool(found) == expect_findings
        trials.append((name, ok, len(found) if isinstance(found, list) else found))
        if not ok:
            failed += 1
            print(f"  FAIL  {name}: expected {'findings' if expect_findings else 'clean'}, "
                  f"got {found[:2] if isinstance(found, list) else found}")
        else:
            print(f"  ok    {name}")

    if not MANIFEST.exists():
        print("no manifest — run --build first"); return 1

    # 1. The unmutated construction must be clean, or every trial below is noise.
    trial("GT-CLEAN            construction verifies against its own bytes", verify, False)

    # 2. One sample changed. If a corpus can be edited without the check noticing,
    #    the manifest describes an idea of the file, not the file.
    def flip(pcm, rate, rows):
        i = rows[len(rows) // 2]["corpus_region_start_sample"] * 2 + 40
        pcm[i] = (pcm[i] + 1) % 256
    trial("GT-FLIP             a single altered sample is detected",
          lambda: verify(flip), True)

    # 3. 50 ms inserted before a word: the classic accumulating-offset defect,
    #    injected. Everything after the insertion point must go red.
    def insert(pcm, rate, rows):
        at = rows[3]["corpus_region_start_sample"] * 2
        pcm[at:at] = silence(int(0.050 * rate))
    trial("GT-INSERT           50 ms inserted mid-corpus is detected",
          lambda: verify(insert), True)

    # 4. Two rows swapped. This is the "paired the wrong occurrence" failure that
    #    burned this spike once already, expressed in the manifest.
    def swap(pcm, rate, rows):
        rows[2]["corpus_region_start_sample"], rows[5]["corpus_region_start_sample"] = \
            rows[5]["corpus_region_start_sample"], rows[2]["corpus_region_start_sample"]
        rows[2]["corpus_region_end_sample"], rows[5]["corpus_region_end_sample"] = \
            rows[5]["corpus_region_end_sample"], rows[2]["corpus_region_end_sample"]
    trial("GT-SWAP             two boundary rows exchanged are detected",
          lambda: verify(swap), True)

    # 5. A gap filled with signal. Silence between words is part of the claim.
    def fill(pcm, rate, rows):
        b = rows[1]["corpus_region_end_sample"] * 2
        pcm[b:b + 200] = b"\x11" * 200
    trial("GT-GAPFILL          a non-silent gap is detected",
          lambda: verify(fill), True)

    # 6. The trimmer is not a no-op. Prepending silence to a source must move the
    #    detected onset by the amount prepended, and must not move the boundary
    #    RELATIVE to the region -- which is the quantity the layout uses.
    def trim_moves():
        src = sorted((WORDS).rglob("*.wav"))
        if not src:
            return ["no per-word audio cached"]
        pcm, rate, _c, _b = wav_pcm(src[0])
        a = region_for(pcm, rate)
        pre = int(0.5 * rate)
        b = region_for(silence(pre) + pcm, rate)
        moved = b["onset"] - a["onset"]
        rel_a = a["onset"] - a["region_start"]
        rel_b = b["onset"] - b["region_start"]
        bad = []
        if abs(moved - pre) > 1:
            bad.append(f"onset moved {moved} samples, expected {pre}")
        if rel_a != rel_b:
            bad.append(f"region-relative onset changed {rel_a} -> {rel_b}")
        return bad
    trial("GT-TRIM             onset detection tracks a 500 ms prepend", trim_moves, False)

    # 8. Runaway synthesis. The one defect this build actually hit, and the one
    #    a byte-perfect layout cannot see.
    def runaway(pcm, rate, rows):
        rows[4]["speech_ms"] = statistics.median(r["speech_ms"] for r in rows) * 20
    trial("GT-RUNAWAY          a word 20x the median duration is detected",
          lambda: verify(runaway), True)

    # 9. The two accounting bases must be DIFFERENT COMPUTATIONS. If every start
    #    is moved to the instant the previous word ended, the tolerant figure has
    #    to read 100% and the strict one has to collapse. A pair of numbers that
    #    move together is one number reported twice.
    def bases_differ():
        if not RESULTS.exists():
            return ["no scores yet"]
        res = json.loads(RESULTS.read_text(encoding="utf-8"))
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        truth = {c["lang"]: {r["i"]: r for r in c["words"]} for c in man["corpora"]}
        for row in res["corpora"]:
            t = truth.get(row["lang"]) or {}
            for w in row.get("words", []):
                if "true_s" in w and w["i"] - 1 in t:
                    w["obs_s"] = t[w["i"] - 1]["end_s"]      # exactly at the previous end
        out = analyse(results=res, manifest=man, write=False)
        bad = []
        for row in out["corpora"]:
            d = row.get("silence_decomposition")
            if not d:
                continue
            if d["median_drift_ms_silence_tolerant"] != 0.0:
                bad.append(f"{row['lang']}: every start moved into the silence and the tolerant "
                           f"median is {d['median_drift_ms_silence_tolerant']}, not 0")
        return bad
    trial("GT-BASES            strict and silence-tolerant are different computations",
          bases_differ, False)

    # 10. THE BUG THIS AUTHOR ACTUALLY SHIPPED, thirty minutes before writing this
    #     trial. `_emit` splits the two bases into two files by POPPING the FA
    #     blocks out of the rows. Run it a second time on rows it has already
    #     split and there is nothing left to pop — so it rewrote the FA file with
    #     three skip notices and destroyed six measured results that existed
    #     nowhere else. Re-deriving an artifact from disk is a normal thing to do
    #     and it silently deleted evidence. The split is now idempotent and this
    #     is the check that says so.
    def split_idempotent():
        rows = [
            {"lang": "x-gt", "matched_within_drift_pct": 1.0,
             "fa_vs_groundtruth": {"median_drift_ms": 29.4},
             "asr_minus_fa": {"median_ms": -449.1}},
            {"lang": "x-gtlong", "matched_within_drift_pct": 2.0, "fa_skipped": "over the cap"},
        ]
        first_asr, first_fa = _split(rows, {})
        second_asr, second_fa = _split(first_asr, {r["lang"]: r for r in first_fa})
        bad = []
        if first_fa != second_fa:
            bad.append(f"second split changed the FA basis: {first_fa} -> {second_fa}")
        if second_asr != first_asr:
            bad.append("second split changed the ASR basis")
        # And the failure mode itself: with no prior, the second pass MUST lose it.
        # If this assertion stops holding, the trial has stopped testing anything.
        _, lost = _split(first_asr, {})
        if any("median_drift_ms" in r for r in lost):
            bad.append("the no-prior path did not reproduce the original defect, so this "
                       "trial no longer proves the carry-forward is what saves it")
        return bad
    trial("GT-IDEMPOTENT       re-splitting the two bases does not delete the FA basis",
          split_idempotent, False)

    # 7. The SCORER, not the construction. If the drift figures do not move when
    #    the truth moves, the scorer is not reading the truth -- which is the
    #    fifth-instrument failure in its purest form.
    def scorer(shift_ms=None, reverse=False):
        if not RESULTS.exists():
            return None
        res = json.loads(RESULTS.read_text(encoding="utf-8"))
        out = []
        for c in res["corpora"]:
            ws = [w for w in c["words"] if "true_s" in w]
            if not ws:
                continue
            truth = [w["true_s"] for w in ws]
            if reverse:
                truth = truth[::-1]
            if shift_ms:
                truth = [t + shift_ms / 1000.0 for t in truth]
            sd = [(w["obs_s"] - t) * 1000.0 for w, t in zip(ws, truth)]
            d = [abs(x) for x in sd]
            out.append({"lang": c["lang"], "median": statistics.median(d),
                        "signed": statistics.median(sd),
                        "within": 100.0 * sum(1 for x in d if x <= DRIFT_MS) / c["display_words"]})
        return out

    base = scorer()
    if base is None:
        print("  skip  GT-SHIFT / GT-REVERSE: no scores yet (run --score)")
    else:
        def shifted():
            # The SIGNED median is the deterministic one: moving every true start
            # 120 ms later moves median(obs - true) by exactly -120. Asserting on
            # the ABSOLUTE median would be wrong -- if the errors are one-sided,
            # a later truth makes |obs - true| SMALLER, and a check written to
            # expect +120 would fail on a correct scorer. That is the shape of
            # mistake this whole spike keeps making, so it is written out.
            sh = scorer(shift_ms=120)
            return [f"{b['lang']}: signed median moved {s['signed'] - b['signed']:+.1f}ms, "
                    f"expected exactly -120ms"
                    for b, s in zip(base, sh) if abs((s["signed"] - b["signed"]) + 120) > 1.0]
        trial("GT-SHIFT            a +120 ms truth offset moves the signed median", shifted, False)

        def reversed_truth():
            rv = scorer(reverse=True)
            # Reversing the truth must destroy the score. If it does not, the
            # scorer is insensitive to WHICH word it is comparing.
            return [f"{b['lang']}: within-drift {r['within']:.1f}% survived a reversed truth"
                    for b, r in zip(base, rv) if r["within"] >= max(20.0, b["within"] - 20.0)]
        trial("GT-REVERSE          a reversed truth destroys the score", reversed_truth, False)

    print(f"\nself-test: {len(trials) - failed} passed, {failed} failed")
    return 1 if failed else 0


# ── CLI ──────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="SPIKE A constructed ground truth")
    ap.add_argument("--build", action="store_true", help="synthesize per-word audio and concatenate")
    ap.add_argument("--one", action="store_true", help="make exactly ONE paid call and stop")
    ap.add_argument("--paragraph", action="store_true", help="also synthesize the long natural fixtures")
    ap.add_argument("--lang", action="append", help="restrict to these languages")
    ap.add_argument("--verify", action="store_true", help="prove the manifest against the bytes. No API, no ASR")
    ap.add_argument("--score", action="store_true", help="score the bar against the constructed truth")
    ap.add_argument("--analyse", action="store_true",
                    help="decompose drift into constructed silence vs real misplacement. No API, no ASR")
    ap.add_argument("--no-fa", action="store_true", help="skip forced alignment while scoring")
    ap.add_argument("--fa-only", action="store_true",
                    help="recompute only the forced-alignment basis, reusing recorded ASR starts")
    ap.add_argument("--model", default="base")
    ap.add_argument("--ctype", default="int8")
    ap.add_argument("--self-test", action="store_true", help="mutate the harness and prove it fails")
    a = ap.parse_args()

    if not any((a.build, a.verify, a.score, a.analyse, a.fa_only, a.self_test)):
        ap.print_help()
        return
    if a.build:
        fx = json.loads(FIXTURES.read_text(encoding="utf-8"))
        build(a.lang or list(fx["languages"]), a.one, a.paragraph)
    if a.verify:
        f = verify()
        print("\n".join(f) if f else "verify: clean — every boundary reproduces from the bytes")
        if f:
            sys.exit(1)
    if a.fa_only:
        fa_only()
    if a.score:
        score(a.model, a.ctype, not a.no_fa)
    if a.score or a.analyse:
        res = analyse()
        for row in res["corpora"]:
            d = row.get("silence_decomposition")
            if d:
                print(f"  {row['lang']:<12} strict {row['matched_within_drift_pct']:>5.1f}%  "
                      f"silence-tolerant {d['matched_within_drift_pct_silence_tolerant']:>5.1f}%  "
                      f"({d['tokens_timestamped_inside_that_silence']} starts inside the "
                      f"{d['median_constructed_silence_before_word_ms']:.0f}ms gap this file inserted)")
    if a.self_test:
        sys.exit(self_test())


if __name__ == "__main__":
    main()
