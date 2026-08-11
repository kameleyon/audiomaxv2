#!/usr/bin/env node
/**
 * conformance.mjs — the Phase 0 accessibility gate (ADR-0004).
 *
 * WHAT IT IS
 * A headless client that drives the documented §9 flows and asserts, for every
 * disclosure, that it is (1) reachable, (2) correctly ADDRESSED rather than
 * merely tallied, and (3) carries a catalogue string in all three supported
 * languages. It answers one question: does the backend FORECLOSE an accessible
 * client. It does not answer whether a blind user can use the product, and
 * ADR-0004 says so in the decision itself.
 *
 * WHAT IT IS NOT
 * A screen-reader pass. Halo still cannot issue PASS. See LIMITS, printed below
 * on every run.
 *
 * THREE STATES, NOT TWO
 * pass · fail · UNESTABLISHED. A check whose input was never obtained is RED.
 * Nothing is implemented today, so a default run is red from top to bottom, and
 * that is the honest reading: a green harness over absent code would be the
 * vacuous-gate defect this project has filed four times.
 *
 * USAGE
 *   node tests/a11y/conformance.mjs                     # no backend → all red
 *   node tests/a11y/conformance.mjs --base-url=http://localhost:8080 \
 *        [--document-id=<id>] [--allow-writes] [--allow-commit]
 *   node tests/a11y/conformance.mjs --stub              # drive the built-in fixture over HTTP
 *   node tests/a11y/conformance.mjs --self-test         # mutation battery
 *   node tests/a11y/conformance.mjs --list              # the checks and why each exists
 *
 * EXIT  0 clean · 1 findings · 2 clean but the private spec was absent, so the
 *       vocabulary could not be verified against it
 */

import { readFileSync, existsSync } from 'node:fs';
import { CHECKS } from './checks.mjs';
import {
  SPEC_CHECKS, Unestablished, LIMITS, ASSUMPTIONS, LANGS, ALIGN_KEY_COUNT,
} from './contract.mjs';
import { drive, readS9, PROBE_TEXT } from './drive.mjs';
import { makeFixture, transportFor, NO_VOICE_REASON } from './fixture.mjs';
import { startStub, httpTransport } from './stub.mjs';

const SPEC_PATH = 'resources/specs/2026-08-08-audiomax-backend-design.md';

const argv = process.argv.slice(2);
const flag = (n) => argv.includes(`--${n}`);
const opt = (n) => {
  const hit = argv.find((a) => a.startsWith(`--${n}=`));
  return hit ? hit.slice(n.length + 3) : null;
};

// ── running checks ───────────────────────────────────────────────────────

const PASS = 'pass'; const FAIL = 'fail'; const UNEST = 'unestablished';

function runOne(check, input) {
  try {
    const detail = check.run(input);
    return detail ? { state: FAIL, detail } : { state: PASS, detail: '' };
  } catch (err) {
    if (err instanceof Unestablished) return { state: UNEST, detail: err.message };
    return { state: FAIL, detail: `the check itself threw: ${err?.stack?.split('\n')[0] ?? err}` };
  }
}

const runConformance = (o) => CHECKS.map((c) => ({ id: c.id, why: c.why, ...runOne(c, o) }));
const runSpec = (text) => SPEC_CHECKS.map((c) => ({ id: c.id, why: c.title, ...runOne(c, text) }));

// ── the self-test ────────────────────────────────────────────────────────
// Every mutation below breaks the fixture in ONE place and must drive the named
// check red. The battery runs the SHIPPED checks over a mutated fixture through
// the SHIPPED driver; nothing here re-implements a predicate.

const cat = (d, lang) => d.catalogue[lang];

/** [id, mutate(data) | null, extra drive options] */
const MUTATIONS = [
  ['A-VOICES-ROUTE-EXISTS', (d) => { d.voicesStatus.fr = 404; }],
  ['A-VOICES-NONEMPTY-FOR-ROUTED-LANG', (d) => { d.voices.es = []; }],
  ['A-VOICES-EMPTY-CARRIES-REASON', (d) => { d.noVoiceReason = null; }],
  ['A-VOICES-EMPTY-REASON-TRANSLATED', (d) => { delete cat(d, 'fr')[NO_VOICE_REASON]; }],
  ['A-VOICES-ROW-FIELDS', (d) => { delete d.voices.fr[0].gender; }],
  ['A-VOICES-SYNC-GRADE-NEVER-NULL', (d) => { d.voices.fr[0].sync_grade = null; }],
  ['A-VOICES-SAMPLE-AUDIBLE', (d) => { d.voices.fr[1].sample_url = null; }],

  ['A-SPEECH-BLOCKER-REACHABLE', (d) => {
    // ADR-0004 specimen 1, in its exact form: a counter with no raiser.
    d.quote.speech_blocker = { blocked_language_unsupported: 0 };
    d.quote.speech_available_segments = 12;
  }],
  ['A-SPEECH-IDENTITY', (d) => { d.quote.speech_available_segments = 10; }],
  ['A-BLOCKED-LANG-ANNOUNCED', (d) => { d.segments[9].rendition_status = 'failed'; }],
  ['A-BLOCKED-LANG-STRING', (d) => { delete cat(d, 'es').blocked_language_unsupported; }],

  ['A-QUOTE-200-AT-ANY-BALANCE', (d) => { d.quoteStatus = 402; }],
  ['A-QUOTE-BALANCE-MAY-BE-NEGATIVE', (d) => { d.quote.balance_after = 0; }],
  ['A-QUOTE-SYNC-IDENTITY', (d) => { d.quote.word_sync_unmeasured_segments = 7; }],
  ['A-QUOTE-FIELDS', (d) => { delete d.quote.spoken_bytes; }],
  ['A-QUOTE-INSERTED-PRICED-SEPARATELY', (d) => { d.quote.inserted_characters = 99999; }],
  ['A-QUOTE-NO-ALIGN-PERMANENCE', (d) => { d.quote.align_permanence = 'permanent'; }],
  ['A-RENDER-409-ON-STALE-ETAG', (d) => { d.ignoreEtag = true; }],
  ['A-RENDER-402-INSUFFICIENT', (d) => { d.renderCommit.body.segments_enqueued = 3; }],

  ['A-SYNC-STORE-EMPTY', null, { s9: { parsed: { pass: false, claim: 'mutated for the trial' } } }],
  ['A-SYNC-NO-AVAILABLE-WITHOUT-A-GRADED-PAIR', (d) => { d.quote.word_sync_available_segments = 3; }],
  ['A-SYNC-UNMEASURED-WHILE-UNSEEDED', (d) => { d.quote.word_sync_unmeasured_segments = 0; }],
  ['A-SYNC-GRADE-STRINGS', (d) => { delete cat(d, 'fr').provisional; }],

  ['A-TEXT-BEFORE-AUDIO', (d) => { d.blocksStatus = 409; }],
  ['A-DOCUMENT-OMITS-BLOCKS', (d) => { d.document.blocks = d.blocks; }],
  ['A-TEXT-A11Y-FIDELITY', (d) => { delete d.blocks[0].heading_level; }],

  ['A-SPANS-POSITIONED', (d) => { delete d.spansFull[0].char_offset; }],
  ['A-SPANS-KIND-AND-REASON-DOMAIN', (d) => { d.spansFull[0].kind = 'skip'; }],
  ['A-SPANS-TOTALS-KEYED-BY-REASON', (d) => { d.totalsOverride = { footnotes: 4 }; }],
  ['A-SPANS-DROPPED-ONE-PER-MARKER', (d) => { d.spansFull[5].count = 18; }],
  ['A-SPANS-SURVIVE-VERBOSITY-OFF', (d) => {
    d.spansOff = d.spansOff.filter((s) => s.reason !== 'dropped_marker');
  }],
  ['A-SEGMENTS-PROVENANCE', (d) => { delete d.segments[0].block_start_offsets; }],
  ['A-SEGMENTS-BOTH-THRESHOLDS', (d) => { delete d.segmentsEnvelope.match_conf_threshold; }],
  ['A-ALIGN-REASON-IS-ARRAY', (d) => { d.segments[3].align_reason = 'excessive_drop'; }],
  ['A-DEGRADED-IS-200', (d) => { d.segments[1].audio_url = null; }],

  ['A-CATALOGUE-LOCALES', (d) => { delete cat(d, 'fr').failed; }],
  ['A-CATALOGUE-COVERS-EMITTED-TOKENS', (d) => { delete cat(d, 'es').dropped_marker; }],
  ['A-CATALOGUE-ALIGN-STATE-KEYS', (d) => { delete cat(d, 'fr')['unavailable+no_transcriber']; }],
  ['A-CATALOGUE-COMPOUND-KEY', (d) => {
    // N4-C2 in its exact form: the compound state loses its single key while
    // both of its parts keep theirs, so a naive implementation concatenates.
    delete cat(d, 'fr')['degraded+low_confidence+voice_substituted'];
    delete cat(d, 'es')['degraded+low_confidence+voice_substituted'];
    delete cat(d, 'en')['degraded+low_confidence+voice_substituted'];
  }],
  ['A-CATALOGUE-LOW-CONF-SPLIT', (d) => {
    cat(d, 'es')['unavailable+low_confidence'] = cat(d, 'es')['degraded+low_confidence'];
  }],
  ['A-CATALOGUE-PENDING-KEY', (d) => { delete cat(d, 'es').pending; }],
  ['A-CATALOGUE-ERROR-CODES', (d) => { delete cat(d, 'fr').ocr_low_confidence; }],
  ['A-CATALOGUE-NO-TOKEN-ECHO', (d) => { cat(d, 'fr').excessive_drop = 'excessive_drop'; }],
  ['A-CATALOGUE-NOT-STUBBED-FROM-EN',
   (d) => { cat(d, 'fr')['degraded+wrong_match'] = cat(d, 'en')['degraded+wrong_match']; }],

  ['A-PROGRESS-RESOLUTION', (d) => { d.progress_resolution = 'approximate'; }],
  ['A-NARRATION-ROUTE', (d) => { delete d.narration.lang; }],
  ['A-NO-5XX', (d) => { d.voicesStatus.en = 503; }],
  ['A-ERRORS-CODED', (d) => { delete d.renderCommit.body.code; }],
];

/** [id, mutate(specText)] — the spec legs, mutated in memory like doc-check does. */
const SPEC_MUTATIONS = [
  ['SPEC-SKIP-REASON', (s) => s.replace("| 'footnote' | 'page_number'", "| 'page_number'")],
  ['SPEC-INSERTED-REASON', (s) => s.replace("| 'table_preamble' | 'table_cell_header'", "| 'table_cell_header'")],
  ['SPEC-SPAN-REASON-COUNT', (s) => s.replace('**16** `SpanReason`', '**15** `SpanReason`')],
  ['SPEC-ALIGN-CAUSES', (s) => s.replace('｜engine_error', '')],
  ['SPEC-ALIGN-STATUS', (s) => s.replace('| `align_status` | `pending` · `ok`', '| `align_status` | `ok`')],
  ['SPEC-ERROR-CODES', (s) => s.replace('never generic 500s: `extract_failed`', 'never generic 500s: `extraction_failed`')],
  ['SPEC-SYNC-GRADE', (s) => s.replace('(H26-C3 — `unmeasured`', '(H26-C3 — `unmeasure`')],
  ['SPEC-SPAN-KIND', (s) => s.replace('//   dropped      ', '//   dropt        ')],
  // Derived from ALIGN_KEY_COUNT rather than pinned to a literal. The literal
  // was `**20 keys per language**` and went a NO-OP the day `incomplete_match`
  // moved the budget to 22 (H34-C2) — a specimen that silently stops testing is
  // the exact defect `--self-test` exists to make loud, so it is computed now.
  ['SPEC-ALIGN-KEY-COUNT', (s) => s.replace(
    `**${ALIGN_KEY_COUNT} keys per language**`, `**${ALIGN_KEY_COUNT + 1} keys per language**`)],
  ['SPEC-RENDITION-STATUS', (s) => s.replace('`status` (`pending｜queued', '`status` (`queued')],
  ['SPEC-RENDITION-STATUS-ANNOUNCED',
   (s) => s.replace('`segment_renditions.status` values (`blocked_credits`',
                    '`segment_renditions.status` values (`blocked_credit`')],
  ['SPEC-NO-ROUTE-ROW', (s) => s.replace('| **NO ROUTE. Sets', '| **Google / Gemini TTS. Sets')],
  ['SPEC-UNROUTED-LANG',
   (s) => s.replace('| **Any other language** |', '| `de`, standard voice | Some provider |\n| **Any other language** |')],
];

/**
 * Checks with no mutation, and WHY. J33-m1 was filed this round because two
 * harnesses claimed every control was asserted in both directions while a third
 * of them had no specimen. This list is COMPUTED from the tables above, so a
 * check added tomorrow with no mutation names itself here in the same run.
 */
const UNMUTATED_NOTES = {};

const DRIVE_OPTS = { allowWrites: true, allowCommit: true };

async function observeFixture(mutate, extra = {}) {
  const data = makeFixture();
  if (mutate) mutate(data);
  return drive(transportFor(data), { ...DRIVE_OPTS, ...extra });
}

async function selfTest() {
  const results = [];
  const record = (ok, msg) => results.push([ok, msg]);
  const specText = existsSync(SPEC_PATH) ? readFileSync(SPEC_PATH, 'utf8') : null;

  // ── leg 1 · baseline ───────────────────────────────────────────────────
  // The real S9 verdict, not a pinned one: this harness asserts against the
  // repository as it stands, the way doc-check mutates the real documents.
  const realS9 = await readS9();
  const baseObs = await observeFixture(null, { s9: realS9 });
  const base = runConformance(baseObs);
  const baseBad = base.filter((r) => r.state !== PASS);
  record(baseBad.length === 0,
    baseBad.length === 0 ? 'BASELINE: the conformant fixture passes every check'
      : `BASELINE: ${baseBad.length} check(s) are not green on a CONFORMANT fixture, so their mutations ` +
        `prove nothing — ${baseBad.map((r) => `${r.id} [${r.state}] ${r.detail}`).join(' | ')}`);
  const redAtBaseline = new Set(baseBad.map((r) => r.id));

  const baseSpec = specText ? runSpec(specText) : null;
  if (baseSpec) {
    const bad = baseSpec.filter((r) => r.state !== PASS);
    record(bad.length === 0,
      bad.length === 0 ? 'BASELINE: the vocabulary agrees with the spec'
        : `BASELINE: ${bad.map((r) => `${r.id} ${r.detail}`).join(' | ')}`);
    for (const r of bad) redAtBaseline.add(r.id);
  }

  // ── leg 2 · CTL-NO-VACUOUS ─────────────────────────────────────────────
  // Every check, against an observation that contains nothing. A check that
  // passes here passes because there is nothing to test, which is exactly the
  // `[ART-FIGURE]`-is-vacuous defect. There is no allowlist and there is no
  // exception.
  const vacuous = runConformance({}).filter((r) => r.state === PASS);
  record(vacuous.length === 0,
    vacuous.length === 0 ? 'CTL-NO-VACUOUS: no check passes over an empty observation'
      : `CTL-NO-VACUOUS: ${vacuous.map((r) => r.id).join(', ')} went GREEN with no backend at all`);

  // ── leg 3 · CTL-DEAD-BACKEND ───────────────────────────────────────────
  // A server that answers 404 to everything. Two checks legitimately survive it
  // (they assert the SHAPE of an error, and a coded 404 is a well-shaped error);
  // the allowlist is named here rather than left implicit.
  const DEAD_OK = ['A-NO-5XX', 'A-ERRORS-CODED'];
  const deadObs = await drive(async () => ({ status: 404, body: { code: 'not_found' } }),
    { ...DRIVE_OPTS, s9: realS9 });
  const deadPass = runConformance(deadObs).filter((r) => r.state === PASS).map((r) => r.id);
  const deadUnexpected = deadPass.filter((id) => !DEAD_OK.includes(id));
  record(deadUnexpected.length === 0,
    deadUnexpected.length === 0
      ? `CTL-DEAD-BACKEND: only ${DEAD_OK.join(' and ')} survive a 404-everything server, as documented`
      : `CTL-DEAD-BACKEND: ${deadUnexpected.join(', ')} passed against a server that answers nothing`);

  // ── leg 4 · the mutation battery ───────────────────────────────────────
  const covered = new Set();
  for (const [id, mutate, extra] of MUTATIONS) {
    covered.add(id);
    if (redAtBaseline.has(id)) {
      record(false, `${id}: ALREADY RED at baseline — a mutation cannot show a check firing on its own defect ` +
        'when it is already firing. Fix the baseline first.');
      continue;
    }
    const obs = await observeFixture(mutate, { s9: realS9, ...(extra ?? {}) });
    const hit = runConformance(obs).find((r) => r.id === id);
    if (!hit) { record(false, `${id}: no such check`); continue; }
    record(hit.state === FAIL,
      hit.state === FAIL ? id
        : `${id}: the mutation left it ${hit.state.toUpperCase()}, not FAIL — ` +
          'a check that goes UNESTABLISHED on its own defect is red for the wrong reason ' +
          `(${hit.detail})`);
  }
  for (const [id, mutate] of SPEC_MUTATIONS) {
    covered.add(id);
    if (!specText) { record(false, `${id}: the private spec is absent, so this leg could not be falsified`); continue; }
    if (redAtBaseline.has(id)) { record(false, `${id}: ALREADY RED at baseline`); continue; }
    const mutated = mutate(specText);
    if (mutated === specText) { record(false, `${id}: MUTATION WAS A NO-OP — the specimen no longer matches the spec`); continue; }
    const hit = runSpec(mutated).find((r) => r.id === id);
    record(hit?.state === FAIL,
      hit?.state === FAIL ? id : `${id}: the mutation left it ${hit?.state ?? 'missing'} (${hit?.detail ?? ''})`);
  }

  // ── leg 5 · the wire ───────────────────────────────────────────────────
  // The same fixture, over real HTTP, through the transport a live run uses.
  // Without this the driver's URL building, verbs and JSON handling would be the
  // one part of the harness nothing executes.
  {
    const data = makeFixture();
    const stub = await startStub(data);
    try {
      const obs = await drive(httpTransport(stub.origin, null), { ...DRIVE_OPTS, s9: realS9 });
      const bad = runConformance(obs).filter((r) => r.state !== PASS);
      record(bad.length === 0,
        bad.length === 0 ? 'CTL-WIRE: the HTTP driver reproduces the in-memory result exactly'
          : `CTL-WIRE: over HTTP, ${bad.map((r) => `${r.id} [${r.state}]`).join(', ')}`);
    } finally { await stub.close(); }
  }

  // ── leg 6 · the three ADR-0004 acceptance specimens, over HTTP ─────────
  // "A harness that passes while any of them is present has not been built."
  //
  // SPECIMEN 3 IS BUILT TO THE ADR, NOT TO THE ROADMAP, AND THE TWO DIFFER.
  // ADR-0004: "an `align_reason` with **no string in one of the three supported
  // languages**". Roadmap Phase 0: "no string in ANY supported language".
  // The roadmap's wording is satisfied only when a key is missing from all three
  // at once, so a catalogue with en and es and no fr would pass a harness built
  // to it — the exact H21-C1 shape, where the gate defining conformance mis-states
  // its own trigger. The ADR is the artifact that defines this harness, and it is
  // the stronger reading, so the specimen deletes ONE locale. The roadmap line
  // needs correcting; that is a document finding, not a harness setting.
  const SPECIMENS = [
    ['speech_blocker returns 0 for every document',
     (d) => { d.quote.speech_blocker = { blocked_language_unsupported: 0 }; d.quote.speech_available_segments = 12; },
     'A-SPEECH-BLOCKER-REACHABLE'],
    ['GET /voices?lang= returns an empty list with no reason',
     (d) => { d.noVoiceReason = null; },
     'A-VOICES-EMPTY-CARRIES-REASON'],
    ['an align state with no string in ONE of the three supported languages',
     (d) => { delete cat(d, 'fr')['unavailable+excessive_drop']; },
     'A-CATALOGUE-ALIGN-STATE-KEYS'],
  ];
  for (const [name, mutate, expect] of SPECIMENS) {
    const data = makeFixture(); mutate(data);
    const stub = await startStub(data);
    try {
      const obs = await drive(httpTransport(stub.origin, null), { ...DRIVE_OPTS, s9: realS9 });
      const rs = runConformance(obs);
      const hit = rs.find((r) => r.id === expect);
      record(hit?.state === FAIL, hit?.state === FAIL
        ? `ADR-0004 specimen: ${name} → ${expect} FAILS`
        : `ADR-0004 specimen NOT CAUGHT: ${name} → ${expect} was ${hit?.state ?? 'missing'}`);
    } finally { await stub.close(); }
  }

  // ── report ─────────────────────────────────────────────────────────────
  const failed = results.filter(([ok]) => !ok);
  console.log(`self-test: ${results.length - failed.length} passed, ${failed.length} failed`);
  console.log('  (each mutates the fixture or the spec and runs the SHIPPED checks over it)\n');
  for (const [, msg] of failed) console.log(`  FAIL  ${msg}`);

  const known = [...CHECKS.map((c) => c.id), ...SPEC_CHECKS.map((c) => c.id)];
  const unmutated = known.filter((id) => !covered.has(id));
  if (!failed.length) {
    console.log(`  ${covered.size} check IDs have a mutation and every one of them fires.`);
    console.log(`  plus 4 controls: BASELINE, CTL-NO-VACUOUS, CTL-DEAD-BACKEND, CTL-WIRE,`);
    console.log('  and the three ADR-0004 acceptance specimens, driven over HTTP.');
  }
  console.log(`\n  NOT mutated (${unmutated.length}): ${unmutated.length ? unmutated.join(', ') : '—'}`);
  for (const id of unmutated) if (UNMUTATED_NOTES[id]) console.log(`    ${id}: ${UNMUTATED_NOTES[id]}`);
  if (unmutated.length) console.log('  Those are verified by hand, not by this harness.');
  console.log('\n  A GREEN SELF-TEST IS NOT CONFORMANCE. It says the checks fire on constructed');
  console.log('  defects. Conformance needs a backend, and there is not one yet.');

  process.exit(failed.length ? 1 : 0);
}

// ── the report ───────────────────────────────────────────────────────────

function printBlock(title, lines) {
  console.log(`\n${title}`);
  for (const l of lines) console.log(l ? `  ${l}` : '');
}

function printResults(label, results) {
  console.log(`\n${label}`);
  const mark = { [PASS]: 'PASS', [FAIL]: 'FAIL', [UNEST]: '????' };
  for (const r of results) {
    console.log(`  ${mark[r.state]}  ${r.id.padEnd(42)} ${r.state === PASS ? '' : r.detail}`);
  }
}

async function main() {
  if (flag('list')) {
    console.log('CONTRACT — the vocabulary, re-derived from the spec:\n');
    for (const c of SPEC_CHECKS) console.log(`  ${c.id.padEnd(34)} ${c.title}`);
    console.log('\nCONFORMANCE — the §9 API surface:\n');
    for (const c of CHECKS) console.log(`  ${c.id.padEnd(42)} ${c.why}`);
    console.log(`\n${CHECKS.length} conformance checks · ${SPEC_CHECKS.length} contract checks`);
    process.exit(0);
  }
  if (flag('self-test')) return selfTest();

  const baseUrl = opt('base-url') ?? process.env.AUDIOMAX_BASE_URL ?? null;
  const useStub = flag('stub');

  console.log('audiomax API conformance harness — the Phase 0 accessibility gate (ADR-0004)');

  let obs = {};
  let mode;
  let stub = null;
  if (useStub) {
    mode = 'STUB — the built-in fixture, over HTTP. NOT an implementation.';
    stub = await startStub(makeFixture());
    obs = await drive(httpTransport(stub.origin, null),
      { allowWrites: true, allowCommit: true });
  } else if (baseUrl) {
    mode = `LIVE — ${baseUrl}`;
    obs = await drive(httpTransport(baseUrl, process.env.AUDIOMAX_TOKEN ?? null), {
      documentId: opt('document-id'),
      allowWrites: flag('allow-writes'),
      allowCommit: flag('allow-commit'),
    });
  } else {
    mode = 'NO BACKEND — nothing was driven, so nothing is established';
    obs.s9 = await readS9();
  }
  console.log(`mode: ${mode}`);
  if (stub) await stub.close();

  const results = runConformance(obs);
  const specText = existsSync(SPEC_PATH) ? readFileSync(SPEC_PATH, 'utf8') : null;
  const specResults = specText ? runSpec(specText) : null;

  if (specResults) printResults('CONTRACT — the vocabulary this harness asserts, re-derived from the spec:', specResults);
  else printBlock('CONTRACT — NOT VERIFIED', [
    `${SPEC_PATH} is absent (it is gitignored by owner decision), so the enumerations in`,
    'contract.mjs were not checked against the design. Every conformance result below is',
    'relative to a vocabulary nothing confirmed in this run.',
  ]);

  printResults('CONFORMANCE — the §9 API surface:', results);

  const tally = (rs, s) => rs.filter((r) => r.state === s).length;
  const cFail = tally(results, FAIL); const cUnest = tally(results, UNEST);
  const sFail = specResults ? tally(specResults, FAIL) : 0;
  const sUnest = specResults ? tally(specResults, UNEST) : 0;

  if (obs.skipped?.length) {
    printBlock('FLOWS NOT DRIVEN in this run (each leaves its checks UNESTABLISHED, which is red):',
      obs.skipped);
  }

  printBlock('WHAT THIS HARNESS CANNOT SEE', LIMITS);
  printBlock('WHERE IT ASSERTS A SHAPE THE SPEC DOES NOT STATE',
    ASSUMPTIONS.flatMap(([id, text]) => [`${id}`, `  ${text}`, '']));

  console.log('\nSUMMARY');
  console.log(`  contract     ${specResults ? `${tally(specResults, PASS)} pass · ${sFail} fail · ${sUnest} unestablished` : 'NOT VERIFIED (spec absent)'}`);
  console.log(`  conformance  ${tally(results, PASS)} pass · ${cFail} fail · ${cUnest} unestablished`);
  console.log(`  languages    ${LANGS.join(', ')} — every catalogue assertion is made in all three`);

  if (cFail + cUnest + sFail + sUnest === 0) {
    if (useStub) {
      // A green --stub run is a WIRE result. It says the driver, the checks and
      // a hand-written fixture agree with each other. Nothing here was measured
      // against audiomax, and this line exists so a green --stub can never be
      // pasted anywhere as a conformance result.
      console.log('\n  STUB ONLY. The harness drove its own fixture and agreed with itself.');
      console.log('  This is a wire test. It establishes NOTHING about audiomax, which is unimplemented.');
      console.log('  The gate is `--base-url=` against a real backend, and it has never been run.');
      process.exit(0);
    }
    if (!specResults) {
      console.log('\n  clean, but the vocabulary was never checked against the spec. Exit 2.');
      process.exit(2);
    }
    console.log('\n  clean. This says the backend does not FORECLOSE an accessible client.');
    console.log('  It does not say a blind user can use the product. Halo still cannot issue PASS.');
    process.exit(0);
  }
  console.log('\n  NOT CLEAN. An UNESTABLISHED check is red: its input was never obtained, so the');
  console.log('  disclosure it guards is not proven reachable. It is never a pass.');
  process.exit(1);
}

// PROBE_TEXT is exported for a live upload; referenced here so `--list` users can
// see it exists without reading drive.mjs.
if (flag('print-probe')) { console.log(PROBE_TEXT); process.exit(0); }

main().catch((err) => {
  console.error(`conformance: the harness itself failed — ${err?.stack ?? err}`);
  process.exit(1);
});
