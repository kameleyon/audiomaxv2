/**
 * contract.mjs — the vocabulary the conformance harness asserts against, and
 * the control that binds that vocabulary to the spec.
 *
 * WHY THIS FILE IS SEPARATE FROM THE CHECKS
 * J33-M2, filed this round: "a control redefined the shipped expression inside
 * the test, so changing the shipped threshold left the control green." There is
 * no shipped implementation to import from yet — `apps/`, `worker/` and
 * `aligner/` have `/health` and little else — so the strongest available form of
 * "import what you assert" is:
 *
 *   1. every enumeration lives in exactly ONE place (below), read by every check;
 *   2. `SPEC_CHECKS` re-derives those enumerations FROM THE SPEC at run time and
 *      fails when the two disagree — set equality, both directions, not
 *      "every token I listed appears somewhere in the document";
 *   3. the one predicate that IS already shipped — `voice_langs` ships empty —
 *      is obtained by EXECUTING `supabase/tests/verify_voice_langs.mjs` and
 *      reading its S9 verdict, never by re-writing its regex here.
 *
 * When an implementation exists, (1) must be replaced by importing the server's
 * own enums. Until then a divergence between this file and the spec is caught by
 * (2), and a divergence between this file and a future server is caught by
 * nothing. That is stated in LIMITS and printed on every run.
 */

/** Thrown by a check whose INPUT was never obtained. Never a pass. */
export class Unestablished extends Error {}

/** Read a required value out of an observation, or refuse to judge. */
export function need(value, what) {
  if (value === undefined || value === null) throw new Unestablished(what);
  return value;
}

// ── The vocabulary ───────────────────────────────────────────────────────
// Sources are named per line so SPEC_CHECKS and a reader can find the origin.

/** The three supported languages. `CLAUDE.md` audience rubric; `ht` is OUT. */
export const LANGS = ['en', 'es', 'fr'];

/** Languages §3.5 routes to a provider. Everything else hits the no-route row. */
export const ROUTED_LANGS = ['en', 'es', 'fr'];

/** A language deliberately outside §3.5 — used to reach the refusal path. */
export const UNROUTED_LANG = 'de';

/** §6.3 `align_status`. */
export const ALIGN_STATUS = ['pending', 'ok', 'degraded', 'unavailable'];

/**
 * §9 — the NINE causes. At most one per reason set.
 *
 * `incomplete_match` was added 2026-08-11 by `H34-C2`: the match step's residue
 * — a display word the bounded re-sync jumped over, or an observed word that
 * matched no display text — needed a segment-level cause, and ONE cause covers
 * both sides deliberately, because the two can co-occur in a segment and two
 * causes would make `{display, observation}` a reachable reason set with no key.
 * `SPEC-ALIGN-CAUSES` below re-derives this list from §9 at run time, so this
 * copy cannot drift from the document without going red.
 */
export const ALIGN_CAUSES = [
  'unsupported_language', 'no_transcriber', 'transcription_unreliable',
  'wrong_match', 'engine_error', 'low_confidence', 'transcript_mismatch',
  'excessive_drop', 'incomplete_match',
];

/** §9 — the one context value. At most one per reason set, cause optional. */
export const ALIGN_CONTEXT = ['voice_substituted'];

/** §7.2a — the whole `segment_renditions.status` domain (nine). */
export const RENDITION_STATUS = [
  'pending', 'queued', 'synthesizing', 'ready', 'failed',
  'blocked_credits', 'blocked_quota', 'blocked_provider', 'blocked_language_unsupported',
];

/**
 * §9 — the five the catalogue budgets, because they are the ones a user must be
 * TOLD about. `queued` and `synthesizing` are progress, not disclosure; demanding
 * a string for them would make the harness fail a conformant catalogue, and
 * folding them into the five would let a refusal ship without words.
 */
export const RENDITION_STATUS_ANNOUNCED = [
  'blocked_credits', 'blocked_quota', 'blocked_provider',
  'blocked_language_unsupported', 'failed',
];

/** §3.2 `SkipReason` (6). */
export const SKIP_REASON = [
  'footnote', 'page_number', 'citation', 'caption', 'toc_filler',
  'running_header',
];

/** §3.2 `InsertedReason` (8). */
export const INSERTED_REASON = [
  'table_preamble', 'table_cell_header', 'figure_no_description',
  'math_unnarratable', 'chapter_announcement', 'disclosure_summary',
  'table_cell', 'math_narration',
];

/** §3.2 `SpanReason` = SkipReason ∪ InsertedReason ∪ two. Sixteen. */
export const SPAN_REASON = [
  ...new Set([...SKIP_REASON, ...INSERTED_REASON, 'suppressed_narration', 'dropped_marker']),
];

/** §9.1 — the five `kind` values a client filters on. */
export const SPAN_KIND = ['skipped', 'undescribed', 'inserted', 'suppressed', 'dropped'];

/** §7.1a / §9 `sync_grade`. Four. */
export const SYNC_GRADE = ['unmeasured', 'provisional', 'at_or_above_bar', 'below_bar'];

/** §9 error codes. Nine, explicit, never a generic 500. */
export const ERROR_CODES = [
  'extract_failed', 'unsupported_source', 'ocr_failed', 'ocr_low_confidence',
  'insufficient_credits', 'provider_failed', 'document_too_large',
  'archive_rejected', 'url_blocked',
];

/**
 * §9 — the `align_*` catalogue budget: 19 reason sets + 2 splits + pending.
 *
 * 19 = 9 causes alone + 9 causes each with `voice_substituted` + `voice_substituted`
 * alone. Was 17/20 at eight causes; `incomplete_match` (`H34-C2`, 2026-08-11)
 * adds one cause, hence two reason sets and two keys.
 */
export const ALIGN_KEY_COUNT = 22;

/** §9.1 — the four address fields that make a disclosure POSITIONED. */
export const SPAN_ADDRESS_FIELDS = ['start_block_ord', 'end_block_ord', 'segment_ord', 'char_offset'];

// ── Catalogue key resolution, without inventing a key format ─────────────
// §9 says the catalogue is "keyed on `align_status` × the canonical reason set"
// and that "reason sets are sorted and joined into one key". It does not say
// with WHAT. A harness that pinned a separator would assert a contract the spec
// does not state, so key identity is resolved by TOKEN SET instead: split a key
// on everything that is not [a-z0-9_] and compare the resulting set. That is
// agnostic to `:`/`+`/`.`/`|`/`/` and still catches the real defect — a reason
// set with no single key (N4-C2), and a token with no key at all.
//
// RESIDUAL ASSUMPTION, and it is listed in LIMITS: the separator is not `_`.

/** The set of enum tokens a catalogue key addresses. */
export function keyTokens(key) {
  return new Set(String(key).split(/[^a-z0-9_]+/).filter(Boolean));
}

const sameSet = (a, b) => a.size === b.size && [...a].every((x) => b.has(x));

/** Keys in `messages` whose token set is exactly `tokens`. */
export function keysResolving(messages, tokens) {
  const want = new Set(tokens);
  return Object.keys(messages).filter((k) => sameSet(keyTokens(k), want));
}

// ── The one predicate that is already shipped ────────────────────────────
// S9 is Atlas's, it is committed, and it is the premise of
// A-SYNC-NO-AVAILABLE-WHILE-STORE-EMPTY. Executed, not reimplemented.
export const S9_COMMAND = ['node', 'supabase/tests/verify_voice_langs.mjs'];

/** Parse the S9 verdict out of that script's stdout. */
export function parseS9(stdout) {
  const m = String(stdout).match(/^\s*(PASS|FAIL)\s+S9\b(.*)$/m);
  if (!m) return null;
  return { pass: m[1] === 'PASS', claim: m[2].trim() };
}

// ── SPEC_CHECKS — the vocabulary above, re-derived from the document ─────
// Each leg parses the spec and compares SETS in both directions. `spec` is
// gitignored (owner decision), so when it is absent every leg is UNESTABLISHED
// and the run says so; it is never silently skipped.

const stripLineComments = (t) => t.split('\n').map((l) => l.replace(/\/\/.*$/, '')).join('\n');
const quoted = (t) => [...t.matchAll(/'([a-z_]+)'/g)].map((m) => m[1]);
const ticked = (t) => [...t.matchAll(/`([a-z_.]+)`/g)].map((m) => m[1]);

function diff(actual, expected) {
  const a = new Set(actual); const e = new Set(expected);
  const missing = [...e].filter((x) => !a.has(x));
  const extra = [...a].filter((x) => !e.has(x));
  if (!missing.length && !extra.length) return null;
  const parts = [];
  if (missing.length) parts.push(`in contract.mjs but NOT in the spec: ${missing.join(', ')}`);
  if (extra.length) parts.push(`in the spec but NOT in contract.mjs: ${extra.join(', ')}`);
  return parts.join(' · ');
}

/** A spec-derived set, or null when the anchor no longer matches. */
function derive(spec, re, extract, transform = (x) => x) {
  const m = spec.match(re);
  if (!m) return null;
  return transform(extract(stripLineComments(m[1])));
}

export const SPEC_CHECKS = [
  {
    id: 'SPEC-SKIP-REASON',
    title: '§3.2 `type SkipReason` matches SKIP_REASON exactly',
    run: (spec) => {
      const got = derive(spec, /type SkipReason =([\s\S]*?)\n\s*\ntype/, quoted);
      if (!got) throw new Unestablished('the `type SkipReason` union no longer parses');
      return diff(got, SKIP_REASON);
    },
  },
  {
    id: 'SPEC-INSERTED-REASON',
    title: '§3.2 `type InsertedReason` matches INSERTED_REASON exactly',
    run: (spec) => {
      const got = derive(spec, /type InsertedReason =([\s\S]*?)\n\s*\n\/\//, quoted);
      if (!got) throw new Unestablished('the `type InsertedReason` union no longer parses');
      return diff(got, INSERTED_REASON);
    },
  },
  {
    id: 'SPEC-SPAN-REASON-COUNT',
    title: '§9 states SpanReason has 16 members and SPAN_REASON has that many',
    run: (spec) => {
      const m = spec.match(/\*\*(\d+)\*\*\s+`SpanReason`/);
      if (!m) throw new Unestablished('the SpanReason count sentence no longer parses');
      return Number(m[1]) === SPAN_REASON.length ? null
        : `the spec says ${m[1]}; SPAN_REASON has ${SPAN_REASON.length}`;
    },
  },
  {
    id: 'SPEC-ALIGN-CAUSES',
    title: '§9 cause set matches ALIGN_CAUSES exactly, and the spec counts what it lists',
    run: (spec) => {
      const m = spec.match(/causes are `([^`]+)`\s*\(\*\*(\d+)\*\*/);
      if (!m) throw new Unestablished('the §9 cause enumeration no longer parses');
      const d = diff(m[1].split('｜'), ALIGN_CAUSES);
      if (d) return d;
      return Number(m[2]) === ALIGN_CAUSES.length ? null
        : `the spec counts ${m[2]} causes and enumerates ${ALIGN_CAUSES.length}`;
    },
  },
  {
    id: 'SPEC-ALIGN-STATUS',
    title: '§6.3 `align_status` row matches ALIGN_STATUS exactly',
    run: (spec) => {
      const got = derive(spec, /\|\s*`align_status`\s*\|([^|]+)\|/, ticked);
      if (!got) throw new Unestablished('the §6.3 `align_status` row no longer parses');
      return diff(got, ALIGN_STATUS);
    },
  },
  {
    id: 'SPEC-ERROR-CODES',
    title: '§9 error codes match ERROR_CODES exactly',
    run: (spec) => {
      const got = derive(spec, /\*\*Error codes\*\* are[^:]*:([\s\S]*?)\.\n/, ticked);
      if (!got) throw new Unestablished('the §9 error-code sentence no longer parses');
      return diff(got, ERROR_CODES);
    },
  },
  {
    id: 'SPEC-SYNC-GRADE',
    title: '§9 `sync_grade` values match SYNC_GRADE exactly',
    run: (spec) => {
      const got = derive(spec, /\(H26-C3 — ((?:`[a-z_]+`,?\s*)+)\)/, ticked);
      if (!got) throw new Unestablished('the §9 `sync_grade` enumeration no longer parses');
      return diff(got, SYNC_GRADE);
    },
  },
  {
    id: 'SPEC-SPAN-KIND',
    title: '§9.1 `kind` block matches SPAN_KIND exactly',
    run: (spec) => {
      const from = spec.indexOf('`reason` is typed SpanReason');
      const to = spec.indexOf('These are DISCLOSURE spans');
      if (from < 0 || to < 0 || to <= from) throw new Unestablished('the §9.1 kind block no longer parses');
      const got = [...spec.slice(from, to).matchAll(/^\s*\/\/\s{3}([a-z_]+)\s{2,}/gm)].map((m) => m[1]);
      return diff(got, SPAN_KIND);
    },
  },
  {
    id: 'SPEC-ALIGN-KEY-COUNT',
    title: '§9 budgets the same number of `align_*` catalogue keys as ALIGN_KEY_COUNT',
    run: (spec) => {
      const m = spec.match(/\*\*(\d+) keys per language\*\*/);
      if (!m) throw new Unestablished('the §9 catalogue budget sentence no longer parses');
      return Number(m[1]) === ALIGN_KEY_COUNT ? null
        : `the spec budgets ${m[1]} align_* keys; ALIGN_KEY_COUNT is ${ALIGN_KEY_COUNT}`;
    },
  },
  {
    id: 'SPEC-RENDITION-STATUS',
    title: '§7.2a `segment_renditions.status` domain matches RENDITION_STATUS exactly',
    run: (spec) => {
      // Anchored INSIDE §7.2a. Unanchored, the first `status` enum in the
      // document is `documents.status` (uploaded｜extracting｜…), and this leg
      // read that one and reported a divergence that did not exist — a guard
      // measuring the wrong table, caught by its own baseline.
      const from = spec.indexOf('### 7.2a');
      const to = spec.indexOf('### 7.2b');
      if (from < 0 || to < 0 || to <= from) throw new Unestablished('§7.2a no longer parses');
      const m = spec.slice(from, to).match(/`status`\s*\(`([^`]+)`\)/);
      if (!m) throw new Unestablished('the §7.2a `status` enumeration no longer parses');
      return diff(m[1].split('｜'), RENDITION_STATUS);
    },
  },
  {
    id: 'SPEC-RENDITION-STATUS-ANNOUNCED',
    title: '§9 budgets catalogue strings for exactly the five in RENDITION_STATUS_ANNOUNCED',
    run: (spec) => {
      const m = spec.match(/user-reachable `segment_renditions\.status` values \(([^)]+)\)/);
      if (!m) throw new Unestablished('the §9 announced-status sentence no longer parses');
      const d = diff(ticked(m[1]), RENDITION_STATUS_ANNOUNCED);
      if (d) return d;
      const stray = RENDITION_STATUS_ANNOUNCED.filter((s) => !RENDITION_STATUS.includes(s));
      return stray.length ? `announced but outside the status domain: ${stray.join(', ')}` : null;
    },
  },
  {
    id: 'SPEC-NO-ROUTE-ROW',
    title: '§3.5 still ends in a NO ROUTE row, so the refusal has a raiser',
    run: (spec) => {
      // J17-C1: the moment this table becomes total over languages,
      // `blocked_language_unsupported` has no reachable raiser and
      // A-SPEECH-BLOCKER-REACHABLE can never be satisfied by any document.
      const m = spec.match(/\|\s*\*\*Any other language\*\*\s*\|([^|]*)\|/);
      if (!m) throw new Unestablished('the §3.5 no-route row no longer parses');
      return /NO ROUTE/.test(m[1]) && /blocked_language_unsupported/.test(m[1]) ? null
        : 'the §3.5 last row no longer refuses with `blocked_language_unsupported`';
    },
  },
  {
    id: 'SPEC-UNROUTED-LANG',
    title: `the harness's unrouted probe language (\`${UNROUTED_LANG}\`) is genuinely unrouted`,
    run: (spec) => {
      // If someone adds `de` to §3.5, the probe stops reaching the refusal path
      // and A-SPEECH-BLOCKER-REACHABLE goes quietly unsatisfiable. The §3.5
      // table is the region searched, not the whole document.
      const from = spec.indexOf('### 3.5 Synthesize');
      const to = spec.indexOf('**J17-C1');
      if (from < 0 || to < 0) throw new Unestablished('§3.5 no longer parses');
      const table = spec.slice(from, to);
      return table.includes(`\`${UNROUTED_LANG}\``)
        ? `\`${UNROUTED_LANG}\` now appears in the §3.5 routing table — pick another unrouted probe language`
        : null;
    },
  },
];

// ── What this harness cannot see. Printed on every run. ──────────────────
export const LIMITS = [
  'It does NOT substitute for NVDA or VoiceOver. ADR-0004 is explicit: it answers only',
  'whether the backend FORECLOSES an accessible client. A real screen-reader transcript',
  'is still required before the product launches to blind users (Phase 10, Halo).',
  '',
  'It cannot see, and no green line here should be read as covering:',
  '  · whether a string is CORRECT, idiomatic, or grammatical in es/fr — it checks that a',
  '    string exists, is not the enum token, and is not a copy of the English. Proof grades copy.',
  '  · whether `sample_text` is actually IN `lang`, or whether `sample_url` plays.',
  '  · whether audio is audible, gapless, or correctly timed — that is SPIKE A and Phase 6.',
  '  · time-to-first-text as a NUMBER. It asserts text is served while audio is incomplete;',
  '    it sets no latency bound, because no implementation exists to measure one against.',
  '  · anything about a client: focus order, headings, rotor navigation, keyboard-only use.',
  '  · whether the catalogue key SEPARATOR is what a client expects — §9 does not state one,',
  '    so keys are resolved by token set, which assumes the separator is not `_`.',
  '  · whether the request bodies it sends are the ones the API will accept. Several are',
  '    ASSUMPTIONS (printed below) because §9 documents paths and payloads, not requests.',
  '  · a real backend, today. Nothing is implemented, so every conformance check is',
  '    UNESTABLISHED until one exists, and UNESTABLISHED is red here, never green.',
];

/**
 * Every place this harness asserts a shape the spec does not state. Printed on
 * every run and reported to the document owners. An assumption a reader cannot
 * see is indistinguishable from a contract.
 */
export const ASSUMPTIONS = [
  ['A-VOICES-EMPTY-CARRIES-REASON',
   '§9 names the empty `GET /voices?lang=` list as a defect (ADR-0004) but does not specify the ' +
   'payload that fixes it. This harness requires `{ voices: [], reason: "<token>" }` and requires ' +
   'the token to resolve in all three catalogues. Nexus must specify the real shape.'],
  ['A-VOICES-SAMPLE-AUDIBLE',
   '§9 says `sample_url` is "NULL only while the sample render is pending" and gives no field ' +
   'that says so. This harness requires `sample_status: "pending"` on a row whose `sample_url` is null.'],
  ['A-CATALOGUE-* (payload shape)',
   '§9 documents `GET /i18n/messages?locale=` and not its body. Assumed `{ locale, messages: {key: string} }`.'],
  ['A-CATALOGUE-* (key format)',
   '§9 says reason sets are "sorted and joined into one key" and names no separator. Keys are ' +
   'resolved by token set instead of by identity.'],
  ['A-QUOTE-SYNC-IDENTITY',
   '§8.2 writes the identity as `available + unmeasured + |segments with any blocker| == segments` ' +
   'and then works it as `27 + 12 + 3 = 42` — a SUM over `align_blocker`. The two differ if one ' +
   'segment can carry two blockers. The harness asserts the spec\'s own arithmetic (the sum).'],
  ['drive.mjs (POST /documents)',
   '§9 documents no request body for upload. The harness sends ' +
   '`{ source: "text", lang_hint, text }` and, in a live run, prefers `--document-id=` over uploading.'],
  ['drive.mjs (auth)',
   'No auth scheme is specified anywhere. `AUDIOMAX_TOKEN` is sent as a bearer token when set.'],
];
