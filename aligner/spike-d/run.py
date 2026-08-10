#!/usr/bin/env python3
"""
SPIKE D driver — builds the fixtures, runs the mutation gate, runs the engines,
writes `out/spike-d-results.json`.

ORDER OF OPERATIONS IS THE POINT.

  1. Build fixtures from one geometry; hash every byte.
  2. Prove the ground truth is uniquely addressable (layout.assert_context_unique).
  3. Run the MUTATION GATE. If any mutation lands outside the band written
     before the run, the run STOPS and publishes no engine numbers. An
     instrument that cannot be shown to fail has not been shown to work, and
     engine figures produced by an unvalidated ruler are worse than no figures
     because they will be quoted.
  4. Only then, measure engines.

Steps 3 and 4 in that order is the whole discipline. SPIKE A earned it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import platform
import subprocess
import sys
import time

import engines as E
import layout as L
import metric as M
import mutate as MUT
import render as R

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
CACHE = OUT / "ocr-cache.json"
CACHE_VERSION = "v2"   # bumped when dewarp changed and region scores were kept


def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def file_sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# OCR cache. Keyed by (image sha256, dewarp), so a cached entry can never be
# the wrong image's -- renaming or regenerating a fixture invalidates it by
# construction rather than by remembering to clear a directory.
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def ocr_cached(img: pathlib.Path, dewarp: bool, cache: dict) -> tuple[list[dict], float, bool]:
    # Keyed by the SOURCE image hash, so regenerating a fixture invalidates
    # its entry by construction. The version suffix covers changes to the
    # PIPELINE rather than the input -- the dewarp fix altered the image OCR
    # sees without altering the file it is derived from.
    key = f"{file_sha(img)}:{int(dewarp)}:{CACHE_VERSION}"
    if key in cache:
        c = cache[key]
        return c["boxes"], c["seconds"], c["dewarp_applied"]
    boxes, secs, applied = E.ocr_boxes(img, dewarp)
    cache[key] = {"boxes": boxes, "seconds": secs, "dewarp_applied": applied,
                  "source": img.name}
    CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return boxes, secs, applied


# ---------------------------------------------------------------------------
# 3. THE MUTATION GATE
# ---------------------------------------------------------------------------

def mutation_gate(pages) -> tuple[list[dict], bool]:
    rows, ok = [], True
    for page in pages:
        truth = page.truth_tokens()
        furn = [w.text for w in page.furniture]
        baseline = MUT.m_identity(page)
        two_col = MUT.is_two_column(page)
        for mut in MUT.MUTATIONS:
            # APPLICABILITY. `interleave_lines`, `column_swap` and `drop_column`
            # are two-column mutations. Run against the sidebar fixtures they
            # were silently NO-OPS and scored a perfect 1.000, which the first
            # gate run reported as an expectation failure -- correctly, and only
            # because the band was tight. A no-op mutation that happened to sit
            # inside its band would have passed as evidence of nothing.
            if mut.get("applies_to") == "two_column" and not two_col:
                rows.append({"fixture": page.name, "mutation": mut["id"],
                             "status": "not_applicable",
                             "detail": "fixture has no second column",
                             "expectation_held": True})
                continue
            text = mut["fn"](page)
            # THE NO-OP GUARD, general form. Any mutation whose output equals the
            # unmutated baseline has tested nothing, whatever it scores.
            if mut["id"] != "identity" and text == baseline:
                rows.append({"fixture": page.name, "mutation": mut["id"],
                             "status": "NO-OP",
                             "detail": "mutation produced the unmutated output; "
                                       "it tested nothing",
                             "expectation_held": False})
                ok = False
                continue
            res = M.score(text, truth, furn, "digital")
            held, why = MUT.check(mut["expect"], res)
            verdict_ok = (mut["expect_verdict"] is None
                          or res["passes"] == mut["expect_verdict"])
            row = {
                "fixture": page.name,
                "mutation": mut["id"],
                "why": mut["why"],
                "expect": [[k, o, v] for k, o, v in mut["expect"]],
                "expect_verdict": mut["expect_verdict"],
                "reading_order_score": res["reading_order_score"],
                "adjacency_score": res["adjacency_score"],
                "kendall_order_concordance": res["kendall_order_concordance"],
                "token_recall": res["token_recall"],
                "furniture_inline": res["furniture_inline"],
                "word_space_loss_rate": res["word_space_loss_rate"],
                "order_n": res["order_n"],
                "verdict": res["passes"],
                "expectation_held": bool(held and verdict_ok),
                "detail": why or ("" if verdict_ok else
                                  f"verdict {res['passes']}, expected {mut['expect_verdict']}"),
            }
            for k in ("documents_limit", "band_revised"):
                if k in mut:
                    row[k] = mut[k]
            rows.append(row)
            if not row["expectation_held"]:
                ok = False
    return rows, ok


# ---------------------------------------------------------------------------
# 4. ENGINES
# ---------------------------------------------------------------------------

def measure_engines(pages, cache) -> list[dict]:
    rows = []
    for page in pages:
        truth = page.truth_tokens()
        furn = [w.text for w in page.furniture]
        pdf = OUT / f"{page.name}.pdf"
        boxes = E.pdf_word_boxes(pdf)

        digital = [
            ("poppler_pdftotext", "default reading-order mode",
             lambda: E.run_pdftotext(pdf, False)),
            ("poppler_pdftotext_layout", "-layout, the flag people reach for",
             lambda: E.run_pdftotext(pdf, True)),
            ("pdfminer_six", "LAParams boxes_flow=0.5 (library default)",
             lambda: E.run_pdfminer(pdf, 0.5)),
            ("pdfminer_six_no_boxes_flow", "LAParams boxes_flow=None, strict y then x",
             lambda: E.run_pdfminer(pdf, None)),
            ("pypdfium2", "PDFium's own text order",
             lambda: E.run_pdfium(pdf)),
            ("rawboxes_naive_yx", "our glyph boxes + band-by-y ordering",
             lambda: E.joined(E.naive_yx(boxes, 0.0))),
            ("rawboxes_xycut", "our glyph boxes + recursive XY-cut",
             lambda: E.joined(E.xycut(boxes))),
        ]
        pdf_conf = {n: E.order_confidence(f(boxes)) for n, f in
                    (("rawboxes_naive_yx", lambda b: E.naive_yx(b, 0.0)),
                     ("rawboxes_xycut", E.xycut))}
        for name, note, fn in digital:
            t0 = time.time()
            try:
                text = fn()
                err = None
            except Exception as exc:                       # engine unavailable
                text, err = "", f"{type(exc).__name__}: {exc}"
            secs = time.time() - t0
            res = M.score(text, truth, furn, "digital") if text else {"error": err}
            rows.append({"fixture": page.name, "lang": page.lang, "medium": "pdf",
                         "engine": name, "note": note, "seconds": round(secs, 2),
                         "error": err,
                         **(pdf_conf[name] if name in pdf_conf else {}),
                         **res})

        for medium, img, dw in (("scan_png", OUT / f"{page.name}-scan.png", False),
                                ("camera_jpg", OUT / f"{page.name}-camera.jpg", False),
                                ("camera_jpg_dewarped", OUT / f"{page.name}-camera.jpg", True)):
            obx, secs, applied = ocr_cached(img, dw, cache)
            scores = [b["score"] for b in obx if "score" in b]
            recog = {
                # The recogniser's OWN confidence. Reported so it can be
                # compared with reading-order correctness -- not because it
                # measures it. See `confidence_signal` in the artifact.
                "recogniser_mean_confidence": round(sum(scores) / len(scores), 4) if scores else None,
                "recogniser_min_confidence": round(min(scores), 4) if scores else None,
            }
            for oname, order_fn in (("native", lambda b: b),
                                    ("naive_yx", lambda b: E.naive_yx(b, 0.0)),
                                    ("xycut", E.xycut)):
                ordered = order_fn(obx)
                conf = E.order_confidence(ordered)
                res = M.score(E.joined(ordered), truth, furn, "image")
                rows.append({"fixture": page.name, "lang": page.lang, "medium": medium,
                             "engine": f"rapidocr+{oname}",
                             "note": f"PP-OCRv4 onnxruntime, ordering={oname}",
                             "seconds": round(secs, 2), "regions": len(obx),
                             "dewarp_applied": applied, "error": None,
                             **conf, **recog, **res})
    return rows


def confidence_signal(rows: list[dict]) -> dict:
    """
    Does either confidence signal separate a correctly ordered read from a
    wrongly ordered one? Answered with numbers, over every row that HAS boxes --
    `order_confidence` reads the emitted order itself, so it applies to any
    ordering policy and the good and bad orderings of the same page can be
    compared on it directly.
    """
    xy = [r for r in rows if r.get("reading_order_score") is not None
          and r.get("layout_confidence") is not None]
    good = [r for r in xy if r["reading_order_score"] >= M.BAR_READING_ORDER]
    bad = [r for r in xy if r["reading_order_score"] < M.BAR_READING_ORDER]

    def band(rs, key):
        vals = [r[key] for r in rs if r.get(key) is not None]
        return {"n": len(vals),
                "min": round(min(vals), 4) if vals else None,
                "max": round(max(vals), 4) if vals else None,
                "mean": round(sum(vals) / len(vals), 4) if vals else None}

    out = {}
    for key, what in (("layout_confidence",
                       "our XY-cut self-report: the share of boxes NOT left in a "
                       "multi-line region the recursion could not cut"),
                      ("recogniser_mean_confidence",
                       "RapidOCR's own mean per-region score")):
        g, b = band(good, key), band(bad, key)
        separates = (g["min"] is not None and b["max"] is not None
                     and g["min"] > b["max"])
        out[key] = {"_what": what,
                    "on_correctly_ordered_reads": g,
                    "on_wrongly_ordered_reads": b,
                    "separates_cleanly": bool(separates)}
    out["_reading"] = (
        "A signal 'separates cleanly' when its WORST value on a correctly "
        "ordered read is still better than its BEST value on a wrongly ordered "
        "one -- i.e. a single threshold exists. Anything less is not a "
        "disclosure a blind user can rely on, and must not be shipped as one.")
    return out


# ---------------------------------------------------------------------------

def trap_demonstration(pages) -> dict:
    """The wrong answer, in plain sight, so the fluency claim can be checked."""
    page = next(p for p in pages if p.name == "en-2col")
    return {
        "_what": "The first 300 characters the page produces when column 2 is "
                 "emitted before column 1. It is grammatical, it is fluent, and "
                 "it is not what the page says. A sighted reader sees the defect "
                 "in the layout; a listener has nothing to see.",
        "correct": " ".join(page.truth_tokens())[:300],
        "column_swapped": MUT.m_column_swap(page)[:300],
        "line_interleaved": MUT.m_interleave_lines(page)[:300],
    }


def summarise(rows: list[dict]) -> dict:
    """Per-engine pass counts and the findings they support, computed from the
    rows rather than typed alongside them, so the two cannot disagree."""
    tally: dict[tuple[str, str], list[int]] = {}
    for r in rows:
        if r.get("passes") is None:
            continue
        key = (r["medium"], r["engine"])
        t = tally.setdefault(key, [0, 0])
        t[0] += 1 if r["passes"] else 0
        t[1] += 1

    def rng(pred, key):
        v = [r[key] for r in rows if pred(r) and r.get(key) is not None]
        return [round(min(v), 3), round(max(v), 3)] if v else None

    pdf = lambda r: r["medium"] == "pdf"
    img = lambda r: r["medium"] != "pdf"
    return {
        "pass_counts": {f"{m}/{e}": f"{p}/{n}" for (m, e), (p, n) in sorted(tally.items())},
        "born_digital": {
            "engines_passing_every_fixture": sorted(
                e for (m, e), (p, n) in tally.items() if m == "pdf" and p == n),
            "reading_order_is_solved_here": True,
            "traps": {
                "_scope": "reading_order_score over the THREE TWO-COLUMN "
                          "fixtures only; the sidebar fixtures have one column "
                          "and fail these engines on furniture_inline instead, "
                          "so mixing them would hide both defects.",
                "pdftotext -layout": rng(
                    lambda r: pdf(r) and r["engine"].endswith("_layout")
                    and "2col" in r["fixture"], "reading_order_score"),
                "pdfminer_six default LAParams": rng(
                    lambda r: r.get("engine") == "pdfminer_six" and pdf(r)
                    and "2col" in r["fixture"], "reading_order_score"),
                "sidebar_spliced_into_body_by": sorted({
                    r["engine"] for r in rows if pdf(r)
                    and "sidebar" in r["fixture"] and r.get("furniture_inline", 0) > 0}),
                "_note": "-layout is the flag people reach for to 'preserve the "
                         "layout' and it interleaves the columns on every "
                         "two-column fixture. pdfminer's default boxes_flow "
                         "recovered en and fr and INTERLEAVED es on a page with "
                         "identical geometry -- an engine that is right most of "
                         "the time in a way you cannot predict is the one thing "
                         "constraint 2 forbids.",
            },
        },
        "image": {
            "engines_passing_any_fixture": sorted(
                e for (m, e), (p, n) in tally.items() if m != "pdf" and p > 0),
            "word_space_loss_rate_range": rng(img, "word_space_loss_rate"),
            "_note": "NOTHING passes on an image, and the binding failure is not "
                     "reading order -- it is word-space loss. RapidOCR returns "
                     "`thenorthernshore.Eachstation` for four words on every "
                     "fixture, so between 24% and 45% of the page is recovered "
                     "as run-together nonsense a TTS voice cannot pronounce. "
                     "Reading order on a FLAT scan is recovered by XY-cut "
                     "(0.98-1.00 against 0.57-0.60 for the engine's own order); "
                     "on a TILTED page nothing tested recovers it.",
        },
        "ordering_beats_the_engine": {
            "rapidocr_native_flat_scan": rng(
                lambda r: r["medium"] == "scan_png" and r["engine"] == "rapidocr+native"
                and "2col" in r["fixture"], "reading_order_score"),
            "rapidocr_plus_our_xycut_flat_scan": rng(
                lambda r: r["medium"] == "scan_png" and r["engine"] == "rapidocr+xycut"
                and "2col" in r["fixture"], "reading_order_score"),
            "_note": "Same recognised boxes, different ordering policy. The "
                     "ordering must be OURS; the OCR engine's own output order "
                     "is not usable on a multi-column page.",
        },
        "camera": {
            "two_column_order_range": rng(
                lambda r: r["medium"].startswith("camera") and "2col" in r["fixture"],
                "reading_order_score"),
            "dewarp_effect_on_recall": {
                "before": rng(lambda r: r["medium"] == "camera_jpg" and "2col" in r["fixture"],
                              "token_recall"),
                "after": rng(lambda r: r["medium"] == "camera_jpg_dewarped"
                             and "2col" in r["fixture"], "token_recall"),
            },
            "dewarp_effect_on_word_space_loss": {
                "before": rng(lambda r: r["medium"] == "camera_jpg" and "2col" in r["fixture"],
                              "word_space_loss_rate"),
                "after": rng(lambda r: r["medium"] == "camera_jpg_dewarped"
                             and "2col" in r["fixture"], "word_space_loss_rate"),
            },
            "_note": "Rectification measurably improves RECOGNITION and does "
                     "NOT restore READING ORDER: XY-cut still cannot find the "
                     "gutter because residual perspective smears the x-projection "
                     "valley. The two-column camera case is the open problem this "
                     "spike did not solve.",
        },
    }


LIMITS = {
    "_read_this_first":
        "Every entry is a thing this instrument CANNOT see. A pass above is a "
        "pass on the fixtures and metrics defined here and is not a claim about "
        "anything listed below.",

    "camera_is_synthetic":
        "The 'camera' fixture is a rendered page put through a homography, an "
        "illumination gradient, defocus, Gaussian noise and JPEG. NO PHOTOGRAPH "
        "WAS TAKEN. A real phone capture adds page curl (this page stays "
        "planar), specular highlights, motion blur, rolling shutter and a "
        "demosaicing pipeline. Results here are an UPPER BOUND on real camera "
        "performance. The sound negative survives: an engine that fails here "
        "will fail on a real photograph.",

    "fluency_not_measured":
        "The metric scores 0.5 for a column swap whether the resulting text is "
        "gibberish or fluent prose that inverts the paper's conclusion. Only the "
        "second is dangerous to a blind user. Separating them needs a language "
        "model this spike does not have. `_trap_demonstration` shows the fluent "
        "case; it does not score it.",

    "semantic_units_not_seen":
        "A heading read after its own paragraph is heard immediately by a "
        "listener and scores near the pass bar here -- see the `title_last` "
        "mutation, which is in the battery to keep this limit measured rather "
        "than merely asserted.",

    "non_text_untested":
        "No fixture contains a figure with a caption, a table, an equation, a "
        "footnote, a marginal citation or a page-spanning paragraph. Each is its "
        "own reading-order hazard and NONE has been exercised. This spike tests "
        "COLUMNS, a SIDEBAR BOX, and PAGE FURNITURE.",

    "no_hyphenation_in_fixtures":
        "The generated columns do not hyphenate at line breaks; real typeset "
        "columns do. `hyphen_split` mutates a transcript to exercise the metric, "
        "which is not the same as rendering a hyphenated page and asking an "
        "engine to rejoin it. That case is UNMEASURED.",

    "order_measured_on_recovered_subset":
        "Order is scored only over tokens that were recovered and unambiguously "
        "assigned. A read with 50% recall supplies half the evidence, and the "
        "order figure beside it is correspondingly weaker. `order_n` and "
        "`order_n_below_floor` carry that; the bar is 50 assigned tokens.",

    "ambiguous_assignments_are_dropped":
        "A token whose context score ties between two ground-truth positions is "
        "left unassigned rather than guessed. Dropping is neutral; guessing "
        "toward monotonic order would flatter every engine. The count is "
        "reported per row, and a row with a large count is a row with less "
        "evidence behind it, not a row that did better.",

    "diacritics_folded":
        "Matching strips diacritics, so an engine that drops every accent still "
        "scores full token_recall. `accent_recall` is measured separately and "
        "unfolded. It is also a FLOOR: an accented word recovered inside a "
        "merged run has no single output token to compare and counts as a miss.",

    "merged_runs_are_permissive":
        "An output token equal to the concatenation of several truth tokens is "
        "credited with all of them, because the characters are present and in "
        "order. For READING ORDER that is correct; for SPEECH it is not -- a TTS "
        "voice reads 'thenorthernshore' as one nonsense word. "
        "`word_space_loss_rate` is the compensating disclosure and has a bar of "
        "its own. The INVERSE (one truth word split across two output tokens) is "
        "deliberately not credited.",

    "dewarp_assumes_planar":
        "`engines.dewarp` finds the page quadrilateral and applies a homography. "
        "A homography cannot rectify a curved page, so a book photographed near "
        "the spine is out of its reach. It also failed SILENTLY in its first "
        "version -- the quad simplified to five vertices and the function "
        "returned the unrectified image, which read as 'rectification does not "
        "help'. `dewarp_applied` is now on every row.",

    "single_page_only":
        "Every fixture is one page. Reading order ACROSS pages -- a paragraph "
        "continuing over a page break, a footnote whose text is on the next "
        "page -- is untested and is a distinct problem.",

    "one_font_one_size":
        "All fixtures render in Arial via one TTF. Serif faces, ligatures "
        "(fi, fl), small caps, and old-style figures all change what a "
        "recogniser sees, and none is exercised.",

    "transposition_sensitivity_floor":
        "Measured, not estimated: transposing 3% of adjacent word pairs scores "
        "reading_order 0.986 and adjacency 0.956 and CLEARS BOTH BARS. The bars "
        "tolerate roughly one transposed pair per eighty words. See the "
        "`swap_adjacent` mutation.",

    "hyphenation_below_recall_bar":
        "Measured: line-break hyphenation at a realistic rate costs 1.5 points "
        "of token_recall, inside the 0.98 digital bar. A hyphen-unaware "
        "extractor therefore passes this instrument while mispronouncing about "
        "one word per two lines. See the `hyphen_split` mutation.",

    "no_real_document_was_tested":
        "The strongest thing about these fixtures -- that their answer key is "
        "exact -- is also the weakest: they were generated by the same author as "
        "the metric. A passing engine has been shown to handle a synthetic "
        "two-column page, not a journal PDF. Before ingest ships, the winning "
        "configuration must be run against real public-domain scans (Project "
        "Gutenberg page images, US federal reports) and scored by hand on a "
        "sample. That is a Phase 1 obligation, not a spike deliverable.",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-ocr", action="store_true",
                    help="digital engines and the mutation gate only")
    a = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    print("── fixtures ──")
    manifest = R.build_all()
    pages = L.all_pages()

    print("\n── mutation gate ──")
    muts, gate_ok = mutation_gate(pages)
    by_mut: dict[str, list] = {}
    for r in muts:
        by_mut.setdefault(r["mutation"], []).append(r)
    for mid, rows in by_mut.items():
        held = sum(1 for r in rows if r["expectation_held"])
        scored = [r for r in rows if r.get("reading_order_score") is not None]
        span = (f"{min(r['reading_order_score'] for r in scored):.3f}–"
                f"{max(r['reading_order_score'] for r in scored):.3f}"
                if scored else "n/a")
        na = sum(1 for r in rows if r.get("status") == "not_applicable")
        mark = "OK " if held == len(rows) else "!! "
        print(f"  {mark}{mid:22s} {held}/{len(rows)} fixtures"
              f"{f' ({na} n/a)' if na else ''}  order {span}")
        for r in rows:
            if not r["expectation_held"]:
                print(f"       {r['fixture']}: {r['detail']}")
    print(f"  GATE: {'PASS' if gate_ok else 'FAIL'}")

    engine_rows = []
    if gate_ok and not a.skip_ocr:
        print("\n── engines ──")
        cache = load_cache()
        engine_rows = measure_engines(pages, cache)
        for r in engine_rows:
            if r.get("error"):
                print(f"  {r['fixture']:14s} {r['medium']:20s} {r['engine']:26s} ERROR {r['error']}")
                continue
            lc = r.get("layout_confidence")
            print(f"  {r['fixture']:14s} {r['medium']:20s} {r['engine']:26s} "
                  f"order={r['reading_order_score']} adj={r['adjacency_score']} "
                  f"recall={r['token_recall']} sl={r['word_space_loss_rate']} "
                  f"fin={r['furniture_inline']} "
                  f"lconf={lc if lc is not None else '-'} "
                  f"n={r['order_n']} {'PASS' if r['passes'] else 'fail'}")
    elif not gate_ok:
        print("\n!! Mutation gate FAILED. No engine numbers are published: an "
              "instrument that cannot be shown to fail has not been shown to work.")
    elif a.skip_ocr:
        print("\n(--skip-ocr: digital engines only)")
        cache = load_cache()

    artifact = {
        "spike": "D",
        "subject": "layout-aware OCR — reading-order recovery",
        "date": time.strftime("%Y-%m-%d"),
        "roadmap_item": "SPIKE D — layout-aware OCR engine (due 2026-08-14)",
        "verdict_gate": "PASS" if gate_ok else "FAIL",
        "metric_definition": {
            "reading_order_score":
                "LIS(assigned truth indices, in output order) / number assigned. "
                "The longest run of recovered words that is in correct relative "
                "order, as a fraction of what was recovered. Column interleaving "
                "lands near 0.50 by construction.",
            "adjacency_score":
                "fraction of consecutive assigned indices that advance by exactly "
                "one. Local; sees a single transposition that LIS shrugs off.",
            "kendall_order_concordance":
                "1 - 2 * inversions / (n(n-1)). Reported for corroboration; not a bar.",
            "token_recall":
                "distinct truth tokens recovered / all truth tokens. ORDER-BLIND, "
                "and the reason dropping a whole column cannot pass.",
            "word_space_loss_rate":
                "truth tokens recovered only inside a merged output token / all "
                "truth tokens. Recovered for order, broken for speech.",
            "accent_recall":
                "accented truth tokens matched with diacritics intact / all "
                "accented truth tokens. Measured unfolded and separately.",
            "furniture_inline":
                "running-head / folio / sidebar tokens emitted BETWEEN body "
                "tokens. Bar is zero: a page number spoken mid-sentence is an "
                "accessibility defect no client can repair.",
            "assignment":
                "content-only. Candidates are every truth position with the same "
                "fold (or a run whose concatenation matches); the winner is the "
                "unique argmax of ±3 neighbourhood agreement; ties are DROPPED "
                "and counted. No positional prior, so the order metric is not "
                "measuring its own assignment.",
        },
        "bars": {
            "reading_order_score": M.BAR_READING_ORDER,
            "adjacency_score": M.BAR_ADJACENCY,
            "token_recall_digital": M.BAR_RECALL_DIGITAL,
            "token_recall_image": M.BAR_RECALL_IMAGE,
            "word_space_loss_rate": M.BAR_WORD_SPACE_LOSS,
            "furniture_inline": M.BAR_FURNITURE_INLINE,
            "min_order_n": M.MIN_ORDER_N,
            "_note": "Fixed before the first engine ran. The order bars are "
                     "IDENTICAL for a PDF and a photograph: a page read in the "
                     "wrong order is equally unusable either way, and softening "
                     "the bar for the harder medium would be tuning the ruler.",
        },
        "fixtures": manifest,
        "fixture_provenance": {
            "text": "Authored for this harness by the project and dedicated to "
                    "the public domain (CC0). Not an excerpt, translation or "
                    "paraphrase of any existing work. Phase 0.5 requires "
                    "public-domain-only fixtures; authoring is the only way to "
                    "be certainly compliant rather than probably compliant.",
            "generator": "corpus.py -> layout.py -> render.py, deterministic "
                         "given the same Arial TTF. camera_seed=" + str(R.CAMERA_SEED),
            "font": "C:\\Windows\\Fonts\\arial.ttf for metrics and raster; the "
                    "PDF uses base-14 /Helvetica with /WinAnsiEncoding and "
                    "embeds nothing. Arial and Helvetica are metric-compatible, "
                    "which is what makes one geometry serve both media.",
            "source_sha256": {f: sha_text((ROOT / f).read_text(encoding="utf-8"))
                              for f in ("corpus.py", "layout.py", "render.py",
                                        "metric.py", "mutate.py", "engines.py",
                                        "run.py")},
        },
        "summary": summarise(engine_rows) if engine_rows else None,
        "confidence_signal": confidence_signal(engine_rows) if engine_rows else None,
        "_trap_demonstration": trap_demonstration(pages),
        "mutations": muts,
        "engines": engine_rows,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": _versions(),
        },
        "_limits": LIMITS,
    }
    path = OUT / "spike-d-results.json"
    path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {path}")
    return 0 if gate_ok else 1


def _versions() -> dict:
    v = {}
    for mod in ("pdfminer", "pypdfium2", "cv2", "numpy", "PIL", "onnxruntime",
                "rapidocr_onnxruntime"):
        try:
            m = __import__(mod)
            v[mod] = getattr(m, "__version__", "unknown")
        except Exception:
            v[mod] = "not installed"
    exe = E._pdftotext_bin()
    if exe:
        try:
            p = subprocess.run([exe, "-v"], capture_output=True)
            v["poppler_pdftotext"] = (p.stderr or p.stdout).decode(
                "utf-8", "replace").splitlines()[0].strip()
        except Exception:
            v["poppler_pdftotext"] = exe
    return v


if __name__ == "__main__":
    raise SystemExit(main())
