/**
 * fixture.mjs — a CONFORMANT backend, and the mutations that break it one
 * assertion at a time.
 *
 * READ THIS BEFORE TRUSTING A GREEN SELF-TEST.
 * This file is not an implementation and it is not evidence about one. It is
 * the specimen a mutation battery needs: `--self-test` proves each check fires
 * on its own defect by breaking THIS and running the SHIPPED checks over it.
 * That establishes the checks work. It establishes nothing whatever about
 * audiomax, because audiomax does not exist yet.
 *
 * The fixture answers requests; it never builds an observation. `drive.mjs`
 * builds every observation, from here, from the stub server, and from a live
 * backend, so a mutation exercises the real request sequence.
 */

import {
  ALIGN_CAUSES, ERROR_CODES, RENDITION_STATUS, SPAN_REASON, SYNC_GRADE,
} from './contract.mjs';

// ── the catalogue, generated from the vocabulary so it cannot drift ──────
// §9 budgets 22 align_* keys: 19 reason sets, +2 because `align_status` splits
// `low_confidence`, +1 for `pending`. Built here rather than typed out, so a
// change to ALIGN_CAUSES changes the specimen too — which is how the ninth
// cause, `incomplete_match` (H34-C2, 2026-08-11), reached this fixture without
// anyone editing it. The count in this comment is the only part that had to be
// touched, and that is the argument for generating the rest.
const STATUS_OF_CAUSE = {
  unsupported_language: ['unavailable'],
  no_transcriber: ['unavailable'],
  transcription_unreliable: ['degraded'],
  wrong_match: ['degraded'],
  engine_error: ['unavailable'],
  low_confidence: ['degraded', 'unavailable'],   // §6.3: behaviourally different
  transcript_mismatch: ['unavailable'],
  excessive_drop: ['unavailable'],
};

export function alignKeys() {
  const keys = ['pending', 'ok+voice_substituted'];
  for (const cause of ALIGN_CAUSES) {
    for (const status of STATUS_OF_CAUSE[cause] ?? ['unavailable']) {
      keys.push(`${status}+${cause}`);
      keys.push(`${status}+${cause}+voice_substituted`);
    }
  }
  return keys;
}

/** The empty-voice-catalogue reason. §9 budgets no key for it — see ASSUMPTIONS. */
export const NO_VOICE_REASON = 'no_voice_for_language';

export function catalogueKeys() {
  return [
    ...alignKeys(),
    ...RENDITION_STATUS,
    ...SPAN_REASON,
    ...ERROR_CODES,
    ...SYNC_GRADE,
    NO_VOICE_REASON,
  ];
}

const SENTENCE = {
  en: (k) => `English sentence explaining the state ${k} to a reader.`,
  es: (k) => `Frase en español que explica el estado ${k} al lector.`,
  fr: (k) => `Phrase en français qui explique l'état ${k} au lecteur.`,
};

function catalogue(locale) {
  return Object.fromEntries(catalogueKeys().map((k) => [k, SENTENCE[locale](k)]));
}

const voiceRow = (id, lang, provider, gender) => ({
  voice_id: id, provider, gender, is_clone: false, lang,
  sample_url: `https://example.invalid/samples/${id}.opus`,
  sample_status: 'ready',
  sample_text: { en: 'This is how this voice sounds.', es: 'Así suena esta voz.',
                 fr: 'Voici le son de cette voix.' }[lang],
  // `voice_langs` ships with no graded rows (S9), so every pair reads
  // `unmeasured` and carries no evidence. A fixture that shipped
  // `at_or_above_bar` here would be asserting a measurement nobody has taken.
  sync_grade: 'unmeasured', sync_pct: null, sync_matched_words: null, sync_measured_at: null,
});

const SPANS_FULL = [
  { kind: 'skipped', reason: 'footnote', count: 4, start_block_ord: 1, end_block_ord: 1,
    segment_ord: 1, char_offset: 431, start_ms: 41200, end_ms: 41200 },
  { kind: 'undescribed', reason: 'figure_no_description', count: 1, start_block_ord: 2, end_block_ord: 2,
    segment_ord: 2, char_offset: 0, start_ms: 52900, end_ms: 55100 },
  { kind: 'undescribed', reason: 'math_unnarratable', count: 3, start_block_ord: 5, end_block_ord: 5,
    segment_ord: 8, char_offset: 12, start_ms: 1200, end_ms: 4800 },
  { kind: 'inserted', reason: 'table_preamble', count: 1, start_block_ord: 4, end_block_ord: 4,
    segment_ord: 6, char_offset: 0, spoken_chars: 34, start_ms: 0, end_ms: 2400 },
  { kind: 'suppressed', reason: 'suppressed_narration', count: 1, start_block_ord: 5, end_block_ord: 5,
    segment_ord: 7, char_offset: 610, start_ms: null, end_ms: null },
  { kind: 'dropped', reason: 'dropped_marker', count: 1, start_block_ord: 1, end_block_ord: 1,
    segment_ord: 1, char_offset: 452, start_ms: null, end_ms: null },
];

// With BOTH controls off, the table linearization is withheld — so its span
// changes kind and reason, per §9.1 ("`kind: suppressed` when content_narration
// withholds them"). Its ADDRESS does not move, which is the invariant
// A-SPANS-SURVIVE-VERBOSITY-OFF asserts: no level may remove the positional
// record. Comparing kind here would make the harness reject a conformant
// backend for obeying the spec.
const SPANS_OFF = SPANS_FULL.map((s) => (s.reason === 'table_preamble'
  ? { ...s, kind: 'suppressed', reason: 'suppressed_narration', spoken_chars: 0, start_ms: null, end_ms: null }
  : s));

const totalsOf = (spans) => spans.reduce((acc, s) => {
  acc[s.reason] = (acc[s.reason] ?? 0) + s.count;
  return acc;
}, {});

/**
 * A fresh, fully conformant backend state.
 *
 * `structuredClone` is load-bearing, not tidiness. Without it the span objects
 * are the module-level constants, and a mutation trial that deletes a field
 * corrupts every LATER trial in the same process — which is how the wire leg
 * first went red on three checks that had nothing to do with it. Shared mutable
 * state between tests, in the harness whose job is to find that class of bug.
 */
export function makeFixture() {
  return structuredClone({
    document_id: 'doc_probe',
    prefs: { disclosure_verbosity: 'full', content_narration: 'full', ui_locale: 'fr' },
    credits: { balance: 0 },
    document: {
      id: 'doc_probe',
      primary_lang: 'fr',
      text_ready_at: '2026-08-10T10:00:00Z',
      audio_ready: false,
      scan_quality: null,
      epub_a11y_metadata: null,
      chapters: [{ chapter_id: 'ch1', title: 'Chapitre premier', heading_level: 1, start_block_ord: 0 }],
      description_coverage: { figures: 1, described: 0 },
      math_coverage: { math: 3, narrated: 0 },
    },
    blocks: [
      { ord: 0, type: 'heading', lang: 'fr', heading_level: 1, text: 'Chapitre premier' },
      { ord: 1, type: 'paragraph', lang: 'fr', text: 'Le narrateur commence son récit…' },
      { ord: 2, type: 'figure', lang: 'fr', alt_text: null, caption: null },
      { ord: 3, type: 'paragraph', lang: 'de', text: 'Der folgende Absatz ist absichtlich auf Deutsch…' },
      { ord: 4, type: 'table', lang: 'fr', rows: [['Colonne A', 'Colonne B'], ['1', '2']] },
      { ord: 5, type: 'paragraph', lang: 'fr', text: 'Le tableau ci-dessous dépasse le seuil…' },
    ],
    voices: {
      en: [voiceRow('v_en_1', 'en', 'lemonfox', 'female'), voiceRow('v_en_2', 'en', 'fish', 'male')],
      es: [voiceRow('v_es_1', 'es', 'fish', 'female')],
      fr: [voiceRow('v_fr_1', 'fr', 'fish', 'female'), voiceRow('v_fr_2', 'fr', 'fish', 'male')],
      de: [],
    },
    noVoiceReason: NO_VOICE_REASON,
    quote: {
      segments: 12,
      quote_etag: 'W/"q:7f3a"',
      display_characters: 36400,
      spoken_characters: 41850,
      inserted_characters: 1200,
      spoken_bytes: 43100,
      credits: 42,
      balance_after: -42,
      align_blocker: { excessive_drop: 1, no_transcriber: 3, transcription_unreliable: 0 },
      word_sync_available_segments: 0,
      word_sync_unmeasured_segments: 8,
      speech_blocker: { blocked_language_unsupported: 3 },
      speech_available_segments: 9,
    },
    quoteStatus: 200,
    segmentsEnvelope: {
      segment_set_id: 'set_1',
      match_conf_threshold: 0.72,
      align_conf_threshold: 0.55,
    },
    segments: [
      seg(0, 'fr', 'ok', [], 'ready'),
      seg(1, 'fr', 'degraded', ['voice_substituted', 'low_confidence'], 'ready'),
      seg(2, 'fr', 'pending', [], null),
      seg(3, 'fr', 'unavailable', ['excessive_drop'], 'ready'),
      seg(4, 'fr', 'ok', [], 'ready'),
      seg(5, 'fr', 'ok', [], 'ready'),
      seg(6, 'fr', 'ok', [], 'ready'),
      seg(7, 'fr', 'ok', [], 'ready'),
      seg(8, 'fr', 'ok', [], 'ready'),
      seg(9, 'de', 'unavailable', ['no_transcriber'], 'blocked_language_unsupported'),
      seg(10, 'de', 'unavailable', ['no_transcriber'], 'blocked_language_unsupported'),
      seg(11, 'de', 'unavailable', ['no_transcriber'], 'blocked_language_unsupported'),
    ],
    narration: { text: 'Tableau, 2 colonnes, 2 lignes. Colonne A : 1. Colonne B : 2.', lang: 'fr' },
    progress_resolution: 'exact',
    catalogue: { en: catalogue('en'), es: catalogue('es'), fr: catalogue('fr') },
    spansFull: SPANS_FULL,
    spansOff: SPANS_OFF,
    renderCommit: { status: 402, body: { code: 'insufficient_credits', segments_enqueued: 0 } },
    // ── knobs a mutation turns; all conformant as they stand ──────────────
    ignoreEtag: false,          // when true the render route stops honouring etags
    voicesStatus: {},           // lang -> a non-200 status
    blocksStatus: 200,
    totalsOverride: null,       // replaces the manifest totals wholesale
  });
}

function seg(ord, lang, align_status, align_reason, rendition_status) {
  return {
    ord, lang, align_status, align_reason, rendition_status,
    audio_url: rendition_status === 'ready' ? `https://example.invalid/a/${ord}.opus` : null,
    duration_ms: rendition_status === 'ready' ? 42000 : null,
    start_block_ord: Math.min(ord, 5),
    end_block_ord: Math.min(ord, 5),
    skipped_block_ords: [],
    block_start_offsets: [0],
  };
}

const json = (status, body) => ({ status, body });

/** Build a transport over a fixture state. Used in-memory AND by the stub server. */
export function respondFrom(data) {
  return async (method, path) => {
    const url = new URL(path, 'http://fixture.invalid');
    const p = url.pathname;
    const query = url.searchParams;
    const id = data.document_id;

    if (method === 'POST' && p === '/documents') return json(201, { document_id: id });

    if (method === 'GET' && p === '/voices') {
      const lang = query.get('lang');
      const forced = data.voicesStatus[lang];
      if (forced && forced !== 200) return json(forced, { code: 'not_found' });
      const rows = data.voices[lang];
      if (!rows) return json(200, { voices: [], reason: data.noVoiceReason });
      if (rows.length === 0) {
        return data.noVoiceReason === null
          ? json(200, { voices: [] })
          : json(200, { voices: [], reason: data.noVoiceReason });
      }
      return json(200, { voices: rows });
    }

    if (method === 'GET' && p === '/me/credits') return json(200, data.credits);
    if (method === 'PUT' && p === '/me/preferences') return json(200, data.prefs);

    if (method === 'GET' && p === '/i18n/messages') {
      const locale = query.get('locale');
      const messages = data.catalogue[locale];
      if (!messages) return json(404, { code: 'unsupported_locale' });
      return json(200, { locale, messages });
    }

    if (p === `/documents/${id}`) {
      const off = data.prefs.disclosure_verbosity === 'off' && data.prefs.content_narration === 'off';
      const spans = off ? data.spansOff : data.spansFull;
      return json(200, {
        ...data.document,
        preferences: data.prefs,
        skip_manifest: { totals: data.totalsOverride ?? totalsOf(spans), by_chapter: [], spans },
      });
    }
    if (p === `/documents/${id}/blocks`) {
      return data.blocksStatus === 200
        ? json(200, { blocks: data.blocks })
        : json(data.blocksStatus, { code: 'extract_failed' });
    }
    if (/^\/documents\/[^/]+\/blocks\/\d+\/narration$/.test(p)) {
      return data.narration ? json(200, data.narration) : json(404, { code: 'not_found' });
    }
    if (p === `/documents/${id}/quote`) return json(data.quoteStatus, data.quote);
    if (p === `/documents/${id}/segments`) {
      return json(200, { ...data.segmentsEnvelope, segments: data.segments });
    }
    if (p === `/documents/${id}/progress`) {
      return json(200, { progress_resolution: data.progress_resolution });
    }
    if (method === 'POST' && p === `/documents/${id}/render`) {
      return json(data.renderCommit.status, data.renderCommit.body);
    }
    return json(404, { code: 'not_found' });
  };
}

/**
 * The render route needs the request body to decide 409 vs 402, so it is
 * wrapped rather than folded into the router above — the stub server and the
 * in-memory transport share this wrapper too.
 */
export function transportFor(data) {
  const base = respondFrom(data);
  return async (method, path, body) => {
    const p = new URL(path, 'http://x.invalid').pathname;
    if (method === 'POST' && /\/render$/.test(p)) {
      const stale = !data.ignoreEtag && body?.quote_etag !== data.quote.quote_etag;
      if (stale) return json(409, { code: 'quote_changed', quote_etag: data.quote.quote_etag });
    }
    // The preference write has to TAKE EFFECT, or the verbosity=off manifest is
    // the default manifest and A-SPANS-SURVIVE-VERBOSITY-OFF compares a payload
    // with itself. It passed that way until its mutation refused to fire.
    if (method === 'PUT' && p === '/me/preferences') {
      Object.assign(data.prefs, body ?? {});
      return json(200, data.prefs);
    }
    return base(method, path, body);
  };
}
