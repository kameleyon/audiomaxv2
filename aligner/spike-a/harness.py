#!/usr/bin/env python3
"""
SPIKE A — shared measurement primitives.

WHY THIS FILE EXISTS. Round 26 (Halo) found that four measuring instruments were
wrong before one was right, and then that the fifth was wrong too. Three of those
defects were the SAME defect implemented independently in three files:

  * `fa.py`, `reference.py` and `wx.py` each compared two token streams by
    SURFACE-FORM UNIQUENESS -- keep a token only if it occurs exactly once in
    both streams. That silently deletes every short frequent function word (the
    hardest to place, and the ones a reader's eye is on most often) and keeps
    long content words whose larger spans inflate overlap. n fell to 14-21
    (H26-M8). It ALSO deleted every numeral, because the aligner emits
    `nineteen eighty four` and the reference emits `1984`, so neither is
    "unique in both" -- which is why the hard tokens the fixtures exist to test
    never reached the comparison at all (H26-B2).

  * every file that needed an audio duration read the WAV header, and the Fish
    `es`/`fr` headers declare `nframes = 0x7FFFFFFF` -- 48,695 seconds for a
    ten-second clip (H26-m1).

The fix for the first is to stop pairing streams against EACH OTHER by surface
form and instead map BOTH onto the DISPLAY TEXT, which is the thing a highlight
actually moves over. The display token is the unit of comparison; a numeral and
its spoken expansion are one unit, and function words are retained because
pairing is POSITIONAL (display index), not lexical.

The fix for the second is to derive duration from the file size and never trust
the header.

Both live here once, so a repair cannot land in two of the three call sites --
which is the failure class this repository has recorded seven times.
"""
from __future__ import annotations

import json
import pathlib
import re
import statistics
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import measure as M  # noqa: E402  (display_words / match / norm live there)

# ── Audio ────────────────────────────────────────────────────────────────

def wav_info(path: pathlib.Path) -> dict:
    """
    Duration derived from FILE SIZE, never from the declared chunk size.

    H26-m1. Fish `s2-pro` returns a streaming WAV whose `data` chunk size is the
    sentinel 0xFFFFFFFC and whose RIFF size is 0xFFFFFFE4, because the length is
    not known when the header is written. Read literally that is 48,695 seconds
    of audio. Anything computing a realtime factor, a cost per audio-hour, or a
    drift-per-second from the header is off by a factor of ~4,600 -- in the
    flattering direction, which is the direction that does not get noticed.
    """
    b = path.read_bytes()
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        raise ValueError(f"{path.name}: not a RIFF/WAVE file")
    i, fmt, declared, off = 12, None, None, None
    while i + 8 <= len(b):
        cid = b[i:i + 4]
        sz = struct.unpack("<I", b[i + 4:i + 8])[0]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", b[i + 8:i + 24])
        elif cid == b"data":
            declared, off = sz, i + 8
            break
        i += 8 + sz + (sz & 1)
    if fmt is None or off is None:
        raise ValueError(f"{path.name}: no fmt/data chunk")
    _, channels, rate, _, block_align, bits = fmt
    block_align = block_align or (channels * bits // 8) or 1
    real_bytes = len(b) - off
    return {
        "path": path.name,
        "bytes": len(b),
        "sample_rate": rate,
        "channels": channels,
        "bits": bits,
        "seconds": real_bytes / (rate * block_align),
        "declared_data_bytes": declared,
        "actual_data_bytes": real_bytes,
        # The defect, recorded rather than silently corrected, so a downstream
        # reader can see which files carry it.
        "header_length_bogus": declared != real_bytes,
        "header_declared_seconds": declared / (rate * block_align),
    }


def wav_seconds(path: pathlib.Path) -> float:
    return wav_info(path)["seconds"]


def write_json(path: pathlib.Path, obj) -> None:
    """
    Write an artifact with LF endings, on every platform.

    `pathlib.write_text` uses the platform default, so on this Windows host every
    artifact this harness produced was CRLF. `.gitattributes` explains at length
    why that matters: `doc-check` matches fenced blocks as ```ts\n, and a CRLF
    working copy made EVERY TypeScript block in the spec invisible to the gate
    while it reported clean. The artifacts are now read by the gate too
    (`ART-*`), so they get the same rule as the documents rather than relying on
    git to normalise something on the way past.
    """
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")


def repair_wav_header(raw: bytes) -> bytes:
    """
    Rewrite the RIFF and `data` sizes to the real byte counts. Samples untouched.

    Eight bytes change. This runs at the WRITER (tts.py) so audio generated from
    now on is honest about its own length, and is idempotent for a file that is
    already correct.
    """
    if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        return raw
    b = bytearray(raw)
    i = 12
    while i + 8 <= len(b):
        cid = bytes(b[i:i + 4])
        sz = struct.unpack("<I", bytes(b[i + 4:i + 8]))[0]
        if cid == b"data":
            real = len(b) - (i + 8)
            struct.pack_into("<I", b, i + 4, real)
            struct.pack_into("<I", b, 4, (i + 8 + real) - 8)
            return bytes(b)
        if sz in (0xFFFFFFFF, 0xFFFFFFFC) or i + 8 + sz > len(b):
            break
        i += 8 + sz + (sz & 1)
    return bytes(b)


# ── Display-anchored comparison ──────────────────────────────────────────

def display_units(text: str):
    """[(token, char_start, char_end)] -- the spans a client highlights."""
    return M.display_words(text)


def units_from_asr(tokens, display, lang: str) -> dict:
    """
    Map an ASR token stream onto DISPLAY token indices.

    Uses the shipped `measure.match`, which is monotonic by construction and
    knows the spoken-form expansions (`1984` -> nineteen eighty four,
    `Dra.` -> doctora). One display token may consume several observed tokens;
    the returned span covers all of them, which is the span a highlight covers.

    Returns {display_index: {"s", "e", "obs", "via_normalizer"}}.
    """
    matched, _ = M.match(tokens, display, lang)
    out = {}
    for m in matched:
        out[m["disp_idx"]] = {
            "s": m["s"], "e": m["e"], "obs": m["obs_w"],
            "via_normalizer": bool(m.get("via_normalizer")),
        }
    return out


def units_from_expansion(spans, disp_index) -> dict:
    """
    Collapse forced-alignment tokens back onto their display token.

    `spans` is the aligner's per-token output and `disp_index[i]` is the display
    token that produced aligner token i. A display token expanded to three
    aligner tokens gets ONE span running from the first start to the last end --
    the same unit the reference side produces, which is the whole point.
    """
    out = {}
    for sp, di in zip(spans, disp_index):
        cur = out.get(di)
        if cur is None:
            out[di] = {"s": sp["s"], "e": sp["e"], "obs": sp["w"], "parts": 1}
        else:
            cur["s"] = min(cur["s"], sp["s"])
            cur["e"] = max(cur["e"], sp["e"])
            cur["obs"] += " " + sp["w"]
            cur["parts"] += 1
    return out


def pair_by_display(a: dict, b: dict):
    """
    Positional pairing on display index. No uniqueness filter, no surface-form
    equality -- so `the`, `de`, `a`, `les` are compared like every other word.
    """
    return [(i, a[i], b[i]) for i in sorted(set(a) & set(b))]


def overlap_pct(x, y) -> float:
    inter = max(0.0, min(x["e"], y["e"]) - max(x["s"], y["s"]))
    union = max(x["e"], y["e"]) - min(x["s"], y["s"])
    return 100.0 * inter / union if union > 0 else 0.0


def score_pairs(pairs, display):
    """
    The score sheet, with SIGNED and ABSOLUTE start deltas reported side by side.

    H26-M1: `+2 ms` was a SIGNED median quoted against `reference.py`'s ABSOLUTE
    one. Symmetric noise drives a signed median to zero while the absolute median
    stays large, so the two are not comparable and the near-zero one reads as an
    accuracy claim it cannot support. Both are emitted here, always, from one
    function -- the arrangement in which the mistake cannot be made again.
    """
    if not pairs:
        return None
    ov = [overlap_pct(x, y) for _, x, y in pairs]
    signed = [(x["s"] - y["s"]) * 1000.0 for _, x, y in pairs]
    absol = [abs(d) for d in signed]
    srt = sorted(absol)
    return {
        "words": len(pairs),
        "median_overlap_pct": round(statistics.median(ov), 1),
        "pct_overlap_50": round(100.0 * sum(1 for o in ov if o >= 50) / len(ov), 1),
        "median_signed_start_delta_ms": round(statistics.median(signed), 1),
        "median_abs_error_ms": round(statistics.median(absol), 1),
        "p95_abs_error_ms": round(srt[int(0.95 * (len(srt) - 1))], 1),
        "worst_tokens": [display[i][0] for i, _, _ in
                         sorted(pairs, key=lambda p: overlap_pct(p[1], p[2]))[:3]],
    }


# ── expect_hard (J22-M2) ─────────────────────────────────────────────────

SENT_END = re.compile(r"[.!?…][\"'”’)\]]*\s")


def hard_token_report(spec: dict, display, resolved: dict, lang: str):
    """
    Evaluate `expect_hard` -- declared in fixtures.json since the first run and
    read by NOTHING until now (J22-M2). It is the falsification condition for a
    100% match rate: these display substrings are the ones we assert will not
    appear verbatim in a transcript, so a run that reports everything matched
    while none of them went through the normalizer path is measuring the wrong
    thing.

    `resolved` maps display index -> {"via_normalizer": bool} for the tokens the
    run actually placed. Returns one row per declared hard token.
    """
    rows = []
    for want in spec.get("expect_hard", []) or []:
        idxs = [i for i, (tok, _, _) in enumerate(display) if want in tok]
        # A multi-word hard token ("1 250") spans several display tokens.
        if not idxs and " " in want:
            parts = want.split()
            for i in range(len(display) - len(parts) + 1):
                if [display[i + k][0] for k in range(len(parts))] == parts:
                    idxs = list(range(i, i + len(parts)))
                    break
        if not idxs:
            rows.append({"token": want, "status": "absent_from_fixture"})
            continue
        placed = [i for i in idxs if i in resolved]
        if not placed:
            rows.append({"token": want, "status": "unmatched", "display_indices": idxs})
        elif any(resolved[i].get("via_normalizer") for i in placed):
            rows.append({"token": want, "status": "matched_via_normalizer",
                         "display_indices": idxs,
                         "heard": " ".join(str(resolved[i].get("obs", "")) for i in placed)})
        else:
            rows.append({"token": want, "status": "matched_verbatim",
                         "display_indices": idxs,
                         "heard": " ".join(str(resolved[i].get("obs", "")) for i in placed)})
    return rows


def hard_falsification(rows, matched_pct: float):
    """
    fixtures.json:13-15, verbatim: "If a run reports 100% matched and these were
    not resolved by the normalizer path, the harness is measuring the wrong
    thing." Implemented literally, including the 100% trigger.
    """
    unresolved = [r["token"] for r in rows if r["status"] != "matched_via_normalizer"]
    return {
        "expect_hard_declared": len(rows),
        "expect_hard_via_normalizer": len(rows) - len(unresolved),
        "expect_hard_unresolved": unresolved,
        "expect_hard_falsifies_match_rate": bool(matched_pct >= 100.0 and unresolved),
    }


# ── Cost (H26-M6) ────────────────────────────────────────────────────────
# The roadmap requires `compute_cost_per_audio_hour_usd` as a RETURNED NUMBER and
# no file in out/ contained it. The only timing on disk was ~15 s of wall clock
# against ~11.6 s of audio -- 1.3x realtime INCLUDING MODEL LOAD, which is a
# fixed cost paid once per worker process and amortised to nothing over a 9-hour
# book. Quoting it per clip is how a 63-second corpus produces a per-book number.
#
# What the harness can measure is CPU-SECONDS PER AUDIO-SECOND. What it cannot
# measure is a price. So the price is an explicit, named INPUT recorded beside
# the result, and the measured quantity is emitted separately so any reader can
# recompute the cost against a rate they trust.
RATE_USD_PER_VCPU_HOUR = 0.02778
RATE_SOURCE = ("Railway usage-based compute, $0.000463 per vCPU-minute "
               "(spec:72 puts the worker on Railway). ASSUMPTION, not a measurement: "
               "re-derive against the invoice before this number is quoted in a decision.")


def cost_block(cpu_seconds: float, audio_seconds: float, load_seconds: float,
               wall_seconds: float, threads: int) -> dict:
    cpu_per_audio_sec = cpu_seconds / audio_seconds if audio_seconds else None
    return {
        "audio_seconds": round(audio_seconds, 2),
        "decode_wall_seconds": round(wall_seconds, 2),
        "model_load_seconds": round(load_seconds, 2),
        "cpu_threads": threads,
        # Amortised: model load is excluded. Both factors are emitted so the
        # amortisation is visible rather than asserted.
        "realtime_factor_amortised": round(wall_seconds / audio_seconds, 3) if audio_seconds else None,
        "realtime_factor_including_model_load": round((wall_seconds + load_seconds) / audio_seconds, 3) if audio_seconds else None,
        "cpu_seconds_per_audio_second": round(cpu_per_audio_sec, 3) if cpu_per_audio_sec else None,
        "compute_cost_per_audio_hour_usd": round(cpu_per_audio_sec * RATE_USD_PER_VCPU_HOUR, 4) if cpu_per_audio_sec else None,
        "cost_basis_usd_per_vcpu_hour": RATE_USD_PER_VCPU_HOUR,
        "cost_basis_source": RATE_SOURCE,
    }
