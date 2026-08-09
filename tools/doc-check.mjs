#!/usr/bin/env node
/**
 * doc-check — mechanical consistency gate for the governing documents.
 *
 * WHY THIS EXISTS
 * Seven audits found one defect class: a fix lands in the artifact where it was
 * raised and not in the artifact that implements it. Three attempts to solve it
 * with process rules failed, because every rule relied on remembering sites.
 *
 * WHY IT LOOKS LIKE THIS (round 7 rebuild)
 * v1 of this script was itself the defect. Jury and Halo instrumented it and
 * found: a guard passing on the word "utterance"; a flattener that stripped `_`
 * and killed five guards; "bidirectional" asserted in three artifacts and never
 * implemented; and a --self-test that exercised *copies* of the guards against
 * *frozen string literals*, so the shipped guards could rot while it reported
 * 22/22. Halo: "A test that constructs its own input can only ever tell you
 * about the input."
 *
 * So: every check is a function of a document set. --self-test mutates the REAL
 * documents in memory and runs the REAL checks over them, asserting each goes
 * red. Nothing is verified by a copy.
 *
 * USAGE   node tools/doc-check.mjs [--self-test]
 * EXIT    0 clean · 1 findings · 2 not applicable (private docs absent)
 */

import { readFileSync, existsSync, readdirSync } from 'node:fs';

const DOCS = {
  spec: 'resources/specs/2026-08-08-audiomax-backend-design.md',
  roadmap: 'resources/roadmap/2026-08-08-backend-roadmap.md',
  claude: 'CLAUDE.md',
  readme: 'README.md',
};
const PRIVATE = new Set(['spec', 'roadmap']);   // gitignored by owner decision
const CURRENT_REVISION = 18;
// Counted from disk, not hand-maintained — a pinned literal is how the v7
// version guard came to sit green over its own defect (N7-C9).
const ROUNDS_ON_DISK = existsSync('resources/audits')
  ? readdirSync('resources/audits').filter((f) => /founding-documents(-round\d+)?\.md$/.test(f)).length
  : 0;

const read = (p) => (existsSync(p) ? readFileSync(p, 'utf8') : null);
const lineOf = (t, i) => t.slice(0, i).split('\n').length;
const section = (t, from, to) => {
  const s = t.search(from);
  if (s < 0) return '';
  const rest = t.slice(s + 1).search(to);
  return rest < 0 ? t.slice(s) : t.slice(s, s + 1 + rest);
};

// ── Prose regressions ────────────────────────────────────────────────────
// One per finding that recurred AFTER being reported fixed. `mutate` restores
// the defect in the live document so --self-test can prove the guard fires.
const BANNED = [
  { id: 'N4-M2', doc: 'spec', re: /character count is what the provider bills/i,
    why: 'providers bill SPOKEN characters, counted after stage 4.5',
    mutate: (t) => t.replace(/Providers bill \*\*spoken\*\*/, 'character count is what the provider bills —') },
  { id: 'R4-C5', doc: 'spec', re: /spoken from the message catalogue in the user's locale/i,
    why: 'sentinels use segments.lang, never ui_locale',
    mutate: (t) => t.replace(/spoken from the message catalogue \*\*in `segments\.lang`[^*]*\*\*/,
      "spoken from the message catalogue in the user's locale") },
  { id: 'N3-R11', doc: 'spec', re: /RLS by user_id on every table(?![^.]*(?:join|exempt|catalogue))/i,
    why: 'voices has no user_id; state the join mechanism and the exemption',
    mutate: (t) => t.replace(/\*\*RLS on every table carrying user data \(N3-R11\)\.\*\*/,
      'RLS by `user_id` on every table.') },
  { id: 'N4-C1', doc: 'roadmap', re: /normalize\(segments\.text\[cs:ce\]\) == w`? for every (?:word|token)/i,
    why: 'the per-span form is repudiated in §6.2 — use group_id monotonicity',
    mutate: (t) => t.replace(/\(a\) `group_id` monotonicity between groups/,
      '`normalize(segments.text[cs:ce]) == w` for every word of every fixture') },
  { id: 'J-C1', doc: 'claude', re: /there is no middle state/i,
    why: 'the gate has five severities; PASS WITH FIXES permits a commit',
    mutate: (t) => t.replace(/Minor and Polish findings never block a commit\./,
      'There is no middle state.') },
  { id: 'J-C10', doc: 'readme', re: /resources\/ is gitignored in full/i,
    why: 'resources/audits/ is committed — the governance trail is versioned',
    mutate: (t) => t.replace(/Internal working documents never reach the/,
      '`resources/` is gitignored in full: internal documents never reach the') },
  { id: 'N5-m3', doc: 'spec', re: /align_reason: (?!\[)[a-z_]+/,
    why: 'align_reason is an array; write align_reason: [value]',
    mutate: (t) => t.replace(/align_reason: \[transcript_mismatch\]/, 'align_reason: transcript_mismatch') },
  { id: 'N3-R3', doc: 'spec', re: /Word timings are JSONB on the segment\b/i,
    why: 'timings are per-rendition — computed against a rendition\'s audio',
    mutate: (t) => t.replace(/Word timings are JSONB on the rendition/, 'Word timings are JSONB on the segment') },
  { id: 'N3-R5', doc: 'readme', re: /Seven stages/i,
    why: 'eight stages — Normalize (4.5) owns the provenance trace',
    mutate: (t) => t.replace(/Eight stages/, 'Seven stages') },
  { id: 'R4-M2', doc: 'spec', re: /documents\.align_degraded_ratio|chapters\.align_degraded_ratio/i,
    why: 'the ratio is per-voice; it lives only in the rollup tables',
    mutate: (t) => t.replace(/`document_align_rollup \(document_id,/, '`documents.align_degraded_ratio` (`document_id,') },
  { id: 'N5-M2', doc: 'roadmap', re: /Record (?:display )?char_count/i,
    why: 'the column is display_char_count',
    mutate: (t) => t.replace(/Record `display_char_count`/, 'Record display `char_count`') },
  { id: 'R5-C6', doc: 'spec', re: /text_hash = H\((?![^)]*lexicon_fingerprint)/,
    why: 'a global lexicon_version re-bills the library; the fingerprint is per-segment',
    mutate: (t) => t.replace(/lexicon_fingerprint, lang/, 'lexicon_version, lang') },
  // N9-C4: the excluding form cancels the \p{No} exception. It was copied into
  // both documents twice, each time by a "fix" that added the correct rule and
  // left the wrong one standing.
  { id: 'N9-C4', doc: 'spec', re: /\\p\{N\}(?![dl])/, wholeDoc: true,
    why: 'the floor is \\p{Nd}/\\p{Nl}; \\p{N} swallows \\p{No} and cancels the dropped_marker exception',
    mutate: (t) => t.replace(/or `\\p\{Nd\}`\/`\\p\{Nl\}`/, 'or `\\p{N}`') },
  { id: 'N9-M4', doc: 'spec', re: /genuinely ambiguous: permanent for this render/i,
    why: 'transcript_mismatch and low_confidence are classified once in the derivation table',
    mutate: (t) => t.replace(/\*\*Permanence is a field, not an inference/,
      'genuinely ambiguous: permanent for this render, possibly not for another voice. **Permanence is a field, not an inference') },
  // J12-M1 / J15-M8, open since round 12. Every real leak in this chain was an
  // ADDED copy at a new site, and a presence guard cannot see one — Jury proved
  // it by pasting the wrong claim into four files at a green gate. These are the
  // missing direction: they fire when the WRONG classification appears ANYWHERE
  // in the document, not when the right one goes missing from one place.
  { id: 'N15-CONTRA-UNRELIABLE', doc: 'spec', wholeDoc: true,
    re: /`transcription_unreliable`[^.]{0,120}(?:is|are) `permanent`/,
    why: 'a (lang, voice) fact classified permanent tells a blind user the only remedy this design offers — another voice — cannot help. Wherever it appears',
    mutate: (t) => t.replace(/\*\*`transcript_mismatch`\*\* are `permanent`/,
      '**`transcript_mismatch`** and `transcription_unreliable` are `permanent`') },
  { id: 'N15-CONTRA-TRANSCRIBER', doc: 'spec', wholeDoc: true,
    re: /`no_transcriber`[^.]{0,120}(?:is|are) (?:`retryable`|`render_specific`)/,
    why: 'no_transcriber means no transcriber exists for the language. Classified retryable or render_specific it invites a paid retry — $1.35–$32 — that is structurally incapable of succeeding (J15-C2)',
    mutate: (t) => t.replace(/`voice_substituted`, `low_confidence`,/,
      '`no_transcriber` is `retryable`; `voice_substituted`, `low_confidence`,') },
  { id: 'R5-C3', doc: 'spec', re: /monotonic between groups and unconstrained within one\.?\s*$/im,
    why: 'state the ordering DOMAIN — "monotonic" alone validates nothing',
    mutate: (t) => t.replace(/\*\*Stated over display offsets[\s\S]{0,80}?\*\*/,
      'Order is monotonic between groups and unconstrained within one.') },
];

// ── Structural requirements ──────────────────────────────────────────────
// `need` must appear in a NORMATIVE position. `mutate` reduces it to a single
// non-normative mention — the faithful mutation for a one-occurrence defect,
// which total deletion cannot model (Halo H6-M19).
// ── INVARIANTS ───────────────────────────────────────────────────────────
// Halo, round 11: "Every one of the BANNED guards protects a sentence that was
// PREVIOUSLY wrong. Not one protects a sentence that is currently right and
// load-bearing. A guard set shaped by history rather than by risk."
//
// These guard the sentences a blind user's session depends on. Each is
// currently TRUE and must stay true; deleting or inverting it must go red.
const INVARIANTS = [
  { id: 'INV-QUOTE', doc: 'spec', re: /"align_blocker":\s*\{/,
    why: 'the §8.2 quote must carry align_blocker — it is the only pre-payment word-sync disclosure',
    mutate: (t) => t.replace(/"align_blocker": \{[^}]*\},/, '') },
  { id: 'INV-LANG', doc: 'spec', re: /\*\*Never cross a language boundary\*\*/,
    why: 'without it a Haitian Creole passage is spoken by a French voice (H-C2)',
    mutate: (t) => t.replace(/- \*\*Never cross a language boundary\*\*[^\n]*\n/, '') },
  { id: 'INV-FALLBACK', doc: 'spec', re: /No cross-language fallback for synthesized speech/i,
    why: 'the sentinel a blind user most needs must not arrive least intelligible (R5-C7)',
    mutate: (t) => t.replace(/\*\*No cross-language fallback for synthesized speech\*\*/,
      'Cross-language fallback is permitted for synthesized speech') },
  // The `normalization_opaque` chain has leaked to a new site in each of
  // rounds 9, 10 and 11. Jury: "if I find a third copy next round, the honest
  // conclusion won't be that the fixes are bad, it will be that this remedy
  // needs a guard instead of another round of reading." This is that guard —
  // it asserts the value is voice-dependent everywhere it is classified.
  { id: 'INV-UNRELIABLE-PERM', doc: 'spec',
    re: /`transcription_unreliable`[^.]{0,160}are `render_specific`/,
    why: 'transcription_unreliable is a (lang, voice) fact — another voice genuinely can change it, so it is render_specific. Classifying it permanent hides the only remedy this design offers a blind user (R14-A1, successor to INV-OPAQUE-PERM)',
    mutate: (t) => t.replace(/`transcription_unreliable`\*\* and \*\*`wrong_match`\*\* are `render_specific`/,
      '`wrong_match`** are `render_specific`') },
  { id: 'INV-TRANSCRIBER-PERM', doc: 'spec',
    re: /`no_transcriber`[^.]{0,160}are `permanent`/,
    why: 'J16-M7 — no_transcriber had only a contradiction guard. Deleting it from the permanent list writes no wrong sentence, so nothing fired, and the derivation fell through to "else retryable" — inviting a blind ht user to pay again for a retry that cannot succeed. This is the presence half of the pair',
    mutate: (t) => t.replace(/`unsupported_language`, \*\*`no_transcriber`\*\*, /,
      '`unsupported_language`, ') },
  // J17-M6 / N12-C7, open since round 12 — every INVARIANT guarded the SPEC, and
  // CLAUDE.md's own precedence rule says the roadmap is what gets built. Halo
  // demonstrated three roadmap deletions passing at a green gate. These are the
  // roadmap counterparts for the sentences a blind user's session depends on.
  { id: 'INV-RM-FALLBACK', doc: 'roadmap',
    re: /No cross-language fallback for synthesized speech/,
    why: 'R5-C7 in the artifact an engineer builds from. Without it, a Creole passage with no catalogue string is spoken by a French voice instead of recorded as a disclosure span',
    mutate: (t) => t.replace(/No cross-language fallback for synthesized speech/,
      'Cross-language fallback is permitted for synthesized speech') },
  { id: 'INV-RM-BLOCKER-ARITY', doc: 'roadmap',
    re: /`transcription_unreliable`\*\*`｜`\*\*`wrong_match`/,
    why: 'J17-C2 — the rendition blocker must carry THREE values. Scheduled with two, the column cannot hold transcription_unreliable, which is the ht pre-payment word-sync disclosure. This column has broken in three consecutive rounds, always by writing the new sentence without deleting the old',
    mutate: (t) => t.replace(/`\*\*`transcription_unreliable`\*\*`｜`\*\*`wrong_match`\*\*`\)/,
      '`**`wrong_match`**`)') },
  { id: 'INV-RM-DRIFT', doc: 'roadmap',
    re: /drift bound is fixed at 250 ?ms BEFORE this spike runs/i,
    why: 'H17-C3 — the SPIKE A pass bar is a share of words matched INSIDE the drift bound, so a bound chosen after the measurement sets its own pass rate. The number must be fixed first, and the measurement may move it only publicly with the reason recorded',
    mutate: (t) => t.replace(/\*\*The drift bound is fixed at 250 ?ms BEFORE this spike runs \(H17-C3\)\.\*\*/i,
      'The drift bound is chosen during the spike.') },
  { id: 'INV-OFFSETS', doc: 'spec', re: /len\(block_start_offsets\)/,
    why: 'without the length invariant nothing can be announced at a position',
    mutate: (t) => t.replace(/len\(block_start_offsets\)/, 'len(offsets)') },
];

const STRUCTURAL = [
  { id: 'R5-C1', doc: 'spec', need: 'content_narration', min: 4,
    why: 'content narration must be a separate axis — one switch deleted every table' },
  { id: 'R5-C8', doc: 'spec', need: 'blocks/:ord/narration', min: 1,
    why: 'large tables are otherwise unreachable in both channels' },
  { id: 'R5-C4', doc: 'spec', need: 'excessive_drop', min: 3,
    why: 'the dropped-span floor needs a raiser that is stored AND announceable' },
  { id: 'N5-M6', doc: 'spec', need: 'Derived, not authored', min: 1,
    why: 'align_permanence must be derived from the reason set' },
  { id: 'R5-M13', doc: 'roadmap', need: 'DECISION — what artifact satisfies the accessibility gate', min: 1,
    why: 'the decision must precede the stages it would exercise' },
  { id: 'R5-M8', doc: 'roadmap', need: 'their address IS validated', min: 1,
    why: 'an inserted-token address nothing validates is not an address' },
  { id: 'H6-C8', doc: 'roadmap', need: 'NFC', min: 1,
    why: 'the grapheme-cluster floor must be in the artifact that gets built, not only the spec' },
];

// ── Controls that must trace end to end ──────────────────────────────────
const CONTROLS = [
  { name: 'disclosure_verbosity', hash: 'disclosure_fingerprint', catalogue: true },
  { name: 'content_narration',    hash: 'disclosure_fingerprint', catalogue: true },
  { name: 'skip_policy',          hash: null, route: 'skip-policy',
    note: 'changes which segments exist -> new segment_set_id, not a hash change' },
  { name: 'user_lexicon',         hash: 'lexicon_fingerprint', route: 'lexicon' },
  { name: 'ui_locale',            hash: null, catalogue: true,
    note: 'governs displayed text only, never synthesized speech' },
];

// ── The checks. One function, so the harness runs exactly what ships. ─────
function runChecks(src) {
  const out = [];
  const add = (severity, check, doc, line, message) =>
    out.push({ severity, check, doc, line, message, id: message.match(/\[([\w-]+)\]/)?.[1] });

  const schemaText = section(src.spec, /^#+\s*7\.\s*Data model/m, /^#+\s*8\./m);
  const phase1 = section(src.roadmap, /^##\s*Phase 1/m, /^##\s*Phase 2/m);
  const phase45 = section(src.roadmap, /^##\s*Phase 4\.5/m, /^##\s*Phase 5/m);
  const apiSection = section(src.spec, /^#+\s*9\.\s/m, /^#+\s*10\./m);

  if (!schemaText) add('CRITICAL', 'locator', 'spec', 0, '[LOC-7] §7 Data model not found');
  if (!phase1) add('CRITICAL', 'locator', 'roadmap', 0, '[LOC-P1] Phase 1 not found');

  // 1. Field coverage, forward
  const declared = new Map();
  for (const block of src.spec.matchAll(/```ts\n([\s\S]*?)```/g)) {
    const base = lineOf(src.spec, block.index);
    let iface = '?';
    block[1].split('\n').forEach((raw, i) => {
      const im = raw.match(/^\s*(?:export\s+)?(?:interface|type)\s+(\w+)/);
      if (im) { iface = im[1]; return; }
      if (raw.trim().startsWith('//')) return;
      for (const fm of raw.matchAll(/(?:^|\s|\{)(\w+)\??\s*:/g)) declared.set(fm[1], { line: base + i + 1, iface });
    });
  }
  const NESTED_OK = new Set(['origin', 'w', 'cs', 'ce', 's', 'e', 'conf', 'group_id', 'reason',
    'header_rows', 'header_cols', 'rows', 'cells', 'row', 'col', 'is_header', 'scope',
    'rowspan', 'colspan', 'string', 'number', 'boolean']);
  // R14-m3 — MINIMUM HARVEST. A check that silently checks nothing is the
  // failure this tool was rebuilt in round 7 to eliminate, and it has happened
  // twice: J12-M5 (`spoken_chars` invisible to a line-anchored regex, gate
  // green) and the round-14 CRLF accident, where `/```ts\n/` matched nothing,
  // FWD iterated an empty set and PASSED SILENTLY — only REV screamed. The gate
  // was saved by the loud half of a bidirectional check, not by design. The
  // inverse accident turns the gate green over an empty harvest.
  //
  // These floors are deliberately far below real counts. They are a smoke
  // alarm for "the parse returned nothing", not a coverage target.
  const FLOORS = [
    // J15-M6: measured 40. A floor AT the measured value is not a smoke alarm —
    // deleting any one field trips a CRITICAL that blames a parse bug which does
    // not exist, sending the next author hunting line endings. 20 is half the
    // real count: a parse that returns nothing still trips it, ordinary edits
    // never do.
    ['declared interface fields', declared.size, 20],
    ['§7 schema text', schemaText.length, 2000],
    ['Phase 1 text', phase1.length, 1000],
  ];
  for (const [what, got, min] of FLOORS) {
    if (got < min) {
      add('CRITICAL', 'harvest', 'spec', 0,
        `[HARVEST] parsed ${got} ${what}, expected >= ${min} — the parse returned ` +
        `little or nothing, so every check downstream of it is vacuous. ` +
        `Suspect line endings, a renamed heading, or a changed fence syntax.`);
    }
  }

  for (const [field, meta] of declared) {
    if (NESTED_OK.has(field)) continue;
    if (!schemaText.includes(field)) {
      add('CRITICAL', 'field-coverage', 'spec', meta.line,
        `[FWD] \`${field}\` declared in ${meta.iface} but absent from §7 Data model`);
    }
  }

  // 1b. Field coverage, reverse. Enum values are harvested ONLY from
  // parenthesised `｜`-delimited value lists — v1 harvested on `·`, which is
  // the COLUMN separator in §7.2/§7.2a, silently exempting 42 real columns
  // including every one the round-6 fixes added (N7-C1/N7-C8).
  const enumValues = new Set();
  // (a) parenthesised `｜`-delimited value lists in §7
  for (const m of schemaText.matchAll(/\(`?([a-z][a-z0-9_]*(?:`?｜`?[a-z][a-z0-9_]*)+)`?\)/g)) {
    for (const v of m[1].split(/｜/)) enumValues.add(v.replace(/`/g, '').trim());
  }
  // (b) members of any union DECLARED in a ts block — SpanReason,
  // InsertedReason, SkipReason. These are enum values wherever they appear;
  // allowlisting them one at a time is the "remember the site" failure mode
  // this tool exists to replace.
  // Every single-quoted lowercase literal inside a ts block is a union member.
  // The earlier pair of patterns missed `table_cell_header` because the first
  // alternative consumed the NEXT value's opening quote — an overlapping-match
  // bug, and exactly the kind of thing a per-value allowlist would have hidden.
  for (const block of src.spec.matchAll(/```ts\n([\s\S]*?)```/g)) {
    for (const m of block[1].matchAll(/'([a-z][a-z0-9_]*)'/g)) enumValues.add(m[1]);
  }
  // (c) levels of the two narration controls, declared as table rows in §3.8
  for (const m of src.spec.matchAll(/^\|\s*`(full|positional|summary|off)`\s*\|/gm)) enumValues.add(m[1]);
  const tablesSeen = new Set([
    ...[...schemaText.matchAll(/^\|\s*`([a-z][a-z0-9_]*)`\s*\|/gm)].map((m) => m[1]),
    ...[...schemaText.matchAll(/^#+\s*7\.\d\w*\s+`([a-z][a-z0-9_]*)`/gm)].map((m) => m[1]),
  ]);
  const SCHEMA_ONLY = new Set([
    'user_id', 'document_id', 'chapter_id', 'segment_id', 'voice_id', 'id',
    'created_at', 'deleted_at', 'set_expires_at', 'superseded_by', 'segment_set_id',
    'is_active', 'status', 'storage_path', 'source_type', 'is_skipped', 'skip_reason',
    'total_chars', 'parent_id', 'depth', 'start_block', 'end_block', 'title', 'ord',
    'spoken_text', 'inserted_speech', 'normalization_trace', 'text_hash',
    'lexicon_fingerprint', 'normalizer_version', 'disclosure_fingerprint',
    'lexicon_overrides', 'align_status', 'align_reason', 'align_permanence',
    'align_conf', 'align_conf_threshold', 'align_degraded_ratio', 'words',
    'start_block_ord', 'end_block_ord', 'skipped_block_ords', 'block_start_offsets',
    'display_char_count', 'display_byte_count', 'speaker_label', 'skip_manifest',
    'audio_path', 'duration_ms', 'encoder_delay', 'encoder_padding',
    'requested_lang', 'spoken_lang', 'voice_substituted', 'provider', 'cost_usd',
    'is_clone', 'gender', 'provider_voice_id', 'scan_quality', 'figures_total',
    'figures_without_description', 'math_total', 'math_unnarratable',
    'epub_a11y_metadata', 'skip_policy', 'disclosure_verbosity', 'content_narration',
    'ui_locale', 'playback_rate', 'surface_form', 'phoneme', 'offset_ms',
    'char_offset_in_block', 'block_ord', 'segment_ord', 'progress_resolution',
    'balance_after', 'delta', 'lexicon_version', 'retry', 're_render', 'align_blocker',
    'low_confidence', 'unavailable',
    // R14-A1 successors: `no_normalizer`/`normalization_opaque` were
    // prediction-era blockers and neither blocks word sync under observation.
    'no_transcriber', 'transcription_unreliable', 'wrong_match',
    // J15-M7: these were dead allowlist entries when added (absent from §7),
    // pre-silencing the guard that would have demanded a column. They are now
    // real `segment_renditions` columns AND word-record keys, so the entries
    // are live and earn their place.
    'asr_conf', 'match_conf', 'observed_words',
    'unsupported_language', 'engine_error', 'transcript_mismatch', 'excessive_drop',
    'pending', 'degraded', 'ok', 'permanent', 'retryable', 'render_specific',
    'blocked_quota', 'blocked_credits', 'blocked_provider',
    'en', 'es', 'fr', 'ht',
  ]);
  for (const m of schemaText.matchAll(/`([a-z][a-z0-9_]{2,})`/g)) {
    const ident = m[1];
    if (declared.has(ident) || tablesSeen.has(ident) || SCHEMA_ONLY.has(ident)) continue;
    if (NESTED_OK.has(ident) || enumValues.has(ident)) continue;
    add('MAJOR', 'field-coverage-reverse', 'spec', lineOf(src.spec, m.index),
      `[REV] \`${ident}\` appears in §7 but traces to no interface field, table, or allowlist entry`);
  }

  // 1c. TABLE PLACEMENT (N8-C2). `CLAUDE.md` names "a field on the wrong
  // table" first among the required properties, and three artifacts claimed it
  // was covered while Jury moved `align_status` onto `segments` and `text_hash`
  // onto the global `voices` catalogue with zero findings. Whole-§7 membership
  // is table-agnostic by construction, so placement needs its own map.
  // A DECLARATION is a backticked identifier in list context — adjacent to a
  // `,` `·` or `|` separator. A mention inside explanatory prose ("because
  // `duration_ms` is per-rendition") is a reference, not a column, and treating
  // the two alike produced a false positive on the first run.
  const declaredCols = (cell) => {
    const out = new Set();
    // Allow a type suffix INSIDE the backticks — §7.2/§7.2a write columns as
    // `words JSONB`, `align_reason[]`, `skipped_block_ords int[]`. Requiring a
    // bare identifier made 4 of 11 PLACEMENT rows vacuous (N9-M2).
    for (const m of cell.matchAll(/(^|[,·|]\s*|\s)\*{0,2}`([a-z][a-z0-9_]*)(?:\[\]|\s+[A-Za-z]+(?:\[\])?)?`\*{0,2}(?=\s*[,·|]|\s*$)/g)) {
      out.add(m[2]);
    }
    return out;
  };
  const columnsOf = new Map();
  for (const m of schemaText.matchAll(/^\|\s*`([a-z][a-z0-9_]*)`\s*\|([^|]*)\|/gm)) {
    columnsOf.set(m[1], declaredCols(m[2]));
  }
  // Split on subsection headings. A lookahead with `$` under the /m flag stops
  // at the first line end, so the previous form captured zero-length bodies and
  // the placement map was silently empty — the guard had no data at all.
  for (const chunk of schemaText.split(/^### /m).slice(1)) {
    const h = chunk.match(/^7\.\d\w*\s+`([a-z][a-z0-9_]*)`/);
    if (!h) continue;
    // Cut at a PARAGRAPH break before bold prose (`\n\n**`), not at any
    // line-initial `**` — the column run wraps, and its continuation lines
    // start with `**` too, so the tighter cut truncated the list mid-way.
    const cut = chunk.search(/\n\n\*\*/);
    const body = cut > 0 ? chunk.slice(0, cut) : chunk;
    columnsOf.set(h[1], new Set([...(columnsOf.get(h[1]) ?? []), ...declaredCols(body)]));
  }
  // Placements the design argues for explicitly. Each entry is a decision some
  // audit round paid for; moving one silently undoes that round.
  const PLACEMENT = [
    ['align_status', 'segment_renditions', 'N3-R3 — timings are computed against a rendition\'s audio'],
    ['align_reason', 'segment_renditions', 'N3-R3'],
    ['words', 'segment_renditions', 'N3-R3'],
    ['audio_path', 'segment_renditions', 'J-N8 — a voice change must not orphan paid audio'],
    ['duration_ms', 'segment_renditions', 'J-N8'],
    ['text_hash', 'segments', 'per-segment re-render identity'],
    ['disclosure_fingerprint', 'segments', 'H6-C1 — per-segment, never a global scalar'],
    ['lexicon_fingerprint', 'segments', 'R5-C6 — per-segment, never a global counter'],
    // `align_blocker` is deliberately absent from PLACEMENT: after N9-C3 it
    // lives on BOTH tables — text-level reasons on `segments`, the provider
    // fact on `segment_renditions`. The round-8 row encoded the position that
    // finding overturned, so the guard fired against the correct fix (J10-C1).
    // COL below still requires it on `segments`.
    ['spoken_text', 'segments', 'stage 4.5 output, one per segment'],
    ['block_start_offsets', 'segments', 'H-N1 — segmentation provenance'],
  ];
  for (const [col, table, why] of PLACEMENT) {
    for (const [t, cols] of columnsOf) {
      if (t !== table && cols.has(col)) {
        add('CRITICAL', 'table-placement', 'spec', 0,
          `[PLACE] \`${col}\` appears on \`${t}\` — it belongs on \`${table}\` (${why})`);
      }
    }
  }

  // 2. Migration coverage — tables AND every text_hash input column (N7-C3)
  for (const table of tablesSeen) {
    if (!phase1.includes(table)) {
      add('CRITICAL', 'migration-coverage', 'roadmap', 0,
        `[MIG-T] table \`${table}\` is defined in spec §7 and built by no Phase 1 item`);
    }
  }
  const hashInputs = (src.spec.match(/text_hash = H\(([^)]*)\)/) || [, ''])[1]
    .split(',').map((s) => s.trim().replace(/[`*]/g, '')).filter((s) => /^[a-z_]+$/.test(s));
  for (const col of hashInputs) {
    if (col === 'text' || col === 'lang') continue;
    if (!phase1.includes(col)) {
      add('CRITICAL', 'migration-coverage', 'roadmap', 0,
        `[MIG-H] \`${col}\` is a text_hash input and is not built by any Phase 1 item`);
    }
  }

  // 2b. EVERY identifier the spec introduces must reach the roadmap (Halo,
  // round 8). Eight of the last round's Criticals were remedies with no guard
  // at all, and seven shared one shape: the fix is in the spec and the roadmap
  // does not know about it. `MIG-H` was the right instinct at the wrong scope —
  // a point guard for one instance. This is the class.
  const introduced = new Set();
  // EVERY union member, not just the line-initial one. `chapter_announcement`
  // and `toc_filler` sit mid-line and were invisible to the guard built for
  // the class (Halo acceptance mutation 1, N9-M3).
  for (const block of src.spec.matchAll(/```ts\n([\s\S]*?)```/g)) {
    for (const m of block[1].matchAll(/'([a-z][a-z0-9_]*)'/g)) introduced.add(m[1]);
  }
  // §7 and §9 are where remedies land — but not only there. `align_blocker`
  // was introduced in §6.3 and was invisible to this harvest, so the guard
  // built for the class missed the Critical that defined the class (N9-M3).
  const s6 = section(src.spec, /^#+\s*6\.\s/m, /^#+\s*7\./m);
  // §8 is the PAYMENT section and was sectioned by nothing, so the entire
  // pre-payment disclosure block could be deleted with the gate clean (N11-C1).
  const s8 = section(src.spec, /^#+\s*8\.\s/m, /^#+\s*9\./m);
  const scopes = [schemaText, apiSection, s6, s8];
  for (const m of src.spec.matchAll(/`([a-z][a-z0-9_]{4,})`/g)) {
    if (scopes.some((s) => s.includes(`\`${m[1]}\``))) introduced.add(m[1]);
  }
  // Compound runs: `progress_resolution: exact｜block_approximate`, and jsonc
  // payload keys. The closing-backtick requirement made four blind-user
  // disclosure channels invisible to the harvest (N11-C2).
  for (const s of scopes) {
    for (const m of s.matchAll(/`([a-z][a-z0-9_]{4,})\s*:/g)) introduced.add(m[1]);
    // Enum runs only INSIDE a backticked span — `a｜b｜c`. An unanchored pipe
    // pattern also matched ordinary prose ("index", "numeric").
    for (const run of s.matchAll(/`([a-z][a-z0-9_]*(?:｜[a-z][a-z0-9_]*)+)`/g)) {
      for (const v of run[1].split('｜')) if (v.length >= 4) introduced.add(v);
    }
    for (const m of s.matchAll(/^\s*"([a-z][a-z0-9_]{4,})":/gm)) introduced.add(m[1]);
  }
  // Vocabulary that legitimately never appears in a build item: prose nouns,
  // rejected designs, and identifiers owned by another document.
  // `Block.kind` members and nested JSONB payload fields are built by the
  // adapter and table items that carry them; they are not separate build
  // tasks. Exempted as a CLASS with a stated reason, rather than one at a time
  // — Jury M3: "judgement stored in a list with no rationale field".
  const blockKinds = new Set(
    [...((src.spec.match(/kind:\s*((?:'[a-z_]+'\s*\|?\s*)+)/) || [, ''])[1])
      .matchAll(/'([a-z_]+)'/g)].map((m) => m[1]));
  const nestedPayload = new Set(['row', 'col', 'marker', 'punctuation', 'symbol', 'emoji']);
  const NOT_A_BUILD_ITEM = new Set([
    'lexicon_version', 'segment_ord', 'block_ord', 'char_offset', 'char_offset_in_block',
    'surface_form', 'phoneme', 'balance_after', 'delta', 'start_block', 'end_block',
    'total_chars', 'storage_path', 'source_type', 'created_at', 'is_active', 'is_clone',
    'gender', 'provider_voice_id', 'playback_rate', 'parent_id', 'document_id',
    'chapter_id', 'segment_id', 'voice_id', 'user_id', 'retry', 're_render',
    'permanent', 'retryable', 'render_specific', 'pending', 'degraded',
    'unavailable', 'ok', 'uploaded', 'extracting', 'structuring', 'ready', 'deleting',
    'extract_failed', 'positional', 'summary', 'full', 'off', 'exact',
  ]);
  // Word-boundary, not substring: `table_cell` was satisfied by
  // `table_cell_header` (Halo acceptance mutation 5).
  const inRoadmap = (id) => new RegExp(`\\b${id}\\b`).test(src.roadmap);
  for (const ident of introduced) {
    if (NOT_A_BUILD_ITEM.has(ident) || blockKinds.has(ident) || nestedPayload.has(ident)) continue;
    if (!inRoadmap(ident)) {
      add('CRITICAL', 'spec-to-roadmap', 'roadmap', 0,
        `[S2R] \`${ident}\` is introduced by the spec and appears NOWHERE in the roadmap — the remedy is unbuildable as scheduled`);
    }
  }

  // 2c. PHASE SCOPE. Presence anywhere in 500 lines is not scheduling. Each
  // entry must appear in the phase that BUILDS it (Halo acceptance mutation 6).
  const phaseOf = (h) => section(src.roadmap, h, /^##\s*Phase/m);
  const PHASE_BOUND = [
    ['surface_form', /^##\s*Phase 1/m, 'Phase 1 — NFC on write, the N8-C3 remedy'],
    ['align_blocker', /^##\s*Phase 1/m, 'Phase 1 — the column'],
    ['dropped_marker', /^##\s*Phase 4\.5/m, 'Phase 4.5 — the producer'],
    ['chapter_announcement', /^##\s*Phase 4\.5/m, 'Phase 4.5 — the producer'],
    ['table_cell', /^##\s*Phase 4\.5/m, 'Phase 4.5 — the producer'],
  ];
  for (const [ident, heading, why] of PHASE_BOUND) {
    if (!new RegExp(`\\b${ident}\\b`).test(phaseOf(heading))) {
      add('CRITICAL', 'phase-scope', 'roadmap', 0,
        `[PHASE] \`${ident}\` is not in ${why} — presence elsewhere in the roadmap is not scheduling`);
    }
  }

  // 2c-ii. PRODUCER SIGNATURE PARITY. Phase 4.5's `utter(` must take the same
  // arguments the spec declares. A control mentioned elsewhere in the phase is
  // not a control the producer is told about (Halo acceptance mutation 6).
  const argsOf = (t) => new Set(((t.match(/utter\(([\s\S]*?)\)/) || [, ''])[1])
    .split(',').map((s) => s.trim().replace(/[`*\n ]/g, '')).filter((s) => /^[a-z_.[\]]+$/.test(s)));
  const specArgs = argsOf(src.spec);
  const roadArgs = argsOf(phaseOf(/^##\s*Phase 4\.5/m));
  for (const a of specArgs) {
    if (!roadArgs.has(a)) {
      add('CRITICAL', 'phase-scope', 'roadmap', 0,
        `[PHASE] Phase 4.5's utter() signature is missing \`${a}\` — the producer is never told about it`);
    }
  }

  // 2d. §7.2 COLUMN PRESENCE. A declared column may not silently vanish from
  // the data model (Halo acceptance mutations 2b and 7).
  // (table, column) pairs, not a segments-only list. Retiring the PLACEMENT
  // row for `align_blocker` was correct — it encoded the position N9-C3
  // overturned — but it was the only watcher, and nothing replaced it, so the
  // rendition half of the remedy could be deleted at a green gate (J11-M2).
  const REQUIRED_COLS = [
    ['segments', 'align_blocker'], ['segments', 'disclosure_fingerprint'],
    ['segments', 'lexicon_fingerprint'], ['segments', 'text_hash'],
    ['segments', 'spoken_text'], ['segments', 'normalizer_version'],
    ['segment_renditions', 'align_blocker'], ['segment_renditions', 'align_status'],
    ['segment_renditions', 'words'], ['segment_renditions', 'audio_path'],
  ];
  for (const [table, col] of REQUIRED_COLS) {
    if (!(columnsOf.get(table) ?? new Set()).has(col)) {
      add('CRITICAL', 'column-presence', 'spec', 0,
        `[COL] \`${col}\` is required on \`${table}\` and is absent from its §7 column run`);
    }
  }

  // 2e. §9.1 SPAN KINDS. The kind enumeration is what a client filters on;
  // losing one silently drops a disclosure channel (Halo acceptance mutation 3).
  const manifest = section(src.spec, /^### 9\.1/m, /^#+\s*10\./m);
  for (const k of ['skipped', 'undescribed', 'inserted', 'suppressed', 'dropped']) {
    if (!new RegExp(`"kind":\\s*"${k}"`).test(manifest)) {
      add('CRITICAL', 'span-kind', 'spec', 0,
        `[KIND] §9.1 has no worked example with kind "${k}" — a client filtering on kind loses that channel`);
    }
  }

  // 3. Prose regressions — normative lines only (blockquotes cite superseded
  // wording deliberately). `_` is NOT stripped: it is the identifier separator.
  // Invariants: the guarded sentence must be PRESENT. BANNED guards absence;
  // these guard presence, which is the half that was missing.
  for (const inv of INVARIANTS) {
    if (!inv.re.test(src[inv.doc])) {
      add('CRITICAL', 'invariant', inv.doc, 0,
        `[${inv.id}] a load-bearing invariant is missing or inverted — ${inv.why}`);
    }
  }

  for (const ban of BANNED) {
    src[ban.doc].split('\n').forEach((raw, i) => {
      if (/^\s*>/.test(raw)) return;
      // `wholeDoc` guards match a token that may be split across a wrapped
      // line, so they run against the raw line without emphasis stripping.
      const flat = ban.wholeDoc ? raw : raw.replace(/[*`~]/g, '');
      const m = flat.match(ban.re);
      if (m) add('CRITICAL', 'prose-regression', ban.doc, i + 1,
        `[${ban.id}] "${m[0].slice(0, 60)}" — ${ban.why}`);
    });
  }

  // 4. Structural requirements — count occurrences, not presence
  for (const g of STRUCTURAL) {
    const n = src[g.doc].split(g.need).length - 1;
    if (n < g.min) {
      add('CRITICAL', 'structural', g.doc, 0,
        `[${g.id}] "${g.need}" appears ${n}× (needs ≥${g.min}) — ${g.why}`);
    }
  }

  // 5. Producer signature — the open paren is the point (N6-M1)
  const producerSig = (src.spec.match(/\butter\([^)]*\)/) || [''])[0];
  if (producerSig && !phase45.includes('utter(')) {
    add('MAJOR', 'producer-signature', 'roadmap', 0,
      '[PROD] Phase 4.5 never names `utter(` — the phase header states a superseded signature');
  }

  // 6. Control chain
  for (const c of CONTROLS) {
    const missing = [];
    if (!schemaText.includes(c.name)) missing.push('schema column');
    if (!apiSection.includes(c.route ?? c.name)) missing.push('write route');
    if (!phase1.includes(c.name)) missing.push('migration');
    if (c.hash) {
      if (!producerSig.includes(c.name)) missing.push('producer input');
      if (!hashInputs.includes(c.hash)) missing.push('text_hash');
    }
    if (c.catalogue && !new RegExp(`i18n|catalogue`).test(apiSection)) missing.push('catalogue');
    if (missing.length) {
      add('CRITICAL', 'control-chain', 'spec', 0,
        `[CTL-${c.name}] chain broken at: ${missing.join(', ')}`);
    }
  }

  // 7. SELF-DESCRIPTION. Jury round 7: "It already checks the documents; it
  // doesn't yet check what the documents say about it." Every claim the
  // artifacts make ABOUT this tool, and about their own revision, is checked.
  for (const [key, txt] of Object.entries(src)) {
    for (const m of txt.matchAll(/(\d+)\s+prose[- ]regression guards/gi)) {
      if (Number(m[1]) !== BANNED.length) {
        add('MAJOR', 'self-description', key, lineOf(txt, m.index),
          `[SD-COUNT] claims ${m[1]} prose guards; there are ${BANNED.length}`);
      }
    }
    for (const m of txt.matchAll(/\*\*Revision:\*\*\s*v(\d+)/g)) {
      if (Number(m[1]) !== CURRENT_REVISION) {
        add('MAJOR', 'self-description', key, lineOf(txt, m.index),
          `[SD-REV] header says v${m[1]}; current revision is v${CURRENT_REVISION}`);
      }
    }
    for (const m of txt.matchAll(/rounds?\s*1[–-](\d+)/gi)) {
      if (Number(m[1]) < ROUNDS_ON_DISK) {
        add('MAJOR', 'self-description', key, lineOf(txt, m.index),
          `[SD-ROSTER] roster says rounds 1–${m[1]}; ${ROUNDS_ON_DISK} audit records exist`);
      }
    }
    // The roadmap enumerates rounds as a FILENAME list, which the range form
    // above cannot see — so the guard sat green over a stale roster (N8-M1).
    // `\d` not `\d+` made `-round10.md` parse as round 1 — the guard would have
    // reported a stale roster forever once the count reached double digits.
    const named = [...txt.matchAll(/-round(\d+)\.md/g)].map((x) => Number(x[1]));
    if (named.length && Math.max(...named) < ROUNDS_ON_DISK) {
      add('MAJOR', 'self-description', key, lineOf(txt, txt.indexOf('-round')),
        `[SD-ROSTER] filename roster stops at -round${Math.max(...named)}.md; ${ROUNDS_ON_DISK} records exist`);
    }
  }
  // Enum-count claims must match the declared union.
  const irCount = (src.spec.match(/type InsertedReason =([\s\S]*?)\n\n/) || [, ''])[1]
    .split('|').filter((s) => /'/.test(s)).length;
  // Match "all five" AND the "every" evasion that emptied this guard in v7
  // (N8-M10/N8-m2): rewording a wrong count to a vague word is not a fix.
  for (const m of src.spec.matchAll(/\b(all|every)\s+(\w+)?\s*`?InsertedReason`?\s+values/gi)) {
    const words = { two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9 };
    const raw = (m[2] ?? '').toLowerCase();
    if (!raw) {
      add('MAJOR', 'self-description', 'spec', lineOf(src.spec, m.index),
        `[SD-ENUM] states "every InsertedReason values" with no number; the union declares ${irCount} — write the number`);
      continue;
    }
    const claimed = words[raw] ?? Number(raw);
    if (claimed !== irCount) {
      add('MAJOR', 'self-description', 'spec', lineOf(src.spec, m.index),
        `[SD-ENUM] claims "${m[1]} ${raw}" InsertedReason values (${claimed}); the union declares ${irCount}`);
    }
  }

  return out;
}

// ── Load ─────────────────────────────────────────────────────────────────
const src = {};
const missing = [];
for (const [key, path] of Object.entries(DOCS)) {
  src[key] = read(path);
  if (src[key] === null) missing.push(key);
}
if (missing.length) {
  // Exit 2 ONLY when every missing document is one of the deliberately
  // gitignored ones. A missing CLAUDE.md is a real failure and must not wear
  // the "not applicable" label (N7-M5).
  const allPrivate = missing.every((k) => PRIVATE.has(k));
  if (allPrivate) {
    console.log('doc-check: NOT RUN — the private design documents are absent:');
    for (const k of missing) console.log(`  ${DOCS[k]}`);
    console.log('\n`resources/` is gitignored by design, so this gate runs only where those');
    console.log('documents exist. It is an authoring gate, not CI. Exit 2 is NOT a pass.');
    process.exit(2);
  }
  console.log('doc-check: FAILED — required tracked documents are missing:');
  for (const k of missing.filter((k) => !PRIVATE.has(k))) console.log(`  ${DOCS[k]}`);
  process.exit(1);
}

// ── Self-test: mutate the REAL documents, run the REAL checks ────────────
if (process.argv.includes('--self-test')) {
  const results = [];
  const baseline = runChecks(src);
  if (baseline.length) {
    console.log('self-test: ABORTED — baseline is not clean, so red/green is meaningless.');
    console.log('Fix the findings from `node tools/doc-check.mjs` first.');
    process.exit(1);
  }

  const trial = (id, doc, mutate) => {
    const mutated = { ...src, [doc]: mutate(src[doc]) };
    if (mutated[doc] === src[doc]) {
      results.push([false, `${id}: MUTATION WAS A NO-OP — the specimen no longer matches the document`]);
      return;
    }
    // Exact ID only. `f.message.includes(id)` let `REV` pass on an `[SD-REV]`
    // message — a substring false-green Jury demonstrated (N8-M6).
    const fired = runChecks(mutated).some((f) => f.id === id);
    results.push([fired, fired ? id : `${id}: guard did NOT fire on its own defect`]);
  };

  for (const b of BANNED) trial(b.id, b.doc, b.mutate);
  for (const inv of INVARIANTS) trial(inv.id, inv.doc, inv.mutate);
  // Structural: reduce to below `min`, the faithful mutation for a
  // one-occurrence defect (total deletion is the one mutation every
  // presence-predicate survives).
  for (const g of STRUCTURAL) {
    trial(g.id, g.doc, (t) => {
      let seen = 0;
      return t.split(g.need).reduce((acc, part, i) =>
        i === 0 ? part : acc + (++seen < g.min ? g.need : '~~X~~') + part, '');
    });
  }
  trial('PROD', 'roadmap', (t) => t.replace(/utter\(/g, 'utterance of ('));
  trial('MIG-H', 'roadmap', (t) => t.split('disclosure_fingerprint').join('~~X~~'));
  trial('REV', 'spec', (t) => t.replace(/### 7\.2 `segments`/, '### 7.2 `segments`\n\n`bogus_spurious_column` ·'));
  trial('SD-REV', 'spec', (t) => t.replace(/\*\*Revision:\*\* v\d+/, '**Revision:** v3'));
  trial('SD-COUNT', 'spec', (t) => t.replace(/`node tools\/doc-check\.mjs`/, '99 prose-regression guards via `node tools/doc-check.mjs`'));
  trial('CTL-ui_locale', 'spec', (t) => t.split('ui_locale').join('~~X~~'));
  // Faithful FWD specimen: delete a declared interface field from §7 entirely.
  // The first attempt renamed a table row, which exercises MIG-T instead — the
  // harness reported it as a dead guard, correctly. A mutation that does not
  // reproduce the defect proves nothing about the guard for it.
  // Move a column onto the wrong table — Jury's N8-C2 demonstration, as a test.
  trial('PLACE', 'spec', (t) =>
    t.replace(/(### 7\.2 `segments`[\s\S]{0,400}?`display_byte_count`)/,
      '$1 · `align_status`'));
  // ── Halo's seven acceptance mutations, round 9, installed as trials in
  // round 10 after three rounds of being read rather than executed. Halo:
  // "A specimen that lives in an audit report protects nothing; a specimen
  // that lives in results.push cannot be forgotten and fails the build."
  trial('S2R', 'roadmap', (t) => t.split('`chapter_announcement`,').join(''));           // 1
  trial('S2R', 'roadmap', (t) => t.split('align_blocker').join('~~X~~'));                // 2a
  trial('COL', 'spec', (t) => t.replace(/ · \*\*`align_blocker`\*\*/, ''));              // 2b
  trial('KIND', 'spec', (t) => t.replace(/"kind": "dropped"/, '"kind": "skipped"'));     // 3
  trial('PHASE', 'roadmap', (t) => t.replace(/NFC on `user_lexicon\.surface_form`/, 'NFC on the lexicon key')); // 4
  trial('S2R', 'roadmap', (t) => t.replace(/, \*\*`table_cell`\*\*/, ''));               // 5
  trial('PHASE', 'roadmap', (t) => t.replace(/skip_policy, content_narration,/, 'skip_policy,')); // 6
  trial('COL', 'spec', (t) => t.replace(/ · \*\*`disclosure_fingerprint`\*\*/, ''));     // 7

  trial('FWD', 'spec', (t) => {
    const i = t.search(/^#+\s*7\.\s*Data model/m);
    return t.slice(0, i) + t.slice(i).split('`heading_level`').join('~~X~~');
  });

  const failed = results.filter(([ok]) => !ok);
  console.log(`self-test: ${results.length - failed.length} passed, ${failed.length} failed`);
  console.log('  (each mutates the live document and runs the shipped checks)\n');
  for (const [, msg] of failed) console.log(`  FAIL  ${msg}`);
  if (!failed.length) {
    // Honest coverage, not "every guard". Three consecutive rounds this tool
    // was over-claimed in the sentence beside the number (N7-C7, N8-M10).
    const covered = new Set(results.map(([, m]) => String(m).split(':')[0]));
    console.log(`  ${covered.size} check IDs have a mutation and all of them fire.`);
    console.log('  NOT mutated: LOC-7, LOC-P1, MIG-T, SD-ROSTER, SD-ENUM, HARVEST, and');
    console.log('  4 of 5 CTL-* chains. Those are verified by hand, not by this harness.');
  }
  process.exit(failed.length ? 1 : 0);
}

// ── Report ───────────────────────────────────────────────────────────────
const findings = runChecks(src);
const order = { BLOCKER: 0, CRITICAL: 1, MAJOR: 2, MINOR: 3 };
findings.sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9));

if (!findings.length) {
  console.log('doc-check: clean — 0 findings');
  console.log(`  prose guards ${BANNED.length} · structural ${STRUCTURAL.length} · controls ${CONTROLS.length}`);
  console.log('  run --self-test to verify each guard still fires on its own defect');
} else {
  console.log(`doc-check: ${findings.length} finding(s)\n`);
  for (const f of findings) {
    console.log(`  ${f.severity.padEnd(8)} ${f.check.padEnd(22)} ${DOCS[f.doc]}:${f.line}`);
    console.log(`           ${f.message}\n`);
  }
}
process.exit(findings.length ? 1 : 0);
