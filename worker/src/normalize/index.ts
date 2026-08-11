/**
 * The spoken-form normaliser — the product path.
 *
 * WHERE THIS CAME FROM, AND WHY IT MOVED. This logic was written inside
 * `aligner/spike-a/measure.py` as four module-level fixture tables (`NUM`,
 * `TENS`, `ABBREV`, `spoken_forms`). It is what took SPIKE A's match rate from
 * 91.7% to 100%, so it is not a measurement detail — it is the thing that makes
 * word sync work, and Jury and Halo both said repeatedly that a harness hack is
 * not the product. A normaliser that exists only in the instrument means the
 * shipped matcher is a DIFFERENT matcher from the measured one, and every figure
 * on disk describes software nobody runs.
 *
 * The harness now delegates here (`cli.ts`), so the number SPIKE A reports and
 * the behaviour the worker ships are the same code. There is no Python copy left
 * to drift, and no fallback to one: if this module cannot be reached, the harness
 * raises. CLAUDE.md constraint 2 applies to instruments as much as to providers.
 *
 * WHAT IT DOES NOT DO. It does not decide what the provider said. It enumerates
 * the forms a display token MIGHT have been spoken as, and the matcher accepts
 * whichever was actually transcribed. Enumerating a form costs a candidate;
 * asserting one would be prediction, which §6.1 removed.
 */
import { abbreviationForms } from './abbreviations.ts';
import { orthographyForms } from './orthography.ts';
import { digitRuns, digitsOf, wholeNumberWord, yearForm, type Lang } from './numerals.ts';

export { LANGS, isLang, digitsOf, digitRuns, type Lang } from './numerals.ts';
export { ABBREVIATIONS, abbreviationForms } from './abbreviations.ts';
export { orthographyForms, ORTHOGRAPHY_VARIANT_COUNT } from './orthography.ts';

/**
 * Fold a token to its comparable form: NFC, lowercase, punctuation removed.
 *
 * The apostrophe survives because it is INSIDE words in all three supported
 * languages — `l'eau`, `don't`, `d'accord` — and stripping it merges tokens a
 * reader sees as distinct.
 *
 * NFC first, then lowercase, then strip: composing before casing keeps `É` and
 * `E`+combining-acute folding to the same string, which is not true if the
 * combining mark is stripped as punctuation first.
 */
export function foldToken(token: string): string {
  return token.normalize('NFC').toLowerCase().replace(/[^\p{L}\p{N}_']/gu, '');
}

/**
 * The SECOND fold — the same token with its diacritics removed.
 *
 * This is NOT a replacement for `foldToken` and the matcher must never reach for
 * it first. It exists because the two sides of the comparison disagree about
 * accents for reasons that have nothing to do with what was said:
 *
 *   - the recogniser restores accents imperfectly, in both directions, and
 *     writes `eleve` for `élève` often enough to be measured;
 *   - extracted document text loses them — a PDF with a subset font, a scan run
 *     through OCR, text pasted out of a system that never had them.
 *
 * Measured on SPIKE A's `fr` long fixture: 92 of 1186 display tokens (7.8%) were
 * spoken correctly, recognised correctly, and dropped by the matcher because one
 * side spelled `bibliotheque` and the other `bibliothèque`. A dropped token is a
 * SKIPPED word for a reader following the caret.
 *
 * The cost is real and is why this is ranked below the exact fold rather than
 * folded into it: `ou`/`où`, `sur`/`sûr`, `des`/`dès` in French and `ano`/`año`
 * in Spanish are different words that collapse here. The matcher therefore tries
 * the exact fold at every candidate position first and only then this one, and
 * records the relaxation on the match so a caller can see it (`match_conf` drops
 * to the `normalized` band, never `exact`).
 */
export function foldTokenLoose(token: string): string {
  return foldToken(token).normalize('NFD').replace(/\p{Mn}/gu, '').normalize('NFC');
}

/**
 * ELISION. `l'équipe` is ONE token on the page and TWO in the transcript.
 *
 * Word-level ASR tokenisers split French elision at the apostrophe and attach
 * the apostrophe to the SECOND half — faster-whisper emits `l` then `'équipe`,
 * `aujourd` then `'hui`, `d` then `'être`. The display token matches neither
 * half, so the whole word is unplaceable: 59 of 1186 display tokens (5.0%) on
 * SPIKE A's `fr` long fixture, and they are not evenly spread — `l'`, `d'`,
 * `qu'`, `n'`, `c'` are the most frequent openings in written French.
 *
 * Both splits are offered because the convention is not universal: some engines
 * write `l'` + `équipe`. Offering a form costs a candidate; asserting one would
 * be prediction, which §6.1 removed.
 *
 * Split at the FIRST interior apostrophe only. `c'est-à-dire` has two and is a
 * single display token whose fold has already lost its hyphens; enumerating
 * every partition of it would produce candidates no engine emits.
 */
export function elisionForms(folded: string): string[][] {
  const at = folded.indexOf("'");
  if (at <= 0 || at >= folded.length - 1) return [];
  const head = folded.slice(0, at);
  const tail = folded.slice(at + 1);
  return [
    [head, `'${tail}`],
    [`${head}'`, tail],
  ];
}

/** Display tokens with the character offsets a highlight is addressed by. */
export interface DisplayToken {
  readonly text: string;
  /** `cs` in §9.1 — inclusive character start. */
  readonly cs: number;
  /** `ce` in §9.1 — exclusive character end. */
  readonly ce: number;
}

export function displayTokens(text: string): DisplayToken[] {
  const out: DisplayToken[] = [];
  for (const m of text.matchAll(/\S+/gu)) {
    out.push({ text: m[0], cs: m.index, ce: m.index + m[0].length });
  }
  return out;
}

/**
 * Every token SEQUENCE one display token might have been spoken as, folded.
 *
 * A sequence, not a token, because expansion is one-to-MANY: `1984` is three
 * spoken tokens. The inverse — many display tokens heard as one — is
 * `groupedDigitForms` below, and the two together are what let a matcher place
 * every word of a European-formatted number.
 *
 * Order is significant to the caller, which tries longer sequences first: a
 * three-token year form must be attempted before the bare-digit form, or `1984`
 * consumes only "nineteen" and the remaining two tokens become unmatched
 * observations — counted, before this existed, as engine hallucinations.
 */
export function spokenForms(displayToken: string, lang: Lang): string[][] {
  const folded = foldToken(displayToken);
  if (!folded) return [];

  const forms: string[][] = [[folded]];
  const digits = digitsOf(displayToken);
  if (digits) {
    // Heard as its digits — the engine read them back rather than expanding.
    forms.push([digits]);
    // `Number` rather than `parseInt`: a 17-digit page number is not a number
    // we can expand, and Number's precision loss on such input is caught by the
    // range test in `yearForm` and by `wholeNumberWord` missing the key.
    const n = Number(digits);
    const whole = wholeNumberWord(n, lang);
    if (whole !== null) forms.push([whole]);
    const year = yearForm(n, lang);
    if (year !== null) forms.push(year);
    // Grouped digits read as their groups: `1,250` → "1" "250".
    const runs = digitRuns(displayToken);
    if (runs.length) forms.push(runs);
  }
  for (const expansion of abbreviationForms(folded, lang)) forms.push([expansion]);
  // The SAME word spelled the other way. Measured: 14 of the 25 display tokens
  // absent from the English chapter transcript were British spellings the
  // recogniser wrote in American form (`spike-a-english.json`,
  // `clips[].orthography_probe`). A one-token alternative, so it does not
  // disturb the longest-first order the caller depends on.
  for (const spelling of orthographyForms(folded, lang)) forms.push([spelling]);
  for (const split of elisionForms(folded)) forms.push(split);

  // De-duplicated: `elisionForms` and an abbreviation expansion can arrive at the
  // same sequence, and a repeated candidate makes the matcher do the same work
  // twice and a reader of `forms` believe there is more evidence than there is.
  const seen = new Set<string>();
  const out: string[][] = [];
  for (const seq of forms) {
    // `foldToken` is applied to each element rather than to the sequence: an
    // elision half is already folded, and folding it again is a no-op, but a
    // numeral expansion arrives as a word and is not.
    const cleaned = seq.map(foldToken).filter(Boolean);
    if (cleaned.length === 0) continue;
    const key = cleaned.join('\u0000');
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(cleaned);
  }
  return out;
}

/**
 * MANY-TO-ONE. The inverse case, and the one that kept `fr` below the bar.
 *
 * French — and most of continental Europe — writes a thousands separator as a
 * SPACE. `1 250` is TWO display tokens on the page and ONE token in the audio,
 * "1250". Without this the display side can never be fully placed, `fr` sits
 * permanently below the coverage floor for a typographic convention, and the
 * unplaced observation is charged to the engine as an invention.
 *
 * Returns the folded digit string a RUN of display tokens would be heard as,
 * or null when the run is not a digit group. EVERY token in the run must carry
 * at least one digit. The harness's original form concatenated the digits of
 * whatever tokens it was handed, so a run of `pages 47` joined to "47" and could
 * place the word "pages" on an observation of "47" — a word the engine never
 * said, recorded as matched. That is the failure this whole module exists to
 * stop, so it is not carried across.
 */
export function groupedDigitForm(run: readonly string[]): string | null {
  if (run.length < 2) return null;
  let joined = '';
  for (const token of run) {
    const digits = digitsOf(token);
    if (!digits) return null;
    joined += digits;
  }
  return joined;
}

/** The largest number of display tokens `groupedDigitForm` will collapse. */
export const MAX_GROUPED_TOKENS = 3;

/**
 * The whole normalisation of one token, as the harness and the worker both
 * consume it. One shape, one producer.
 */
export interface NormalizedToken {
  readonly token: string;
  readonly fold: string;
  /** `fold` with diacritics removed. Ranked BELOW `fold`; see `foldTokenLoose`. */
  readonly loose: string;
  readonly digits: string;
  readonly forms: string[][];
  /** `forms` under the loose fold, positionally parallel to `forms`. */
  readonly looseForms: string[][];
}

export function normalizeToken(token: string, lang: Lang): NormalizedToken {
  const forms = spokenForms(token, lang);
  return {
    token,
    fold: foldToken(token),
    loose: foldTokenLoose(token),
    digits: digitsOf(token),
    forms,
    // Positionally parallel so the matcher can fall back at a candidate WITHOUT
    // re-deriving which form it was trying — the two arrays are one table read
    // twice, not two tables that can disagree.
    looseForms: forms.map((seq) => seq.map(foldTokenLoose)),
  };
}
