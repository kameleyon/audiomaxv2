/**
 * The delegation bridge — one JSON request in, one JSON response out.
 *
 * `aligner/spike-a/measure.py` is Python and the product path is TypeScript, so
 * without this there are TWO normalisers and the measured behaviour is not the
 * shipped behaviour. That is the defect class this repository has recorded
 * repeatedly: a repair lands in one of two implementations of the same idea.
 *
 * One process per language per run, not one per token — the harness sends every
 * display and observed token in a single request. The cost is a process spawn;
 * the benefit is that there is no second copy of the tables to drift.
 *
 * It reads stdin to EOF and writes one line of JSON. It has no fallback: an
 * unparseable request or an unsupported language exits non-zero with a message
 * on stderr, and the caller raises. A normaliser that silently degrades to
 * identity would return a plausible, wrong match rate.
 */
import { isLang, normalizeToken, type Lang, type NormalizedToken } from './index.ts';
import { COVERAGE_FLOOR_PCT, DRIFT_BOUND_MS } from './contract.ts';
import { MAX_GROUPED_TOKENS, groupedDigitForm } from './index.ts';

export interface NormalizeRequest {
  readonly lang: string;
  /** Display tokens, in page order. */
  readonly display: readonly string[];
  /** Observed tokens from the transcriber, in time order. */
  readonly observed?: readonly string[];
}

export interface NormalizeResponse {
  readonly lang: Lang;
  readonly display: NormalizedToken[];
  readonly observed: NormalizedToken[];
  /**
   * For each display index, the grouped digit form of the run starting there,
   * keyed by run length. The harness cannot compute this itself without owning
   * a second copy of the rule.
   */
  readonly grouped: Record<string, Record<string, string>>;
  readonly contract: {
    readonly drift_bound_ms: number;
    readonly coverage_floor_pct: number;
    readonly max_grouped_tokens: number;
  };
}

export function normalizeRequest(request: NormalizeRequest): NormalizeResponse {
  const { lang } = request;
  if (!isLang(lang)) {
    throw new Error(
      `unsupported language ${JSON.stringify(lang)}. The supported set is en, es, fr; ` +
        `§3.5 refuses anything else at the no-route row before synthesis, so a token in ` +
        `another language should never reach the normaliser.`,
    );
  }
  if (!Array.isArray(request.display)) {
    throw new Error('request.display must be an array of display tokens');
  }
  const display = request.display.map((t) => normalizeToken(t, lang));
  const observed = (request.observed ?? []).map((t) => normalizeToken(t, lang));

  const grouped: Record<string, Record<string, string>> = {};
  for (let i = 0; i < request.display.length; i += 1) {
    for (let span = 2; span <= MAX_GROUPED_TOKENS; span += 1) {
      if (i + span > request.display.length) break;
      const form = groupedDigitForm(request.display.slice(i, i + span));
      if (form === null) continue;
      (grouped[String(i)] ??= {})[String(span)] = form;
    }
  }

  return {
    lang,
    display,
    observed,
    grouped,
    contract: {
      drift_bound_ms: DRIFT_BOUND_MS,
      coverage_floor_pct: COVERAGE_FLOOR_PCT,
      max_grouped_tokens: MAX_GROUPED_TOKENS,
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
  let request: NormalizeRequest;
  try {
    request = JSON.parse(raw) as NormalizeRequest;
  } catch (error) {
    throw new Error(`stdin is not JSON: ${(error as Error).message}`);
  }
  process.stdout.write(`${JSON.stringify(normalizeRequest(request))}\n`);
}

// `import.meta.filename` is the resolved path on both platforms this repository
// is developed and shipped on; comparing hand-built file:// URLs is false on one
// of them (the same trap `index.ts` documents).
if (process.argv[1] && import.meta.filename === process.argv[1]) {
  main().catch((error: unknown) => {
    process.stderr.write(`normalize: ${(error as Error).message}\n`);
    process.exitCode = 1;
  });
}
