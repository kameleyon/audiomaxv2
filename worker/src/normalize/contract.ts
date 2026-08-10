/**
 * The match contract — spec §6.1's four invariants, executable.
 *
 * "All four are load-bearing; a violation is a defect, not a quality signal."
 * They were prose in the spec and arithmetic scattered through a measurement
 * script; a violation could therefore only be noticed by someone reading a JSON
 * file. Here each one is a function that returns the violations, so the matcher
 * can refuse to emit a highlight map that breaks one.
 *
 *   1. MONOTONICITY over display offsets.
 *   2. A DRIFT BOUND of 250 ms, fixed before SPIKE A ran (H17-C3).
 *   3. A COVERAGE FLOOR, below which the segment is `degraded`.
 *   4. TWO CONFIDENCES, TWO FIELDS — `asr_conf` and `match_conf`.
 */

/**
 * §6.1 invariant 2. Fixed at 250 ms BEFORE SPIKE A ran and not tunable from
 * here: the pass bar is expressed as a share of words inside this bound, so
 * whoever moves the bound moves the pass rate. Moving it is a public act with a
 * recorded reason, which means editing this constant and saying why — not
 * passing a different value at a call site.
 */
export const DRIFT_BOUND_MS = 250;

/**
 * §6.1 invariant 3. The spec leaves the NUMBER open ("how many display
 * characters may go unmatched"); this is the roadmap's SPIKE A pass bar,
 * `matched_within_drift_pct >= 95`, applied to coverage. It is that figure
 * reused, not a new bar invented here — if the roadmap moves its bar this
 * constant moves with it.
 */
export const COVERAGE_FLOOR_PCT = 95;

export interface MatchedToken {
  /** Index into the display token list. */
  readonly displayIndex: number;
  /** §9.1 character start of the display token. */
  readonly cs: number;
  /** §9.1 character end of the display token. */
  readonly ce: number;
  /** Observed start time, seconds. */
  readonly start: number;
  /** Observed end time, seconds. */
  readonly end: number;
}

export interface Violation {
  readonly invariant: 'monotonicity' | 'drift_bound' | 'coverage_floor' | 'confidence_fields';
  readonly detail: string;
  readonly at?: number;
}

/**
 * Invariant 1 — matched display offsets are non-decreasing.
 *
 * A book contains "the" four thousand times. Without this an unconstrained fuzzy
 * match produces a highlight that jumps backwards, which for a sighted reader is
 * a distraction and for a screen-reader user following the caret is a lost
 * place. Checked on the OFFSET, not the index, because two matches may share an
 * index (the many-to-one case) and that is not a regression.
 */
export function checkMonotonic(matches: readonly MatchedToken[]): Violation[] {
  const out: Violation[] = [];
  for (let i = 1; i < matches.length; i += 1) {
    const prev = matches[i - 1];
    const cur = matches[i];
    if (!prev || !cur) continue;
    if (cur.cs < prev.cs) {
      out.push({
        invariant: 'monotonicity',
        at: i,
        detail: `display offset moved backwards: ${prev.cs} → ${cur.cs}`,
      });
    }
  }
  return out;
}

/**
 * LOCAL drift, per §6.1: "displacement between a matched token's timestamp and
 * the position implied by ITS NEIGHBOURS."
 *
 * Neighbours, not a global fit. A global character→time model over a whole clip
 * reports a sentence-boundary pause as drift, which measures prosody and calls
 * it misalignment. Returns null for a token with no two-sided neighbourhood —
 * the first and last matched token are UNMEASURED, and counting them as passing
 * is a free pass always in the permissive direction (J22-M4).
 */
export function localDriftMs(
  prev: MatchedToken,
  cur: MatchedToken,
  next: MatchedToken,
): number | null {
  const spanChars = next.cs - prev.cs;
  const spanSeconds = next.start - prev.start;
  if (spanChars <= 0 || spanSeconds <= 0) return null;
  const predicted = prev.start + spanSeconds * ((cur.cs - prev.cs) / spanChars);
  return Math.abs(cur.start - predicted) * 1000;
}

/** Invariant 2 — every measurable token sits inside the bound. */
export function checkDriftBound(
  matches: readonly MatchedToken[],
  boundMs: number = DRIFT_BOUND_MS,
): Violation[] {
  const out: Violation[] = [];
  for (let i = 1; i < matches.length - 1; i += 1) {
    const prev = matches[i - 1];
    const cur = matches[i];
    const next = matches[i + 1];
    if (!prev || !cur || !next) continue;
    const drift = localDriftMs(prev, cur, next);
    if (drift === null) continue;
    if (drift > boundMs) {
      out.push({
        invariant: 'drift_bound',
        at: i,
        detail: `local drift ${drift.toFixed(1)} ms exceeds the ${boundMs} ms bound`,
      });
    }
  }
  return out;
}

/**
 * Invariant 3 — coverage is measured in display CHARACTERS, not tokens.
 *
 * §6.1 says characters, and the two differ in the direction that matters: a
 * matcher that places every short function word and drops the long content words
 * scores well on tokens and leaves most of the page unhighlighted.
 */
export function coveragePct(matches: readonly MatchedToken[], displayCharacters: number): number {
  if (displayCharacters <= 0) return 0;
  // Distinct spans, so a many-to-one match cannot count a character twice.
  const seen = new Set<string>();
  let covered = 0;
  for (const m of matches) {
    const key = `${m.cs}:${m.ce}`;
    if (seen.has(key)) continue;
    seen.add(key);
    covered += Math.max(0, m.ce - m.cs);
  }
  return (100 * Math.min(covered, displayCharacters)) / displayCharacters;
}

export function checkCoverageFloor(
  matches: readonly MatchedToken[],
  displayCharacters: number,
  floorPct: number = COVERAGE_FLOOR_PCT,
): Violation[] {
  const pct = coveragePct(matches, displayCharacters);
  if (pct >= floorPct) return [];
  return [{
    invariant: 'coverage_floor',
    detail: `coverage ${pct.toFixed(1)}% is below the ${floorPct}% floor; the segment is degraded ` +
      `and must say so — silence here is how "mostly worked" becomes "shipped"`,
  }];
}

/**
 * Invariant 4 — TWO confidences, TWO fields.
 *
 * `asr_conf` is the recogniser's confidence that it heard the token it emitted.
 * `match_conf` is OUR confidence that the token belongs to the display word we
 * attached it to. They are independent: a perfectly recognised "the" can be
 * attached to the wrong one of four thousand, and a token the recogniser was
 * unsure of can be placed unambiguously because it is the only numeral in the
 * neighbourhood. Collapsing them into one number reports the smaller problem.
 *
 * `match_conf` is therefore derived from the MATCH EVIDENCE and never reads
 * `asr_conf`.
 */
export type MatchEvidence =
  /** The folded display token and the folded observation are identical. */
  | 'exact'
  /** Placed through a spoken form — a numeral expansion or an abbreviation. */
  | 'normalized'
  /** Several display tokens heard as one; the span is shared, not resolved. */
  | 'shared_token';

export interface Confidences {
  readonly asr_conf: number | null;
  readonly match_conf: number;
}

const MATCH_CONF: Readonly<Record<MatchEvidence, number>> = {
  exact: 1,
  normalized: 0.8,
  shared_token: 0.5,
};

export function confidences(evidence: MatchEvidence, asrConf: number | null): Confidences {
  return { asr_conf: asrConf, match_conf: MATCH_CONF[evidence] };
}

/**
 * The check that the two fields have not been quietly collapsed into one. A
 * payload where `match_conf` is always exactly `asr_conf` is a payload with one
 * confidence wearing two names, which is what J15-C5/J16-C1 deleted a field for.
 */
export function checkConfidenceFields(rows: readonly Confidences[]): Violation[] {
  if (rows.length < 2) return [];
  const someAsr = rows.some((r) => r.asr_conf !== null);
  const allEqual = rows.every((r) => r.asr_conf !== null && r.asr_conf === r.match_conf);
  if (someAsr && allEqual) {
    return [{
      invariant: 'confidence_fields',
      detail: 'match_conf equals asr_conf on every row: the two fields §6.1 requires are one ' +
        'quantity written twice, and a wrong match with a confident recogniser is invisible',
    }];
  }
  return [];
}

/** Every invariant, in one call, for a caller that must not emit on violation. */
export function checkMatchContract(input: {
  readonly matches: readonly MatchedToken[];
  readonly displayCharacters: number;
  readonly confidences?: readonly Confidences[];
  readonly driftBoundMs?: number;
  readonly coverageFloorPct?: number;
}): Violation[] {
  return [
    ...checkMonotonic(input.matches),
    ...checkDriftBound(input.matches, input.driftBoundMs ?? DRIFT_BOUND_MS),
    ...checkCoverageFloor(
      input.matches,
      input.displayCharacters,
      input.coverageFloorPct ?? COVERAGE_FLOOR_PCT,
    ),
    ...checkConfidenceFields(input.confidences ?? []),
  ];
}
