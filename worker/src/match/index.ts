/**
 * The matcher, as the rest of the worker sees it.
 *
 * §6.1's invariants live in `../normalize/contract.ts` and are re-exported here
 * so a caller that produces a highlight map and a caller that refuses to emit an
 * invalid one reach for the same names.
 */
export {
  matchTokens,
  LOOKAHEAD,
  MAX_RESYNC_SKIP,
  RESYNC_ANCHOR_TOKENS,
  type DisplayToken,
  type MatchResult,
  type MatchedToken,
  type ObservedToken,
  type Resync,
} from './match.ts';
export { matchRequest, type MatchRequest, type MatchResponse } from './cli.ts';
export {
  DRIFT_BOUND_MS,
  COVERAGE_FLOOR_PCT,
  checkMatchContract,
  checkMonotonic,
  coveragePct,
  localDriftMs,
  type MatchEvidence,
  type Violation,
} from '../normalize/contract.ts';
