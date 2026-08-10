/**
 * The delegation bridge for the matcher — one JSON request in, one out.
 *
 * The same argument `normalize/cli.ts` carries, for the component it is now more
 * true of: `aligner/spike-a/measure.py` is Python and the product path is
 * TypeScript, so without this there are TWO matchers and the number SPIKE A
 * publishes describes software nobody runs. The normaliser was moved for that
 * reason and the matcher was left behind — which is how a re-sync defect could
 * be diagnosed in a comment in the instrument while the product had no matcher
 * at all to diagnose.
 *
 * One process per clip, not one per token. It reads stdin to EOF and writes one
 * line of JSON. There is NO fallback: an unparseable request or an unsupported
 * language exits non-zero and the caller raises. A matcher that silently
 * degraded to "match nothing" would report a plausible, wrong coverage.
 */
// `foldToken` is imported rather than reimplemented so the fold the caller
// checks itself against is the SAME function the matcher compared with — a
// second copy here would make the alarm agree with the wrong bell.
import { foldToken, isLang, type Lang } from '../normalize/index.ts';
import { matchTokens, type DisplayToken, type MatchResult, type ObservedToken } from './match.ts';

export interface MatchRequest {
  readonly lang: string;
  /** Display tokens in page order, as `[text, cs, ce]`. */
  readonly display: readonly (readonly [string, number, number])[];
  /** Observed tokens in time order. */
  readonly observed: readonly ObservedToken[];
}

export interface MatchResponse extends MatchResult {
  readonly lang: Lang;
  /**
   * The folds this run used, so the caller can assert that ITS idea of a fold
   * and the product's agree. `measure.py` keeps a Python `norm()` because
   * `harness.py` and `groundtruth.py` fold arbitrary tokens with it; without
   * this, that copy is a second source of truth with no alarm on it.
   */
  readonly folds: {
    readonly display: string[];
    readonly observed: string[];
  };
}

export function matchRequest(request: MatchRequest): MatchResponse {
  const { lang } = request;
  if (!isLang(lang)) {
    throw new Error(
      `unsupported language ${JSON.stringify(lang)}. The supported set is en, es, fr; ` +
        `§3.5 refuses anything else at the no-route row before synthesis.`,
    );
  }
  if (!Array.isArray(request.display) || !Array.isArray(request.observed)) {
    throw new Error('request.display and request.observed must both be arrays');
  }
  const display: DisplayToken[] = request.display.map((row, i) => {
    if (!Array.isArray(row) || row.length !== 3 || typeof row[0] !== 'string'
      || typeof row[1] !== 'number' || typeof row[2] !== 'number') {
      throw new Error(`request.display[${i}] must be [text, cs, ce]`);
    }
    return { text: row[0], cs: row[1], ce: row[2] };
  });
  const observed: ObservedToken[] = request.observed.map((o, i) => {
    if (!o || typeof o.w !== 'string' || typeof o.s !== 'number' || typeof o.e !== 'number') {
      throw new Error(`request.observed[${i}] must carry w, s and e`);
    }
    return o;
  });

  const result = matchTokens(display, observed, lang);
  return {
    ...result,
    lang,
    folds: {
      display: display.map((d) => foldToken(d.text)),
      observed: observed.map((o) => foldToken(o.w)),
    },
  };
}

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(chunk as Buffer);
  return Buffer.concat(chunks).toString('utf8');
}

export async function main(): Promise<void> {
  const raw = await readStdin();
  let request: MatchRequest;
  try {
    request = JSON.parse(raw) as MatchRequest;
  } catch (error) {
    throw new Error(`stdin is not JSON: ${(error as Error).message}`);
  }
  process.stdout.write(`${JSON.stringify(matchRequest(request))}\n`);
}

if (process.argv[1] && import.meta.filename === process.argv[1]) {
  main().catch((error: unknown) => {
    process.stderr.write(`match: ${(error as Error).message}\n`);
    process.exitCode = 1;
  });
}
