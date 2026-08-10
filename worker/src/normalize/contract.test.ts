import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  COVERAGE_FLOOR_PCT,
  DRIFT_BOUND_MS,
  checkConfidenceFields,
  checkCoverageFloor,
  checkDriftBound,
  checkMatchContract,
  checkMonotonic,
  confidences,
  coveragePct,
  localDriftMs,
  type MatchedToken,
} from './contract.ts';

const tok = (displayIndex: number, cs: number, ce: number, start: number): MatchedToken => ({
  displayIndex, cs, ce, start, end: start + 0.2,
});

describe('the bound and the floor are constants, not call-site arguments', () => {
  it('fixes the drift bound at the number set before SPIKE A ran', () => {
    // H17-C3. The pass bar is a share of words inside this bound, so whoever
    // moves the bound moves the pass rate.
    assert.equal(DRIFT_BOUND_MS, 250);
  });

  it('takes the coverage floor from the roadmap bar rather than inventing one', () => {
    assert.equal(COVERAGE_FLOOR_PCT, 95);
  });
});

describe('invariant 1 — monotonicity', () => {
  it('accepts non-decreasing display offsets', () => {
    assert.deepEqual(checkMonotonic([tok(0, 0, 2, 0), tok(1, 3, 5, 0.3), tok(2, 6, 10, 0.6)]), []);
  });

  it('accepts a repeated offset, which is the many-to-one case', () => {
    assert.deepEqual(checkMonotonic([tok(0, 0, 1, 0), tok(1, 0, 1, 0)]), []);
  });

  it('REPORTS a highlight that jumps backwards', () => {
    // A book contains "the" four thousand times; an unconstrained fuzzy match
    // sends the caret to the wrong one and a reader loses their place.
    const v = checkMonotonic([tok(0, 40, 43, 0), tok(1, 4, 7, 0.3)]);
    assert.equal(v.length, 1);
    assert.equal(v[0]?.invariant, 'monotonicity');
    assert.match(v[0]?.detail ?? '', /backwards/);
  });
});

describe('invariant 2 — the 250 ms drift bound', () => {
  it('measures displacement against NEIGHBOURS, not a global fit', () => {
    // Evenly spaced characters and time: the middle token is where its
    // neighbours imply, so drift is zero.
    const d = localDriftMs(tok(0, 0, 3, 0), tok(1, 10, 13, 1), tok(2, 20, 23, 2));
    assert.equal(d, 0);
  });

  it('returns null where there is no two-sided neighbourhood to measure', () => {
    assert.equal(localDriftMs(tok(0, 0, 3, 0), tok(1, 10, 13, 1), tok(2, 0, 3, 2)), null);
    assert.equal(localDriftMs(tok(0, 0, 3, 1), tok(1, 10, 13, 1), tok(2, 20, 23, 1)), null);
  });

  it('accepts a token inside the bound', () => {
    // Predicted 1.000 s, observed 1.200 s → 200 ms, under 250.
    assert.deepEqual(checkDriftBound([tok(0, 0, 3, 0), tok(1, 10, 13, 1.2), tok(2, 20, 23, 2)]), []);
  });

  it('REPORTS a token outside it', () => {
    // Predicted 1.000 s, observed 1.400 s → 400 ms.
    const v = checkDriftBound([tok(0, 0, 3, 0), tok(1, 10, 13, 1.4), tok(2, 20, 23, 2)]);
    assert.equal(v.length, 1);
    assert.equal(v[0]?.invariant, 'drift_bound');
    assert.match(v[0]?.detail ?? '', /250 ms bound/);
  });

  it('leaves the endpoints unmeasured rather than crediting them', () => {
    // J22-M4: adding the first and last matched token to the numerator as
    // though measured is a free pass, always in the permissive direction.
    const v = checkDriftBound([tok(0, 0, 3, 0), tok(1, 10, 13, 9), tok(2, 20, 23, 2)]);
    assert.equal(v.length, 1, 'only the interior token is judged');
  });
});

describe('invariant 3 — the coverage floor', () => {
  it('counts display CHARACTERS, not tokens', () => {
    // Two short tokens placed out of ten characters is 20% coverage, however
    // many tokens that is.
    assert.equal(coveragePct([tok(0, 0, 1, 0), tok(1, 2, 3, 1)], 10), 20);
  });

  it('does not count a shared span twice', () => {
    assert.equal(coveragePct([tok(0, 0, 5, 0), tok(0, 0, 5, 0)], 10), 50);
  });

  it('REPORTS a segment below the floor and says it is degraded', () => {
    const v = checkCoverageFloor([tok(0, 0, 5, 0)], 100);
    assert.equal(v.length, 1);
    assert.match(v[0]?.detail ?? '', /degraded/);
  });

  it('accepts a segment at the floor', () => {
    assert.deepEqual(checkCoverageFloor([tok(0, 0, 95, 0)], 100), []);
  });

  it('reports zero coverage for an empty segment instead of dividing by zero', () => {
    assert.equal(coveragePct([], 0), 0);
  });
});

describe('invariant 4 — two confidences, two fields', () => {
  it('derives match_conf from the match evidence and never from asr_conf', () => {
    const exact = confidences('exact', 0.4);
    const normalized = confidences('normalized', 0.99);
    assert.equal(exact.asr_conf, 0.4);
    assert.equal(exact.match_conf, 1);
    assert.equal(normalized.match_conf, 0.8);
    assert.ok(
      exact.match_conf > normalized.match_conf,
      'a confidently recognised token can still be the less confidently PLACED one',
    );
  });

  it('grades a shared span lowest, because it is not resolved', () => {
    assert.ok(confidences('shared_token', 0.9).match_conf < confidences('normalized', 0.1).match_conf);
  });

  it('REPORTS the two fields collapsed into one quantity', () => {
    const rows = [{ asr_conf: 0.9, match_conf: 0.9 }, { asr_conf: 0.4, match_conf: 0.4 }];
    const v = checkConfidenceFields(rows);
    assert.equal(v.length, 1);
    assert.match(v[0]?.detail ?? '', /one\s+quantity written twice/);
  });

  it('accepts a transcriber that reports no confidence at all', () => {
    assert.deepEqual(checkConfidenceFields([
      { asr_conf: null, match_conf: 1 }, { asr_conf: null, match_conf: 0.8 },
    ]), []);
  });
});

describe('checkMatchContract', () => {
  it('is clean on a well-formed segment', () => {
    assert.deepEqual(checkMatchContract({
      matches: [tok(0, 0, 3, 0), tok(1, 10, 13, 1), tok(2, 20, 23, 2)],
      // Nine matched characters over a nine-character segment. Coverage is
      // measured over the CHARACTERS OF DISPLAY TOKENS, not the span between
      // the first and last, so the whitespace between them is not unmatched.
      displayCharacters: 9,
      confidences: [confidences('exact', 0.9), confidences('normalized', 0.9)],
    }), []);
  });

  it('reports every invariant a broken segment violates, not the first', () => {
    const v = checkMatchContract({
      matches: [tok(0, 20, 23, 0), tok(1, 10, 13, 1.9), tok(2, 30, 33, 2)],
      displayCharacters: 1000,
      confidences: [{ asr_conf: 0.5, match_conf: 0.5 }, { asr_conf: 0.6, match_conf: 0.6 }],
    });
    const kinds = new Set(v.map((x) => x.invariant));
    assert.ok(kinds.has('monotonicity'));
    assert.ok(kinds.has('drift_bound'));
    assert.ok(kinds.has('coverage_floor'));
    assert.ok(kinds.has('confidence_fields'));
  });
});
