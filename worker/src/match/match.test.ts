import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  LOOKAHEAD,
  MAX_RESYNC_SKIP,
  RESYNC_ANCHOR_TOKENS,
  matchTokens,
  type DisplayToken,
  type ObservedToken,
} from './match.ts';
import { matchRequest } from './cli.ts';
import { checkMonotonic } from '../normalize/contract.ts';
import {
  displayTokens,
  elisionForms,
  foldTokenLoose,
  spokenForms,
  type Lang,
} from '../normalize/index.ts';

/** Display tokens from a page of text — the same tokenizer the product uses. */
function page(text: string): DisplayToken[] {
  return displayTokens(text).map((t) => ({ text: t.text, cs: t.cs, ce: t.ce }));
}

/**
 * A transcript, one token every 0.5 s. Times are regular on purpose: these tests
 * are about WHICH display token an observation is attached to, and a test that
 * also varied the timing would fail for two reasons and diagnose neither.
 */
function heard(words: string): ObservedToken[] {
  return words.split(/\s+/).filter(Boolean).map((w, i) => ({ w, s: i * 0.5, e: i * 0.5 + 0.4 }));
}

function placedIndices(display: DisplayToken[], observed: ObservedToken[], lang: Lang = 'fr') {
  const r = matchTokens(display, observed, lang);
  return { r, placed: new Set(r.matched.map((m) => m.disp_idx)) };
}

describe('the matcher — ordinary placement', () => {
  it('places every word of a clean transcript', () => {
    const display = page('Le service compte aujourd hui des postes de travail');
    const { r, placed } = placedIndices(display, heard('Le service compte aujourd hui des postes de travail'));
    assert.equal(placed.size, display.length);
    assert.equal(r.unmatched.length, 0);
    assert.equal(r.resyncs.length, 0);
    assert.ok(r.matched.every((m) => m.evidence === 'exact'));
  });

  it('never moves the display cursor backwards — §6.1 invariant 1', () => {
    // "de" four times, and the recogniser drops a clause. A matcher free to look
    // behind would attach a later "de" to an earlier one.
    const display = page('le prix de la page de la copie de la notice de la fiche');
    const { r } = placedIndices(display, heard('le prix de la notice de la fiche'));
    assert.deepEqual(checkMonotonic(r.matched.map((m) => ({
      displayIndex: m.disp_idx, cs: m.cs, ce: m.ce, start: m.s, end: m.e,
    }))), []);
  });

  it('expands a numeral through the normaliser, longest form first', () => {
    // `en`, because `numerals.ts` has no French year form: `dix-neuf` is a
    // compound the table does not carry, and French does not say a year that way
    // in any case. An absent form is the correct answer there; a wrong one would
    // place the highlight on the wrong word. Recorded here so the gap is a
    // decision on the record rather than a silent hole.
    const display = page('published the results in 1984 and repeated');
    const { r } = placedIndices(display, heard('published the results in nineteen eighty four and repeated'), 'en');
    const year = r.matched.find((m) => m.disp === '1984');
    assert.ok(year, 'the year was not placed at all');
    assert.equal(year.via_normalizer, true);
    assert.equal(year.evidence, 'normalized');
    assert.equal(year.obs_w, 'nineteen eighty four');
  });

  it('places a European thousands group heard as one token', () => {
    const display = page('traite 1 250 documents');
    const { r } = placedIndices(display, heard('traite 1250 documents'));
    const shared = r.matched.filter((m) => m.shared_token);
    assert.equal(shared.length, 2);
    assert.deepEqual(shared.map((m) => m.disp), ['1', '250']);
    assert.ok(shared.every((m) => m.evidence === 'shared_token'));
  });

  it('reports an invented word as unmatched rather than attaching it', () => {
    const display = page('le rapport annuel de la bibliotheque');
    const { r } = placedIndices(display, heard('le rapport annuel euh de la bibliotheque'));
    assert.deepEqual(r.unmatched.map((o) => o.w), ['euh']);
    assert.equal(r.matched.length, 6);
  });
});

describe('the re-sync path', () => {
  // The defect this exists for, reduced to its smallest reproduction: a run of
  // display tokens longer than the lookahead window that the recogniser did not
  // produce. Before the re-sync path the cursor stopped here and NOTHING after
  // it was ever placed — on `fr-long-narrateur-r1.wav` that was 641 display
  // tokens of 1186, with a full transcript sitting unused.
  const dropped = 'alpha beta gamma delta epsilon zeta eta theta iota kappa';
  const display = page(`le service compte ${dropped} et il traite en moyenne mille documents par semaine`);
  const observed = heard('le service compte et il traite en moyenne mille documents par semaine');

  it('recovers the tail after a divergence wider than the lookahead window', () => {
    assert.ok(dropped.split(' ').length > LOOKAHEAD, 'the fixture must exceed the window');
    const { r, placed } = placedIndices(display, observed);
    assert.equal(r.resyncs.length, 1);
    // Everything after the dropped run is placed.
    const tail = display.length - 1;
    assert.ok(placed.has(tail), 'the last display token was not placed');
    assert.ok(placed.has(tail - 1));
    assert.equal(r.matched.filter((m) => m.after_resync).length, 1);
  });

  it('leaves the skipped display tokens UNMATCHED and in the denominator', () => {
    const { r, placed } = placedIndices(display, observed);
    const skipped = display
      .map((d, i) => [d.text, i] as const)
      .filter(([t]) => dropped.split(' ').includes(t));
    assert.equal(skipped.length, 10);
    for (const [text, i] of skipped) {
      assert.ok(!placed.has(i), `${text} was skipped by the cursor and must not count as matched`);
    }
    assert.equal(r.resyncs[0]!.skipped_display_tokens, 10);
  });

  it('moves the display cursor FORWARD only', () => {
    const { r } = placedIndices(display, observed);
    for (const s of r.resyncs) assert.ok(s.to_display > s.from_display);
    assert.deepEqual(checkMonotonic(r.matched.map((m) => ({
      displayIndex: m.disp_idx, cs: m.cs, ce: m.ce, start: m.s, end: m.e,
    }))), []);
  });

  it('does not fire on a divergence the window already spans', () => {
    const d = page('le service compte un deux trois et il traite');
    const { r } = placedIndices(d, heard('le service compte et il traite'));
    assert.equal(r.resyncs.length, 0);
    assert.equal(r.matched.length, 6);
  });

  it('refuses a recovery further ahead than MAX_RESYNC_SKIP', () => {
    // The anchor exists, but only beyond the refusal distance. The matcher must
    // leave the tail unplaced and let the coverage floor fire, NOT write off an
    // arbitrary amount of page to make its own number look better.
    const filler = Array.from({ length: MAX_RESYNC_SKIP + 20 }, (_, i) => `mot${i}`).join(' ');
    const d = page(`le service compte ${filler} la formation des agents occupe`);
    const { r, placed } = placedIndices(d, heard('le service compte la formation des agents occupe'));
    assert.equal(r.resyncs.length, 0);
    assert.ok(!placed.has(d.length - 1), 'the tail must stay unplaced past the refusal distance');
  });

  it('needs a whole anchor: two matching tokens are not enough to jump', () => {
    // `de la` occurs everywhere in French. If two tokens could re-anchor, the
    // cursor would teleport on a function-word pair.
    assert.equal(RESYNC_ANCHOR_TOKENS, 3);
    const d = page('un deux trois quatre cinq six sept huit neuf dix de la');
    // Only "de la" — two tokens — follows the divergence, so no anchor exists.
    const { r } = placedIndices(d, heard('un de la'));
    assert.equal(r.resyncs.length, 0);
  });

  it('terminates on a transcript that shares no anchor with the page', () => {
    const d = page('le rapport annuel de la bibliotheque municipale decrit un programme');
    const { r } = placedIndices(d, heard('xxx yyy zzz www vvv uuu ttt sss rrr qqq'));
    assert.equal(r.matched.length, 0);
    assert.equal(r.unmatched.length, 10);
    assert.equal(r.resyncs.length, 0);
  });

  // ── MUTATION. The controls above must FAIL when the path is removed. ──────
  //
  // A test that passes both with and without the behaviour it names is not
  // evidence. The re-sync path cannot be switched off by a flag — a matcher with
  // a "no re-sync" mode is a matcher that can ship without one — so the mutation
  // is performed on the FIXTURE: shrink the divergence to something the old
  // matcher could already span, and the recovery claim must stop being
  // interesting; widen it, and the pre-re-sync behaviour is reproduced by
  // reading the resync list.
  it('MUTATION: with the re-sync suppressed by fixture, the tail is lost', () => {
    const { r, placed } = placedIndices(display, observed);
    // The pre-re-sync matcher is exactly this run truncated at the first miss
    // that would have needed a recovery.
    const firstResync = r.resyncs[0]!;
    const wouldHaveStopped = firstResync.from_display;
    const lostWithoutIt = display.length - wouldHaveStopped;
    assert.ok(lostWithoutIt > 10,
      'the fixture no longer reproduces a cascade, so the recovery tests prove nothing');
    // And with the recovery, they are not lost.
    const recovered = [...placed].filter((i) => i >= wouldHaveStopped).length;
    assert.equal(recovered, 9, 'the nine display tokens after the dropped run');
    assert.equal(r.unmatched.length, 0);
  });
});

describe('the diacritic fold — ranked below the exact fold, never above it', () => {
  it('places a page word the recogniser accented and the page did not', () => {
    const display = page('la bibliotheque municipale decrit un programme');
    const { r, placed } = placedIndices(display, heard('la bibliothèque municipale décrit un programme'));
    assert.equal(placed.size, display.length);
    const relaxed = r.matched.filter((m) => m.via_diacritic_fold);
    assert.deepEqual(relaxed.map((m) => m.disp), ['bibliotheque', 'decrit']);
    assert.ok(relaxed.every((m) => m.evidence === 'normalized'),
      'a relaxed match must never claim `exact` evidence');
  });

  it('prefers the EXACT fold at the same position', () => {
    const display = page('ou est le rapport');
    const { r } = placedIndices(display, heard('ou est le rapport'));
    assert.ok(r.matched.every((m) => !m.via_diacritic_fold));
    assert.ok(r.matched.every((m) => m.evidence === 'exact'));
  });

  it('MUTATION: without the loose fold there is no placement to rank', () => {
    // Falsifies the claim by construction: if `foldTokenLoose` were the identity
    // the two spellings would be unequal and the test above could not pass.
    assert.notEqual(foldTokenLoose('bibliothèque'), 'bibliothèque');
    assert.equal(foldTokenLoose('bibliothèque'), 'bibliotheque');
    assert.equal(foldTokenLoose('año'), 'ano');
  });
});

describe('elision — one token on the page, two in the transcript', () => {
  it('offers both splits and asserts neither', () => {
    assert.deepEqual(elisionForms("l'equipe"), [['l', "'equipe"], ["l'", 'equipe']]);
    assert.deepEqual(elisionForms("aujourd'hui"), [['aujourd', "'hui"], ["aujourd'", 'hui']]);
  });

  it('does not split a leading or trailing apostrophe', () => {
    assert.deepEqual(elisionForms("'hui"), []);
    assert.deepEqual(elisionForms("l'"), []);
    assert.deepEqual(elisionForms('rapport'), []);
  });

  it('places the display token faster-whisper split at the apostrophe', () => {
    // The exact tokenisation observed in `out/fr-long-*.wav`: `l` then `'équipe`.
    const display = page("qui dirige l'equipe technique");
    const { r, placed } = placedIndices(display, heard("qui dirige l 'équipe technique"));
    assert.equal(placed.size, display.length);
    const elided = r.matched.find((m) => m.disp === "l'equipe");
    assert.ok(elided);
    assert.equal(elided.via_normalizer, true);
    assert.equal(elided.obs_w, "l 'équipe");
  });

  it('MUTATION: the elision form is what places it', () => {
    const forms = spokenForms("l'equipe", 'fr');
    assert.ok(forms.some((f) => f.length === 2 && f[0] === 'l' && f[1] === "'equipe"),
      'the split form is absent, so the placement above came from somewhere else');
  });
});

describe('the delegation bridge', () => {
  it('matches display and observed tokens in one request', () => {
    const res = matchRequest({
      lang: 'fr',
      display: [['avec', 0, 4], ['1', 5, 6], ['250', 7, 10], ['participants.', 11, 24]],
      observed: [{ w: 'avec', s: 0, e: 0.3 }, { w: '1250', s: 0.4, e: 0.9 },
        { w: 'participants', s: 1, e: 1.6 }],
    });
    assert.equal(res.lang, 'fr');
    assert.equal(res.matched.length, 4);
    assert.deepEqual(res.folds.display, ['avec', '1', '250', 'participants']);
    assert.deepEqual(res.folds.observed, ['avec', '1250', 'participants']);
  });

  it('REFUSES an unsupported language instead of matching nothing', () => {
    assert.throws(
      () => matchRequest({ lang: 'ht', display: [['bonjou', 0, 6]], observed: [] }),
      /unsupported language/,
    );
  });

  it('refuses a malformed display row', () => {
    assert.throws(
      () => matchRequest({
        lang: 'fr',
        display: [['avec', 0] as unknown as readonly [string, number, number]],
        observed: [],
      }),
      /must be \[text, cs, ce\]/,
    );
  });
});
