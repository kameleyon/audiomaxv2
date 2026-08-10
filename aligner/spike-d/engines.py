#!/usr/bin/env python3
"""
SPIKE D candidate engines.

Two questions are deliberately kept apart, because conflating them is how a
spike ends up recommending a 2 GB dependency for a problem a hundred lines of
geometry solves:

    RECOGNITION  — turning marks into characters. Only an image needs it.
    ORDERING     — turning positioned text into a reading sequence. EVERY
                   medium needs it, including a born-digital PDF that already
                   contains perfect characters in an arbitrary order.

So the engines are built as (source of positioned tokens) x (ordering policy):

  SOURCES     pdfminer_chars   raw glyph boxes from the PDF, clustered into
                               words here. No layout analysis -- deliberately,
                               so an ordering policy is measured rather than
                               pdfminer's ordering measured twice.
              rapidocr         PP-OCRv4 detection+recognition via onnxruntime,
                               Apache-2.0, ~15 MB of models, CPU.
  ORDERING    native           whatever the tool itself emits
              naive_yx         band by y across the FULL page width, then sort
                               by x. THE failure mode. It is here as a real
                               engine, not a simulation: if the metric does not
                               punish this on the real two-column PDF, the
                               metric is wrong.
              xycut            recursive XY-cut. ~90 lines, no dependency.

Whole-tool baselines (`pdftotext`, `pdfminer` with its own LAParams, `pdfium`)
are run too, because if one of them already recovers reading order then the
right answer for born-digital PDFs is "use it", and the layout work is only
needed on the image path.
"""
from __future__ import annotations

import pathlib
import shutil
import statistics
import subprocess
import time

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# ORDERING POLICIES — medium-independent, they take boxes and return an order
# ---------------------------------------------------------------------------


def naive_yx(boxes: list[dict], page_h: float) -> list[dict]:
    """
    Band by vertical position across the whole page, then left to right.

    This is what a reasonable person writes in twenty minutes and it is exactly
    wrong on a two-column page: the band spans the gutter, so a line of column 1
    and the line beside it in column 2 are emitted as one line.
    """
    if not boxes:
        return []
    h = statistics.median(b["y1"] - b["y0"] for b in boxes) or 1.0
    band = max(h * 0.6, 1.0)
    return sorted(boxes, key=lambda b: (round((b["y0"] + b["y1"]) / 2 / band), b["x0"]))


def xycut_stats(boxes: list[dict], min_gap_ratio: float = 0.55) -> tuple[list[dict], dict]:
    """
    Recursive XY-cut (Nagy & Seth), instrumented. Split on the widest whitespace
    valley, preferring whichever axis offers the larger absolute gap; recurse;
    emit top-to-bottom for a horizontal split and left-to-right for a vertical
    one. A region with no qualifying valley is read left-to-right.

    Horizontal cut wins ties: a page is a stack of bands before it is a row of
    columns, and cutting a full-measure heading off before splitting the columns
    is what keeps the heading ahead of both.

    THE GAP FLOOR is the one non-classical detail, and the SCALE IT IS MEASURED
    AGAINST is load-bearing. `unit` is the median glyph height over the WHOLE
    PAGE and is computed once, not per region. A first version recomputed it
    inside the recursion; a region containing only title glyphs then got a floor
    scaled to the title, its cuts changed, and the sidebar box was spliced into
    the body on the `*-sidebar` fixtures. Two copies of this function existed at
    that moment -- one instrumented, one not -- and they disagreed, which is
    precisely the drift SPIKE A ended by deleting its second normaliser. There
    is one implementation now and `xycut` delegates to it.

    A floor that is too small shatters paragraphs into lines, which is harmless
    because lines are re-emitted in order. One that is too large merges the
    columns, which is the failure that matters. 0.55 is on the safe side of that
    asymmetry.
    """
    if len(boxes) <= 1:
        return list(boxes), {"cuts": 0, "unordered_boxes": 0, "min_accepted_margin": None}
    unit = statistics.median(b["y1"] - b["y0"] for b in boxes) or 1.0
    floor = unit * min_gap_ratio
    stats = {"cuts": 0, "unordered_boxes": 0, "margins": []}

    def best_gap(bx, lo_key, hi_key):
        iv = sorted(((b[lo_key], b[hi_key]) for b in bx))
        gap, at, reach = 0.0, None, iv[0][1]
        for lo, hi in iv[1:]:
            if lo - reach > gap:
                gap, at = lo - reach, (reach + lo) / 2.0
            reach = max(reach, hi)
        return gap, at

    def rec(bx: list[dict]) -> list[dict]:
        if len(bx) <= 1:
            return list(bx)
        gy, aty = best_gap(bx, "y0", "y1")
        gx, atx = best_gap(bx, "x0", "x1")
        if gy >= floor and gy >= gx:
            top = [b for b in bx if (b["y0"] + b["y1"]) / 2 < aty]
            bot = [b for b in bx if (b["y0"] + b["y1"]) / 2 >= aty]
            if top and bot:
                stats["cuts"] += 1
                stats["margins"].append(gy / floor)
                return rec(top) + rec(bot)
        if gx >= floor * 1.5 and atx is not None:
            left = [b for b in bx if (b["x0"] + b["x1"]) / 2 < atx]
            right = [b for b in bx if (b["x0"] + b["x1"]) / 2 >= atx]
            if left and right:
                stats["cuts"] += 1
                stats["margins"].append(gx / (floor * 1.5))
                return rec(left) + rec(right)
        if max(b["y1"] for b in bx) - min(b["y0"] for b in bx) > 1.8 * unit:
            stats["unordered_boxes"] += len(bx)
        return naive_yx(bx, 0.0)

    ordered = rec(boxes)
    return ordered, {"cuts": stats["cuts"],
                     "unordered_boxes": stats["unordered_boxes"],
                     "min_accepted_margin": (round(min(stats["margins"]), 3)
                                             if stats["margins"] else None)}


def xycut(boxes: list[dict], min_gap_ratio: float = 0.55) -> list[dict]:
    return xycut_stats(boxes, min_gap_ratio)[0]


def order_confidence(ordered: list[dict]) -> dict:
    """
    THE CONFIDENCE SIGNAL the roadmap asks for — and the first thing to say
    about it is that it is NOT the recogniser's.

    An OCR engine's per-region score answers "am I sure these marks are those
    letters". It is silent on reading order: a two-column page read straight
    across scores high confidence on every region, because every region really
    was read correctly. A product that surfaces recogniser confidence as its
    quality signal reports high confidence on exactly the failure a blind user
    cannot detect. The signal has to come from geometry.

    WHAT IT MEASURES. Walk the EMITTED order and cut it into emitted lines --
    runs of boxes at the same height whose x advances. A correctly ordered page
    produces emitted lines that lie inside one column, so the gaps within a line
    are word gaps. A page read across the gutter produces emitted lines that
    START IN ONE COLUMN AND END IN THE OTHER, so somewhere inside the line there
    is a gap the width of a gutter. That gap is the signature of the failure,
    and it is visible without knowing the right answer.

        layout_confidence = 1 - (boxes in emitted lines containing a gap wider
                                 than 1.5 x median glyph height) / all boxes

    A FIRST VERSION OF THIS WAS WRONG and is worth recording, because it was
    wrong in the flattering direction's opposite: it counted every box in a
    multi-line region XY-cut had declined to cut, which includes every ordinary
    paragraph, and returned 0.02 on a page read perfectly. A signal that reports
    no confidence in a correct read is as useless as one that reports full
    confidence in a broken one -- it just fails safe instead of unsafe.

    It applies to ANY ordering, not only XY-cut's, so a passing and a failing
    ordering of the same page can be compared on it. Whether it actually
    separates them is measured in `run.confidence_signal` and reported as
    `separates_cleanly`; it is not assumed here.
    """
    if not ordered:
        return {"layout_confidence": None, "emitted_lines": 0, "suspect_lines": 0}
    unit = statistics.median(b["y1"] - b["y0"] for b in ordered) or 1.0
    gutter = 1.5 * unit
    lines, cur = [], [ordered[0]]
    for b in ordered[1:]:
        prev = cur[-1]
        same_row = abs((b["y0"] + b["y1"]) / 2 - (prev["y0"] + prev["y1"]) / 2) < 0.6 * unit
        advances = b["x0"] >= prev["x0"]
        if same_row and advances:
            cur.append(b)
        else:
            lines.append(cur)
            cur = [b]
    lines.append(cur)

    suspect_boxes = suspect_lines = 0
    for ln in lines:
        widest = max((b["x0"] - a["x1"] for a, b in zip(ln, ln[1:])), default=0.0)
        if widest > gutter:
            suspect_lines += 1
            suspect_boxes += len(ln)
    return {"layout_confidence": round(1.0 - suspect_boxes / len(ordered), 4),
            "emitted_lines": len(lines),
            "suspect_lines": suspect_lines}


ORDERINGS = {
    "naive_yx": lambda bx: naive_yx(bx, 0.0),
    "xycut": lambda bx: xycut(bx),
}


# ---------------------------------------------------------------------------
# SOURCE: born-digital PDF glyph boxes
# ---------------------------------------------------------------------------

def pdf_word_boxes(path: pathlib.Path) -> list[dict]:
    """
    Raw glyph boxes clustered into words. NO pdfminer layout analysis
    (`laparams=None`), so the ordering policy under test is the only ordering
    in the pipeline.
    """
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTChar

    chars = []
    for page in extract_pages(str(path), laparams=None):
        stack = list(page)
        while stack:
            el = stack.pop()
            if isinstance(el, LTChar):
                chars.append(el)
            elif hasattr(el, "__iter__"):
                stack.extend(el)
    if not chars:
        return []
    rows = sorted(((c.y1, c.y0, c.x0, c.x1, c.get_text(), c.size) for c in chars),
                  key=lambda r: (-r[0], r[2]))
    # group into visual lines by baseline proximity
    lines: list[list] = []
    for r in rows:
        if lines and abs(lines[-1][0][0] - r[0]) < max(1.5, r[5] * 0.35):
            lines[-1].append(r)
        else:
            lines.append([r])
    words = []
    for ln in lines:
        ln.sort(key=lambda r: r[2])
        cur, cx1 = [], None
        for r in ln:
            if cur and (r[2] - cx1) > r[5] * 0.26:
                words.append(cur)
                cur = []
            cur.append(r)
            cx1 = r[3]
        if cur:
            words.append(cur)
    out = []
    for w in words:
        txt = "".join(r[4] for r in w).strip()
        if not txt:
            continue
        out.append({"text": txt,
                    "x0": min(r[2] for r in w), "x1": max(r[3] for r in w),
                    "y0": min(792.0 - r[0] for r in w),   # flip to top-left origin
                    "y1": max(792.0 - r[1] for r in w)})
    return out


# ---------------------------------------------------------------------------
# SOURCE: OCR
# ---------------------------------------------------------------------------

_ocr = None


def ocr_engine():
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    return _ocr


def dewarp(img_path: pathlib.Path) -> tuple[np.ndarray, bool]:
    """
    Rectify a photographed page: find the page quadrilateral and unwarp it.

    Twenty-five lines of OpenCV, no model, no service. It is here because a
    reading-order result on a tilted photograph confounds two failures -- the
    recogniser struggling with perspective, and the ORDERING policy being fed
    boxes whose y-coordinates slide across the page because the page is tilted.
    Running the same OCR with and without it separates them, and that separation
    is the difference between "we need a document-understanding vendor" and "we
    need a homography".

    It assumes a PLANAR page. A page with spine curl is not planar and this will
    not fix it; see `_limits.dewarp_assumes_planar`.
    """
    g = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    blur = cv2.GaussianBlur(g, (5, 5), 0)
    otsu, _ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # TWO SWEEPS, because a single guess failed twice in two different ways and
    # both failures were silent.
    #
    #   THRESHOLD. Otsu picked 159 on the camera fixture. The page carries a
    #   vignette, so its far corners sit near 150 and were thresholded OUT: the
    #   detected "page" was the bright middle, and rectifying to it CROPPED AWAY
    #   COLUMN 2. Recall did not improve and reading order did not improve, and
    #   the honest-looking conclusion "rectification does not help" would have
    #   been drawn from an image with a column missing.
    #
    #   EPSILON. At 0.02*perimeter the outline simplifies to five vertices and
    #   the first version returned the input unchanged, again silently.
    #
    # Both sweeps are scored on the same quantity -- the area of the recovered
    # quadrilateral -- and the largest plausible quadrilateral wins.
    best_quad, best_area = None, 0.0
    h_img, w_img = g.shape
    for frac in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5):
        _, th = cv2.threshold(blur, otsu * frac, 255, cv2.THRESH_BINARY)
        th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
        cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        c = max(cnts, key=cv2.contourArea)
        if cv2.contourArea(c) < 0.25 * h_img * w_img:
            continue
        peri = cv2.arcLength(c, True)
        for eps in (0.01, 0.02, 0.03, 0.04, 0.05, 0.07):
            approx = cv2.approxPolyDP(c, eps * peri, True)
            if len(approx) == 4:
                area = cv2.contourArea(approx)
                # Reject a "page" that fills the frame -- that is the frame.
                if best_area < area <= 0.985 * h_img * w_img:
                    best_quad, best_area = approx, area
                break
    if best_quad is None:
        return g, False
    pts = best_quad.reshape(4, 2).astype(np.float32)
    s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
    src = np.float32([pts[np.argmin(s)], pts[np.argmin(d)],
                      pts[np.argmax(s)], pts[np.argmax(d)]])
    h, w = g.shape
    dst = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    return cv2.warpPerspective(g, cv2.getPerspectiveTransform(src, dst), (w, h)), True


def ocr_boxes(img_path: pathlib.Path, do_dewarp: bool = False) -> tuple[list[dict], float, bool]:
    """Returns (regions, seconds, dewarp_applied). A region is one detected text line."""
    applied = False
    if do_dewarp:
        img, applied = dewarp(img_path)
    else:
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    t0 = time.time()
    res, _ = ocr_engine()(img)
    secs = time.time() - t0
    out = []
    for box, text, score in (res or []):
        pts = np.asarray(box, dtype=np.float32)
        # The recogniser's own confidence is carried through so it can be
        # COMPARED with reading-order correctness rather than assumed to track
        # it. See run.py's confidence_signal block: it does not track it.
        out.append({"text": text, "score": float(score),
                    "x0": float(pts[:, 0].min()), "x1": float(pts[:, 0].max()),
                    "y0": float(pts[:, 1].min()), "y1": float(pts[:, 1].max())})
    return out, secs, applied


# ---------------------------------------------------------------------------
# WHOLE-TOOL BASELINES
# ---------------------------------------------------------------------------

def _pdftotext_bin() -> str | None:
    for c in (shutil.which("pdftotext"),
              r"C:\Program Files\Git\mingw64\bin\pdftotext.exe"):
        if c and pathlib.Path(c).exists():
            return c
    return None


def run_pdftotext(path: pathlib.Path, layout: bool) -> str:
    exe = _pdftotext_bin()
    if not exe:
        raise RuntimeError("pdftotext (poppler) not found")
    cmd = [exe, "-q", "-enc", "UTF-8"] + (["-layout"] if layout else []) + [str(path), "-"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"pdftotext exit {p.returncode}: {p.stderr[:200]!r}")
    return p.stdout.decode("utf-8", "replace")


def run_pdfminer(path: pathlib.Path, boxes_flow) -> str:
    from pdfminer.high_level import extract_text
    from pdfminer.layout import LAParams
    return extract_text(str(path), laparams=LAParams(boxes_flow=boxes_flow))


def run_pdfium(path: pathlib.Path) -> str:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(path))
    try:
        tp = doc[0].get_textpage()
        return tp.get_text_bounded()
    finally:
        doc.close()


def joined(boxes: list[dict]) -> str:
    return " ".join(b["text"] for b in boxes)
