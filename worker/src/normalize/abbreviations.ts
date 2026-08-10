/**
 * Abbreviation expansion — `Dr.` is four characters on the page and two
 * syllables of "docteur" in the audio.
 *
 * One abbreviation can have SEVERAL spoken forms (`St.` is "saint" or "street"),
 * so the value is a list and the matcher tries each. It does not disambiguate;
 * it accepts whichever the engine actually said, which is the whole point of
 * observing rather than predicting (§6.1).
 *
 * Keys are stored FOLDED — lowercased, punctuation stripped — because that is
 * the form `foldToken` produces and the form the lookup receives. Storing `Dr.`
 * here and folding at lookup time is how the table silently stops matching.
 */
import type { Lang } from './numerals.ts';

export const ABBREVIATIONS: Readonly<Record<Lang, Readonly<Record<string, readonly string[]>>>> = {
  en: {
    dr: ['doctor'],
    mr: ['mister'],
    mrs: ['missus'],
    ms: ['miz'],
    prof: ['professor'],
    st: ['saint', 'street'],
    vs: ['versus'],
  },
  es: {
    dr: ['doctor'],
    dra: ['doctora'],
    sr: ['senor'],
    sra: ['senora'],
    prof: ['profesor'],
    profa: ['profesora'],
  },
  fr: {
    dr: ['docteur'],
    dre: ['docteure'],
    m: ['monsieur'],
    mme: ['madame'],
    mlle: ['mademoiselle'],
    pr: ['professeur'],
    prof: ['professeur'],
    st: ['saint'],
    ste: ['sainte'],
  },
};

/** The spoken alternatives for a FOLDED token, or an empty list. */
export function abbreviationForms(folded: string, lang: Lang): readonly string[] {
  return ABBREVIATIONS[lang][folded] ?? [];
}
