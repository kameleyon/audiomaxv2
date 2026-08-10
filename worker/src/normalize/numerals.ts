/**
 * Numeral expansion — the spoken forms a TTS engine may produce for a number.
 *
 * §6.2 states the problem: the page shows `1984`, the audio says "nineteen
 * eighty-four", and the *i*-th spoken word stops corresponding to the *i*-th
 * display token. Under §6.1 we no longer predict what the provider will say; we
 * transcribe what it did. But the matcher still has to recognise that "nineteen
 * eighty four" and `1984` are the same display token, or it reports a correct
 * engine as an inventing one — which is exactly the conflation Task 3 splits.
 *
 * The tables are ordered pairs, not objects, because the INVERSE map is what the
 * expansion uses and later entries must win: Spanish has both `cien` and
 * `ciento` for 100, and the spoken form of 100 is `ciento`. An object literal
 * would make that dependent on key ordering rules rather than on this sentence.
 */

export type Lang = 'en' | 'es' | 'fr';

export const LANGS: readonly Lang[] = ['en', 'es', 'fr'];

export function isLang(value: string): value is Lang {
  return (LANGS as readonly string[]).includes(value);
}

type NumberWord = readonly [word: string, value: number];

const NUMBER_WORDS: Readonly<Record<Lang, readonly NumberWord[]>> = {
  en: [
    ['zero', 0], ['one', 1], ['two', 2], ['three', 3], ['four', 4], ['five', 5],
    ['six', 6], ['seven', 7], ['eight', 8], ['nine', 9], ['ten', 10],
    ['eleven', 11], ['twelve', 12], ['thirteen', 13], ['fourteen', 14],
    ['fifteen', 15], ['sixteen', 16], ['seventeen', 17], ['eighteen', 18],
    ['nineteen', 19], ['twenty', 20], ['thirty', 30], ['forty', 40],
    ['fifty', 50], ['sixty', 60], ['seventy', 70], ['eighty', 80],
    ['ninety', 90], ['hundred', 100], ['thousand', 1000],
  ],
  es: [
    ['cero', 0], ['uno', 1], ['dos', 2], ['tres', 3], ['cuatro', 4], ['cinco', 5],
    ['seis', 6], ['siete', 7], ['ocho', 8], ['nueve', 9], ['diez', 10],
    ['veinte', 20], ['treinta', 30], ['cuarenta', 40], ['cincuenta', 50],
    ['sesenta', 60], ['setenta', 70], ['ochenta', 80], ['noventa', 90],
    // `cien` precedes `ciento` so that the inverse map below resolves 100 to
    // `ciento`, which is the form spoken before another numeral.
    ['cien', 100], ['ciento', 100], ['mil', 1000],
  ],
  fr: [
    ['zero', 0], ['un', 1], ['deux', 2], ['trois', 3], ['quatre', 4], ['cinq', 5],
    ['six', 6], ['sept', 7], ['huit', 8], ['neuf', 9], ['dix', 10],
    ['vingt', 20], ['trente', 30], ['quarante', 40], ['cinquante', 50],
    ['soixante', 60], ['cent', 100], ['mille', 1000],
  ],
};

function buildInverse(entries: readonly NumberWord[]): ReadonlyMap<number, string> {
  const m = new Map<number, string>();
  // Later entries overwrite earlier ones on purpose — see `cien`/`ciento`.
  for (const [word, value] of entries) m.set(value, word);
  return m;
}

// Written out per language rather than derived with a cast: a `Record<Lang, …>`
// built from `Object.fromEntries` is a `Record<string, …>` wearing a claim, and
// adding a fourth language would then typecheck with three entries.
const INVERSE: Readonly<Record<Lang, ReadonlyMap<number, string>>> = {
  en: buildInverse(NUMBER_WORDS.en),
  es: buildInverse(NUMBER_WORDS.es),
  fr: buildInverse(NUMBER_WORDS.fr),
};

/** The digits of a token, in order, with every other character dropped. */
export function digitsOf(token: string): string {
  return token.replace(/[^0-9]/g, '');
}

/** Each maximal run of digits, so `1,250` yields `['1', '250']`. */
export function digitRuns(token: string): string[] {
  return token.match(/[0-9]+/g) ?? [];
}

/**
 * The YEAR form: `1984` → "nineteen" "eighty" "four".
 *
 * Bounded to 1100–2099 deliberately. Outside that range a four-digit number is
 * far more often a quantity than a year, and "one thousand two hundred fifty"
 * is a different expansion this function does not claim to produce. Returning
 * nothing is correct here: an absent form costs a match the plain-digit form may
 * still make, whereas a WRONG form places a highlight on the wrong word.
 */
export function yearForm(n: number, lang: Lang): string[] | null {
  if (!Number.isInteger(n) || n < 1100 || n > 2099) return null;
  const words = INVERSE[lang];
  const hi = Math.floor(n / 100);
  const lo = n % 100;
  const head = words.get(hi);
  if (head === undefined) return null;
  if (lo === 0) return [head];
  const whole = words.get(lo);
  if (whole !== undefined) return [head, whole];
  const tens = words.get(lo - (lo % 10));
  const units = words.get(lo % 10);
  if (tens === undefined || units === undefined) return null;
  return [head, tens, units];
}

/** The single word for a number, when the language has one (`3` → "three"). */
export function wholeNumberWord(n: number, lang: Lang): string | null {
  return INVERSE[lang].get(n) ?? null;
}
