/**
 * checks.mjs — every assertion the conformance harness makes about the §9 API.
 *
 * A check returns `null` to pass, a STRING to fail, or throws `Unestablished`
 * when the input it judges was never obtained. Those are three states, not two:
 * an UNESTABLISHED check is RED. A harness that treated a missing backend as
 * "nothing to check" would be the `[ART-FIGURE]`-is-vacuous defect this project
 * has filed four times, and it is what `CTL-NO-VACUOUS` exists to prevent —
 * every check below is run against an EMPTY observation and must go red.
 *
 * Checks read ONE observation object built by `drive.mjs`. They never fetch, so
 * they are pure and mutation-testable.
 */

import {
  Unestablished, need,
  LANGS, ROUTED_LANGS, UNROUTED_LANG,
  ALIGN_STATUS, ALIGN_CAUSES, ALIGN_CONTEXT, RENDITION_STATUS, RENDITION_STATUS_ANNOUNCED,
  SPAN_REASON, SPAN_KIND, SPAN_ADDRESS_FIELDS, SYNC_GRADE, ERROR_CODES,
  keysResolving,
} from './contract.mjs';

const isInt = (v) => Number.isInteger(v);
const isStr = (v) => typeof v === 'string' && v.length > 0;
const sum = (obj) => Object.values(obj).reduce((n, v) => n + (Number(v) || 0), 0);

/** A response that must exist and must have answered 200. */
function ok200(res, what) {
  need(res, what);
  need(res.status, `${what} (no status recorded)`);
  if (res.status !== 200) return null;      // caller decides how to phrase it
  return need(res.body, `${what} (200 with no body)`);
}

/** Every response the run collected, flattened, for the sweeping checks. */
function allResponses(o) {
  const out = [];
  const walk = (node, path) => {
    if (!node || typeof node !== 'object') return;
    if (isInt(node.status) && 'body' in node) { out.push([path, node]); return; }
    for (const [k, v] of Object.entries(node)) walk(v, path ? `${path}.${k}` : k);
  };
  walk(o, '');
  return out;
}

/** Catalogue messages for one locale. */
function messagesFor(o, lang) {
  const res = need(o.catalogue?.[lang], `GET /i18n/messages?locale=${lang}`);
  if (res.status !== 200) return { fail: `GET /i18n/messages?locale=${lang} answered ${res.status}` };
  const body = need(res.body, `the ${lang} catalogue body`);
  const messages = need(body.messages, `\`messages\` in the ${lang} catalogue`);
  if (typeof messages !== 'object') throw new Unestablished(`the ${lang} catalogue \`messages\` is not an object`);
  return { messages };
}

/** Assert a token set resolves to exactly one key, in all three languages. */
function resolvesEverywhere(o, tokens, label) {
  const problems = [];
  for (const lang of LANGS) {
    const { messages, fail } = messagesFor(o, lang);
    if (fail) return fail;
    const hits = keysResolving(messages, tokens);
    if (hits.length === 0) problems.push(`${lang}: no key for ${label}`);
    else if (hits.length > 1) problems.push(`${lang}: ${hits.length} keys resolve ${label} (${hits.join(', ')})`);
    else if (!isStr(messages[hits[0]])) problems.push(`${lang}: the key for ${label} has an empty string`);
  }
  return problems.length ? problems.join(' · ') : null;
}

/**
 * Enum tokens the run actually OBSERVED, so the catalogue is checked against
 * reality rather than against a list this file could get wrong.
 *
 * `single` holds the tokens §9 budgets as STANDALONE keys — the five rendition
 * statuses, the sixteen SpanReasons and the four sync grades. `align_reason`
 * members are deliberately NOT here: §9 keys them on `align_status` × the reason
 * SET, so `low_confidence` alone is not a key and demanding one would make the
 * harness fail a conformant catalogue. Those go in `sets`.
 */
function observedTokens(o) {
  const segs = need(o.segments?.body?.segments, 'GET /documents/:id/segments — `segments`');
  const single = new Set();
  const sets = [];
  for (const s of segs) {
    if (RENDITION_STATUS_ANNOUNCED.includes(s.rendition_status)) single.add(s.rendition_status);
    if (Array.isArray(s.align_reason) && s.align_reason.length) {
      sets.push([s.align_status, ...[...s.align_reason].sort()]);
    }
  }
  const spans = o.document?.body?.skip_manifest?.spans ?? [];
  for (const sp of spans) if (isStr(sp.reason)) single.add(sp.reason);
  for (const lang of [...ROUTED_LANGS, UNROUTED_LANG]) {
    for (const row of o.voices?.[lang]?.body?.voices ?? []) {
      if (isStr(row.sync_grade)) single.add(row.sync_grade);
    }
  }
  return { single: [...single], sets };
}

export const CHECKS = [
  // ── The voice catalogue: the door every degraded-path remedy points at ──
  {
    id: 'A-VOICES-ROUTE-EXISTS',
    why: '§9 — `voices` was a table reachable by no route while four routes require a `voice_id`.',
    run: (o) => {
      const bad = [];
      for (const lang of ROUTED_LANGS) {
        const res = need(o.voices?.[lang], `GET /voices?lang=${lang}`);
        if (res.status !== 200) { bad.push(`${lang} answered ${res.status}`); continue; }
        if (!Array.isArray(res.body?.voices)) bad.push(`${lang} returned no \`voices\` array`);
      }
      return bad.length ? bad.join(' · ') : null;
    },
  },
  {
    id: 'A-VOICES-NONEMPTY-FOR-ROUTED-LANG',
    why: '§3.5 routes en/es/fr to a provider. A routed language with no voice is a remedy with no door.',
    run: (o) => {
      const bad = [];
      for (const lang of ROUTED_LANGS) {
        const body = ok200(need(o.voices?.[lang], `GET /voices?lang=${lang}`), `GET /voices?lang=${lang}`);
        if (!body) { bad.push(`${lang} did not answer 200`); continue; }
        if (!Array.isArray(body.voices) || body.voices.length === 0) bad.push(`${lang} returned an empty catalogue`);
      }
      return bad.length ? bad.join(' · ') : null;
    },
  },
  {
    id: 'A-VOICES-EMPTY-CARRIES-REASON',
    why: 'ADR-0004 acceptance specimen 2 — an empty list with NO REASON points at a door that does not exist.',
    run: (o) => {
      const probed = need(o.voices, 'any GET /voices response');
      const bad = [];
      let sawEmpty = false;
      for (const [lang, res] of Object.entries(probed)) {
        if (res?.status !== 200 || !Array.isArray(res.body?.voices)) continue;
        if (res.body.voices.length > 0) continue;
        sawEmpty = true;
        if (!isStr(res.body.reason)) bad.push(`lang=${lang} returned [] with no \`reason\``);
      }
      if (!sawEmpty) {
        throw new Unestablished(
          `no GET /voices response was empty, so the "empty with no reason" defect was never exercised — ` +
          `probe an unrouted language (this run used lang=${UNROUTED_LANG})`);
      }
      return bad.length ? bad.join(' · ') : null;
    },
  },
  {
    id: 'A-VOICES-EMPTY-REASON-TRANSLATED',
    why: 'An untranslated enum token is not a status message a user can receive (WCAG 4.1.3).',
    run: (o) => {
      const tokens = [];
      for (const res of Object.values(need(o.voices, 'any GET /voices response'))) {
        if (res?.status === 200 && Array.isArray(res.body?.voices) && res.body.voices.length === 0
            && isStr(res.body.reason)) tokens.push(res.body.reason);
      }
      if (!tokens.length) throw new Unestablished('no empty voice catalogue carried a reason to translate');
      const bad = tokens.map((t) => resolvesEverywhere(o, [t], `\`${t}\``)).filter(Boolean);
      return bad.length ? [...new Set(bad)].join(' · ') : null;
    },
  },
  {
    id: 'A-VOICES-ROW-FIELDS',
    why: '§9 — the three things a blind user needs to choose BEFORE paying, plus the identifying columns.',
    run: (o) => {
      const required = ['voice_id', 'provider', 'gender', 'is_clone', 'lang', 'sample_text',
                        'sync_pct', 'sync_matched_words', 'sync_measured_at'];
      const bad = [];
      let rows = 0;
      for (const lang of ROUTED_LANGS) {
        for (const row of need(o.voices?.[lang], `GET /voices?lang=${lang}`).body?.voices ?? []) {
          rows++;
          for (const f of required) if (!(f in row)) bad.push(`${lang}/${row.voice_id ?? '?'} has no \`${f}\``);
          if (!('sample_url' in row)) bad.push(`${lang}/${row.voice_id ?? '?'} has no \`sample_url\``);
        }
      }
      if (!rows) throw new Unestablished('no voice rows were returned for any routed language');
      return bad.length ? bad.slice(0, 8).join(' · ') : null;
    },
  },
  {
    id: 'A-VOICES-SYNC-GRADE-NEVER-NULL',
    why: '§9 — "`sync_grade` is never NULL in this payload": a bare verdict is still a verdict a user can compare.',
    run: (o) => {
      const bad = [];
      let rows = 0;
      for (const lang of ROUTED_LANGS) {
        for (const row of need(o.voices?.[lang], `GET /voices?lang=${lang}`).body?.voices ?? []) {
          rows++;
          if (row.sync_grade === null || row.sync_grade === undefined) bad.push(`${lang}/${row.voice_id} has a NULL sync_grade`);
          else if (!SYNC_GRADE.includes(row.sync_grade)) bad.push(`${lang}/${row.voice_id} sync_grade=${row.sync_grade}`);
        }
      }
      if (!rows) throw new Unestablished('no voice rows were returned for any routed language');
      return bad.length ? bad.slice(0, 8).join(' · ') : null;
    },
  },
  {
    id: 'A-VOICES-SAMPLE-AUDIBLE',
    why: 'R14-M1 — to compare twelve voices a blind user must HEAR them, not issue twelve quotes.',
    run: (o) => {
      const bad = [];
      let rows = 0;
      for (const lang of ROUTED_LANGS) {
        for (const row of need(o.voices?.[lang], `GET /voices?lang=${lang}`).body?.voices ?? []) {
          rows++;
          if (!isStr(row.sample_text)) bad.push(`${lang}/${row.voice_id} has no \`sample_text\``);
          if (!isStr(row.sample_url) && row.sample_status !== 'pending') {
            bad.push(`${lang}/${row.voice_id} has no \`sample_url\` and does not say the render is pending`);
          }
        }
      }
      if (!rows) throw new Unestablished('no voice rows were returned for any routed language');
      return bad.length ? bad.slice(0, 8).join(' · ') : null;
    },
  },

  // ── The refusal: it must be raised, announced, and translated ───────────
  {
    id: 'A-SPEECH-BLOCKER-REACHABLE',
    why: 'ADR-0004 acceptance specimen 1 — a `speech_blocker` that returns 0 for EVERY document has no raiser (J17-C1).',
    run: (o) => {
      const q = need(o.quote?.body, 'GET /documents/:id/quote body');
      const blocker = need(q.speech_blocker, '`speech_blocker` in the quote');
      const n = blocker.blocked_language_unsupported;
      if (!isInt(n)) return '`speech_blocker.blocked_language_unsupported` is missing or not an integer';
      const langs = need(o.fixtureFacts?.unrouted_segment_count,
        'how many segments of the probe document are in an unrouted language');
      if (langs < 1) throw new Unestablished('the probe document contains no unrouted-language segment');
      return n >= 1 ? null
        : `the probe document has ${langs} segment(s) in \`${UNROUTED_LANG}\`, which §3.5 refuses, ` +
          'and the quote reports blocked_language_unsupported: 0 — the counter has no reachable raiser';
    },
  },
  {
    id: 'A-SPEECH-IDENTITY',
    why: '§8.2 — "will I hear all of it?" is answerable only if the buckets partition the segments.',
    run: (o) => {
      const q = need(o.quote?.body, 'GET /documents/:id/quote body');
      const segments = need(q.segments, '`segments` in the quote');
      const avail = need(q.speech_available_segments, '`speech_available_segments`');
      const blocked = sum(need(q.speech_blocker, '`speech_blocker`'));
      return avail + blocked === segments ? null
        : `speech_available_segments (${avail}) + speech_blocker (${blocked}) = ${avail + blocked}, not ${segments}`;
    },
  },
  {
    id: 'A-BLOCKED-LANG-ANNOUNCED',
    why: '§3.5 no-route row — the refusal is an announced status, never silence and never a 500.',
    run: (o) => {
      const segs = need(o.segments?.body?.segments, 'GET /documents/:id/segments — `segments`');
      const refused = segs.filter((s) => s.rendition_status === 'blocked_language_unsupported');
      const unrouted = segs.filter((s) => isStr(s.lang) && !ROUTED_LANGS.includes(s.lang));
      if (!unrouted.length) throw new Unestablished('no segment in an unrouted language was served');
      if (refused.length !== unrouted.length) {
        const others = [...new Set(unrouted.map((s) => String(s.rendition_status)))];
        return `${unrouted.length} segment(s) are in an unrouted language and ${refused.length} carry ` +
          `\`blocked_language_unsupported\` — the rest report ${others.join(', ')}`;
      }
      const bad = segs.filter((s) => isStr(s.rendition_status) && !RENDITION_STATUS.includes(s.rendition_status));
      return bad.length ? `unknown rendition_status: ${[...new Set(bad.map((s) => s.rendition_status))].join(', ')}` : null;
    },
  },
  {
    id: 'A-BLOCKED-LANG-STRING',
    why: '§9 — "a refusal that cannot be announced is worse than a refusal." The user otherwise learns `3`.',
    run: (o) => resolvesEverywhere(o, ['blocked_language_unsupported'], '`blocked_language_unsupported`'),
  },

  // ── The quote: the pre-payment disclosure channel ───────────────────────
  {
    id: 'A-QUOTE-200-AT-ANY-BALANCE',
    why: '`CLAUDE.md` constraint 4 / N12-C1 — the user who cannot pay is the user this disclosure decides everything for.',
    run: (o) => {
      const res = need(o.quote, 'GET /documents/:id/quote');
      const balance = need(o.credits?.body?.balance, 'GET /me/credits — `balance`');
      const credits = o.quote?.body?.credits;
      if (res.status === 402) return 'GET /quote answered 402 — it must never refuse for balance; it debits nothing';
      if (res.status !== 200) return `GET /quote answered ${res.status}`;
      if (isInt(credits) && balance >= credits) {
        throw new Unestablished(
          `the account held ${balance} credits and the quote costs ${credits}, so the ZERO-BALANCE case ` +
          'was never exercised — run this against an account that cannot afford the render');
      }
      return null;
    },
  },
  {
    id: 'A-QUOTE-BALANCE-MAY-BE-NEGATIVE',
    why: '§8.2 — `balance_after` is an arithmetic result, not an authorization.',
    run: (o) => {
      const q = need(o.quote?.body, 'GET /documents/:id/quote body');
      const balance = need(o.credits?.body?.balance, 'GET /me/credits — `balance`');
      const credits = need(q.credits, '`credits` in the quote');
      const after = need(q.balance_after, '`balance_after` in the quote');
      if (after !== balance - credits) return `balance_after is ${after}; ${balance} - ${credits} = ${balance - credits}`;
      if (after >= 0) throw new Unestablished('balance_after was not negative, so clamping could not be observed');
      return null;
    },
  },
  {
    id: 'A-QUOTE-SYNC-IDENTITY',
    why: '§8.2 — "THAT IDENTITY IS THE POINT": it is what makes an unmeasured pair impossible to count as working.',
    run: (o) => {
      const q = need(o.quote?.body, 'GET /documents/:id/quote body');
      const segments = need(q.segments, '`segments` in the quote');
      const avail = need(q.word_sync_available_segments, '`word_sync_available_segments`');
      const unmeasured = need(q.word_sync_unmeasured_segments, '`word_sync_unmeasured_segments`');
      const blocked = sum(need(q.align_blocker, '`align_blocker`'));
      const total = avail + unmeasured + blocked;
      return total === segments ? null
        : `${avail} + ${unmeasured} + ${blocked} = ${total}, not ${segments} — a segment is in two buckets or none`;
    },
  },
  {
    id: 'A-QUOTE-FIELDS',
    why: '§8.2 — the pre-payment payload. A field a client cannot read is a disclosure that does not exist.',
    run: (o) => {
      const q = need(o.quote?.body, 'GET /documents/:id/quote body');
      const required = ['segments', 'quote_etag', 'display_characters', 'spoken_characters',
                        'inserted_characters', 'spoken_bytes', 'credits', 'balance_after',
                        'align_blocker', 'word_sync_available_segments', 'word_sync_unmeasured_segments',
                        'speech_blocker', 'speech_available_segments'];
      const missing = required.filter((f) => !(f in q));
      return missing.length ? `the quote has no ${missing.join(', ')}` : null;
    },
  },
  {
    id: 'A-QUOTE-INSERTED-PRICED-SEPARATELY',
    why: '§9.1 — the cost of disclosure must be visible BEFORE it is incurred, or a11y chatter is a silent charge.',
    run: (o) => {
      const q = need(o.quote?.body, 'GET /documents/:id/quote body');
      const inserted = need(q.inserted_characters, '`inserted_characters`');
      const spoken = need(q.spoken_characters, '`spoken_characters`');
      if (!isInt(inserted) || !isInt(spoken)) return '`inserted_characters` / `spoken_characters` are not integers';
      return inserted <= spoken ? null
        : `inserted_characters (${inserted}) exceeds spoken_characters (${spoken})`;
    },
  },
  {
    id: 'A-QUOTE-NO-ALIGN-PERMANENCE',
    why: 'N13-C1 — a per-document permanence scalar told a blind user to pay again for a different voice.',
    run: (o) => {
      const q = need(o.quote?.body, 'GET /documents/:id/quote body');
      return 'align_permanence' in q ? '`align_permanence` is back in the quote; N13-C1 deleted it' : null;
    },
  },
  {
    id: 'A-RENDER-409-ON-STALE-ETAG',
    why: '§9 — the number they agreed to is the number they are charged.',
    run: (o) => {
      const res = need(o.renderStale, 'POST /documents/:id/render with a stale quote_etag');
      if (res.status !== 409) return `a stale quote_etag was answered ${res.status}, not 409`;
      return res.body?.code === 'quote_changed' ? null
        : `409 carried code ${JSON.stringify(res.body?.code)}, not \`quote_changed\``;
    },
  },
  {
    id: 'A-RENDER-402-INSUFFICIENT',
    why: '§8.2 — 402 belongs to the COMMITTING route only. The asymmetry with the quote is the whole point.',
    run: (o) => {
      const res = need(o.renderCommit, 'POST /documents/:id/render with a fresh quote_etag');
      if (res.status !== 402) return `an unaffordable render was answered ${res.status}, not 402`;
      if (res.body?.code !== 'insufficient_credits') {
        return `402 carried code ${JSON.stringify(res.body?.code)}, not \`insufficient_credits\``;
      }
      const enqueued = res.body?.segments_enqueued;
      return enqueued === undefined || enqueued === 0 ? null
        : `402 also enqueued ${enqueued} segment(s) — never a partial render`;
    },
  },

  // ── Word sync: it must be disclosed as NOT established ──────────────────
  {
    id: 'A-SYNC-STORE-EMPTY',
    why: 'S9 in supabase/tests/verify_voice_langs.mjs, executed here. It is the PREMISE of the next check.',
    run: (o) => {
      const s9 = need(o.s9, 'the S9 verdict from verify_voice_langs.mjs');
      if (s9.error) throw new Unestablished(`verify_voice_langs.mjs could not be executed: ${s9.error}`);
      if (!s9.parsed) throw new Unestablished('verify_voice_langs.mjs ran but printed no S9 line');
      return s9.parsed.pass ? null
        : 'S9 is FAILING — `voice_langs` no longer ships empty. A-SYNC-NO-AVAILABLE-WHILE-STORE-EMPTY ' +
          'is written against an empty store and must be re-derived from the grades that now exist.';
    },
  },
  {
    id: 'A-SYNC-NO-AVAILABLE-WITHOUT-A-GRADED-PAIR',
    why: '§8.2 — the ONLY way to raise `word_sync_available_segments` is a row that clears §7.1a\'s evidence floor.',
    run: (o) => {
      // Derived entirely from the API, so it stays meaningful after grades are
      // written. It is the anti-optimism invariant: a missing measurement must
      // show up as a number the user is told, never as a working default.
      const q = need(o.quote?.body, 'GET /documents/:id/quote body');
      const avail = need(q.word_sync_available_segments, '`word_sync_available_segments`');
      if (avail === 0) return null;
      const lang = need(o.quote_voice_lang, 'the language the quote voice was chosen for');
      const voiceId = need(o.quote_voice_id, 'the voice the quote was taken for');
      const row = (o.voices?.[lang]?.body?.voices ?? []).find((v) => v.voice_id === voiceId);
      if (!row) throw new Unestablished(`the quoted voice ${voiceId} was not in GET /voices?lang=${lang}`);
      return row.sync_grade === 'at_or_above_bar' ? null
        : `the quote reports ${avail} segment(s) with working word sync while \`${voiceId}\`/${lang} reads ` +
          `\`${row.sync_grade}\` — an ungraded pair is being counted as working`;
    },
  },
  {
    id: 'A-SYNC-UNMEASURED-WHILE-UNSEEDED',
    why: 'The brief\'s disclosure requirement: `voice_langs` ships empty, every pair `unmeasured`, and the quote must say word sync is NOT ESTABLISHED.',
    run: (o) => {
      const s9 = need(o.s9, 'the S9 verdict from verify_voice_langs.mjs');
      if (!s9.parsed) throw new Unestablished('the S9 premise was never established');
      if (!s9.parsed.pass) {
        throw new Unestablished('`voice_langs` no longer ships empty of grades — this check\'s premise is gone. ' +
          'Re-derive it from the grades that now exist rather than deleting it.');
      }
      const rows = ROUTED_LANGS.flatMap((l) => o.voices?.[l]?.body?.voices ?? []);
      if (!rows.length) throw new Unestablished('no voice rows were served, so no grade could be read');
      const graded = rows.filter((r) => r.sync_grade !== 'unmeasured');
      if (graded.length) {
        throw new Unestablished(
          `${graded.length} voice row(s) already carry a grade (${[...new Set(graded.map((r) => r.sync_grade))].join(', ')}) ` +
          'even though no migration seeds one — a producer has run, so "ships unmeasured" no longer describes this system');
      }
      const q = need(o.quote?.body, 'GET /documents/:id/quote body');
      const avail = need(q.word_sync_available_segments, '`word_sync_available_segments`');
      const unmeasured = need(q.word_sync_unmeasured_segments, '`word_sync_unmeasured_segments`');
      const problems = [];
      if (avail !== 0) problems.push(`the quote claims ${avail} segment(s) have working word sync while every pair reads \`unmeasured\``);
      if (unmeasured === 0) problems.push('no segment landed in `word_sync_unmeasured_segments`, so the user is never told sync is unestablished');
      return problems.length ? problems.join(' · ') : null;
    },
  },
  {
    id: 'A-SYNC-GRADE-STRINGS',
    why: 'H26-C3 — otherwise `word_sync_unmeasured_segments` is an integer with no sentence, and the user learns `12`.',
    run: (o) => {
      const bad = SYNC_GRADE.map((g) => resolvesEverywhere(o, [g], `\`${g}\``)).filter(Boolean);
      return bad.length ? bad.join(' · ') : null;
    },
  },

  // ── Text before audio ──────────────────────────────────────────────────
  {
    id: 'A-TEXT-BEFORE-AUDIO',
    why: '`CLAUDE.md` constraint 3 / §3.7 — reading never waits on synthesis.',
    run: (o) => {
      const doc = need(o.document?.body, 'GET /documents/:id body');
      const blocks = need(o.blocks, 'GET /documents/:id/blocks');
      need(doc.text_ready_at, '`text_ready_at` on the document');
      const audioReady = doc.audio_ready;
      if (audioReady !== false) {
        throw new Unestablished(
          'the probe document already has complete audio, so "text served while audio is incomplete" ' +
          'was never exercised — run against a freshly extracted document');
      }
      if (blocks.status !== 200) return `GET /blocks answered ${blocks.status} while text_ready_at was set`;
      const list = blocks.body?.blocks;
      if (!Array.isArray(list) || list.length === 0) return 'GET /blocks answered 200 with no blocks';
      // The request the driver issued carries no voice_id and no rendition, so a
      // 200 here IS "text served without audio". Asserted over the recorded
      // request rather than assumed, so a future driver that starts sending one
      // makes this check say so instead of quietly weakening.
      if (/voice_id=/.test(String(blocks.request))) {
        return 'the blocks request carried a voice_id, so this run did not establish that reading is ungated by a rendition';
      }
      return null;
    },
  },
  {
    id: 'A-DOCUMENT-OMITS-BLOCKS',
    why: 'R4-M11 — a 2,000-page PDF cannot ship its blocks in one response, and time-to-first-text is hard.',
    run: (o) => {
      const doc = need(o.document?.body, 'GET /documents/:id body');
      return 'blocks' in doc ? 'GET /documents/:id returned `blocks`; the paginated route is the only one' : null;
    },
  },
  {
    id: 'A-TEXT-A11Y-FIDELITY',
    why: 'H-M9 — heading level, language, alt text and table structure must SURVIVE extraction or no client can invent them.',
    run: (o) => {
      const list = need(o.blocks?.body?.blocks, 'GET /documents/:id/blocks — `blocks`');
      if (!list.length) throw new Unestablished('no blocks were returned');
      const bad = [];
      for (const b of list) {
        if (!isStr(b.lang)) bad.push(`block ${b.ord} has no \`lang\``);
        if (b.type === 'heading' && !isInt(b.heading_level)) bad.push(`heading block ${b.ord} has no \`heading_level\``);
        if (b.type === 'figure' && !('alt_text' in b)) bad.push(`figure block ${b.ord} has no \`alt_text\` field`);
        if (b.type === 'table' && !Array.isArray(b.rows)) bad.push(`table block ${b.ord} has no row structure`);
      }
      const kinds = new Set(list.map((b) => b.type));
      for (const k of ['heading', 'figure', 'table']) {
        if (!kinds.has(k)) bad.push(`the probe document served no \`${k}\` block, so its fidelity is untested`);
      }
      return bad.length ? bad.slice(0, 8).join(' · ') : null;
    },
  },

  // ── §9.1 disclosure spans: positioned, not tallied ──────────────────────
  {
    id: 'A-SPANS-POSITIONED',
    why: '§9.1 — a document-level tally does nothing for someone at minute 47 who needs "three footnotes skipped here."',
    run: (o) => {
      const spans = need(o.document?.body?.skip_manifest?.spans, '`skip_manifest.spans`');
      if (!spans.length) throw new Unestablished('the probe document disclosed no spans');
      const bad = [];
      for (const [i, sp] of spans.entries()) {
        for (const f of SPAN_ADDRESS_FIELDS) if (!isInt(sp[f])) bad.push(`span ${i} (${sp.reason}) has no integer \`${f}\``);
      }
      return bad.length ? bad.slice(0, 8).join(' · ') : null;
    },
  },
  {
    id: 'A-SPANS-KIND-AND-REASON-DOMAIN',
    why: 'N8-C1 — a span with no `kind` is lost by a client filtering on kind, and the channel goes silent again.',
    run: (o) => {
      const spans = need(o.document?.body?.skip_manifest?.spans, '`skip_manifest.spans`');
      if (!spans.length) throw new Unestablished('the probe document disclosed no spans');
      const bad = [];
      for (const [i, sp] of spans.entries()) {
        if (!SPAN_KIND.includes(sp.kind)) bad.push(`span ${i} kind=${JSON.stringify(sp.kind)}`);
        if (!SPAN_REASON.includes(sp.reason)) bad.push(`span ${i} reason=${JSON.stringify(sp.reason)}`);
      }
      return bad.length ? bad.slice(0, 8).join(' · ') : null;
    },
  },
  {
    id: 'A-SPANS-TOTALS-KEYED-BY-REASON',
    why: 'N8-M7 — three spellings of one reason, and a client keying on span.reason got `undefined`.',
    run: (o) => {
      const manifest = need(o.document?.body?.skip_manifest, '`skip_manifest`');
      const totals = need(manifest.totals, '`skip_manifest.totals`');
      const spans = need(manifest.spans, '`skip_manifest.spans`');
      if (!spans.length) throw new Unestablished('the probe document disclosed no spans');
      const bad = [];
      for (const k of Object.keys(totals)) if (!SPAN_REASON.includes(k)) bad.push(`totals key \`${k}\` is not a SpanReason`);
      for (const r of new Set(spans.map((s) => s.reason))) {
        if (!(r in totals)) bad.push(`\`${r}\` is positioned in spans and absent from totals`);
      }
      return bad.length ? bad.slice(0, 8).join(' · ') : null;
    },
  },
  {
    id: 'A-SPANS-DROPPED-ONE-PER-MARKER',
    why: 'N9-C6 — 18 markers across 52 blocks aggregated into one address is the tally §9.1 forbids.',
    run: (o) => {
      const spans = need(o.document?.body?.skip_manifest?.spans, '`skip_manifest.spans`');
      const dropped = spans.filter((s) => s.kind === 'dropped');
      if (!dropped.length) throw new Unestablished('the probe document dropped no markers');
      const bad = dropped.filter((s) => s.count !== 1)
        .map((s) => `a dropped span at segment ${s.segment_ord}/${s.char_offset} has count ${s.count}`);
      return bad.length ? bad.slice(0, 5).join(' · ') : null;
    },
  },
  {
    id: 'A-SPANS-SURVIVE-VERBOSITY-OFF',
    why: '§9.1 — "no level of either control may remove the positional record." Otherwise it is silent data loss.',
    run: (o) => {
      const full = need(o.document?.body?.skip_manifest?.spans, '`skip_manifest.spans` at default verbosity');
      const off = need(o.documentVerbosityOff?.body?.skip_manifest?.spans,
        '`skip_manifest.spans` with disclosure_verbosity=off and content_narration=off');
      if (!full.length) throw new Unestablished('the probe document disclosed no spans to lose');
      // ADDRESS only. §9.1 lets `kind`/`reason` change when a control withholds
      // content (`inserted` becomes `suppressed`), so comparing those would
      // reject a backend for obeying the spec. What may never move is the
      // POSITIONAL RECORD — "a user must always be able to learn that something
      // is there, even when they have chosen not to hear it."
      const addr = (s) => `${s.start_block_ord}/${s.segment_ord}:${s.char_offset}`;
      const kept = new Set(off.map(addr));
      const lost = full.map(addr).filter((a) => !kept.has(a));
      return lost.length ? `${lost.length} positioned disclosure(s) vanished at verbosity=off: ${lost.slice(0, 4).join(', ')}` : null;
    },
  },
  {
    id: 'A-SEGMENTS-PROVENANCE',
    why: 'H-B1/R item 2 — v2 put the disclosure channel at the wrong MOMENT in the session.',
    run: (o) => {
      const segs = need(o.segments?.body?.segments, 'GET /documents/:id/segments — `segments`');
      if (!segs.length) throw new Unestablished('no segments were served');
      const bad = [];
      for (const s of segs) {
        if (!isInt(s.start_block_ord)) bad.push(`segment ${s.ord} has no \`start_block_ord\``);
        if (!isInt(s.end_block_ord)) bad.push(`segment ${s.ord} has no \`end_block_ord\``);
        if (!Array.isArray(s.skipped_block_ords)) bad.push(`segment ${s.ord} has no \`skipped_block_ords[]\``);
        if (!Array.isArray(s.block_start_offsets)) bad.push(`segment ${s.ord} has no \`block_start_offsets[]\``);
      }
      return bad.length ? bad.slice(0, 8).join(' · ') : null;
    },
  },

  // ── Alignment disclosure on the segments route ──────────────────────────
  {
    id: 'A-SEGMENTS-BOTH-THRESHOLDS',
    why: 'J16-M3 / J15-C4 — a client given one bound and told to apply it to a different quantity cannot comply.',
    run: (o) => {
      const body = need(o.segments?.body, 'GET /documents/:id/segments body');
      const m = body.match_conf_threshold;
      const a = body.align_conf_threshold;
      const bad = [];
      if (typeof m !== 'number') bad.push('no `match_conf_threshold` (the per-word highlight bound)');
      if (typeof a !== 'number') bad.push('no `align_conf_threshold` (the segment-level degraded bound)');
      return bad.length ? bad.join(' · ') : null;
    },
  },
  {
    id: 'A-ALIGN-REASON-IS-ARRAY',
    why: 'N4-C2 — a substituted-voice path produces ["voice_substituted","low_confidence"] BY DESIGN.',
    run: (o) => {
      const segs = need(o.segments?.body?.segments, 'GET /documents/:id/segments — `segments`');
      if (!segs.length) throw new Unestablished('no segments were served');
      const bad = [];
      for (const s of segs) {
        if (!ALIGN_STATUS.includes(s.align_status)) bad.push(`segment ${s.ord} align_status=${JSON.stringify(s.align_status)}`);
        if (!Array.isArray(s.align_reason)) { bad.push(`segment ${s.ord} align_reason is not an array`); continue; }
        const causes = s.align_reason.filter((r) => ALIGN_CAUSES.includes(r));
        const ctx = s.align_reason.filter((r) => ALIGN_CONTEXT.includes(r));
        const junk = s.align_reason.filter((r) => !ALIGN_CAUSES.includes(r) && !ALIGN_CONTEXT.includes(r));
        if (junk.length) bad.push(`segment ${s.ord} has unknown reason(s) ${junk.join(', ')}`);
        if (causes.length > 1) bad.push(`segment ${s.ord} carries ${causes.length} causes; §9 bounds it at one`);
        if (ctx.length > 1) bad.push(`segment ${s.ord} carries ${ctx.length} contexts; §9 bounds it at one`);
      }
      return bad.length ? bad.slice(0, 8).join(' · ') : null;
    },
  },
  {
    id: 'A-DEGRADED-IS-200',
    why: 'H-C3 — v1 made a degraded segment simultaneously ready and not, so a client refused to play good audio.',
    run: (o) => {
      const res = need(o.segments, 'GET /documents/:id/segments');
      if (res.status !== 200) return `GET /segments answered ${res.status}`;
      const segs = need(res.body?.segments, '`segments`');
      const degraded = segs.filter((s) => s.align_status === 'degraded');
      if (!degraded.length) throw new Unestablished('no degraded segment was served, so H-C3 was not exercised');
      const bad = degraded.filter((s) => !isStr(s.audio_url))
        .map((s) => `degraded segment ${s.ord} has no audio_url`);
      return bad.length ? bad.join(' · ') : null;
    },
  },

  // ── The message catalogue ──────────────────────────────────────────────
  {
    id: 'A-CATALOGUE-LOCALES',
    why: 'ADR-0004 acceptance specimen 3 — a status with NO STRING IN ONE OF THE THREE is the defect.',
    run: (o) => {
      const sets = {};
      for (const lang of LANGS) {
        const { messages, fail } = messagesFor(o, lang);
        if (fail) return fail;
        sets[lang] = new Set(Object.keys(messages));
      }
      const union = new Set(LANGS.flatMap((l) => [...sets[l]]));
      const bad = [];
      for (const lang of LANGS) {
        const missing = [...union].filter((k) => !sets[lang].has(k));
        if (missing.length) bad.push(`${lang} is missing ${missing.length} key(s): ${missing.slice(0, 4).join(', ')}`);
      }
      return bad.length ? bad.join(' · ') : null;
    },
  },
  {
    id: 'A-CATALOGUE-COVERS-EMITTED-TOKENS',
    why: '§6.3 — an untranslated enum token is not a status message a user can receive. Derived from what the API EMITTED.',
    run: (o) => {
      const { single } = observedTokens(o);
      if (!single.length) throw new Unestablished('the run observed no standalone enum token to look up');
      const bad = single.map((t) => resolvesEverywhere(o, [t], `\`${t}\``)).filter(Boolean);
      return bad.length ? bad.slice(0, 6).join(' · ') : null;
    },
  },
  {
    id: 'A-CATALOGUE-ALIGN-STATE-KEYS',
    why: '§9 — the catalogue is keyed on `align_status` × the reason SET. A state the API emits and the catalogue cannot address is silence.',
    run: (o) => {
      const { sets } = observedTokens(o);
      if (!sets.length) throw new Unestablished('no align state carrying a reason was served');
      const seen = new Set();
      const bad = [];
      for (const s of sets) {
        const label = `{${s.join(' + ')}}`;
        if (seen.has(label)) continue;
        seen.add(label);
        const problem = resolvesEverywhere(o, s, label);
        if (problem) bad.push(problem);
      }
      return bad.length ? bad.slice(0, 4).join(' · ') : null;
    },
  },
  {
    id: 'A-CATALOGUE-COMPOUND-KEY',
    why: 'N4-C2 / R4-M1 — ["voice_substituted","low_confidence"] is the state the spec calls LIKELIEST, and concatenating two translated tokens produces ungrammatical fr/es.',
    run: (o) => {
      const { sets } = observedTokens(o);
      const multi = sets.filter((s) => s.length > 2);   // status + two or more reasons
      if (!multi.length) {
        throw new Unestablished('no multi-reason align state was served, so the compound key is untested — ' +
          'the substituted-voice path (`voice_substituted` + a cause) is the one to exercise');
      }
      const bad = multi.map((s) => resolvesEverywhere(o, s, `{${s.join(' + ')}}`)).filter(Boolean);
      return bad.length ? [...new Set(bad)].slice(0, 4).join(' · ') : null;
    },
  },
  {
    id: 'A-CATALOGUE-LOW-CONF-SPLIT',
    why: 'N8-M3 / Phase 10 pass criterion — "highlight the confident spans" and "highlighting is off" must be tellable apart.',
    run: (o) => {
      const problems = [];
      for (const lang of LANGS) {
        const { messages, fail } = messagesFor(o, lang);
        if (fail) return fail;
        const d = keysResolving(messages, ['degraded', 'low_confidence']);
        const u = keysResolving(messages, ['unavailable', 'low_confidence']);
        if (d.length !== 1 || u.length !== 1) {
          problems.push(`${lang}: degraded+low_confidence resolves ${d.length} key(s), unavailable+low_confidence ${u.length}`);
          continue;
        }
        if (messages[d[0]] === messages[u[0]]) problems.push(`${lang}: both states say exactly the same sentence`);
      }
      return problems.length ? problems.join(' · ') : null;
    },
  },
  {
    id: 'A-CATALOGUE-PENDING-KEY',
    why: 'J17-M5 — every rendition passes through `pending`, and it carries no reason, so it fell outside the key.',
    run: (o) => resolvesEverywhere(o, ['pending'], '`align_status: pending`'),
  },
  {
    id: 'A-CATALOGUE-ERROR-CODES',
    why: '§9 lists nine error codes. The roadmap enumerated eight, and the one an extraction failure raises had no string.',
    run: (o) => {
      const bad = ERROR_CODES.map((c) => resolvesEverywhere(o, [c], `\`${c}\``)).filter(Boolean);
      return bad.length ? bad.slice(0, 4).join(' · ') : null;
    },
  },
  {
    id: 'A-CATALOGUE-NO-TOKEN-ECHO',
    why: '§6.3 — a catalogue whose value is its own key has not been translated; it has been renamed.',
    run: (o) => {
      const bad = [];
      for (const lang of LANGS) {
        const { messages, fail } = messagesFor(o, lang);
        if (fail) return fail;
        for (const [k, v] of Object.entries(messages)) {
          if (!isStr(v)) { bad.push(`${lang}/${k} has no string`); continue; }
          if (v.trim() === k) bad.push(`${lang}/${k} echoes its own key`);
          else if (/^[a-z0-9_]+$/.test(v.trim())) bad.push(`${lang}/${k} is a bare enum token, not a sentence`);
        }
      }
      return bad.length ? bad.slice(0, 6).join(' · ') : null;
    },
  },
  {
    id: 'A-CATALOGUE-NOT-STUBBED-FROM-EN',
    why: 'A copy of the English string is an untranslated string wearing a locale header (WCAG 3.1.2 in the client that renders it).',
    run: (o) => {
      const per = {};
      for (const lang of LANGS) {
        const { messages, fail } = messagesFor(o, lang);
        if (fail) return fail;
        per[lang] = messages;
      }
      // Scoped to sentences, not labels: a one- or two-word string can legitimately
      // be identical across languages, and flagging it would be a false positive
      // this harness would then be trained to ignore.
      const bad = [];
      for (const [k, en] of Object.entries(per.en)) {
        if (!isStr(en) || en.trim().split(/\s+/).length < 3) continue;
        for (const lang of ['es', 'fr']) {
          if (per[lang][k] === en) bad.push(`${lang}/${k} is byte-identical to the English sentence`);
        }
      }
      return bad.length ? `${bad.length} untranslated string(s): ${bad.slice(0, 4).join(', ')}` : null;
    },
  },

  // ── Mid-session and remaining routes ───────────────────────────────────
  {
    id: 'A-PROGRESS-RESOLUTION',
    why: '§9 — cross-device resume must say WHICH anchor resolved, or a user cannot tell exact from approximate.',
    run: (o) => {
      const res = need(o.progress, 'POST /documents/:id/progress');
      if (res.status !== 200) return `POST /progress answered ${res.status}`;
      const r = res.body?.progress_resolution;
      return r === 'exact' || r === 'block_approximate' ? null
        : `progress_resolution is ${JSON.stringify(r)}; §9 defines exact | block_approximate`;
    },
  },
  {
    id: 'A-NARRATION-ROUTE',
    why: 'R5-C8 — without it a table over the §3.8 threshold is unreachable in BOTH channels for a blind reader.',
    run: (o) => {
      const res = need(o.narration, 'GET /documents/:id/blocks/:ord/narration');
      if (res.status !== 200) return `the narration route answered ${res.status}`;
      const body = need(res.body, 'the narration body');
      if (!isStr(body.text)) return 'the narration route returned no `text`';
      if (!isStr(body.lang)) return 'the narration route returned no `lang`';
      return null;
    },
  },
  {
    id: 'A-NO-5XX',
    why: '§9 — "error codes are explicit, never generic 500s."',
    run: (o) => {
      const all = allResponses(o);
      if (!all.length) throw new Unestablished('no responses were collected');
      const bad = all.filter(([, r]) => r.status >= 500).map(([p, r]) => `${p} answered ${r.status}`);
      return bad.length ? bad.slice(0, 6).join(' · ') : null;
    },
  },
  {
    id: 'A-ERRORS-CODED',
    why: '§9 — a refusal a client cannot branch on is a refusal a user cannot be told about.',
    run: (o) => {
      const all = allResponses(o);
      if (!all.length) throw new Unestablished('no responses were collected');
      const errors = all.filter(([, r]) => r.status >= 400);
      if (!errors.length) throw new Unestablished('the run produced no error response to inspect');
      const bad = errors.filter(([, r]) => !isStr(r.body?.code)).map(([p, r]) => `${p} (${r.status}) carries no \`code\``);
      return bad.length ? bad.slice(0, 6).join(' · ') : null;
    },
  },
];
