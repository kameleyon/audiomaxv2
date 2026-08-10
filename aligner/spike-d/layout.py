#!/usr/bin/env python3
"""
SPIKE D layout engine — GROUND TRUTH BY CONSTRUCTION.

This is the whole reason the spike can make a claim rather than an impression.
Nothing here reads a page and guesses where the columns are. It PLACES every
word at a known point and records the order it placed them in, so the correct
reading order is an input to the fixture, not a judgement about it. Judging a
real paper by eye would have given a softer number and no way to falsify it.

Coordinates are PDF points (72 per inch), origin TOP-LEFT, y increasing
downward. `render.py` flips y for the PDF and scales for the raster; both come
from this one geometry, so the born-digital fixture and the photographed
fixture describe the same page and share the same truth.

WORD WIDTHS. Advance widths are measured with Pillow against `arial.ttf`, and
the PDF is written with base-14 `/Helvetica`. Those two fonts are
metric-compatible by design -- same advance widths, different outlines -- so a
box measured in one is the box occupied by the other. This is what lets the PDF
avoid embedding a font (which would put a Microsoft font file in the repo) while
still placing every word where the raster places it.

WHAT THIS FILE GUARANTEES, and it is checked rather than asserted in prose:

  1. `reading_order` is index order. Words are appended in the order a human
     reads them: title, then column 1 top-to-bottom, then column 2.
  2. Furniture (running head, folio, sidebar box) is rendered and is NOT in the
     body truth. See `Page.furniture`.
  3. Every body token is uniquely identifiable by (fold, +/-k context) --
     `assert_context_unique` raises if not. Without this the metric's assignment
     step could place a token at the wrong ground-truth index and report an
     order defect that is really an ambiguity. The check runs BEFORE any engine
     does, and it fails the run rather than warning.
"""
from __future__ import annotations

import pathlib
import re
import unicodedata
from dataclasses import dataclass, field

from PIL import ImageFont

ROOT = pathlib.Path(__file__).parent
FONT_PATH = pathlib.Path(r"C:\Windows\Fonts\arial.ttf")

PAGE_W, PAGE_H = 612.0, 792.0          # US Letter, points
MARGIN = 54.0                          # 0.75 in
GUTTER = 24.0
BODY_PT = 9.5
TITLE_PT = 15.0
FURNITURE_PT = 8.0
LEADING = 12.4                         # body baseline-to-baseline
TITLE_LEADING = 19.0

# Pillow needs an integer pixel size; measuring at 10x the point size and
# dividing keeps sub-point precision without a float-size font object.
_MEASURE_SCALE = 10


@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block: str
    line: int
    size: float


@dataclass
class Page:
    lang: str
    name: str
    body: list[Word] = field(default_factory=list)       # THE TRUTH, in order
    furniture: list[Word] = field(default_factory=list)  # rendered, not truth
    width: float = PAGE_W
    height: float = PAGE_H
    columns: list[tuple[float, float]] = field(default_factory=list)

    @property
    def all_words(self) -> list[Word]:
        return self.body + self.furniture

    def truth_tokens(self) -> list[str]:
        return [w.text for w in self.body]


_font_cache: dict[float, ImageFont.FreeTypeFont] = {}


def font_at(pt: float) -> ImageFont.FreeTypeFont:
    if pt not in _font_cache:
        if not FONT_PATH.exists():
            raise FileNotFoundError(
                f"{FONT_PATH} is missing. The layout depends on Arial's advance "
                f"widths being Helvetica's; substituting another face silently "
                f"changes every box in every fixture, so this raises instead of "
                f"falling back to a default font.")
        _font_cache[pt] = ImageFont.truetype(str(FONT_PATH), int(round(pt * _MEASURE_SCALE)))
    return _font_cache[pt]


def advance(text: str, pt: float) -> float:
    """Advance width of `text` in points at size `pt`."""
    return font_at(pt).getlength(text) / _MEASURE_SCALE


def _wrap(tokens: list[str], width: float, pt: float) -> list[list[str]]:
    """
    Greedy word wrap. NO HYPHENATION -- see corpus.py provenance note. A word
    wider than the column is placed alone and allowed to overhang rather than
    being split, because splitting it would create a ground-truth token that
    does not exist on the page.
    """
    lines, cur, cur_w, space = [], [], 0.0, advance(" ", pt)
    for t in tokens:
        w = advance(t, pt)
        add = w if not cur else space + w
        if cur and cur_w + add > width:
            lines.append(cur)
            cur, cur_w = [t], w
        else:
            cur.append(t)
            cur_w += add
    if cur:
        lines.append(cur)
    return lines


def _emit(dest: list[Word], lines: list[list[str]], x: float, y: float,
          pt: float, block: str, leading: float, line0: int = 0) -> float:
    """Place wrapped lines starting at baseline-top `y`; return the next y."""
    space = advance(" ", pt)
    for li, line in enumerate(lines):
        cx = x
        for t in line:
            w = advance(t, pt)
            dest.append(Word(text=t, x0=cx, y0=y, x1=cx + w, y1=y + pt,
                             block=block, line=line0 + li, size=pt))
            cx += w + space
        y += leading
    return y


def build_two_column(lang: str, corpus: dict, furniture: dict,
                     accent_strip: list[str]) -> Page:
    """
    Title across the full measure, then two equal columns.

    Reading order by construction: title -> col1 (all of it) -> col2. This is
    the order the page is APPENDED in, so `page.body` IS the answer key.
    """
    p = Page(lang=lang, name=f"{lang}-2col")
    measure = PAGE_W - 2 * MARGIN
    col_w = (measure - GUTTER) / 2.0
    col_x = [MARGIN, MARGIN + col_w + GUTTER]
    p.columns = [(col_x[0], col_x[0] + col_w), (col_x[1], col_x[1] + col_w)]

    # Furniture first in the LIST but not in the truth: running head and folio.
    head = furniture["head"]
    _emit(p.furniture, [head.split()], MARGIN, MARGIN - 22.0, FURNITURE_PT, "head", LEADING)
    folio = furniture["folio"]
    fx = PAGE_W - MARGIN - advance(folio, FURNITURE_PT)
    _emit(p.furniture, [[folio]], fx, PAGE_H - MARGIN + 14.0, FURNITURE_PT, "folio", LEADING)

    y = MARGIN
    y = _emit(p.body, _wrap(corpus["title"].split(), measure, TITLE_PT),
              MARGIN, y, TITLE_PT, "title", TITLE_LEADING)
    y += 10.0

    # The accent strip sits under the title, spanning the measure. It is BODY
    # truth (it must be read, and in this position) but is scored separately.
    if accent_strip:
        for row in accent_strip:
            y = _emit(p.body, [row.split()], MARGIN, y, BODY_PT, "accent", LEADING)
        y += 8.0

    col_top = y
    for ci, paras in enumerate((corpus["col1"], corpus["col2"])):
        cy, line0 = col_top, 0
        for para in paras:
            lines = _wrap(para.split(), col_w, BODY_PT)
            cy = _emit(p.body, lines, col_x[ci], cy, BODY_PT, f"col{ci+1}", LEADING, line0)
            line0 += len(lines)
            cy += 5.0
    return p


def build_sidebar(lang: str, corpus: dict, furniture: dict) -> Page:
    """
    Single wide column with a boxed sidebar cutting into it.

    The roadmap names "a sidebar page" as the second fixture class. The hazard
    is different from a two-column page: there is only ONE body flow, and the
    box is an INTERRUPTION. A naive top-to-bottom reader splices the box into
    the middle of a sentence -- which for a listener is a non-sequitur mid-
    clause, not a wrongly ordered paragraph.
    """
    p = Page(lang=lang, name=f"{lang}-sidebar")
    measure = PAGE_W - 2 * MARGIN
    main_w = measure * 0.60
    side_x = MARGIN + main_w + GUTTER
    side_w = measure - main_w - GUTTER
    p.columns = [(MARGIN, MARGIN + main_w), (side_x, side_x + side_w)]

    _emit(p.furniture, [furniture["head"].split()], MARGIN, MARGIN - 22.0,
          FURNITURE_PT, "head", LEADING)

    y = MARGIN
    y = _emit(p.body, _wrap(corpus["title"].split(), measure, TITLE_PT),
              MARGIN, y, TITLE_PT, "title", TITLE_LEADING)
    y += 10.0
    body_top = y
    for para in corpus["col1"] + corpus["col2"]:
        y = _emit(p.body, _wrap(para.split(), main_w, BODY_PT), MARGIN, y,
                  BODY_PT, "main", LEADING)
        y += 5.0

    # The box starts a third of the way down the main flow -- deep enough that a
    # top-to-bottom reader hits it mid-paragraph.
    sy = body_top + (y - body_top) * 0.33
    for para in corpus["sidebar"]:
        sy = _emit(p.furniture, _wrap(para.split(), side_w - 10.0, BODY_PT),
                   side_x + 5.0, sy, BODY_PT, "sidebar", LEADING)
    p.sidebar_box = (side_x, body_top + (y - body_top) * 0.33 - 8.0,
                     side_x + side_w, sy + 4.0)
    return p


# ---------------------------------------------------------------------------
# THE UNIQUENESS PROOF
# ---------------------------------------------------------------------------

_PUNCT = re.compile(r"[^\w']", re.UNICODE)


def fold(tok: str) -> str:
    """
    NFKD-strip diacritics, lowercase, drop punctuation.

    Diacritic stripping is deliberate and it is a CHOICE WITH A COST, stated in
    the artifact: it means `turbidite` and `turbidité` fold together, so a
    recogniser that drops every accent still scores full token_recall. That is
    why `accent_recall` exists as a separate, UNFOLDED number -- the order metric
    must not be hostage to an accent, and the accent must not be excused by the
    order metric.
    """
    t = unicodedata.normalize("NFKD", tok)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return _PUNCT.sub("", t.lower())


def context_keys(tokens: list[str], k: int) -> list[tuple]:
    f = [fold(t) for t in tokens]
    n = len(f)
    return [tuple(f[max(0, i - k):i + k + 1]) if False else
            tuple((f[i + d] if 0 <= i + d < n else "\x00") for d in range(-k, k + 1))
            for i in range(n)]


def assert_context_unique(tokens: list[str], name: str, kmax: int = 4) -> int:
    """
    Find the smallest context radius k that makes every body token uniquely
    addressable, and RAISE if no k <= kmax does.

    This is the precondition for the whole metric. If two positions share a
    key, the assignment step has to guess, and a guess in either direction
    produces an order number that describes the guess. SPIKE A's lesson was
    that a metric with an unstated degree of freedom reports the degree of
    freedom; this closes that one before it opens.
    """
    for k in range(1, kmax + 1):
        keys = context_keys(tokens, k)
        if len(set(keys)) == len(keys):
            return k
    keys = context_keys(tokens, kmax)
    dupes = {}
    for i, key in enumerate(keys):
        dupes.setdefault(key, []).append(i)
    worst = [(v, key) for key, v in dupes.items() if len(v) > 1][:5]
    raise ValueError(
        f"{name}: ground truth is not uniquely addressable at context radius "
        f"{kmax}. Colliding positions: {worst}. The corpus must be varied until "
        f"it is; a metric cannot be run on an ambiguous answer key.")


def all_pages() -> list[Page]:
    from corpus import ACCENT_STRIP_ACCENTED, CORPUS, FURNITURE, LANGS
    pages = []
    for lang in LANGS:
        pages.append(build_two_column(lang, CORPUS[lang], FURNITURE[lang],
                                      ACCENT_STRIP_ACCENTED[lang]))
    for lang in ("en", "fr"):
        pages.append(build_sidebar(lang, CORPUS[lang], FURNITURE[lang]))
    return pages


if __name__ == "__main__":
    for p in all_pages():
        k = assert_context_unique(p.truth_tokens(), p.name)
        print(f"{p.name:14s} body={len(p.body):4d} furniture={len(p.furniture):3d} "
              f"context_radius={k}")
