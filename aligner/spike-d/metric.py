#!/usr/bin/env python3
"""
SPIKE D metric — READING ORDER, measured against a constructed answer key.

THE QUESTION THIS FILE ANSWERS
==============================
Not "how many characters did the engine get right". A two-column page read
straight across produces text that is 100% character-accurate and completely
unusable, and a sighted user notices in one second while a blind user does not
notice at all. So character accuracy is reported, but it is not the verdict.

The verdict is: OF THE WORDS THE ENGINE RECOVERED, WHAT FRACTION APPEAR IN THE
ORDER THE PAGE PUTS THEM IN?

THREE NUMBERS, NOT ONE, BECAUSE THEY FAIL SEPARATELY
====================================================
  reading_order_score  LIS(assigned truth indices) / number assigned.
                       "The longest run of recovered words that is in correct
                       relative order, as a fraction of what was recovered."
                       Column interleaving lands near 0.50 because you can
                       follow one column or the other, never both.
  adjacency_score      fraction of consecutive output pairs where the truth
                       index advances by exactly one. Sharper and more local:
                       it sees a single transposed pair that LIS shrugs off.
  token_recall         matched truth tokens / all truth tokens. ORDER-BLIND.
                       It exists so that dropping a whole column cannot be
                       mistaken for good reading order -- an engine that emits
                       only column 1 scores 1.00 on both order metrics.

An engine passes only on all three. `drop_column` in the mutation battery is
the case that proves the third one is load-bearing.

THE ASSIGNMENT STEP, AND WHY IT IS ORDER-BLIND
==============================================
To score order we must know which ground-truth word each output word IS. Doing
that by sequence alignment would be circular: alignment imposes monotonicity,
so a badly ordered output would be forced to look like a well ordered one with
deletions.

So assignment here uses CONTENT ONLY and never position:

  candidates(o_i) = every truth index j with fold(truth[j]) == fold(o_i)
  score(i, j)     = weighted agreement of the +/-3 neighbourhoods
  assign          = the unique argmax; a TIE is left UNASSIGNED

There is no positional prior, no "near the previous match" tiebreak, and no
fallback. A tiebreak toward monotonic order would make every order score
optimistic, which is the one direction a safety metric must not err in; a
tiebreak away from it would invent defects. Ties are dropped and COUNTED
(`ambiguous_assignments`), so the amount of evidence discarded is visible
rather than absorbed.

`layout.assert_context_unique` proves, before any engine runs, that no
tie is possible on a CLEAN read of these fixtures (radius 2 suffices). Ties can
still arise on a noisy read, where a corrupted neighbour flattens the score.
That is why they are counted rather than assumed away.

WHAT THIS METRIC CANNOT SEE — the same block is emitted into the artifact.
==========================================================================
 1. It cannot see order among words it did not recover. Order is measured on
    the recognised subset; a camera photo with 60% recall has 60% of the
    evidence, and `order_n` says so.
 2. It cannot tell a fluent wrong order from a jarring one. `reading_order_score
    = 0.5` is the same number whether the interleaving produces gibberish or
    grammatical prose that says the opposite of the page. Only the second is
    dangerous for a blind user, and distinguishing them needs a language model
    this spike does not have.
 3. It cannot see whether the SEMANTIC unit is right -- a heading read after its
    own paragraph is a defect a reader hears immediately and this metric scores
    as two short inversions.
 4. It is blind to everything not made of words: figure captions bound to the
    wrong figure, table cells linearised by row when the table reads by column,
    equations. The fixtures contain none of these, so the metric has never been
    exercised against them, and a passing score here is not a claim about them.
 5. Diacritics are folded away for matching, so an engine that drops every
    accent still scores full `token_recall`. `accent_recall` is measured
    separately and unfolded for exactly this reason.
"""
from __future__ import annotations

import unicodedata

from layout import fold

# ── Bars. Fixed here, before any engine was run. SPIKE A's H17-C3: a bound
# chosen after seeing the numbers is not a bound. ───────────────────────────
BAR_READING_ORDER = 0.98
BAR_ADJACENCY = 0.95
BAR_RECALL_DIGITAL = 0.98     # a born-digital PDF has the characters already
BAR_RECALL_IMAGE = 0.85       # OCR of a photograph will lose some
BAR_FURNITURE_INLINE = 0      # a page number spoken mid-sentence is a defect
BAR_WORD_SPACE_LOSS = 0.02    # "thenorthernshore" is one nonsense word to a
                              # TTS voice; see assign()'s merged-token note.
                              # Added 2026-08-10, BEFORE any engine comparison
                              # was written down, because the first OCR run
                              # revealed a failure the metric could not see.
MIN_ORDER_N = 50              # below this the order score is reported, flagged,
                              # and not treated as a verdict (SPIKE A n=14).

CTX_RADIUS = 3
CTX_WEIGHT = {1: 4, 2: 2, 3: 1}


def tokenize(text: str) -> list[str]:
    return text.split()


def is_accented(tok: str) -> bool:
    return any(unicodedata.combining(c) for c in unicodedata.normalize("NFD", tok))


def strict(tok: str) -> str:
    """Fold WITHOUT stripping diacritics -- the accent test's comparison form."""
    import re
    t = unicodedata.normalize("NFC", tok).lower()
    return re.sub(r"[^\w']", "", t, flags=re.UNICODE)


def _lis_length(seq: list[int]) -> int:
    """Longest strictly increasing subsequence, patience sorting, O(n log n)."""
    import bisect
    tails: list[int] = []
    for v in seq:
        i = bisect.bisect_left(tails, v)
        if i == len(tails):
            tails.append(v)
        else:
            tails[i] = v
    return len(tails)


def _inversions(seq: list[int]) -> int:
    """Pairwise inversions via a Fenwick tree over compressed ranks."""
    if len(seq) < 2:
        return 0
    ranks = {v: i + 1 for i, v in enumerate(sorted(set(seq)))}
    n = len(ranks)
    tree = [0] * (n + 1)
    inv = 0
    seen = 0
    for v in seq:
        r = ranks[v]
        # count already-seen values strictly greater than r
        i, le = r, 0
        while i > 0:
            le += tree[i]
            i -= i & -i
        inv += seen - le
        seen += 1
        i = r
        while i <= n:
            tree[i] += 1
            i += i & -i
    return inv


MAX_MERGE = 8


def assign(out_tokens: list[str], truth_tokens: list[str],
           suspect_folds: set[str] | None = None):
    """
    Content-only assignment of output tokens to truth indices.

    Returns (spans, ambiguous, no_candidate); spans[i] is the list of truth
    indices output token i accounts for, or None.

    MERGED TOKENS — added after the first OCR run, and the reason matters.
    ====================================================================
    RapidOCR returned `thenorthernshore.Eachstation` for four words. The
    recogniser had every character right and had simply not emitted the spaces.
    The first version of this function matched whitespace tokens only, so those
    four truth words were scored as UNRECOVERED and the words around them lost
    their context; `token_recall` came out at 0.34 on a page the engine had very
    nearly read. A recall figure that low would have been reported as "the OCR
    cannot read the page", and the true statement is "the OCR reads the page and
    loses the spaces". Those recommend different products.

    So an output token is now also matched against a RUN of consecutive truth
    tokens whose concatenated folds equal it. The run contributes all of its
    indices to the order sequence, in order -- which is correct, because the
    characters really are present in that order.

    This is PERMISSIVE, and the compensating disclosure is
    `word_space_loss_rate`: the share of truth tokens recovered only inside a
    merged run. Those words are recovered for READING ORDER and broken for
    SPEECH -- a TTS voice says "thenorthernshore" as one nonsense word -- so the
    rate is a bar of its own rather than a footnote.

    THE INVERSE IS NOT HANDLED. One truth token split across several output
    tokens (line-break hyphenation, or a recogniser splitting a word) stays
    unmatched and costs recall. That is deliberate: `hyphen_split` in the
    mutation battery expects exactly that penalty, and a fix would make the
    hyphenation defect invisible.
    """
    out_f = [fold(t) for t in out_tokens]
    tru_f = [fold(t) for t in truth_tokens]
    n_out, n_tru = len(out_f), len(tru_f)

    by_fold: dict[str, list[tuple[int, int]]] = {}
    for j, f in enumerate(tru_f):
        if not f:
            continue
        by_fold.setdefault(f, []).append((j, 1))
    for j in range(n_tru):
        acc = tru_f[j]
        if not acc:
            continue
        for L in range(2, MAX_MERGE + 1):
            if j + L > n_tru or not tru_f[j + L - 1]:
                break
            acc += tru_f[j + L - 1]
            by_fold.setdefault(acc, []).append((j, L))

    spans: list[list[int] | None] = [None] * n_out
    ambiguous = no_candidate = 0

    for i, f in enumerate(out_f):
        if not f:
            continue
        cands = by_fold.get(f)
        if not cands:
            no_candidate += 1
            continue

        def ctx(j: int, L: int) -> int:
            s = 0
            for d in range(1, CTX_RADIUS + 1):
                oi, tj = i - d, j - d                       # left neighbourhood
                if 0 <= oi < n_out and 0 <= tj and out_f[oi] and out_f[oi] == tru_f[tj]:
                    s += CTX_WEIGHT[d]
                oi, tj = i + d, j + L - 1 + d               # right neighbourhood
                if oi < n_out and tj < n_tru and out_f[oi] and out_f[oi] == tru_f[tj]:
                    s += CTX_WEIGHT[d]
            return s

        # SUSPECT FOLDS. A word printed in the page furniture that ALSO occurs
        # once in the body is, by content alone, indistinguishable from the body
        # occurrence -- so a sidebar's "campaign" was being assigned to the
        # body's "campaign", which dragged the last-body position past the whole
        # sidebar and reported 23 inline furniture tokens against an ordering
        # that had correctly put the sidebar LAST. The metric was failing a
        # correct engine. Such a token must now show at least one agreeing
        # neighbour to be counted as body; with none, it is left unassigned.
        if suspect_folds and f in suspect_folds:
            viable = [(j, L) for j, L in cands if ctx(j, L) >= 1]
            if not viable:
                no_candidate += 1
                continue
            cands = viable

        if len(cands) == 1:
            j, L = cands[0]
            spans[i] = list(range(j, j + L))
            continue
        best, best_score, tie = None, -1, False
        for j, L in cands:
            s = ctx(j, L)
            if s > best_score:
                best, best_score, tie = (j, L), s, False
            elif s == best_score:
                tie = True
        if tie:
            ambiguous += 1          # dropped on purpose; see module docstring
        else:
            j, L = best
            spans[i] = list(range(j, j + L))
    return spans, ambiguous, no_candidate


def score(out_text: str, truth_tokens: list[str], furniture_tokens: list[str],
          medium: str) -> dict:
    """
    Score one engine output against one page's constructed truth.

    `medium` is "digital" or "image" and selects only the RECALL bar. The two
    order bars are identical for both, deliberately: a page read in the wrong
    order is equally unusable whether it arrived as a PDF or a photograph, and
    softening the order bar for the harder medium would be tuning the ruler to
    the result.
    """
    out_tokens = tokenize(out_text)
    furn_f = {fold(t) for t in furniture_tokens if fold(t)}
    spans, ambiguous, no_candidate = assign(out_tokens, truth_tokens, furn_f)

    pairs = [(i, sp) for i, sp in enumerate(spans) if sp is not None]
    seq = [j for _, sp in pairs for j in sp]
    n = len(seq)
    merged_output_tokens = sum(1 for _, sp in pairs if len(sp) > 1)
    truth_in_merged = sum(len(sp) for _, sp in pairs if len(sp) > 1)
    space_loss = truth_in_merged / len(truth_tokens) if truth_tokens else 0.0

    lis = _lis_length(seq)
    order = lis / n if n else None
    adj = (sum(1 for a, b in zip(seq, seq[1:]) if b == a + 1) / (n - 1)) if n > 1 else None
    inv = _inversions(seq)
    tau = (1.0 - 2.0 * inv / (n * (n - 1))) if n > 1 else None

    matched_truth = set(seq)
    recall = len(matched_truth) / len(truth_tokens) if truth_tokens else None

    # Furniture: rendered on the page, absent from the truth. Emitting it is
    # tolerable at the edges and a defect in the middle.
    # FURNITURE INLINE — "is a page number spoken in the middle of a sentence".
    #
    # The first rule was "does any assigned token appear before it AND after
    # it". That failed a CORRECT ordering: the sidebar fixtures put the box
    # last, but a handful of sidebar words also occur in the body, were assigned
    # to those body positions, and pushed the last-assigned position past the
    # whole box -- so 23 inline tokens were reported against an engine that had
    # done the right thing. A metric that fails a correct ordering is the same
    # class of defect as one that passes a wrong one.
    #
    # The rule is now CONTINUITY IN TRUTH SPACE: furniture is inline when it
    # interrupts a contiguous run of body text, i.e. the nearest assigned truth
    # index before it and the nearest after it are neighbours. A page number
    # dropped between truth words k and k+1 is caught; a sidebar emitted after
    # the body ends is not, because nothing contiguous surrounds it.
    prev_j: list[int | None] = [None] * len(out_tokens)
    last = None
    for i, sp in enumerate(spans):
        prev_j[i] = last
        if sp:
            last = sp[-1]
    next_j: list[int | None] = [None] * len(out_tokens)
    nxt = None
    for i in range(len(out_tokens) - 1, -1, -1):
        next_j[i] = nxt
        if spans[i]:
            nxt = spans[i][0]

    # Counted over RUNS, not single tokens. Per-token counting was fragile in
    # both directions: a furniture word that also occurs in the body gets
    # assigned to the body position and vanishes from the count, so a spliced
    # 37-token sidebar registered as 2. A run is decided by fold membership
    # regardless of assignment, so spurious assignment cannot hide it.
    #
    # A run only counts if it contains at least one fold found ONLY in the
    # furniture -- "Box", "S4", "217", "Quarterly". That is what separates a
    # real splice from an accidental two-word overlap like "the campaign"
    # occurring inside ordinary body text, which would otherwise be reported as
    # a defect against a correct ordering.
    truth_folds = {fold(t) for t in truth_tokens if fold(t)}
    furn_only = furn_f - truth_folds
    runs, cur = [], []
    for i, t in enumerate(out_tokens):
        if fold(t) in furn_f:
            cur.append(i)
        else:
            if cur:
                runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)

    furniture_emitted = furniture_inline = 0
    furniture_inline_examples = []
    for run in runs:
        if not any(fold(out_tokens[i]) in furn_only for i in run):
            continue
        furniture_emitted += len(run)
        a, b = prev_j[run[0]], next_j[run[-1]]
        if a is not None and b is not None and 0 < b - a <= 3:
            furniture_inline += len(run)
            for i in run[:8 - len(furniture_inline_examples)]:
                furniture_inline_examples.append(out_tokens[i])

    # Accents, unfolded and separate. See _limits.diacritics_folded.
    # Only spans of length 1 are comparable token-for-token; a merged run has no
    # single output token to compare against. Merged accented words are counted
    # as MISSES, which is the conservative direction and is stated in _limits.
    acc_truth = {j for j, t in enumerate(truth_tokens) if is_accented(t)}
    acc_hit = 0
    for i, sp in pairs:
        if len(sp) == 1 and sp[0] in acc_truth and strict(out_tokens[i]) == strict(truth_tokens[sp[0]]):
            acc_hit += 1
    accent_recall = (acc_hit / len(acc_truth)) if acc_truth else None

    bar_recall = BAR_RECALL_DIGITAL if medium == "digital" else BAR_RECALL_IMAGE
    passes = (order is not None and order >= BAR_READING_ORDER
              and adj is not None and adj >= BAR_ADJACENCY
              and recall is not None and recall >= bar_recall
              and furniture_inline <= BAR_FURNITURE_INLINE
              and space_loss <= BAR_WORD_SPACE_LOSS
              and n >= MIN_ORDER_N)

    return {
        "reading_order_score": round(order, 4) if order is not None else None,
        "adjacency_score": round(adj, 4) if adj is not None else None,
        "kendall_order_concordance": round(tau, 4) if tau is not None else None,
        "token_recall": round(recall, 4) if recall is not None else None,
        "accent_recall": round(accent_recall, 4) if accent_recall is not None else None,
        "order_n": n,
        "order_n_below_floor": n < MIN_ORDER_N,
        "truth_tokens": len(truth_tokens),
        "output_tokens": len(out_tokens),
        "ambiguous_assignments": ambiguous,
        "unmatched_output_tokens": no_candidate,
        "merged_output_tokens": merged_output_tokens,
        "word_space_loss_rate": round(space_loss, 4),
        "furniture_tokens_emitted": furniture_emitted,
        "furniture_inline": furniture_inline,
        "furniture_inline_examples": furniture_inline_examples,
        "inversions": inv,
        "bars": {"reading_order": BAR_READING_ORDER, "adjacency": BAR_ADJACENCY,
                 "token_recall": bar_recall, "furniture_inline": BAR_FURNITURE_INLINE,
                 "word_space_loss": BAR_WORD_SPACE_LOSS, "min_order_n": MIN_ORDER_N},
        "passes": bool(passes),
    }
