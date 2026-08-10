#!/usr/bin/env python3
"""
SPIKE D mutation battery — proving the metric can FAIL.

A metric that cannot fail is not a metric. Every mutation below takes the
PERFECT output (the constructed truth, emitted in the correct order) and breaks
it in one specific, named way, and every mutation carries an EXPECTATION written
before the run. If a mutation lands outside its expected band, the finding is
against THE INSTRUMENT, not against the engine, and `run.py` fails the whole
spike rather than publishing engine numbers produced by a ruler that does not
bend.

Mutating the perfect output rather than an engine's output is deliberate: it
isolates the mutation. A mutation applied to a noisy transcript scores a mixture
of the mutation and the noise, and then a band that misses tells you nothing
about which. The real-world counterpart is separate and is not a simulation at
all -- `engines.naive_yx` is a genuine naive extractor run against the genuine
two-column PDF, and it is expected to land in the same band as `interleave_lines`
for the same reason. That pairing is the load-bearing evidence: the synthetic
mutation and the real defect agree.

EXPECTATION BANDS ARE NOT TUNED. Each was derived by arithmetic before the run
and the derivation is in the `why` field, so a band that had to be widened
afterwards is visible in the diff rather than invisible in a number.
"""
from __future__ import annotations

import random

from layout import Page


def lines_of(page: Page) -> list[dict]:
    """Group the body into rendered lines, in truth order."""
    out: list[dict] = []
    for w in page.body:
        if not out or out[-1]["block"] != w.block or out[-1]["line"] != w.line:
            out.append({"block": w.block, "line": w.line, "tokens": []})
        out[-1]["tokens"].append(w.text)
    return out


def _join(groups) -> str:
    return " ".join(" ".join(g["tokens"]) for g in groups)


def _split_blocks(page: Page):
    """(prefix, col_a, col_b) where prefix is title/accent furniture-free lead."""
    ls = lines_of(page)
    pre = [g for g in ls if g["block"] in ("title", "accent")]
    a = [g for g in ls if g["block"] in ("col1", "main")]
    b = [g for g in ls if g["block"] == "col2"]
    return pre, a, b


# ---------------------------------------------------------------------------
# The mutations. Each returns the mutated output text.
# ---------------------------------------------------------------------------

def m_identity(page):
    return _join(lines_of(page))


def m_interleave_lines(page):
    pre, a, b = _split_blocks(page)
    woven = []
    for i in range(max(len(a), len(b))):
        if i < len(a):
            woven.append(a[i])
        if i < len(b):
            woven.append(b[i])
    return _join(pre + woven)


def m_column_swap(page):
    pre, a, b = _split_blocks(page)
    return _join(pre + b + a)


def m_reverse_all(page):
    return " ".join(reversed(m_identity(page).split()))


def m_shuffle_lines(page):
    ls = lines_of(page)
    rng = random.Random(11)
    sh = ls[:]
    rng.shuffle(sh)
    return _join(sh)


def m_shuffle_paragraphs(page):
    """Shuffle at paragraph granularity -- a coarser, more plausible failure."""
    ls = lines_of(page)
    paras, cur = [], []
    for g in ls:
        cur.append(g)
        if g["tokens"] and g["tokens"][-1].endswith((".", ":")) and len(cur) > 1:
            paras.append(cur)
            cur = []
    if cur:
        paras.append(cur)
    rng = random.Random(29)
    rng.shuffle(paras)
    return _join([g for p in paras for g in p])


def m_drop_column(page):
    pre, a, _ = _split_blocks(page)
    return _join(pre + a)


def m_duplicate_column(page):
    pre, a, b = _split_blocks(page)
    return _join(pre + a + a + b)


def m_char_noise(page):
    """Substitute one character in ~10% of tokens. Order intact, recall down."""
    rng = random.Random(7)
    toks = m_identity(page).split()
    out = []
    for t in toks:
        if len(t) > 3 and rng.random() < 0.10:
            i = rng.randrange(1, len(t) - 1)
            t = t[:i] + rng.choice("aeiounmrl") + t[i + 1:]
        out.append(t)
    return " ".join(out)


def _swap_adjacent(page, rate, seed):
    rng = random.Random(seed)
    toks = m_identity(page).split()
    i = 0
    while i < len(toks) - 1:
        if rng.random() < rate:
            toks[i], toks[i + 1] = toks[i + 1], toks[i]
            i += 2
        else:
            i += 1
    return " ".join(toks)


def m_swap_adjacent(page):
    return _swap_adjacent(page, 0.03, 13)


def m_swap_adjacent_heavy(page):
    return _swap_adjacent(page, 0.12, 17)


def m_furniture_inline(page):
    """Splice the running head, folio and any sidebar into the middle."""
    toks = m_identity(page).split()
    furn = [w.text for w in page.furniture]
    third = len(toks) // 3
    return " ".join(toks[:third] + furn + toks[third:])


def _hyphen_split(page, every, minlen):
    toks = m_identity(page).split()
    out = []
    for n, t in enumerate(toks):
        if len(t) >= minlen and n % every == 0:
            k = len(t) // 2
            out += [t[:k] + "-", t[k:]]
        else:
            out.append(t)
    return " ".join(out)


def m_hyphen_split(page):
    """Realistic rate: about one broken word per two rendered lines."""
    return _hyphen_split(page, 12, 9)


def m_hyphen_split_heavy(page):
    """Every line hyphenated -- narrow columns, justified, no dictionary."""
    return _hyphen_split(page, 3, 7)


def m_title_last(page):
    """
    A heading emitted AFTER the paragraph it introduces.

    This mutation exists to DOCUMENT a blind spot, not to be caught. A listener
    hears it instantly; the metric sees a short block moved a short distance and
    scores it near the pass bar. Its expectation is therefore that it scores
    HIGH, and `documents_limit` marks it as evidence for `_limits`, not as a
    gate. Writing the blind spot into the battery is the only way it stays true
    as the metric changes.
    """
    ls = lines_of(page)
    title = [g for g in ls if g["block"] == "title"]
    rest = [g for g in ls if g["block"] != "title"]
    return _join(rest[:6] + title + rest[6:])


MUTATIONS = [
    {
        "id": "identity",
        "fn": m_identity,
        "why": "Control. The unmutated truth must score 1.0 on every order "
               "metric and 1.0 recall; if it does not, nothing below means "
               "anything.",
        "expect": [("reading_order_score", ">=", 0.999),
                   ("adjacency_score", ">=", 0.999),
                   ("token_recall", ">=", 0.999)],
        "expect_verdict": True,
    },
    {
        "id": "interleave_lines",
        "fn": m_interleave_lines,
        "applies_to": "two_column",
        "why": "THE failure this spike exists for: a line-by-line reader "
               "crossing the gutter. With prefix T tokens and columns of N1~N2~N, "
               "the longest increasing run is T+N of T+2N tokens, so the score "
               "must land near 0.5 while recall stays 1.0.",
        "expect": [("reading_order_score", "between", (0.42, 0.62)),
                   ("token_recall", ">=", 0.98)],
        "expect_verdict": False,
    },
    {
        "id": "column_swap",
        "fn": m_column_swap,
        "applies_to": "two_column",
        "why": "Block-level version of the same defect: column 2 emitted first. "
               "Same arithmetic, same band. Distinct from interleaving because "
               "the output is FLUENT -- both columns read correctly, in the "
               "wrong order -- which is what a listener cannot detect.",
        "expect": [("reading_order_score", "between", (0.42, 0.62)),
                   ("token_recall", ">=", 0.98)],
        "expect_verdict": False,
    },
    {
        "id": "reverse_all",
        "fn": m_reverse_all,
        "why": "Floor check. The score must sit at the noise floor of the "
               "metric, which is NOT 1/n: tokens whose fold repeats across the "
               "page (`the`, `of`) resolve pseudo-randomly once their context "
               "is reversed, and a random permutation of k points has a longest "
               "increasing subsequence of about 2*sqrt(k) (Ulam). With ~200 "
               "such tokens on a 520-token page that is ~28/520 = 0.054.",
        "expect": [("reading_order_score", "<=", 0.10)],
        "expect_verdict": False,
        "band_revised": {
            "from": ("reading_order_score", "<=", 0.02),
            "to": ("reading_order_score", "<=", 0.10),
            "when": "2026-08-10, after the first gate run, before any engine "
                    "numbers were written down",
            "reason": "The original band came from an arithmetic error, not "
                      "from the data: it assumed LIS = 1 on a reversed sequence, "
                      "which is true only if every token is uniquely identified. "
                      "Repeated function words are not, and their assignments "
                      "scatter. Measured 0.035-0.058 across five fixtures. The "
                      "band is widened to the correct floor and this record "
                      "exists so the widening is auditable rather than silent.",
        },
    },
    {
        "id": "shuffle_lines",
        "fn": m_shuffle_lines,
        "why": "Total loss of line order. LIS over a random permutation of L "
               "lines is O(sqrt(L)) lines, far under half.",
        "expect": [("reading_order_score", "<=", 0.45)],
        "expect_verdict": False,
    },
    {
        "id": "shuffle_paragraphs",
        "fn": m_shuffle_paragraphs,
        "why": "Coarser and far more plausible than shuffling lines -- it is "
               "what a block-detecting engine does when it orders the blocks "
               "wrongly. Longest increasing run over ~8 shuffled paragraphs is "
               "about 3, so well under 0.7.",
        "expect": [("reading_order_score", "<=", 0.70)],
        "expect_verdict": False,
    },
    {
        "id": "drop_column",
        "fn": m_drop_column,
        "applies_to": "two_column",
        "why": "PROVES token_recall is load-bearing. Column 2 is simply not "
               "emitted. Both ORDER metrics are perfect -- everything present is "
               "in the right order -- and an order-only instrument would pass "
               "a page with half its text missing.",
        "expect": [("reading_order_score", ">=", 0.99),
                   ("token_recall", "between", (0.35, 0.68))],
        "expect_verdict": False,
    },
    {
        "id": "duplicate_column",
        "fn": m_duplicate_column,
        "why": "Column 1 emitted twice -- a real failure of overlapping block "
               "detection. Recall stays perfect; the repeated block forces the "
               "increasing subsequence to abandon one copy.",
        "expect": [("reading_order_score", "<=", 0.85),
                   ("token_recall", ">=", 0.98)],
        "expect_verdict": False,
    },
    {
        "id": "char_noise",
        "fn": m_char_noise,
        "why": "PROVES the order metric is not just measuring OCR accuracy. "
               "10% of tokens corrupted, order untouched: the order score must "
               "stay at the ceiling while recall drops ~10 points. If order "
               "moved here, it would be a character-accuracy metric wearing an "
               "order metric's name.",
        "expect": [("reading_order_score", ">=", 0.99),
                   ("token_recall", "between", (0.80, 0.95))],
        "expect_verdict": False,
    },
    {
        "id": "swap_adjacent",
        "fn": m_swap_adjacent,
        "why": "SENSITIVITY FLOOR, and it is a limit rather than a gate. ~3% of "
               "adjacent pairs transposed -- prose a listener would find "
               "confusing -- scores order 0.986 and adjacency 0.956, so it "
               "clears BOTH bars. Adjacency is still the more sensitive of the "
               "two (it moves 4x further than LIS), which is why it is a bar at "
               "all; it simply does not move far enough here. The bars tolerate "
               "roughly one transposed pair per eighty words, and that tolerance "
               "is now measured rather than assumed.",
        "expect": [("reading_order_score", ">=", 0.97),
                   ("adjacency_score", "<=", 0.97)],
        "expect_verdict": None,
        "documents_limit": "transposition_sensitivity_floor",
        "band_revised": {
            "from": ("adjacency_score", "<=", 0.95),
            "to": ("adjacency_score", "<=", 0.97),
            "when": "2026-08-10, after the first gate run",
            "reason": "The prediction was that 3% transposition breaks ~9% of "
                      "adjacencies; measured 4.4%, because a transposition that "
                      "lands next to an already-transposed pair or an "
                      "unassigned token breaks fewer than three. The mutation "
                      "is kept at a REALISTIC rate and reclassified from gate to "
                      "limit -- the alternative was to raise the rate until it "
                      "failed, which would have hidden the sensitivity floor "
                      "instead of measuring it. `swap_adjacent_heavy` supplies "
                      "the gate.",
        },
    },
    {
        "id": "swap_adjacent_heavy",
        "fn": m_swap_adjacent_heavy,
        "why": "The gate that `swap_adjacent` cannot be. 12% of pairs "
               "transposed is unambiguously unusable text and must be caught.",
        "expect": [("adjacency_score", "<=", 0.92)],
        "expect_verdict": False,
    },
    {
        "id": "furniture_inline",
        "fn": m_furniture_inline,
        "why": "The running head, folio and sidebar spliced into the middle of "
               "the body -- a page number spoken mid-sentence. Neither order "
               "metric can see it (the body order is untouched), so it is "
               "caught only by furniture_inline, which is why that count is a "
               "gate and not a note.",
        "expect": [("furniture_inline", ">=", 3),
                   ("reading_order_score", ">=", 0.98)],
        "expect_verdict": False,
    },
    {
        "id": "hyphen_split",
        "fn": m_hyphen_split,
        "why": "Line-break hyphenation not rejoined, at a REALISTIC rate -- "
               "about one broken word per two rendered lines. It costs 1.5 "
               "points of recall, which is INSIDE the 0.98 digital bar, so "
               "ordinary hyphenation is not caught. That is the finding: a "
               "hyphen-unaware extractor passes this instrument, and mispronounces "
               "one word per two lines to a listener. The gate is supplied by "
               "`hyphen_split_heavy`; this row exists to keep the blind spot "
               "measured.",
        "expect": [("token_recall", "between", (0.96, 0.995)),
                   ("reading_order_score", ">=", 0.98)],
        "expect_verdict": None,
        "documents_limit": "hyphenation_below_recall_bar",
        "band_revised": {
            "from": ("token_recall", "between", (0.88, 0.98)),
            "to": ("token_recall", "between", (0.96, 0.995)),
            "when": "2026-08-10, after the first gate run",
            "reason": "The band assumed a split rate an order of magnitude "
                      "above what typeset text produces. Measured 0.9845-0.9861. "
                      "The MUTATION was not made harsher to fit the band, "
                      "because a realistic rate that slips under the bar is the "
                      "more useful fact; it is reclassified as a limit and a "
                      "separate heavy variant supplies the gate.",
        },
    },
    {
        "id": "hyphen_split_heavy",
        "fn": m_hyphen_split_heavy,
        "why": "Every line hyphenated -- narrow justified columns with no "
               "dictionary. This must be caught by recall.",
        "expect": [("token_recall", "<=", 0.95),
                   ("reading_order_score", ">=", 0.97)],
        "expect_verdict": False,
    },
    {
        "id": "title_last",
        "fn": m_title_last,
        "why": "DOCUMENTS A BLIND SPOT rather than testing a gate. The heading "
               "is emitted after the paragraph it introduces -- instantly wrong "
               "to a listener, a small local inversion to this metric. It is "
               "expected to score HIGH, and that expectation is the evidence "
               "for _limits.semantic_units_not_seen.",
        "expect": [("reading_order_score", ">=", 0.90)],
        "expect_verdict": None,          # not a gate
        "documents_limit": "semantic_units_not_seen",
    },
]


def is_two_column(page: Page) -> bool:
    return any(w.block == "col2" for w in page.body)


def check(expect, result) -> tuple[bool, str]:
    for key, op, val in expect:
        got = result.get(key)
        if got is None:
            return False, f"{key} is null"
        if op == ">=" and not got >= val:
            return False, f"{key}={got} not >= {val}"
        if op == "<=" and not got <= val:
            return False, f"{key}={got} not <= {val}"
        if op == "between" and not (val[0] <= got <= val[1]):
            return False, f"{key}={got} not in [{val[0]}, {val[1]}]"
    return True, ""
