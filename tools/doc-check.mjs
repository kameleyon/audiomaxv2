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
import { createHash } from 'node:crypto';
import { execSync } from 'node:child_process';

const DOCS = {
  spec: 'resources/specs/2026-08-08-audiomax-backend-design.md',
  roadmap: 'resources/roadmap/2026-08-08-backend-roadmap.md',
  claude: 'CLAUDE.md',
  readme: 'README.md',
  // J19-M2 — the committed documentation surface roughly doubled and none of it
  // was read by any check. Every site of J19-M1 but one sat in this blind region.
  contributing: 'CONTRIBUTING.md',
  adrIndex: 'docs/architecture/README.md',
  glossary: 'docs/glossary.md',
  // H20-M4 — J19-M2 extended DOCS from four files to seven and left the MOST
  // damaged files outside it. Halo found four Criticals in that blind region
  // while the gate exited 0. The ADRs are committed, public, and read as settled.
  codeowners: 'CODEOWNERS',
  adr1: 'docs/architecture/0001-the-segment-is-the-universal-unit.md',
  adr2: 'docs/architecture/0002-observe-what-was-spoken-do-not-predict-it.md',
  adr3: 'docs/architecture/0003-haitian-creole-tts-routing.md',
  adr4: 'docs/architecture/0004-the-accessibility-gate-is-an-api-conformance-harness.md',
  adr5: 'docs/architecture/0005-haitian-creole-is-removed-from-scope.md',
};
const PRIVATE = new Set(['spec', 'roadmap']);   // gitignored by owner decision
const CURRENT_REVISION = 19;

// J22-M5 / H26 — THE MEASUREMENT ARTIFACTS. Round 26 opened with: "The gate was
// green — exit 0, self-test 54/54 — and every finding below is invisible to it,
// because NO GUARD READS `aligner/spike-a/out/`. A headline can contradict its
// own artifact and exit 0." Every check in this file read prose. The documents
// quote numbers; the numbers live here; nothing compared them.
const ARTIFACT_DIR = 'aligner/spike-a/out';
// The audio manifest is the ONLY record in this directory that ties a result to
// the bytes it scored. J26-M5 killed the mtime-based staleness check: git does
// not store mtimes, so a clone sets every file to checkout time and the guard
// was born unreproducible. Everything [ART-STALE] does now is content.
const MANIFEST = 'tts-manifest.json';
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

// Every JSON in the artifact directory, plus every key that appears anywhere in
// it at any depth, plus the CONTENT HASH of every .wav. `keys` is what lets a
// document's claim that SPIKE A "returns" a metric be checked against a file
// that returns it; `wavs` is what lets a result be checked against the audio it
// says it scored, on a fresh clone, where no mtime survives (J26-M5).
function loadArtifacts() {
  const out = { files: {}, keys: new Set(), wavs: {}, present: false };
  if (!existsSync(ARTIFACT_DIR)) return out;
  const walk = (v) => {
    if (Array.isArray(v)) return v.forEach(walk);
    if (v && typeof v === 'object') {
      for (const [k, x] of Object.entries(v)) { out.keys.add(k); walk(x); }
    }
  };
  for (const f of readdirSync(ARTIFACT_DIR)) {
    const p = `${ARTIFACT_DIR}/${f}`;
    if (f.endsWith('.wav')) {
      const buf = readFileSync(p);
      out.wavs[f] = { sha256: createHash('sha256').update(buf).digest('hex'), bytes: buf.length };
      continue;
    }
    if (!f.endsWith('.json')) continue;
    try {
      const data = JSON.parse(readFileSync(p, 'utf8'));
      out.files[f] = { data };
      out.present = true;
      walk(data);
    } catch { /* a malformed artifact is caught by ART-ABSENT below */ }
  }
  return out;
}

// Collect every numeric value stored under a given key, at any depth, in ONE
// artifact file.
//
// J26-M2 — this used to union across EVERY file in the directory and then union
// `<metric>_endpoints_credited` on top, so "any mixture of model, metric
// definition and configuration passes". The published 70.8/77.3/79.2 is exactly
// such a mixture: two endpoint-credited figures from the base run and one raw
// figure from the `small` model. Nothing that unions can see it. Values are
// therefore harvested PER FILE and PER ACCOUNTING BASIS, and a quoted set has to
// be reproducible from one of them.
function valuesIn(data, key) {
  const found = new Set();
  const walk = (v) => {
    if (Array.isArray(v)) return v.forEach(walk);
    if (v && typeof v === 'object') {
      for (const [k, x] of Object.entries(v)) {
        if (k === key && typeof x === 'number') found.add(Number(x.toFixed(1)));
        walk(x);
      }
    }
  };
  walk(data);
  return found;
}

// Every (file, basis) pair that reports `key`. A "basis" is an accounting rule:
// the raw metric, or the endpoint-credited upper bound, which is the SAME
// quantity computed under a different admission rule and is therefore a
// different configuration, not an alternative reading of the same one.
function configurations(art, key) {
  const out = [];
  for (const [f, v] of Object.entries(art.files)) {
    const raw = valuesIn(v.data, key);
    if (raw.size) out.push({ label: `${f} (as reported)`, vals: raw });
    const credited = valuesIn(v.data, `${key}_endpoints_credited`);
    if (credited.size) out.push({ label: `${f} (endpoints credited)`, vals: credited });
  }
  return out;
}

// Every object in an artifact that carries both a language and the duration of
// the audio it scored. That pair is the provenance link [ART-STALE] checks.
function scoredRows(data) {
  const rows = [];
  const walk = (v) => {
    if (Array.isArray(v)) return v.forEach(walk);
    if (v && typeof v === 'object') {
      if (typeof v.lang === 'string' && typeof v.audio_seconds === 'number') rows.push(v);
      for (const x of Object.values(v)) walk(x);
    }
  };
  walk(data);
  return rows;
}

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
  // J18 §5 — Jury: "the repair for my highest-severity finding of round seventeen
  // is the least protected line in the document." Delete spec's no-route row and
  // the routing table is total again, blocked_language_unsupported loses its
  // raiser, speech_blocker returns 0 for every document -- and the gate exits 0.
  { id: 'INV-NO-ROUTE', doc: 'spec',
    re: /\*\*Any other language\*\* \| \*\*NO ROUTE\./,
    why: 'J17-C1 -- the §3.5 routing table must stay NON-TOTAL. A catch-all row makes routing total over languages, so blocked_language_unsupported can never fire and the pre-payment speech disclosure reports 0 for every document. A disclosure with no raiser is worse than absent',
    mutate: (t) => t.replace(/\| \*\*Any other language\*\* \| \*\*NO ROUTE\.[^|]*\|/,
      '| Everything else | Google / Gemini TTS |') },
  // The align_blocker column has produced a Critical in THREE consecutive rounds
  // (J15-C1 -> J16-C2 -> J17-C2), always by writing the new enum without deleting
  // the old. v18 guarded ONE of its four sites. These are the other three.
  { id: 'INV-SEG-BLOCKER-ARITY', doc: 'spec',
    re: /`segments\.align_blocker` \(`null｜no_transcriber｜excessive_drop`\)/,
    why: 'the SEGMENT blocker carries the two VOICE-INDEPENDENT values. Putting transcription_unreliable here stores a (lang, voice) fact in a table with no voice_id -- right for one voice, wrong for every other, discovered after payment (J16-C2)',
    mutate: (t) => t.replace(/`segments\.align_blocker` \(`null｜no_transcriber｜excessive_drop`\)/,
      '`segments.align_blocker` (`null｜no_transcriber｜transcription_unreliable`)') },
  { id: 'INV-RND-BLOCKER-ARITY', doc: 'spec',
    re: /`segment_renditions\.align_blocker`\s*\n?\(`null｜transcription_unreliable｜wrong_match`\)/,
    why: 'the RENDITION blocker must carry THREE values. Drop transcription_unreliable and the column cannot hold the ht pre-payment word-sync disclosure -- the spec twin of INV-RM-BLOCKER-ARITY (J17-C2)',
    mutate: (t) => t.replace(/\(`null｜transcription_unreliable｜wrong_match`\)/,
      '(`null｜wrong_match`)') },
  { id: 'INV-RM-SEG-ARITY', doc: 'roadmap',
    re: /`segments\.align_blocker`\*\* \(`null｜`\*\*`no_transcriber`\*\*`｜`\*\*`excessive_drop`/,
    why: 'roadmap:281 -- the FIFTH site of J17-C2, found mid-fix and left unguarded. This is the enum Atlas builds the segment column from',
    mutate: (t) => t.replace(/\(`null｜`\*\*`no_transcriber`\*\*`｜`\*\*`excessive_drop`\*\*`\)/,
      '(`null｜`**`no_transcriber`**`｜`**`transcription_unreliable`**`)') },
  // hallucination_rate is, by the roadmap's own words, "the only one of the
  // metrics that distinguishes ht from en". It appeared once and in no check.
  { id: 'INV-RM-HALLUCINATION', doc: 'roadmap',
    // J19-m2 / H20-M6, now PROVEN weak: this was a bare presence check, and
    // adding a second mention of the metric elsewhere in the roadmap made the
    // mutation a no-op. Anchored to the SPIKE A item it actually guards.
    re: /3b\. \*\*`hallucination_rate`\*\*/,
    why: 'H17-C3 -- p95_abs_error_ms is a TIMING bound and cannot see the documented ht failure mode: a fluently hallucinated token timed to 50ms and mapped to the wrong word. Delete this metric and SPIKE A cannot distinguish Creole from English',
    mutate: (t) => t.replace(/3b\. \*\*`hallucination_rate`\*\*/, '3b. **`token_error_rate`**') },
  { id: 'INV-OFFSETS', doc: 'spec', re: /len\(block_start_offsets\)/,
    why: 'without the length invariant nothing can be announced at a position',
    mutate: (t) => t.replace(/len\(block_start_offsets\)/, 'len(offsets)') },
  // ── J22-M5 — THE BLIND REGION ────────────────────────────────────────
  // "35 of 38 checks target two files. ZERO checks target the five ADRs, the
  // glossary, CONTRIBUTING.md or CODEOWNERS — and Halo found four Criticals in
  // exactly that blind region while the gate exited 0." DOCS has read those
  // files since round 20; no check has ever asserted anything about them, so
  // reading them bought nothing. These are the first.
  { id: 'INV-CO-DEFAULT', doc: 'codeowners',
    // GitHub CODEOWNERS resolves LAST MATCHING RULE WINS. So the danger is not
    // deletion, it is APPENDING `* SomeoneElse` at the bottom -- which silently
    // takes the commit gate away from Jury for EVERY path including this file,
    // and every specific rule above it. Exactly J22-M6's defeat-by-addition
    // shape, in the file that assigns the reviewers. The guard therefore asserts
    // the catch-all is the FIRST rule and the ONLY one.
    re: /^\*\s+Jury\b/m,
    why: 'CODEOWNERS is last-match-wins, so the `*` default must be the first and only catch-all and must name Jury. A second `*` rule appended below re-owns every path in the file, including CLAUDE.md and this gate',
    mutate: (t) => t.replace(/^\*\s+Jury\b/m, '# * Jury') },
  { id: 'INV-CO-GATE', doc: 'codeowners', re: /^\/tools\/doc-check\.mjs\s+\S/m,
    why: 'the gate tool must have a named reviewer. Weakening a check to make a document pass is the failure this tool exists to prevent, and an unowned path is one nobody is required to look at',
    mutate: (t) => t.replace(/^\/tools\/doc-check\.mjs.*\n/m, '') },
  { id: 'INV-GLOSSARY-BAR', doc: 'glossary',
    re: /`matched_within_drift_pct >= 95`[^.]{0,80}`p95_abs_error_ms <= 300`/,
    why: 'the glossary is where a newcomer learns what the bar IS. Both halves must be stated: a bar quoted as a match rate with no timing half is the H21-C3 defect, in which DRIFT_MS was defined and never applied',
    mutate: (t) => t.replace(/`matched_within_drift_pct >= 95` and `p95_abs_error_ms <= 300`/,
      '`matched_within_drift_pct >= 95`') },
  { id: 'INV-ADR2-OBSERVE', doc: 'adr2', re: /`hallucination_rate`/,
    why: 'ADR-0002 is the decision record for OBSERVE-DO-NOT-PREDICT. hallucination_rate is the only metric that can see an invented token — a failure prediction could not produce and observation can — so an ADR that drops it no longer records the risk its own decision introduced (H26 "do not retire it")',
    mutate: (t) => t.replace(/`hallucination_rate`/g, '`token_error_rate`') },
  { id: 'INV-CONTRIB-GATE', doc: 'contributing', re: /`FAIL`[^|]*\|\s*Any open Blocker or Critical\s*\|\s*\*\*Blocked\*\*/,
    why: 'CONTRIBUTING is the only place a contributor reads the commit gate before running it. The FAIL row is the half that blocks; a table listing only the permissive verdicts is a gate that never closes',
    mutate: (t) => t.replace(/^\|\s*`FAIL`.*\n/m, '') },
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

// Read once at startup. `runChecks` takes an override so --self-test can run the
// shipped artifact guards over a synthetic artifact set.
const ARTIFACTS = loadArtifacts();

// [ART-FIGURE] abstains where prose binds a number to no metric unambiguously.
// Counted and printed, never silent: a check that quietly examines nothing is
// the failure this file was rebuilt in round 7 to end, and J26-M3 is that same
// failure arriving through an `if (!vals.size) continue`.
const ABSTENTIONS = new Map();

// ── The self-test specimens, as DATA ─────────────────────────────────────
// They used to be a run of `trial(...)` calls inside the --self-test branch, so
// their number was knowable only by running it. CONTRIBUTING.md, README.md and
// the roadmap all state that number, and nothing checked them; [SD-SELFTEST]
// below can only exist because the count is computable here.
//
// Each entry is [id, doc, mutate] and mutates the LIVE document. `opts` entries
// instead run the shipped checks over injected non-document state, which is the
// only way to falsify a guard that reads git or the artifact directory.

// A WELL-FORMED synthetic artifact directory, so an artifact trial perturbs one
// property and nothing else. Overrides merge into `files` rather than replacing
// it: the previous specimens replaced the whole map, which silently deleted the
// manifest and made every [ART-STALE] trial pass for the wrong reason.
const SYNTH = ({ files = {}, wavs, keys, ...rest } = {}) => ({
  present: true,
  // The metric names the roadmap's SPIKE A block requires. Listed so an
  // [ART-METRIC] trial can remove them and nothing else.
  keys: keys ?? new Set(['median_abs_error_ms', 'p95_abs_error_ms',
    'matched_within_drift_pct', 'hallucination_rate', 'compute_cost_per_audio_hour_usd']),
  wavs: wavs ?? { 'en.wav': { sha256: 'aaaa', bytes: 4 } },
  files: {
    'tts-manifest.json': { data: [{ path: 'en.wav', sha256: 'aaaa', bytes: 4, seconds: 11.63 }] },
    'x.json': {
      data: [{
        lang: 'en', audio_seconds: 11.63,
        matched_within_drift_pct: 62.5, match_rate_pct: 100, hallucination_rate: 0,
        median_drift_ms: 99.7, p95_drift_ms: 426.7,
        median_abs_error_ms: 120, p95_abs_error_ms: 260,
      }],
    },
    ...files,
  },
  ...rest,
});

const EXTRA_TRIALS = [
  ['PROD', 'roadmap', (t) => t.replace(/utter\(/g, 'utterance of (')],
  ['MIG-H', 'roadmap', (t) => t.split('disclosure_fingerprint').join('~~X~~')],
  ['REV', 'spec', (t) => t.replace(/### 7\.2 `segments`/, '### 7.2 `segments`\n\n`bogus_spurious_column` ·')],
  ['SD-REV', 'spec', (t) => t.replace(/\*\*Revision:\*\* v\d+/, '**Revision:** v3')],
  ['SD-COUNT', 'spec', (t) => t.replace(/`node tools\/doc-check\.mjs`/, '99 prose-regression guards via `node tools/doc-check.mjs`')],
  ['CTL-ui_locale', 'spec', (t) => t.split('ui_locale').join('~~X~~')],
  // Move a column onto the wrong table — Jury's N8-C2 demonstration, as a test.
  ['PLACE', 'spec', (t) => t.replace(/(### 7\.2 `segments`[\s\S]{0,400}?`display_byte_count`)/, '$1 · `align_status`')],
  // ── Halo's seven acceptance mutations, round 9, installed as trials in
  // round 10 after three rounds of being read rather than executed. Halo:
  // "A specimen that lives in an audit report protects nothing; a specimen
  // that lives in results.push cannot be forgotten and fails the build."
  ['S2R', 'roadmap', (t) => t.split('`chapter_announcement`,').join('')],                 // 1
  ['S2R', 'roadmap', (t) => t.split('align_blocker').join('~~X~~')],                      // 2a
  ['COL', 'spec', (t) => t.replace(/ · \*\*`align_blocker`\*\*/, '')],                    // 2b
  ['KIND', 'spec', (t) => t.replace(/"kind": "dropped"/, '"kind": "skipped"')],           // 3
  ['PHASE', 'roadmap', (t) => t.replace(/NFC on `user_lexicon\.surface_form`/, 'NFC on the lexicon key')], // 4
  ['S2R', 'roadmap', (t) => t.replace(/, \*\*`table_cell`\*\*/, '')],                     // 5
  ['PHASE', 'roadmap', (t) => t.replace(/skip_policy, content_narration,/, 'skip_policy,')], // 6
  ['COL', 'spec', (t) => t.replace(/ · \*\*`disclosure_fingerprint`\*\*/, '')],           // 7
  // Faithful FWD specimen: delete a declared interface field from §7 entirely.
  ['FWD', 'spec', (t) => {
    const i = t.search(/^#+\s*7\.\s*Data model/m);
    return t.slice(0, i) + t.slice(i).split('`heading_level`').join('~~X~~');
  }],
  // ── J22-M6 — DEFEAT BY ADDITION. Append a SECOND catch-all row beneath the
  // no-route row. INV-NO-ROUTE still passes (the row it looks for is untouched);
  // NO-ROUTE-TOTAL is the guard that has to see it.
  ['NO-ROUTE-TOTAL', 'spec', (t) => t.replace(
    /(\| \*\*Any other language\*\* \| \*\*NO ROUTE\.[^\n]*\n)/,
    '$1| Everything else | Google / Gemini TTS |\n')],
  // ── J26-M4 — the two synonyms Jury named as defeating the lexical version,
  // INSERTED ABOVE the refusal, where the ordering leg cannot see them. If these
  // two do not go red, the repair is the same denylist with more entries.
  ['NO-ROUTE-TOTAL', 'spec', (t) => t.replace(
    /(\| \*\*Any other language\*\* \| \*\*NO ROUTE\.)/,
    '| Languages not enumerated above | Gemini TTS via OpenRouter |\n$1')],
  ['NO-ROUTE-TOTAL', 'spec', (t) => t.replace(
    /(\| \*\*Any other language\*\* \| \*\*NO ROUTE\.)/,
    '| Fallback | Gemini TTS via OpenRouter |\n$1')],
  // The defeat that survives the restriction leg: a row that NAMES languages and
  // routes their complement. Leg 3 is the only thing that sees it.
  ['NO-ROUTE-TOTAL', 'spec', (t) => t.replace(
    /(\| \*\*Any other language\*\* \| \*\*NO ROUTE\.)/,
    '| Any language other than `en`, `es`, `fr` | Gemini TTS via OpenRouter |\n$1')],
  // A document stating a --self-test result that is not the one the harness
  // declares. Run against README.md rather than CONTRIBUTING.md so the trial
  // stays live while CONTRIBUTING's own count is open.
  ['SD-SELFTEST', 'readme', (t) => `${t}\n\nself-test reports 3 passed, 0 failed.\n`],
  // CODEOWNERS defeat by addition: a bare catch-all appended at the bottom.
  // INV-CO-DEFAULT survives this mutation — it was demonstrated surviving it —
  // which is precisely why CO-DEFAULT exists.
  ['CO-DEFAULT', 'codeowners', (t) => `${t}\n*                               Nobody\n`],
  // ── J22-M5 / H26 — the artifact guards, falsified against injected artifacts.
  // A well-formed synthetic directory: one result file, one manifest, one audio
  // hash that agrees with it. Each trial below perturbs exactly one property.
  ['ART-FIGURE', null, null, {
    // A headline figure the artifact does not contain (H26-C1's exact shape).
    artifacts: SYNTH({ files: { 'x.json': { data: [{ matched_within_drift_pct: 11.1 }] } } }),
  }],
  // J26-M2 — the MIXTURE. Every figure below is real and no run produces the
  // triple: 70.8 and 77.3 are endpoint-credited from the base run, 79.2 is raw
  // from the `small` model. This is the exact set that shipped, and the unioning
  // version of the guard passed it.
  ['ART-FIGURE', 'readme', (t) => `${t}\n\n\`matched_within_drift_pct\` 70.8 / 77.3 / 79.2 against the bar.\n`],
  // J26-M1 — stated in PROSE, with no identifier anywhere near it. This is the
  // form that escaped the membership-only guard and shipped a Critical.
  ['ART-FIGURE', 'readme', (t) => `${t}\n\nOn this corpus the match rate is 42.4% in every language.\n`],
  // J26-M3 — the empty harvest. `hallucination_rate` was tracked under a name no
  // artifact emits, and the guard skipped it with a silent \`continue\` for all
  // twelve documents. Removing the key from every file must now go RED.
  ['ART-VACUOUS', null, null, {
    artifacts: SYNTH({ files: { 'x.json': { data: [{ matched_within_drift_pct: 62.5 }] } } }),
  }],
  ['ART-ABSENT', null, null, {
    artifacts: { present: false, keys: new Set(), files: {}, wavs: {} },
  }],
  ['ART-METRIC', null, null, {
    // Present but returning nothing the roadmap asks for — H26-M6 exactly.
    artifacts: SYNTH({ keys: new Set(['unrelated']), files: { 'x.json': { data: [{ unrelated: 1 }] } } }),
  }],
  ['ART-STALE', null, null, {
    // The successor to the mtime check, falsified on CONTENT: the result says it
    // scored 9.99 s of `en` audio and the manifest says en.wav is 11.63 s. This
    // trial runs identically on a fresh clone, which the mtime version could not
    // do at all (J26-M5).
    artifacts: SYNTH({ files: { 'x.json': { data: [{ lang: 'en', audio_seconds: 9.99 }] } } }),
  }],
  ['ART-STALE', null, null, {
    // The audio no longer hashes to what the manifest recorded — the audio was
    // replaced and every figure scored against it is stale.
    artifacts: SYNTH({ wavs: { 'en.wav': { sha256: 'ffff', bytes: 7 } } }),
  }],
  // ── J22-M6, second half — a brand-new top-level directory, which the old
  // allowlist could not see on the day it was created.
  ['STAGED', null, null, { injectedGitFiles: ['worker/src/queue/render.ts'] }],
];
const TRIAL_COUNT = BANNED.length + INVARIANTS.length + STRUCTURAL.length + EXTRA_TRIALS.length;

// ── The checks. One function, so the harness runs exactly what ships. ─────
function runChecks(src, opts = {}) {
  const out = [];
  ABSTENTIONS.clear();
  const add = (severity, check, doc, line, message) =>
    out.push({ severity, check, doc, line, message, id: message.match(/\[([\w-]+)\]/)?.[1] });
  const art = opts.artifacts ?? ARTIFACTS;

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
  const hashInputs = (src.spec.match(/text_hash = H\(([^)]*)\)/) || ['', ''])[1]
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
    [...((src.spec.match(/kind:\s*((?:'[a-z_]+'\s*\|?\s*)+)/) || ['', ''])[1])
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
  const argsOf = (t) => new Set(((t.match(/utter\(([\s\S]*?)\)/) || ['', ''])[1])
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

  // 6b. ROUTING TOTALITY — INV-NO-ROUTE'S MISSING HALF (J22-M6).
  //
  // INV-NO-ROUTE asserts the no-route row is PRESENT. Jury: "it is defeatable by
  // ADDITION. Append a second catch-all row beneath it and the §3.5 routing
  // table is total again, `blocked_language_unsupported` loses its raiser,
  // `speech_blocker` returns 0 for every document -- and the gate exits 0."
  // A presence guard cannot see an added row. This is the inversion: EVERY
  // catch-all condition in §3.5 must refuse, not route. One named exclusion
  // (the row that refuses), everything else flagged.
  // J26-M4 — THE LEXICAL VERSION DID NOT CLOSE THIS. v26 detected a catch-all
  // with a 15-phrase denylist anchored at the start of the condition cell.
  // Jury: *"'Languages not enumerated above' or 'Fallback' leaves it green while
  // routing goes total — defeatable by addition became defeatable by addition
  // plus a synonym."* A denylist is a list of the phrases someone already
  // thought of; the next author writes the sixteenth.
  //
  // STRUCTURAL REPLACEMENT. Three legs, none of them a phrase list. Every token
  // either leg reasons about is HARVESTED from the spec — the language codes
  // from the declared language line and from the table itself, the non-language
  // dimensions from §7's `voices` column run.
  //
  //   1. ORDERING. Exactly one row refuses, and it is the LAST data row. Any row
  //      appended below it fires whatever its wording. This is the leg that
  //      answers J22-M6, and it is wording-independent by construction.
  //   2. RESTRICTION. Every row above the refusal must constrain SOMETHING: it
  //      must name a language VALUE (a backticked code) or a dimension declared
  //      on `voices`. Naming the routing key itself — "language", "languages" —
  //      is not a constraint, it is the name of the thing being constrained, so
  //      "Languages not enumerated above" fires exactly like "Everything else".
  //   3. NO DOUBLE CLAIM. A language code may appear in at most one condition.
  //      This is what stops the defeat that survives leg 2: a row reading
  //      "Any language other than `en`, `es`, `fr`" names codes, so it looks
  //      restricted, but every code it names is claimed above it — which means
  //      the languages it actually routes are the ones nothing enumerates.
  const routing = section(src.spec, /^###\s*3\.5\s/m, /^###\s*3\.6|^##\s*4\./m);
  // §3.5 contains MORE than the routing table — the retry/re-render table lives
  // under the same heading — so the rows are taken from the FIRST contiguous run
  // of table lines only. Reading the whole section charged `retry` and
  // `re_render` with routing languages on the first run of this guard.
  const routingBlock = [];
  for (const raw of routing.split('\n')) {
    const isRow = /^\s*\|/.test(raw);
    if (isRow) routingBlock.push(raw);
    else if (routingBlock.length) break;
  }
  const routingRows = routingBlock
    .filter((raw) => !/^\s*\|[\s:|-]*\|?\s*$/.test(raw))
    .map((raw) => ({ raw, cells: raw.split('|').slice(1, -1).map((c) => c.trim()) }))
    .slice(1);   // drop the header row; the `---` separator is filtered above
  if (routing && routingRows.length) {
    // Language VALUES: the declared support line ("Languages: `en` / `es` / `fr`")
    // plus every two-letter code the table itself names, so a row for a language
    // that is out of scope (`ht`) still counts as restricted.
    const langCodes = new Set([
      ...[...(src.spec.match(/Languages:[^\n]*/) || [''])[0].matchAll(/`([a-z]{2})`/g)].map((m) => m[1]),
      ...[...routing.matchAll(/`([a-z]{2})`/g)].map((m) => m[1]),
    ]);
    // Non-language dimensions, harvested from the `voices` column run in §7.1.
    // A row may legitimately key on the VOICE rather than the language.
    const voiceCols = columnsOf.get('voices') ?? new Set();
    const dimStems = new Set(['voice']);   // the table's own name; always a dimension
    for (const col of voiceCols) {
      for (const part of col.split('_')) if (part.length >= 4) dimStems.add(part);
    }
    const refusals = routingRows.filter((r) => /NO ROUTE/i.test(r.raw));
    if (refusals.length !== 1) {
      add('CRITICAL', 'routing-totality', 'spec', 0,
        `[NO-ROUTE-TOTAL] §3.5 has ${refusals.length} rows that refuse; exactly one is ` +
        `required. Zero means routing is total by omission, so blocked_language_unsupported ` +
        `has no reachable raiser and §8.2's speech_blocker reports 0 for every document.`);
    } else if (routingRows[routingRows.length - 1] !== refusals[0]) {
      add('CRITICAL', 'routing-totality', 'spec', lineOf(src.spec, src.spec.indexOf(refusals[0].raw)),
        `[NO-ROUTE-TOTAL] the NO ROUTE row is not the LAST row of §3.5; ` +
        `${routingRows.length - 1 - routingRows.indexOf(refusals[0])} row(s) follow it. A row ` +
        `beneath the refusal makes routing total over languages again — this is J22-M6, and ` +
        `it does not matter what the added row is called.`);
    }
    const claimed = new Map();
    for (const r of routingRows) {
      if (/NO ROUTE/i.test(r.raw)) continue;
      const cond = r.cells[0] ?? '';
      const codes = [...cond.matchAll(/`([a-z]{2})`/g)].map((m) => m[1]).filter((c) => langCodes.has(c));
      const dims = [...dimStems].filter((s) => new RegExp(`\\b${s}`, 'i').test(cond));
      if (!codes.length && !dims.length) {
        add('CRITICAL', 'routing-totality', 'spec', lineOf(src.spec, src.spec.indexOf(r.raw)),
          `[NO-ROUTE-TOTAL] §3.5 row "${cond.slice(0, 48)}" ROUTES without constraining ` +
          `anything: it names no language code from {${[...langCodes].sort().join(', ')}} and no ` +
          `dimension declared on \`voices\` {${[...dimStems].sort().join(', ')}}. Naming the ` +
          `routing key ("language", "languages") is not a constraint. An unconstrained routing ` +
          `row makes the table total over languages, which leaves ` +
          `blocked_language_unsupported with no reachable raiser (J17-C1, J22-M6, J26-M4).`);
      }
      for (const c of codes) {
        if (claimed.has(c)) {
          add('CRITICAL', 'routing-totality', 'spec', lineOf(src.spec, src.spec.indexOf(r.raw)),
            `[NO-ROUTE-TOTAL] §3.5 names \`${c}\` in two routing conditions ` +
            `("${claimed.get(c).slice(0, 32)}" and "${cond.slice(0, 32)}"). A second row citing ` +
            `codes already claimed above it is not routing those languages — it is routing ` +
            `the complement, which is the catch-all this table may not contain (J26-M4).`);
        } else {
          claimed.set(c, cond);
        }
      }
    }
  }

  // 6c. CODEOWNERS TOTALITY — the same defeat-by-addition shape, in the file
  // that decides who reviews. GitHub resolves CODEOWNERS by LAST MATCHING RULE,
  // so appending `*  Nobody` at the bottom silently re-owns every path above it
  // -- CLAUDE.md, the audit trail, this gate -- while `*  Jury` is still there
  // for a presence guard to find. INV-CO-DEFAULT checks the rule EXISTS; this
  // checks nothing was added under it. Demonstrated: the first version of
  // INV-CO-DEFAULT did not fire on an appended `*  Nobody`, which is the whole
  // finding restated inside its own repair.
  const coRules = (src.codeowners || '').split('\n')
    .map((l, i) => [l, i])
    .filter(([l]) => l.trim() && !l.trim().startsWith('#'))
    .map(([l, i]) => [l.trim().split(/\s+/), i]);
  const coCatchAll = coRules.filter(([parts]) => parts[0] === '*');
  if (coRules.length) {
    if (coCatchAll.length !== 1) {
      add('CRITICAL', 'codeowners-totality', 'codeowners', (coCatchAll[1]?.[1] ?? 0) + 1,
        `[CO-DEFAULT] ${coCatchAll.length} catch-all \`*\` rules; exactly one is required. ` +
        `CODEOWNERS is LAST-MATCH-WINS, so a second one re-owns every path above it — ` +
        `including CLAUDE.md, resources/audits/ and this gate — without touching the rule a ` +
        `presence check looks for.`);
    } else if (coCatchAll[0][1] !== coRules[0][1]) {
      add('CRITICAL', 'codeowners-totality', 'codeowners', coCatchAll[0][1] + 1,
        `[CO-DEFAULT] the catch-all \`*\` rule is not the FIRST rule. Under last-match-wins ` +
        `every specific rule above it is dead.`);
    } else if (!coCatchAll[0][0].includes('Jury')) {
      add('CRITICAL', 'codeowners-totality', 'codeowners', coCatchAll[0][1] + 1,
        `[CO-DEFAULT] the catch-all \`*\` rule does not name Jury. CLAUDE.md gives Jury the ` +
        `commit gate for everything; no path is exempt.`);
    }
  }

  // 9. THE MEASUREMENT ARTIFACTS (J22-M5 / H26). No guard read aligner/spike-a/out/.
  if (!art.present) {
    add('CRITICAL', 'artifact', 'roadmap', 0,
      `[ART-ABSENT] no parsable JSON in ${ARTIFACT_DIR}. Every artifact check below is ` +
      `vacuous, and a vacuous check that reports nothing is how this gate sat green over ` +
      `two Blockers in round 26.`);
  } else {
    // (a) Every metric the roadmap says SPIKE A RETURNS must be a key in a file
    // it returned. H26-M6: `compute_cost_per_audio_hour_usd` was required by the
    // roadmap and appeared in NO file in out/ -- while the cost claim built on it
    // sat in the headline.
    const spikeBlock = section(src.roadmap, /Return these \w+ numbers per language/m,
      /\*\*Proposed bar/m);
    const required = [...new Set([...spikeBlock.matchAll(/`([a-z][a-z0-9_]*(?:_ms|_pct|_rate|_usd))`/g)]
      .map((m) => m[1]))];
    if (required.length < 4) {
      add('CRITICAL', 'artifact', 'roadmap', 0,
        `[ART-METRIC] harvested only ${required.length} required metric names from the SPIKE A ` +
        `block; expected at least 4. The parse returned little or nothing, so this check is ` +
        `vacuous — suspect a renamed heading.`);
    }
    for (const key of required) {
      if (!art.keys.has(key)) {
        add('CRITICAL', 'artifact', 'roadmap', 0,
          `[ART-METRIC] the roadmap requires SPIKE A to return \`${key}\` and NO file in ` +
          `${ARTIFACT_DIR} contains that key. A metric required in prose and emitted by nothing ` +
          `is a claim, not a measurement (H26-M6).`);
      }
    }
    // (b) A figure attributed to an artifact metric must be IN the artifact,
    // and a SET of figures presented as one result must come out of ONE
    // configuration. H26-C1: "Match rate 100% all three languages" was
    // contradicted by the only file computing it, and the gate exited 0 because
    // no guard opened the file.
    //
    // Three defects in the v26 form, all found by Jury:
    //   J26-M3  `hallucination_rate_pct` is not a key any artifact emits — every
    //           file writes `hallucination_rate` — so `if (!vals.size) continue`
    //           skipped the metric silently for all twelve documents. The metric
    //           that feeds the pre-payment disclosure to blind users had a guard
    //           that checked nothing. The key is corrected below and an EMPTY
    //           HARVEST IS NOW A FINDING ([ART-VACUOUS]), not a `continue`.
    //   J26-M1  it was MEMBERSHIP-ONLY on the literal identifier, so a figure
    //           stated in prose ("match rate is 100%") was invisible. That is how
    //           a Critical shipped in README.md. Metrics now carry a prose alias.
    //   J26-M2  it UNIONED every file and every accounting basis, so a mixture
    //           passed. Checked per (file, basis) now — see `configurations`.
    const TRACKED = [
      { key: 'matched_within_drift_pct', alias: /match(?:ed)?[ _-]within[ _-]drift/i },
      { key: 'match_rate_pct', alias: /match rate/i },
      { key: 'hallucination_rate', alias: /hallucination/i },
      { key: 'median_drift_ms', alias: /median drift/i },
      { key: 'p95_drift_ms', alias: /p95 drift/i },
      { key: 'median_abs_error_ms', alias: /median abs(?:olute)? error/i },
      { key: 'p95_abs_error_ms', alias: /p95 abs(?:olute)? error/i },
    ];
    // The declared bars and bounds. They are targets stated beside a measurement,
    // never a measurement, and they are declared HERE rather than discovered so
    // that adding one is a visible edit.
    const BARS = new Set([95, 250, 300, 2]);
    // A sentence terminator: `.`/`;`/`!`/`?` followed by whitespace or end. The
    // digit lookahead keeps `62.5` and `spike-a-results.json` from ending one.
    const TERMINATOR = /[.;!?](?=\s|$)/g;
    // A number that is a FIGURE, not part of an identifier or a section
    // reference. `agree_within_250ms_pct` must not yield 250, `§6.1` must not
    // yield 6.1, and `2026-08-09` must not yield anything.
    const FIGURE = /(?<![\w.§#-])(\d{1,3}(?:\.\d)?)(%?)(?![\w.\d-])/g;
    // A bare integer is a COUNT far more often than a measurement — "3 hits",
    // "50 ms", "20 keys". A figure qualifies as a reading of a percentage metric
    // only with a decimal or a `%`, and of a millisecond metric only with a
    // decimal or a trailing `ms`. Without this the guard reported `3` from
    // "`matched_within_drift_pct` — 3 hits" as a contradicted measurement.
    const qualifies = (metric, m, txt) => {
      if (m[1].includes('.')) return true;
      if (m[2] === '%') return /_pct$|_rate$/.test(metric);
      return /_ms$/.test(metric) && /^\s?ms\b/.test(txt.slice(m.index + m[0].length));
    };

    for (const { key: metric } of TRACKED) {
      if (!configurations(art, metric).length) {
        add('CRITICAL', 'artifact', 'roadmap', 0,
          `[ART-VACUOUS] no file in ${ARTIFACT_DIR} reports \`${metric}\`, so every ` +
          `[ART-FIGURE] comparison against it checks NOTHING. This is J26-M3 verbatim: the ` +
          `previous version tracked \`${metric}_pct\`-style near-misses and skipped them with ` +
          `a silent \`continue\`. A guard whose input set is empty must go red, not quiet — ` +
          `either the harness stopped emitting the metric or this list has the wrong name.`);
      }
    }

    for (const [key, txt] of Object.entries(src)) {
      // 1. Where each metric is MENTIONED — by identifier or in prose. The two
      // kinds bind differently, because they carry different evidence that the
      // number beside them is a reading of that metric.
      const mentions = [];
      for (const { key: metric, alias } of TRACKED) {
        for (const m of txt.matchAll(new RegExp(`\`?${metric}\`?`, 'g'))) {
          mentions.push({ metric, kind: 'id', at: m.index, end: m.index + m[0].length });
        }
        for (const m of txt.matchAll(new RegExp(alias.source, 'gi'))) {
          mentions.push({ metric, kind: 'prose', at: m.index, end: m.index + m[0].length });
        }
      }
      if (!mentions.length) continue;

      // 2. Every sentence terminator, so attribution cannot cross one. A figure
      // in the next sentence belongs to the next sentence.
      const stops = [...txt.matchAll(TERMINATOR)].map((m) => m.index);
      const crosses = (a, b) => stops.some((s) => s >= Math.min(a, b) && s < Math.max(a, b));

      // 3. BINDING. Three admissible shapes, all of them narrow on purpose. The
      // guard abstains where the prose is ambiguous rather than guessing, and it
      // says so in the run summary — an abstention that is COUNTED is not the
      // silent `continue` of J26-M3.
      //
      //   (a) `<identifier>` … <figure>   — an identifier is strong evidence, so
      //       it reaches 60 chars; nothing with a digit and no sentence end may
      //       lie between, which is what stops "`p95_abs_error_ms` is a timing
      //       bound and cannot see … a token timed to 50 ms".
      //   (b) <prose metric> … <figure>   — "match rate is 100%". 20 chars, and
      //       the gap may hold no digit and no punctuation, so
      //       "Match rate 100% on `en`/`es`, **95.8%" does not charge 95.8 to it.
      //   (c) <figure> <prose metric>     — "8.7% hallucination". Whitespace and
      //       a percent sign only, so `70.8/77.3/79.2, "match rate is 100%"`
      //       does not charge the triple to the phrase that follows it.
      // A slash-run — `70.8 / 77.3 / 79.2` — is ONE quotation, one figure per
      // language, and it binds as a unit. Grouping AFTER binding does not work:
      // the "no digit in the gap" rule then rejects every member but the first,
      // the run collapses to a singleton, and 70.8 alone IS reproducible. The
      // triple is the defect; the triple has to be the thing that is checked.
      const runs = [];
      for (const m of txt.matchAll(FIGURE)) {
        const f = { m, v: Number(m[1]), at: m.index, end: m.index + m[0].length };
        const prev = runs[runs.length - 1];
        const last = prev && prev[prev.length - 1];
        if (last && /^\s*[/·]\s*$/.test(txt.slice(last.end, f.at))) prev.push(f);
        else runs.push([f]);
      }

      let abstained = 0;
      for (const run of runs) {
        const head = run[0];
        const tail = run[run.length - 1];
        let best = null;
        let near = false;
        for (const mention of mentions) {
          let gap = null;
          if (mention.end <= head.at) {
            gap = head.at - mention.end;
            const between = txt.slice(mention.end, head.at);
            if (mention.kind === 'id') {
              if (gap > 60 || /\d/.test(between) || crosses(mention.end, head.at)) gap = null;
            } else if (gap > 20 || !/^[^\d.,;:"()]*$/.test(between)) gap = null;
          } else if (mention.at >= tail.end && mention.kind === 'prose') {
            gap = mention.at - tail.end;
            if (gap > 12 || !/^[\s%]*$/.test(txt.slice(tail.end, mention.at))) gap = null;
          }
          if (gap === null) continue;
          near = true;
          if (!run.some((f) => qualifies(mention.metric, f.m, txt))) continue;
          if (!best || gap < best.gap) best = { gap, metric: mention.metric };
        }
        if (!best) { if (near) abstained += 1; continue; }

        const metric = best.metric;
        const wanted = run.map((f) => f.v);
        if (wanted.every((v) => BARS.has(v))) continue;   // a bar quoted as a bar
        const configs = configurations(art, metric);
        if (!configs.length) continue;                    // already [ART-VACUOUS]
        if (configs.some((c) => wanted.every((v) => c.vals.has(v)))) continue;
        add('MAJOR', 'artifact', key, lineOf(txt, head.at),
          `[ART-FIGURE] quotes ${wanted.join(' / ')} for \`${metric}\`, and NO single ` +
          `configuration in ${ARTIFACT_DIR} produces that${wanted.length > 1 ? ' set' : ''}. ` +
          `Reported: ${configs.map((c) => `${c.label} {${[...c.vals].sort((a, b) => a - b).join(', ')}}`).join(' · ')}. ` +
          `A figure set assembled from more than one file or more than one accounting basis is ` +
          `not a run's output — it is a construction (J26-M2). Re-run the harness or correct ` +
          `the figure, and say which.`);
      }
      if (abstained) ABSTENTIONS.set(key, (ABSTENTIONS.get(key) ?? 0) + abstained);
    }
    // (c) PROVENANCE BY CONTENT (J26-M5). This compared FILESYSTEM MTIMES, and
    // git does not store mtimes: a clone sets every file to checkout time, so
    // the guard was born unreproducible — it could never fire for the reviewer
    // it exists to serve. Nothing below reads a timestamp. Three legs, all of
    // them content that survives a clone:
    //
    //   (i)   the audio manifest must exist and describe every .wav present;
    //   (ii)  every .wav must still hash to the sha256 the manifest recorded —
    //         if the audio changed, every result scoring it is stale;
    //   (iii) every result row that names a language and an `audio_seconds`
    //         must agree with the manifest's duration for that language's audio.
    //
    // Leg (iii) is the direct successor to the mtime check. Round 26's defect
    // was `spike-a-results.json` describing audio it never heard, and the tell
    // was that the audio had been CORRECTED — different bytes, different
    // duration — while the results still carried the old one.
    const manifest = art.files[MANIFEST]?.data;
    const wavs = art.wavs ?? {};
    if (!Array.isArray(manifest)) {
      add('MAJOR', 'artifact', 'roadmap', 0,
        `[ART-STALE] ${ARTIFACT_DIR}/${MANIFEST} is absent or is not a list. It is the only ` +
        `record tying a result to the bytes it scored, and without it no clone can tell ` +
        `whether a figure describes the audio in the repository (J26-M5).`);
    } else {
      const byPath = new Map(manifest.filter((r) => r && r.path).map((r) => [r.path, r]));
      for (const [wav, got] of Object.entries(wavs)) {
        const rec = byPath.get(wav);
        if (!rec) {
          add('MAJOR', 'artifact', 'roadmap', 0,
            `[ART-STALE] ${ARTIFACT_DIR}/${wav} is present and ${MANIFEST} does not describe ` +
            `it. Audio with no recorded hash cannot be tied to any result.`);
        } else if (rec.sha256 !== got.sha256 || rec.bytes !== got.bytes) {
          add('MAJOR', 'artifact', 'roadmap', 0,
            `[ART-STALE] ${ARTIFACT_DIR}/${wav} hashes to ${got.sha256.slice(0, 12)}… ` +
            `(${got.bytes} bytes); ${MANIFEST} records ${String(rec.sha256).slice(0, 12)}… ` +
            `(${rec.bytes} bytes). The audio changed after the manifest was written, so every ` +
            `figure scored against it is stale. Re-run the step that writes it (H26-C1).`);
        }
      }
      for (const rec of byPath.values()) {
        if (!wavs[rec.path]) {
          add('MAJOR', 'artifact', 'roadmap', 0,
            `[ART-STALE] ${MANIFEST} records ${rec.path} and no such file is in ` +
            `${ARTIFACT_DIR}. The evidence a result cites is not in the repository.`);
        }
      }
      for (const [f, v] of Object.entries(art.files)) {
        if (f === MANIFEST) continue;
        for (const row of scoredRows(v.data)) {
          const rec = byPath.get(`${row.lang}.wav`);
          if (!rec) {
            add('MAJOR', 'artifact', 'roadmap', 0,
              `[ART-STALE] ${ARTIFACT_DIR}/${f} reports a result for \`${row.lang}\` and ` +
              `${MANIFEST} has no entry for ${row.lang}.wav — the audio it scored is unidentified.`);
          } else if (Math.abs(Number(rec.seconds) - row.audio_seconds) > 0.011) {
            add('MAJOR', 'artifact', 'roadmap', 0,
              `[ART-STALE] ${ARTIFACT_DIR}/${f} scored ${row.audio_seconds}s of \`${row.lang}\` ` +
              `audio; ${MANIFEST} says ${row.lang}.wav is ${rec.seconds}s. The result describes ` +
              `audio that is not the audio in this repository (H26-C1, J26-M5). Re-run it.`);
          }
        }
      }
    }
  }

  // 8. STAGED STATE (J22-C1). The gate reads the WORKING TREE; `git commit`
  // writes the INDEX. Nothing reconciled them, so a green gate and a Jury pass
  // could both be earned on files the commit would not carry -- and were: three
  // Criticals were repaired on disk and the staged blobs still held the broken
  // text verbatim. Round 18 ruled that the gate governs "the file set under
  // review" and settled spec-vs-commit-set; this is the other axis.
  //
  // J23-M4: this said "advisory by design" while `process.exit(findings.length ? 1 : 0)`
  // treats EVERY finding as blocking -- a false self-description inside the section
  // that exists to check what the artifacts claim about this tool. It IS a hard gate,
  // and that is the right call: a pass earned on unstaged files is not a pass. The
  // comment now matches the code.
  // J22-M6, second half. This filter WAS an allowlist -- `tools/`, `docs/`,
  // `resources/`, `aligner/`, four literal filenames -- and it had been extended
  // twice, each time by a finding that named a file it could not see (J23-M4
  // spike-a-results.json, J24-M7 the gate tool itself). Jury: "it is a
  // whitelist, so a NEW TOP-LEVEL DIRECTORY is invisible the day it is created,
  // which is the day Phase 0 starts." `worker/`, `supabase/`, `openapi/`,
  // `web/`, `apps/mobile/`, `i18n/`, `tests/`, `legal/` are all named in
  // CODEOWNERS and none of them existed in the list.
  //
  // INVERTED. Everything is gate-relevant except a named exclusion set of build
  // and cache output. A new directory is covered on the day it is created, and
  // adding an exclusion is a visible edit to a named list rather than a silent
  // omission from an unnamed one.
  const GATE_IRRELEVANT = [
    /(^|\/)node_modules\//, /(^|\/)__pycache__\//, /\.py[cod]$/, /(^|\/)\.venv\//,
    /(^|\/)venv\//, /^\.turbo\//, /^\.next\//, /^coverage\//, /^dist\//, /^build\//,
    /\.tsbuildinfo$/, /(^|\/)\.DS_Store$/, /(^|\/)Thumbs\.db$/, /\.log$/,
  ];
  const GATE_RELEVANT = (f) => Boolean(f) && !GATE_IRRELEVANT.some((re) => re.test(f));
  try {
    const git = (cmd) => execSync(cmd, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })
      .split(String.fromCharCode(10)).map((x) => x.trim()).filter(Boolean);
    // `injectedGitFiles` exists so --self-test can run the SHIPPED predicate over
    // a synthetic path. A git-state check cannot be exercised by mutating a
    // document, and a guard with no executable falsification is decoration.
    const dirty = opts.injectedGitFiles ?? git('git diff --name-only');
    const untracked = (opts.injectedGitFiles ? [] : git('git ls-files --others --exclude-standard'))
      .filter(GATE_RELEVANT);
    const tracked = dirty.filter(GATE_RELEVANT).concat(untracked);
    if (tracked.length) {
      // J23-m1: attribute to the DOCS key when the first dirty path is one, so the
      // finding does not blame a document with no defect. Paths are in the message.
      const attribKey = Object.keys(DOCS).find((k) => DOCS[k] === tracked[0]) || 'readme';
      add('MAJOR', 'staged-state', attribKey, 0,
        `[STAGED] ${tracked.length} gate-relevant file(s) differ between the working tree ` +
        `and the index: ${tracked.slice(0, 4).join(', ')}${tracked.length > 4 ? ', …' : ''}. ` +
        `This gate read the working tree; a commit would write the index. Run \`git add\` ` +
        `and re-run before treating a pass as applying to what ships.`);
    }
  } catch { /* not a git repo, or git unavailable -- not a documentation defect */ }

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
    // J24-M4 -- the single most recurrent defect in this repository (J18-M3 ->
    // J19-M1 -> J23-M1 -> J24-M2, four recurrences) had NO CHECK. SD-ROSTER knew
    // the range form and the filename form and not the plain-prose count, so the
    // suite reported 54 passed while three documents misstated how many audits
    // exist. 54 measures guards that exist, not defects that recur.
    // Never applied to resources/audits/: a record states what was true at the
    // time it was written. Normalising those counts rewrites history -- which is
    // exactly what a blanket regex did on its first run here, turning round 19's
    // "claimed 17 audit records; the commit made 18" into a sentence that says
    // nothing. Evidence is not a thing to tidy.
    for (const m of txt.matchAll(/([0-9]{1,3})\s+(?:committed\s+)?audit records/gi)) {
      if (Number(m[1]) !== ROUNDS_ON_DISK) {
        add('MAJOR', 'self-description', key, lineOf(txt, m.index),
          `[SD-COUNT-AUDITS] claims ${m[1]} audit records; ${ROUNDS_ON_DISK} exist on disk`);
      }
    }
    }
    // The roadmap enumerates rounds as a FILENAME list, which the range form
    // above cannot see — so the guard sat green over a stale roster (N8-M1).
    // `\d` not `\d+` made `-round10.md` parse as round 1 — the guard would have
    // reported a stale roster forever once the count reached double digits.
    // J19-M2 / J16-M8 x3 — SD-ROSTER above fires only when a roster claim is
    // LESS than ROUNDS_ON_DISK, and ROUNDS_ON_DISK is counted from the very
    // directory the roster describes. So it catches a roster that undercounts
    // and is structurally blind to the opposite: a document CITING a round whose
    // record was never written. That is the J16-M8 defect, which has now
    // occurred three times, twice found by a reviewer reconstructing its own
    // subject from a chat message -- which CLAUDE.md:66-71 forbids.
    // This is the missing direction: cite a round, and its record must exist.
    const cited = [];
    // J24-M6: /round[- ]N/ demands a separator right after 'round', so 'rounds 18'
    // and 'rounds 1-30' and 'rounds 23 and 24' never matched -- and the sentence
    // added to the README this round sat exactly in that blind spot.
    for (const m of txt.matchAll(/rounds?[ -]+([0-9]{1,3})(?:\s*(?:[-–]|and)\s*([0-9]{1,3}))?/gi)) {
      cited.push(Number(m[1]));
      if (m[2]) cited.push(Number(m[2]));
    }
    for (const m of txt.matchAll(/-round([0-9]{1,3})\.md/g)) cited.push(Number(m[1]));
    // J23-M3 -- was [JNHR] x [CMm]: four alphabets, ONE severity class. A guard
    // built to ensure every cited finding has a written record could not see a
    // citation of a BLOCKER, nor single-digit rounds (N8-M8, R5-C6). Widened.
    for (const m of txt.matchAll(/[A-Z]([0-9]{1,2})-[A-Za-z][0-9]/g)) cited.push(Number(m[1]));
    // H-prefixed. It sat green over TWO missing Halo records while five files
    // cited them. A guard that knows one alphabet checks one reviewer.
    if (cited.length && Math.max(...cited) > ROUNDS_ON_DISK) {
      add('MAJOR', 'self-description', key, 0,
        `[SD-UNWRITTEN] cites round ${Math.max(...cited)} but only ${ROUNDS_ON_DISK} audit ` +
        `records exist on disk. CLAUDE.md requires every report stored, and a re-audit to ` +
        `resolve each prior finding BY ID -- which is impossible against a record ` +
        `that was never written. Write it before citing it.`);
    }
    // H21 / J22-M8 -- SD-ROSTER cannot tell a ROSTER from a CITATION. An ADR's
    // References section legitimately cites the specific records behind that
    // decision; demanding it reach the newest round makes the cheapest fix a
    // MIS-citation, and that is exactly what the last run produced -- three ADRs
    // now cite -round19.md for findings recorded in -round18.md. Only documents
    // that MAINTAIN a roster are held to completeness.
    // J25-M3 / J23-m2 -- SCOPING IS A GUARDED BLOCK, NOT A `continue`.
    // This was `if (!ROSTER_KEEPERS.has(key)) continue;` in the middle of the
    // per-document loop, so EVERY check appended after it was silently disabled
    // for 8 of the 12 documents -- and the next author to add a check at the
    // bottom of this loop would have had no way to know. A `continue` scopes one
    // check by skipping all of them; a block scopes exactly the check it wraps.
    const ROSTER_KEEPERS = new Set(['spec', 'roadmap', 'readme', 'adrIndex']);
    if (ROSTER_KEEPERS.has(key)) {
    // J25-M3 -- this guard REWARDED the defect it was narrowed to stop. Demanding
    // that the highest cited record reach ROUNDS_ON_DISK makes the cheapest fix a
    // MIS-citation, and it produced three in a row on one sentence (round21 ->
    // round22 -> round24). Scoping it to roster-keeping DOCUMENTS did not help:
    // readme and adrIndex are roster keepers whose broken citations were prose
    // citations of a specific verdict, not rosters. The distinction is FORM, not
    // document identity -- a roster enumerates a RUN of records; a citation names
    // one. Completeness is only demanded of the former.
    const allNamed = [...txt.matchAll(/-round(\d+)\.md/g)].map((x) => Number(x[1]));
    const isRoster = allNamed.length >= 4 && (Math.max(...allNamed) - Math.min(...allNamed)) <= allNamed.length + 2;
    const named = isRoster ? allNamed : [];
    if (named.length && Math.max(...named) < ROUNDS_ON_DISK) {
      add('MAJOR', 'self-description', key, lineOf(txt, txt.indexOf('-round')),
        `[SD-ROSTER] filename roster stops at -round${Math.max(...named)}.md; ${ROUNDS_ON_DISK} records exist`);
    }
    }   // end ROSTER_KEEPERS block — checks below run for EVERY document

    // A document claiming a --self-test result must claim the real one. The
    // count is stated in three artifacts and was checked by nothing, so the
    // first guard added or removed made all three wrong and the gate silent.
    for (const m of txt.matchAll(/(\d+)\s+passed,\s*\d+\s+failed/g)) {
      if (Number(m[1]) !== TRIAL_COUNT) {
        add('MAJOR', 'self-description', key, lineOf(txt, m.index),
          `[SD-SELFTEST] claims --self-test reports ${m[1]} passed; the harness declares ` +
          `${TRIAL_COUNT} trials. Guard counts move when guards are added; this is the ` +
          `check that says so instead of leaving three documents wrong.`);
      }
    }
  }
  // Enum-count claims must match the declared union.
  const irCount = (src.spec.match(/type InsertedReason =([\s\S]*?)\n\n/) || ['', ''])[1]
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
  // The abort used to be GLOBAL: any baseline finding and the whole suite
  // refused to run. The stated reason — "baseline is not clean, so red/green is
  // meaningless" — is true only of a guard that is ALREADY RED, because for that
  // one guard the mutation proves nothing. It is not true of the other sixty.
  //
  // A global abort therefore makes one open finding blind the entire suite,
  // which is the same shape as the `continue` in J25-M3: a scoping decision that
  // silently disables everything downstream of it. Scoped PER ID instead: a
  // trial whose id is already red at baseline is a FAILURE (its mutation is
  // uninformative), every other trial runs, and the baseline findings are
  // printed at the top where they cannot be mistaken for a clean gate.
  // Keyed on id AND document. [SD-SELFTEST] open on CONTRIBUTING.md says nothing
  // about whether the same guard fires on README.md, and treating it as if it
  // did would disable a live trial for a document with no defect.
  const baselineKeys = new Set(baseline.map((f) => `${f.id}@${f.doc}`));
  const baselineIds = new Set(baseline.map((f) => f.id));
  if (baseline.length) {
    console.log(`self-test: BASELINE IS NOT CLEAN — ${baseline.length} open finding(s).`);
    console.log('THE GATE DOES NOT PASS. `node tools/doc-check.mjs` exits 1. Open:');
    for (const f of baseline) console.log(`  ${f.severity.padEnd(8)} [${f.id}] ${DOCS[f.doc]}`);
    console.log('Trials whose own id is already red below are reported as FAIL: for those,');
    console.log('the mutation proves nothing. The rest are still meaningful.\n');
  }

  const trial = (id, doc, mutate, opts) => {
    if (doc ? baselineKeys.has(`${id}@${doc}`) : baselineIds.has(id)) {
      results.push([false, `${id}: ALREADY RED at baseline — a mutation cannot show this guard ` +
        `firing on its own defect when it is already firing. Fix the open finding.`]);
      return;
    }
    let mutated = src;
    if (doc) {
      mutated = { ...src, [doc]: mutate(src[doc]) };
      if (mutated[doc] === src[doc]) {
        results.push([false, `${id}: MUTATION WAS A NO-OP — the specimen no longer matches the document`]);
        return;
      }
    } else if (!opts) {
      results.push([false, `${id}: neither a document mutation nor injected state — nothing was falsified`]);
      return;
    }
    // Exact ID only. `f.message.includes(id)` let `REV` pass on an `[SD-REV]`
    // message — a substring false-green Jury demonstrated (N8-M6).
    const fired = runChecks(mutated, opts ?? {}).some((f) => f.id === id);
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
  for (const [id, doc, mutate, opts] of EXTRA_TRIALS) trial(id, doc, mutate, opts);

  if (results.length !== TRIAL_COUNT) {
    results.push([false, `TRIAL-COUNT: ran ${results.length} trials, declared ${TRIAL_COUNT} — ` +
      `[SD-SELFTEST] checks documents against the DECLARED number, so the two must agree`]);
  }

  const failed = results.filter(([ok]) => !ok);
  console.log(`self-test: ${results.length - failed.length} passed, ${failed.length} failed`);
  console.log('  (each mutates the live document and runs the shipped checks)\n');
  for (const [, msg] of failed) console.log(`  FAIL  ${msg}`);
  if (!failed.length) {
    // Honest coverage, not "every guard". Three consecutive rounds this tool was
    // over-claimed in the sentence beside the number (N7-C7, N8-M10) — and the
    // hand-written list that replaced those claims had itself gone stale:
    // SD-COUNT-AUDITS and SD-UNWRITTEN were added with no mutation and the
    // sentence beside the number never learned about them. It is COMPUTED now.
    // The file reads itself for bracketed-id literals at the head of a finding
    // message, expands the ids the guard tables generate, and subtracts what the
    // trials cover. A guard added tomorrow with no specimen names itself here,
    // in the same run.
    //
    // Anchored on the opening quote of the message string. A backtick-only
    // pattern found neither LOC-7 nor LOC-P1 (their messages are single-quoted)
    // and DID find the word ID out of a prose comment — an over-claim and an
    // under-claim in the same line, which is the reason this is computed.
    const covered = new Set(results.map(([, m]) => String(m).split(':')[0]));
    const selfSrc = readFileSync(new URL(import.meta.url), 'utf8');
    const known = new Set([
      ...[...selfSrc.matchAll(/(?<=['"`])\[([A-Z][A-Z0-9_-]*)\]/g)].map((m) => m[1]),
      ...BANNED.map((b) => b.id), ...INVARIANTS.map((i) => i.id), ...STRUCTURAL.map((g) => g.id),
      ...CONTROLS.map((c) => `CTL-${c.name}`),
    ]);
    const unmutated = [...known].filter((id) => !covered.has(id)).sort();
    console.log(`  ${covered.size} check IDs have a mutation and all of them fire.`);
    console.log(`  NOT mutated (${unmutated.length}): ${unmutated.join(', ')}`);
    console.log('  Those are verified by hand, not by this harness.');
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
  // Say what was NOT examined. [ART-FIGURE] binds a number to a metric only in
  // three narrow shapes and abstains otherwise; an abstention it did not report
  // would be J26-M3 again, wearing a different regex.
  const skipped = [...ABSTENTIONS.entries()].sort((a, b) => b[1] - a[1]);
  if (skipped.length) {
    const total = skipped.reduce((n, [, c]) => n + c, 0);
    console.log(`  [ART-FIGURE] abstained on ${total} figure(s) whose metric the prose does not`);
    console.log(`  bind unambiguously: ${skipped.map(([k, c]) => `${k} ${c}`).join(', ')}. Those are read by hand.`);
  }
  console.log('  run --self-test to verify each guard still fires on its own defect');
} else {
  console.log(`doc-check: ${findings.length} finding(s)\n`);
  for (const f of findings) {
    console.log(`  ${f.severity.padEnd(8)} ${f.check.padEnd(22)} ${DOCS[f.doc]}:${f.line}`);
    console.log(`           ${f.message}\n`);
  }
}
process.exit(findings.length ? 1 : 0);
