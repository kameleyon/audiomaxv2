/**
 * ORTHOGRAPHY VARIANTS — one word, two spellings, one language.
 *
 * WHY THIS EXISTS, WITH THE MEASUREMENT THAT FORCED IT.
 * `aligner/spike-a/out/spike-a-english.json`, chapter clip: **25** display
 * tokens appear in the transcript in no form the matcher could accept, and
 * `clips[].orthography_probe.absent_tokens_explained_by_orthography` says **14**
 * of them are British spellings the recogniser wrote in American form —
 * `digitisation`, `programme`, `colours`, `organisation`, `synthesiser`,
 * `recognise`, `catalogue`, `neighbouring`, `Digitising`. The paragraph clip's
 * two absent tokens include `cancelled`. Those words were RECOGNISED CORRECTLY
 * and failed to MATCH: `foldToken` folds case, punctuation and diacritics, and
 * folds nothing about en-GB against en-US. Every one of them is a word a blind
 * user's highlight would skip.
 *
 * It is not a corner case. It is most English published outside the United
 * States, and audiomax ingests documents users already have.
 *
 * WHAT THIS IS AND IS NOT. Like every other table in this module it ENUMERATES
 * a form the display token might have been spoken — here, written — as. It never
 * rewrites the display text: the page keeps the author's spelling and the
 * highlight lands on it. Offering a form costs a candidate; asserting one would
 * be prediction, which §6.1 removed.
 *
 * SYMMETRIC, because neither side is fixed. The recogniser's orthography is a
 * property of its training data and the document's is a property of its author,
 * so a US-spelled page against a GB-spelled transcript is the same defect with
 * the arrows reversed. Every pair is looked up from both ends.
 *
 * THE `-ise` TRAP, MEASURED BEFORE IT WAS FIXED. A blanket `ise -> ize` rule
 * turns `raise` into `raize` and `precise` into `precize`. The first run of the
 * probe in `aligner/spike-a/english.py` emitted both into its own residual list,
 * which is how it was caught — it INVENTED two absent tokens while explaining
 * twelve. "-ise that stays -ise" is a closed lexical class, not a pattern, so it
 * is an exception list, generated over inflections rather than hand-listed per
 * form: adding a stem cannot then silently miss its `-ed`/`-ing`/`-s` forms,
 * which is the shape of the defect the list exists to fix.
 *
 * WHY THE OTHER FAMILIES ARE STEM LISTS AND NOT SUFFIX RULES. A suffix rule that
 * produces a NON-WORD is noise: it costs one dead candidate and can never match,
 * because no recogniser emits it. A suffix rule that produces a DIFFERENT REAL
 * WORD is a false match — a highlight on the wrong word, which for a reader
 * following the caret is worse than no highlight. `our -> or` turns `four` into
 * `for`, a token the recogniser emits several hundred times in a chapter; `re ->
 * er` turns `are` into `aer` but `more` into `moer` and `here` into `heer`, and
 * `lled -> led` turns `filled` into `filed`. Those families are therefore closed
 * lists. `-ise`/`-ize` is a rule because it is genuinely open — a document can
 * carry a verb no list anticipated — and because its failures are non-words.
 *
 * SCOPE. `en` only. Spanish and French have no comparable split in the
 * orthographies this product ingests; a table for them would be a table with no
 * measurement behind it.
 */
import type { Lang } from './numerals.ts';

/**
 * `-ise` words that are `-ise` in AMERICAN English too, and `-ize` words that
 * are `-ize` in BRITISH English too. Stems; inflections are generated.
 */
const NEVER_IZE_STEMS = [
  'raise', 'praise', 'appraise', 'apprise', 'reprise', 'noise', 'poise', 'precise',
  'concise', 'promise', 'surprise', 'wise', 'likewise', 'otherwise', 'rise', 'arise',
  'comprise', 'compromise', 'demise', 'devise', 'advise', 'revise', 'supervise',
  'televise', 'improvise', 'disguise', 'guise', 'despise', 'chastise', 'enterprise',
  'franchise', 'merchandise', 'exercise', 'excise', 'incise', 'paradise', 'treatise',
  'anise', 'cruise', 'bruise', 'tortoise', 'mortise', 'expertise', 'valise', 'malaise',
  'mayonnaise', 'surmise', 'exorcise', 'circumcise', 'wise', 'anywise',
];
const NEVER_ISE_STEMS = [
  'size', 'prize', 'seize', 'maize', 'capsize', 'resize', 'downsize', 'oversize',
  'assize', 'baize', 'gaze', 'gauze',
];

function inflect(stems: readonly string[]): ReadonlySet<string> {
  const out = new Set<string>();
  for (const b of stems) {
    out.add(b);
    out.add(`${b}d`);
    out.add(`${b}s`);
    out.add(`${b}r`);
    out.add(`${b}rs`);
    out.add(`${b.slice(0, -1)}ing`);
  }
  return out;
}
const NEVER_SWAP = new Set([...inflect(NEVER_IZE_STEMS), ...inflect(NEVER_ISE_STEMS)]);

/** `-our`/`-or`. See the header: a suffix rule here produces `for` from `four`. */
const OUR_STEMS = [
  'colour', 'behaviour', 'neighbour', 'honour', 'labour', 'favour', 'flavour',
  'harbour', 'humour', 'rumour', 'vapour', 'endeavour', 'odour', 'armour', 'parlour',
  'saviour', 'splendour', 'valour', 'vigour', 'candour', 'clamour', 'demeanour',
  'fervour', 'rancour', 'rigour', 'savour', 'succour', 'tumour', 'ardour',
];
/** `-re`/`-er`. Same reasoning: `here`, `more`, `store`, `figure` all end in `re`. */
const RE_STEMS = [
  'centre', 'theatre', 'metre', 'litre', 'fibre', 'calibre', 'sombre', 'spectre',
  'sceptre', 'lustre', 'meagre', 'sabre', 'louvre', 'goitre', 'mitre', 'nitre',
];
/**
 * `-ce`/`-se`. `practice`/`practise` is a NOUN/VERB distinction in en-GB rather
 * than a spelling difference, so it is deliberately absent: offering `practise`
 * for `practice` would be asserting a part of speech.
 */
const CE_SE_STEMS = ['defence', 'offence', 'pretence', 'licence'];
/** `-ogue`/`-og`. Closed: `vogue`, `rogue` and `brogue` are not pairs. */
const OGUE_STEMS = ['catalogue', 'dialogue', 'monologue', 'analogue', 'epilogue', 'travelogue'];
/**
 * Stems that DOUBLE a final `l` before a suffix in en-GB and do not in en-US.
 * A list, not a rule: `called`, `filled`, `spelled` and `killed` double in BOTH,
 * and `filled -> filed` is a real word.
 */
const DOUBLE_L_STEMS = [
  'travel', 'cancel', 'label', 'model', 'signal', 'marvel', 'level', 'total', 'fuel',
  'jewel', 'counsel', 'equal', 'initial', 'rival', 'dial', 'channel', 'panel',
  'quarrel', 'revel', 'shovel', 'tunnel', 'parcel', 'pencil', 'council', 'grovel',
  'libel', 'duel',
];
/** The mirror family: en-GB writes ONE `l` where en-US writes two. */
const SINGLE_L_STEMS = ['fulfil', 'instal', 'enrol', 'appal', 'distil', 'instil', 'annul'];
/** `-ae`/`-oe` reductions. Closed, because the digraph is not a suffix. */
const LIGATURE_PAIRS: ReadonlyArray<readonly [string, string]> = [
  ['encyclopaedia', 'encyclopedia'], ['paediatric', 'pediatric'], ['anaemia', 'anemia'],
  ['anaesthetic', 'anesthetic'], ['manoeuvre', 'maneuver'], ['oesophagus', 'esophagus'],
  ['foetus', 'fetus'], ['orthopaedic', 'orthopedic'], ['archaeology', 'archeology'],
  ['leukaemia', 'leukemia'], ['diarrhoea', 'diarrhea'], ['gynaecology', 'gynecology'],
];
/** Irregular pairs no suffix rule reaches. Every one is a homophone pair. */
const WORD_PAIRS: ReadonlyArray<readonly [string, string]> = [
  ['programme', 'program'], ['programmes', 'programs'], ['grey', 'gray'],
  ['storey', 'story'], ['storeys', 'stories'], ['plough', 'plow'], ['ploughs', 'plows'],
  ['draught', 'draft'], ['draughts', 'drafts'], ['kerb', 'curb'], ['tyre', 'tire'],
  ['tyres', 'tires'], ['aluminium', 'aluminum'], ['jewellery', 'jewelry'],
  ['moustache', 'mustache'], ['pyjamas', 'pajamas'], ['sceptical', 'skeptical'],
  ['speciality', 'specialty'], ['cheque', 'check'], ['cheques', 'checks'],
  ['mould', 'mold'], ['moulds', 'molds'], ['smoulder', 'smolder'], ['axe', 'ax'],
];

/** Both spellings of one word, reachable from either end. */
const VARIANTS = new Map<string, Set<string>>();
const link = (a: string, b: string): void => {
  if (a === b || !a || !b) return;
  for (const [x, y] of [[a, b], [b, a]] as const) {
    const set = VARIANTS.get(x);
    if (set) set.add(y);
    else VARIANTS.set(x, new Set([y]));
  }
};

for (const [gb, us] of WORD_PAIRS) link(gb, us);
for (const [gb, us] of LIGATURE_PAIRS) for (const s of ['', 's']) link(gb + s, us + s);
for (const stem of OUR_STEMS) {
  const us = `${stem.slice(0, -3)}or`;
  // `-our` followed by a VOWEL loses the `u` in en-GB too (`humorous`,
  // `laborious`), so only consonant-initial suffixes are pairs.
  for (const s of ['', 's', 'ed', 'ing', 'ful', 'less', 'ly']) link(stem + s, us + s);
}
for (const stem of RE_STEMS) {
  const us = `${stem.slice(0, -2)}er`;
  for (const s of ['', 's', 'd']) link(stem + s, us + s);
}
for (const stem of CE_SE_STEMS) {
  const us = `${stem.slice(0, -2)}se`;
  for (const s of ['', 's']) link(stem + s, us + s);
}
for (const stem of OGUE_STEMS) {
  const us = stem.slice(0, -2);
  for (const s of ['', 's']) link(stem + s, us + s);
}
for (const stem of DOUBLE_L_STEMS) {
  for (const [gbSuffix, usSuffix] of [['led', 'ed'], ['ling', 'ing'], ['ler', 'er'],
    ['lers', 'ers'], ['lings', 'ings'], ['lous', 'ous']]) {
    link(stem + gbSuffix, stem + usSuffix);
  }
}
for (const stem of SINGLE_L_STEMS) {
  link(stem, `${stem}l`);
  link(`${stem}s`, `${stem}ls`);
  link(`${stem}ment`, `${stem}lment`);
}

/**
 * The productive `-ise`/`-ize` and `-yse`/`-yze` families, as a RULE, because
 * they are open classes. Both directions, first matching suffix wins.
 */
const IZE_SUFFIXES: ReadonlyArray<readonly [string, string]> = [
  ['isation', 'ization'], ['isations', 'izations'], ['ised', 'ized'], ['ises', 'izes'],
  ['ising', 'izing'], ['isers', 'izers'], ['iser', 'izer'], ['ise', 'ize'],
  ['ysed', 'yzed'], ['yses', 'yzes'], ['ysing', 'yzing'], ['yse', 'yze'],
];

function izeVariant(folded: string): string | null {
  if (NEVER_SWAP.has(folded)) return null;
  for (const [ise, ize] of IZE_SUFFIXES) {
    if (folded.endsWith(ise)) {
      const swapped = folded.slice(0, -ise.length) + ize;
      return NEVER_SWAP.has(swapped) ? null : swapped;
    }
    if (folded.endsWith(ize)) {
      const swapped = folded.slice(0, -ize.length) + ise;
      return NEVER_SWAP.has(swapped) ? null : swapped;
    }
  }
  return null;
}

/**
 * Every OTHER spelling of a FOLDED token in `lang`, or an empty list.
 *
 * The input is folded — lowercased, punctuation stripped — because that is what
 * `foldToken` produces and what the matcher compares. Taking an unfolded token
 * here is how a table silently stops matching (`abbreviations.ts` records the
 * same rule).
 */
export function orthographyForms(folded: string, lang: Lang): readonly string[] {
  if (lang !== 'en' || !folded) return [];
  const out = new Set<string>(VARIANTS.get(folded) ?? []);
  const ize = izeVariant(folded);
  if (ize) out.add(ize);
  out.delete(folded);
  return [...out];
}

/**
 * The number of distinct spellings the closed lists reach. Exported so a test
 * asserts the tables were BUILT, rather than trusting that a loop ran: an empty
 * table and a table that folds nothing are the same observation from outside.
 */
export const ORTHOGRAPHY_VARIANT_COUNT = VARIANTS.size;
