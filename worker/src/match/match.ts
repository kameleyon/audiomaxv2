/**
 * The matcher — the product path, and the thing word sync IS.
 *
 * WHERE THIS CAME FROM. It was `match()` inside `aligner/spike-a/measure.py`,
 * which is a measurement script. `worker/src/normalize/` exists because a
 * normaliser that lives only in the instrument means the shipped behaviour and
 * the measured behaviour are different software; that argument was never weaker
 * for the matcher, it was only never acted on. SPIKE A's numbers are now
 * produced by this file, through `cli.ts`, so the figure on disk and the
 * behaviour a reader gets are the same code.
 *
 * WHAT IT DOES. It walks the recogniser's observed tokens forward and attaches
 * each to a display token, so a highlight has an address. §6.1's first invariant
 * is MONOTONICITY: the display cursor never moves backwards, because a book
 * contains "the" four thousand times and a matcher free to look behind produces
 * a caret that jumps — a distraction for a sighted reader and a lost place for
 * someone following it with a screen reader.
 *
 * ── WHAT CHANGED, AND WHY THE OLD ONE COULD NOT WORK (ADR-0006) ────────────
 *
 * The version this replaces was monotonic greedy with a six-display-token
 * lookahead and NO RE-SYNC PATH. When the recogniser's output diverged from the
 * page by more than that window — a dropped clause, a run of numerals heard as
 * words, a repetition — the display cursor could not catch up, and it never
 * recovered: every remaining observation was consumed as an unmatched
 * "hallucination" and every remaining display token was left unplaced.
 *
 * That is not a recognition limit. Measured on `fr-long-narrateur-r1.wav`, the
 * recogniser produced a FULL 1267-token transcript and the matcher stopped dead
 * at display index 545 of 1186; coverage by decile was
 * [73, 74, 77, 62, 15, 0, 0, 0, 0, 0]. The audio was fine. The matcher was not.
 * Three of six long clips failed this way, and the defect CANNOT OCCUR on an
 * eight-second clip, which is why every short-fixture measurement missed it.
 *
 * The re-sync path is `reanchor` below. Its one hard rule is that it moves the
 * display cursor FORWARD only, so §6.1's monotonicity survives a recovery.
 */
import {
  groupedDigitForm,
  normalizeToken,
  MAX_GROUPED_TOKENS,
  type Lang,
  type NormalizedToken,
} from '../normalize/index.ts';
import { type MatchEvidence } from '../normalize/contract.ts';

/** A display token with the character offsets §9.1 addresses a highlight by. */
export interface DisplayToken {
  readonly text: string;
  readonly cs: number;
  readonly ce: number;
}

/** One word from the recogniser: text, start and end seconds, its confidence. */
export interface ObservedToken {
  readonly w: string;
  readonly s: number;
  readonly e: number;
  readonly p?: number | null;
}

/**
 * Field names are snake_case because this shape crosses the process boundary to
 * `aligner/spike-a/measure.py`, which scores it. One vocabulary on both sides of
 * the bridge; renaming here to satisfy a lint rule would put a translation layer
 * between the shipped matcher and the measurement of it.
 */
export interface MatchedToken {
  readonly obs_w: string;
  readonly disp: string;
  readonly disp_idx: number;
  readonly cs: number;
  readonly ce: number;
  readonly s: number;
  readonly e: number;
  /** Placed through a spoken form rather than the display token's own fold. */
  readonly via_normalizer: boolean;
  /** Several display tokens heard as one; the span is shared, not resolved. */
  readonly shared_token?: boolean;
  /** Placed only after diacritics were removed from both sides. */
  readonly via_diacritic_fold?: boolean;
  /** The first placement after a re-sync — the token that re-acquired the page. */
  readonly after_resync?: boolean;
  readonly evidence: MatchEvidence;
}

/** One recovery: what the cursor did, and how much page it declared unspoken. */
export interface Resync {
  readonly at_observed: number;
  readonly from_display: number;
  readonly to_display: number;
  readonly skipped_display_tokens: number;
  readonly anchor: readonly string[];
}

export interface MatchResult {
  readonly matched: MatchedToken[];
  readonly unmatched: ObservedToken[];
  readonly resyncs: Resync[];
}

/**
 * How far ahead of the cursor a single observation may be placed WITHOUT a
 * re-sync. Unchanged from the version this replaces, deliberately: widening it
 * was the tempting fix and it is the wrong one. A wider window does not recover
 * from a divergence, it only raises the size of divergence needed to cause one,
 * while making every ordinary placement more likely to jump over a real display
 * token — and a jump is unrecoverable under monotonicity.
 */
export const LOOKAHEAD = 6;

/**
 * The re-sync trigger AND the re-sync anchor, which are deliberately the same
 * three tokens rather than two independently tunable numbers.
 *
 * Three consecutive observations that the window cannot place is already outside
 * anything correct audio produces: the normaliser exists precisely so that
 * numerals, abbreviations and elisions do not present as misses. A single
 * invented word is absorbed by the ordinary path and never reaches here.
 *
 * Three is also the shortest anchor worth trusting. One folded French token is
 * `de`; two are `de la`; three carry enough to identify a position on a page.
 */
export const RESYNC_ANCHOR_TOKENS = 3;

/**
 * The furthest forward a re-sync may move the display cursor, in display tokens.
 *
 * Not a tuning knob — a refusal. A recovery that jumps further than this is not
 * a matcher recovering from a local divergence, it is the matcher silently
 * declaring a large piece of the page unspoken, which is the failure the
 * coverage floor exists to make visible (§6.1 invariant 3). Beyond it the
 * matcher would rather leave the observation unmatched and let the floor fire.
 */
export const MAX_RESYNC_SKIP = 200;

// A separator no folded token can contain, written as an ESCAPE rather than a
// literal: a raw NUL byte in the source makes git treat the file as binary,
// and a matcher whose diff cannot be read is a matcher nobody reviews.
const ANCHOR_SEPARATOR = '\u0000';

/**
 * Display positions where each anchor-length run of LOOSE folds begins.
 *
 * Loose, not exact: the anchor is a SEARCH device, not a placement. An anchor
 * that insisted on diacritics would fail to fire on exactly the corpora that
 * need it most — 7.8% of the `fr` fixture's tokens disagree about accents — and
 * the placement it leads to still goes through the exact-first ladder in
 * `placeAt`, so nothing is placed loosely just because it was found loosely.
 */
function anchorIndex(display: readonly NormalizedToken[]): Map<string, number[]> {
  const index = new Map<string, number[]>();
  for (let i = 0; i + RESYNC_ANCHOR_TOKENS <= display.length; i += 1) {
    const parts: string[] = [];
    for (let k = 0; k < RESYNC_ANCHOR_TOKENS; k += 1) parts.push(display[i + k]!.loose);
    if (parts.some((p) => !p)) continue;
    const key = parts.join(ANCHOR_SEPARATOR);
    const at = index.get(key);
    if (at) at.push(i);
    else index.set(key, [i]);
  }
  return index;
}

/** First entry strictly greater than `after`, or null. Positions are ascending. */
function firstAfter(positions: readonly number[], after: number): number | null {
  let lo = 0;
  let hi = positions.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (positions[mid]! <= after) lo = mid + 1;
    else hi = mid;
  }
  return lo < positions.length ? positions[lo]! : null;
}

interface Placement {
  readonly displayIndex: number;
  readonly consumed: number;
  readonly viaNormalizer: boolean;
  readonly viaDiacriticFold: boolean;
}

/**
 * Try to place the observation at `oi` somewhere in the window `[di, di+LOOKAHEAD)`.
 *
 * The ladder, and the order matters twice:
 *
 *   POSITION dominates. The nearest display token is tried first and wins, even
 *   against a stronger form of evidence further along. The cursor is at `di`
 *   because everything before it is placed, so `di` is the strongest prior there
 *   is; a matcher that preferred a cleaner match three tokens ahead would skip
 *   real display words to get it, and monotonicity makes that permanent.
 *
 *   Within one position, EXACT beats LOOSE and LONGER beats SHORTER. Longer
 *   first because a three-token year form must be attempted before the bare
 *   digits, or `1984` consumes only "nineteen".
 */
function placeAt(
  display: readonly NormalizedToken[],
  observedFolds: readonly string[],
  observedLoose: readonly string[],
  di: number,
  oi: number,
): Placement | null {
  const end = Math.min(di + LOOKAHEAD, display.length);
  for (let j = di; j < end; j += 1) {
    const row = display[j]!;
    const order = row.forms
      .map((_, k) => k)
      .sort((a, b) => row.forms[b]!.length - row.forms[a]!.length);
    for (const k of order) {
      const seq = row.forms[k]!;
      if (seq.length === 0 || oi + seq.length > observedFolds.length) continue;
      let exact = true;
      for (let n = 0; n < seq.length; n += 1) {
        if (observedFolds[oi + n] !== seq[n]) { exact = false; break; }
      }
      if (exact) {
        return {
          displayIndex: j,
          consumed: seq.length,
          viaNormalizer: !(seq.length === 1 && seq[0] === row.fold),
          viaDiacriticFold: false,
        };
      }
    }
    for (const k of order) {
      const seq = row.looseForms[k]!;
      if (seq.length === 0 || oi + seq.length > observedLoose.length) continue;
      let loose = true;
      for (let n = 0; n < seq.length; n += 1) {
        if (observedLoose[oi + n] !== seq[n]) { loose = false; break; }
      }
      if (loose) {
        return {
          displayIndex: j,
          consumed: seq.length,
          viaNormalizer: !(seq.length === 1 && row.forms[k]![0] === row.fold),
          viaDiacriticFold: true,
        };
      }
    }
  }
  return null;
}

/**
 * THE RE-SYNC PATH.
 *
 * Called when three consecutive observations could not be placed — the signature
 * of a divergence the window cannot span. It asks one question: is there a
 * position AHEAD of the cursor where the page reads the way the recogniser is
 * currently reading?
 *
 * Forward only, and nearest-forward. Both halves are load-bearing:
 *
 *   FORWARD is §6.1 invariant 1. A backwards re-sync would fix the coverage
 *   number and produce a caret that jumps to an earlier paragraph, which is the
 *   failure monotonicity exists to prevent. If the divergence was the cursor
 *   running AHEAD of the audio, this path cannot help and will not pretend to —
 *   the observation stays unmatched and the coverage floor fires.
 *
 *   NEAREST because the page repeats itself. `MAX_RESYNC_SKIP` bounds how much
 *   page a single recovery may write off; nearest-forward makes the recovery
 *   take the smallest write-off consistent with the evidence.
 *
 * The display tokens jumped over are NOT matched and NOT counted as matched.
 * They are the words the matcher is admitting it lost, and they stay in the
 * denominator.
 */
function reanchor(
  index: Map<string, number[]>,
  observedLoose: readonly string[],
  oi: number,
  di: number,
): number | null {
  if (oi + RESYNC_ANCHOR_TOKENS > observedLoose.length) return null;
  const parts = observedLoose.slice(oi, oi + RESYNC_ANCHOR_TOKENS);
  if (parts.some((p) => !p)) return null;
  const positions = index.get(parts.join(ANCHOR_SEPARATOR));
  if (!positions) return null;
  const j = firstAfter(positions, di);
  if (j === null) return null;
  return j - di <= MAX_RESYNC_SKIP ? j : null;
}

function evidenceOf(placement: { viaNormalizer: boolean; viaDiacriticFold: boolean }): MatchEvidence {
  return placement.viaNormalizer || placement.viaDiacriticFold ? 'normalized' : 'exact';
}

/**
 * Match observed tokens onto display tokens.
 *
 * Returns the placements, the observations that could not be placed, and the
 * re-syncs. An unplaced observation is a CANDIDATE hallucination and not yet a
 * real one — `splitUnmatched` in the harness separates a word the engine
 * invented (the highlight freezes) from a word we failed to join (the highlight
 * skips), because those have opposite meanings for a reader and only the second
 * is our defect.
 */
export function matchTokens(
  display: readonly DisplayToken[],
  observed: readonly ObservedToken[],
  lang: Lang,
): MatchResult {
  const displayNorm = display.map((d) => normalizeToken(d.text, lang));

  // Observations that fold to nothing are punctuation the recogniser emitted as
  // a token. They are dropped BEFORE matching, exactly as the version this
  // replaces did, so they can neither be placed nor charged as hallucinations.
  const kept: ObservedToken[] = [];
  const obsFold: string[] = [];
  const obsLoose: string[] = [];
  const obsDigits: string[] = [];
  for (const o of observed) {
    const n = normalizeToken(o.w, lang);
    if (!n.fold) continue;
    kept.push(o);
    obsFold.push(n.fold);
    obsLoose.push(n.loose);
    obsDigits.push(n.digits);
  }

  // MANY-TO-ONE, precomputed. French writes a thousands separator as a SPACE, so
  // `1 250` is two display tokens and one observation. The rule that a RUN of
  // display tokens is heard as one belongs to the normaliser, not here.
  const grouped: Map<string, string> = new Map();
  for (let i = 0; i < display.length; i += 1) {
    for (let span = 2; span <= MAX_GROUPED_TOKENS; span += 1) {
      if (i + span > display.length) break;
      const form = groupedDigitForm(display.slice(i, i + span).map((d) => d.text));
      if (form !== null) grouped.set(`${i}:${span}`, form);
    }
  }

  const index = anchorIndex(displayNorm);
  const matched: MatchedToken[] = [];
  const unmatched: ObservedToken[] = [];
  const resyncs: Resync[] = [];

  let di = 0;
  let oi = 0;
  // Consecutive unplaced observations, held rather than retired. Holding them is
  // what lets a re-sync re-examine the tokens that SIGNALLED the divergence: the
  // first miss is the best anchor there is, and a matcher that had already
  // charged it as a hallucination would have to anchor on later, worse evidence.
  let pending: ObservedToken[] = [];
  let pendingStart = 0;
  let justResynced = false;

  while (oi < kept.length && di < display.length) {
    const placement = placeAt(displayNorm, obsFold, obsLoose, di, oi);
    if (placement) {
      const j = placement.displayIndex;
      matched.push({
        obs_w: kept.slice(oi, oi + placement.consumed).map((o) => o.w).join(' '),
        disp: display[j]!.text,
        disp_idx: j,
        cs: display[j]!.cs,
        ce: display[j]!.ce,
        s: kept[oi]!.s,
        e: kept[oi + placement.consumed - 1]!.e,
        via_normalizer: placement.viaNormalizer,
        ...(placement.viaDiacriticFold ? { via_diacritic_fold: true } : {}),
        ...(justResynced ? { after_resync: true } : {}),
        evidence: evidenceOf(placement),
      });
      oi += placement.consumed;
      di = j + 1;
      justResynced = false;
      for (const p of pending) unmatched.push(p);
      pending = [];
      continue;
    }

    let placedGroup = false;
    for (let span = MAX_GROUPED_TOKENS; span >= 2; span -= 1) {
      if (di + span > display.length) continue;
      const joined = grouped.get(`${di}:${span}`);
      if (!joined || !obsDigits[oi] || joined !== obsDigits[oi]) continue;
      for (let k = 0; k < span; k += 1) {
        matched.push({
          obs_w: kept[oi]!.w,
          disp: display[di + k]!.text,
          disp_idx: di + k,
          cs: display[di + k]!.cs,
          ce: display[di + k]!.ce,
          s: kept[oi]!.s,
          e: kept[oi]!.e,
          shared_token: true,
          via_normalizer: true,
          ...(justResynced ? { after_resync: true } : {}),
          evidence: 'shared_token',
        });
      }
      oi += 1;
      di += span;
      placedGroup = true;
      break;
    }
    if (placedGroup) {
      justResynced = false;
      for (const p of pending) unmatched.push(p);
      pending = [];
      continue;
    }

    if (pending.length === 0) pendingStart = oi;
    pending.push(kept[oi]!);
    oi += 1;

    while (pending.length >= RESYNC_ANCHOR_TOKENS) {
      const to = reanchor(index, obsLoose, pendingStart, di);
      if (to !== null) {
        resyncs.push({
          at_observed: pendingStart,
          from_display: di,
          to_display: to,
          skipped_display_tokens: to - di,
          anchor: obsLoose.slice(pendingStart, pendingStart + RESYNC_ANCHOR_TOKENS),
        });
        di = to;
        oi = pendingStart;
        pending = [];
        justResynced = true;
        break;
      }
      // No anchor at this position. Retire the oldest held observation and try
      // again one token later, so every position gets an attempt and the loop
      // cannot spin: `pendingStart` strictly increases and `oi` never moves back
      // past it.
      unmatched.push(pending.shift()!);
      pendingStart += 1;
    }
  }

  for (const p of pending) unmatched.push(p);
  for (let i = oi; i < kept.length; i += 1) unmatched.push(kept[i]!);
  return { matched, unmatched, resyncs };
}
