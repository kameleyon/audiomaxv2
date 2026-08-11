/**
 * drive.mjs — turns a transport into ONE observation object.
 *
 * There is exactly one of these. The self-test's in-memory fixture, the stub
 * HTTP server and a live backend all go through this function, so a mutation
 * trial exercises the same request sequence a live run does. If the fixture
 * built observations directly, the mutations would be testing a shape the
 * driver never produces — which is the "test constructs its own input" failure
 * Halo found in doc-check v1.
 *
 * A transport is `async (method, path, body) => { status, body }`. It never
 * throws for an HTTP status; it throws only when the request could not be made,
 * and the driver records that as a missing observation, which every dependent
 * check reads as UNESTABLISHED (red), never as a pass.
 */

import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { S9_COMMAND, parseS9, ROUTED_LANGS, UNROUTED_LANG } from './contract.mjs';

const execFileP = promisify(execFile);

/**
 * The probe document. Self-authored, so the public-domain-only fixture policy
 * (§10, J-M6) is satisfied trivially. It exists to reach four paths at once:
 * a heading, a figure with no description, a table over the narration
 * threshold, and a passage in a language §3.5 does not route.
 */
export const PROBE_TEXT = [
  'Chapitre premier',
  '',
  'Le narrateur commence son récit par une remarque banale sur le temps qu\'il fait.',
  'Il cite une note en bas de page¹ et poursuit sans s\'interrompre.',
  '',
  '[Figure 1]',
  '',
  'Der folgende Absatz ist absichtlich auf Deutsch geschrieben, weil Deutsch in',
  'Abschnitt 3.5 keine Route hat und die Ablehnung erreichbar sein muss.',
  '',
  'Le tableau ci-dessous dépasse le seuil de narration.',
].join('\n');

const q = (params) => new URLSearchParams(params).toString();

/** Record one call. Never throws for a status; records `null` on a transport failure. */
async function call(t, method, path, body) {
  try {
    const res = await t(method, path, body);
    return { request: `${method} ${path}`, status: res.status, body: res.body };
  } catch (err) {
    return { request: `${method} ${path}`, status: null, body: null, transport_error: String(err?.message ?? err) };
  }
}

/** Ask the committed schema proof whether `voice_langs` still ships empty. */
export async function readS9() {
  try {
    const { stdout } = await execFileP(S9_COMMAND[0], S9_COMMAND.slice(1), { encoding: 'utf8' });
    return { parsed: parseS9(stdout), raw: stdout };
  } catch (err) {
    // A non-zero exit still carries stdout, and S9 may well be the PASS line in
    // a run some OTHER proof failed. Read it before giving up.
    const stdout = String(err?.stdout ?? '');
    const parsed = parseS9(stdout);
    if (parsed) return { parsed, raw: stdout, sibling_failure: true };
    return { error: String(err?.message ?? err).split('\n')[0], parsed: null };
  }
}

/**
 * Drive the documented §9 flows.
 *
 * `opts.allowWrites`  — upload, write preferences, post progress.
 * `opts.allowCommit`  — POST /render. It can spend credits; off by default,
 *                       exactly as verify_voice_langs refuses a remote host
 *                       without a second flag.
 * `opts.documentId`   — use an existing document instead of uploading.
 */
export async function drive(t, opts = {}) {
  const o = { skipped: [] };

  // ── 1. the document ──────────────────────────────────────────────────
  let docId = opts.documentId ?? null;
  if (!docId) {
    if (!opts.allowWrites) {
      o.skipped.push('POST /documents — needs --allow-writes, or pass --document-id=<id>');
      return o;
    }
    o.upload = await call(t, 'POST', '/documents',
      { source: 'text', lang_hint: 'fr', text: PROBE_TEXT, title: 'a11y conformance probe' });
    docId = o.upload.body?.document_id ?? o.upload.body?.id ?? null;
    if (!docId) return o;
  }
  o.document_id = docId;

  o.document = await call(t, 'GET', `/documents/${docId}`);
  o.blocks = await call(t, 'GET', `/documents/${docId}/blocks?${q({ from: 0, to: 200 })}`);

  // ── 2. the voice catalogue, including a language §3.5 does not route ──
  o.voices = {};
  for (const lang of [...ROUTED_LANGS, UNROUTED_LANG]) {
    o.voices[lang] = await call(t, 'GET', `/voices?${q({ lang })}`);
  }

  const docLang = o.document.body?.primary_lang ?? 'fr';
  const pick = (lang) => o.voices[lang]?.body?.voices?.[0]?.voice_id ?? null;
  const voiceId = pick(docLang) ?? pick('en') ?? null;
  o.quote_voice_id = voiceId;
  o.quote_voice_lang = pick(docLang) ? docLang : 'en';

  // ── 3. the pre-payment channel ───────────────────────────────────────
  o.credits = await call(t, 'GET', '/me/credits');
  if (voiceId) {
    o.quote = await call(t, 'GET', `/documents/${docId}/quote?${q({ scope: 'document', voice_id: voiceId })}`);
  } else {
    o.skipped.push('GET /quote — no voice_id was obtainable from GET /voices');
  }

  // ── 4. the committing route. Guarded: it can spend money. ────────────
  if (opts.allowCommit && voiceId) {
    o.renderStale = await call(t, 'POST', `/documents/${docId}/render`,
      { scope: 'document', kind: 're_render', voice_id: voiceId, quote_etag: 'W/"q:deliberately-stale"' });
    o.renderCommit = await call(t, 'POST', `/documents/${docId}/render`,
      { scope: 'document', kind: 're_render', voice_id: voiceId, quote_etag: o.quote?.body?.quote_etag ?? null });
  } else {
    o.skipped.push('POST /documents/:id/render — needs --allow-commit (it can spend credits)');
  }

  // ── 5. mid-session surfaces ──────────────────────────────────────────
  if (voiceId) {
    o.segments = await call(t, 'GET',
      `/documents/${docId}/segments?${q({ from: 0, to: 200, voice_id: voiceId })}`);
  }
  const tableOrd = (o.blocks.body?.blocks ?? []).find((b) => b.type === 'table')?.ord;
  if (tableOrd !== undefined) {
    o.narration = await call(t, 'GET', `/documents/${docId}/blocks/${tableOrd}/narration`);
  } else {
    o.skipped.push('GET /blocks/:ord/narration — the probe document served no table block');
  }
  if (opts.allowWrites) {
    o.progress = await call(t, 'POST', `/documents/${docId}/progress`,
      { segment_set_id: o.segments?.body?.segment_set_id ?? null, segment_ord: 0, offset_ms: 0,
        block_ord: 0, char_offset_in_block: 0, voice_id: voiceId });
  } else {
    o.skipped.push('POST /documents/:id/progress — needs --allow-writes');
  }

  // ── 6. the catalogue ─────────────────────────────────────────────────
  o.catalogue = {};
  for (const locale of ['en', 'es', 'fr']) {
    o.catalogue[locale] = await call(t, 'GET', `/i18n/messages?${q({ locale })}`);
  }

  // ── 7. the same manifest with every disclosure control turned OFF ────
  if (opts.allowWrites) {
    const before = o.document.body?.preferences ?? null;
    o.prefsOff = await call(t, 'PUT', '/me/preferences',
      { disclosure_verbosity: 'off', content_narration: 'off' });
    o.documentVerbosityOff = await call(t, 'GET', `/documents/${docId}`);
    o.prefsRestored = await call(t, 'PUT', '/me/preferences',
      { disclosure_verbosity: before?.disclosure_verbosity ?? 'full',
        content_narration: before?.content_narration ?? 'full' });
  } else {
    o.skipped.push('PUT /me/preferences + the verbosity=off manifest — needs --allow-writes');
  }

  // ── 8. the premise that is already shipped, obtained by executing it ─
  // `opts.s9` exists so `--self-test` can falsify a check whose input comes
  // from another process. It is never set on a live run.
  o.s9 = opts.s9 ?? await readS9();

  // ── 9. facts the checks need about the probe, taken from the API ─────
  // These are the API's OWN claims about the document. If the backend
  // mis-detects the German passage as `fr`, the premise reads 0 and
  // A-SPEECH-BLOCKER-REACHABLE goes UNESTABLISHED — red, not green.
  const segs = o.segments?.body?.segments ?? [];
  o.fixtureFacts = {
    unrouted_segment_count: segs.filter((s) => typeof s.lang === 'string' && !ROUTED_LANGS.includes(s.lang)).length,
  };

  return o;
}
