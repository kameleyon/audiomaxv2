import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  displayTokens,
  foldToken,
  groupedDigitForm,
  normalizeToken,
  spokenForms,
} from './index.ts';
import { digitRuns, digitsOf, wholeNumberWord, yearForm } from './numerals.ts';
import { abbreviationForms } from './abbreviations.ts';
import { normalizeRequest } from './cli.ts';

/** Does `forms` contain this exact sequence? */
function hasForm(forms: string[][], seq: string[]): boolean {
  return forms.some((f) => f.length === seq.length && f.every((t, i) => t === seq[i]));
}

describe('foldToken', () => {
  it('lowercases, composes and strips punctuation', () => {
    assert.equal(foldToken('Dr.'), 'dr');
    assert.equal(foldToken('participants.'), 'participants');
    assert.equal(foldToken('«Chen»,'), 'chen');
  });

  it('keeps the apostrophe, which is inside words in all three languages', () => {
    assert.equal(foldToken("l'eau"), "l'eau");
    assert.equal(foldToken("don't"), "don't");
  });

  it('folds decomposed and composed accents to the same string', () => {
    // The failure: strip-then-compose leaves a bare `e` on one side and `é` on
    // the other, so `résultats` never matches itself.
    assert.equal(foldToken('résultats'), foldToken('résultats'));
    assert.equal(foldToken('CHAÎNE'), 'chaîne');
  });

  it('returns empty for a token that is only punctuation', () => {
    assert.equal(foldToken('—'), '');
    assert.equal(foldToken('...'), '');
  });
});

describe('displayTokens', () => {
  it('carries the character offsets a highlight is addressed by', () => {
    const toks = displayTokens('Le Dr Chen');
    assert.deepEqual(toks.map((t) => t.text), ['Le', 'Dr', 'Chen']);
    assert.deepEqual(toks.map((t) => [t.cs, t.ce]), [[0, 2], [3, 5], [6, 10]]);
  });
});

describe('numeral expansion', () => {
  it('expands a year to its spoken form', () => {
    assert.deepEqual(yearForm(1984, 'en'), ['nineteen', 'eighty', 'four']);
    assert.deepEqual(yearForm(1920, 'en'), ['nineteen', 'twenty']);
    assert.deepEqual(yearForm(1900, 'en'), ['nineteen']);
  });

  it('refuses a number outside the year range rather than guessing', () => {
    assert.equal(yearForm(2100, 'en'), null);
    assert.equal(yearForm(47, 'en'), null);
    assert.equal(yearForm(1.5, 'en'), null);
  });

  it('offers the year reading for any four-digit number in range, and that is deliberate', () => {
    // 1250 is far more often a quantity than a year, and the year reading of it
    // — "twelve fifty" — is a form English speakers do use for both. This is an
    // additional CANDIDATE, not an assertion about what was said: the matcher
    // accepts whichever form was transcribed, so an unused candidate costs
    // nothing and a missing one costs a match. Recorded as a test because the
    // alternative — narrowing the range to "plausible years" — would silently
    // drop `1250` from the `fr` fixture's page-number neighbourhood.
    assert.deepEqual(yearForm(1250, 'en'), ['twelve', 'fifty']);
  });

  it('resolves 100 in Spanish to `ciento`, the form spoken before a numeral', () => {
    assert.equal(wholeNumberWord(100, 'es'), 'ciento');
    assert.equal(wholeNumberWord(100, 'fr'), 'cent');
  });

  it('splits grouped digits into their runs', () => {
    assert.deepEqual(digitRuns('1,250'), ['1', '250']);
    assert.equal(digitsOf('1,250'), '1250');
    assert.equal(digitsOf('pages'), '');
  });
});

describe('spokenForms', () => {
  it('states the French gap rather than hiding it', () => {
    // French builds 19 as `dix-neuf` and 80 as `quatre-vingts`; neither is a
    // single entry in the table, so `yearForm` returns nothing for 1984 rather
    // than assembling a form nobody says. The digit readings carry the match,
    // and the SPIKE A `fr` fixture places `1984` on them. This is a test so the
    // gap is a recorded fact instead of a surprise in a later measurement.
    assert.equal(yearForm(1984, 'fr'), null);
    const forms = spokenForms('1984', 'fr');
    assert.ok(hasForm(forms, ['1984']), 'digits read back');
    assert.equal(forms.every((f) => f.length === 1), true, 'no assembled year form');
  });

  it('offers the English year form, which is what makes 1984 matchable', () => {
    const forms = spokenForms('1984', 'en');
    assert.ok(hasForm(forms, ['nineteen', 'eighty', 'four']));
    assert.ok(hasForm(forms, ['1984']));
  });

  it('offers both the joined and the grouped reading of 1,250', () => {
    const forms = spokenForms('1,250', 'en');
    assert.ok(hasForm(forms, ['1250']), 'heard as one number');
    assert.ok(hasForm(forms, ['1', '250']), 'heard as its groups');
  });

  it('expands bare integers the language has a word for', () => {
    assert.ok(hasForm(spokenForms('3', 'en'), ['three']));
    assert.ok(hasForm(spokenForms('3', 'es'), ['tres']));
    assert.ok(hasForm(spokenForms('3', 'fr'), ['trois']));
    assert.ok(hasForm(spokenForms('52', 'en'), ['52']));
  });

  it('expands the abbreviations the three languages actually print', () => {
    assert.ok(hasForm(spokenForms('Dr.', 'en'), ['doctor']));
    assert.ok(hasForm(spokenForms('Dr.', 'fr'), ['docteur']));
    assert.ok(hasForm(spokenForms('Dra.', 'es'), ['doctora']));
    assert.ok(hasForm(spokenForms('Prof.', 'en'), ['professor']));
    assert.ok(hasForm(spokenForms('Prof.', 'fr'), ['professeur']));
    assert.ok(hasForm(spokenForms('Prof.', 'es'), ['profesor']));
  });

  it('offers every alternative for an ambiguous abbreviation', () => {
    assert.deepEqual(abbreviationForms('st', 'en'), ['saint', 'street']);
    const forms = spokenForms('St.', 'en');
    assert.ok(hasForm(forms, ['saint']));
    assert.ok(hasForm(forms, ['street']));
  });

  it('always offers the plain folded form first', () => {
    assert.deepEqual(spokenForms('résultats', 'fr')[0], ['résultats']);
  });

  it('returns nothing for a token with no letters or digits', () => {
    assert.deepEqual(spokenForms('—', 'en'), []);
  });
});

describe('groupedDigitForm — many display tokens heard as one', () => {
  it('joins a European thousands group', () => {
    // `1 250` is two display tokens on the page and one token in the audio.
    // Without this `fr` sits below the coverage floor for a typographic
    // convention, and the unplaced observation is charged to the engine.
    assert.equal(groupedDigitForm(['1', '250']), '1250');
    assert.equal(groupedDigitForm(['1', '250', '000']), '1250000');
  });

  it('refuses a run containing a word', () => {
    // The harness form joined the digits of whatever it was handed, so
    // `pages 47` joined to "47" and could record the word "pages" as matched
    // against an observation of "47".
    assert.equal(groupedDigitForm(['pages', '47']), null);
    assert.equal(groupedDigitForm(['47', 'à']), null);
  });

  it('refuses a single token, which is not a group', () => {
    assert.equal(groupedDigitForm(['1250']), null);
    assert.equal(groupedDigitForm([]), null);
  });
});

describe('normalizeToken', () => {
  it('returns one shape for the harness and the worker both', () => {
    const n = normalizeToken('1,250', 'fr');
    assert.equal(n.token, '1,250');
    assert.equal(n.fold, '1250');
    assert.equal(n.digits, '1250');
    assert.ok(n.forms.length > 0);
  });
});

describe('the delegation bridge', () => {
  it('normalises display and observed tokens in one request', () => {
    const res = normalizeRequest({
      lang: 'fr',
      display: ['avec', '1', '250', 'participants.'],
      observed: ['avec', '1250', 'participants'],
    });
    assert.equal(res.lang, 'fr');
    assert.equal(res.display.length, 4);
    assert.equal(res.observed.length, 3);
    assert.equal(res.grouped['1']?.['2'], '1250');
    assert.equal(res.grouped['0'], undefined, 'a run starting on a word is not a group');
    assert.equal(res.contract.drift_bound_ms, 250);
  });

  it('REFUSES an unsupported language instead of returning identity', () => {
    // A normaliser that degrades to identity returns a plausible, wrong match
    // rate. §3.5 refuses an unsupported language before synthesis, so a token in
    // one reaching here is a bug, not an input.
    assert.throws(() => normalizeRequest({ lang: 'ht', display: ['bonjou'] }), /unsupported language/);
    assert.throws(() => normalizeRequest({ lang: '', display: [] }), /unsupported language/);
  });

  it('refuses a malformed request', () => {
    assert.throws(
      () => normalizeRequest({ lang: 'en' } as unknown as { lang: string; display: string[] }),
      /must be an array/,
    );
  });
});
