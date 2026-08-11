#!/usr/bin/env node
// ============================================================================
// verify_voice_langs.mjs — proves the guarantees §7.1a claims for `voice_langs`
//
// Owner: Atlas.  Run:
//
//   node supabase/tests/verify_voice_langs.mjs                 # dry run
//   node supabase/tests/verify_voice_langs.mjs --print-sql     # dry run + SQL
//   node supabase/tests/verify_voice_langs.mjs --db-url=<url>  # live
//
// TWO MODES, AND THE DIFFERENCE BETWEEN THEM IS NOT COSMETIC.
//
//   DRY RUN (default, no database) reads the migration files and proves each
//   guarantee is DECLARED — that the constraint exists, covers every column it
//   must, and says what it must say. It does NOT prove Postgres enforces it.
//   A dry run passing is evidence about the text, not about the database, and
//   this script says so in its own output rather than letting a green line be
//   read as more than it is.
//
//   LIVE (--db-url) executes every proof inside ONE transaction that ends in
//   ROLLBACK. Nothing is written. Rejections are asserted by catching
//   check_violation / not_null_violation, so "the constraint fired" is
//   observed, not assumed.
//
// SAFETY. Live mode refuses any host that is not loopback unless
// --allow-remote is passed as well. `CLAUDE.md` and this round's brief forbid
// running anything against a remote project; a flag you have to type twice is
// the difference between a decision and an accident.
// ============================================================================

import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const MIG_DIR = join(HERE, '..', 'migrations');

const argv = process.argv.slice(2);
const flag = (n) => argv.includes(`--${n}`);
const opt = (n) => (argv.find((a) => a.startsWith(`--${n}=`)) ?? '').split('=').slice(1).join('=');

const DB_URL = opt('db-url') || '';
const LIVE = DB_URL.length > 0;
const ALLOW_REMOTE = flag('allow-remote');
const PRINT_SQL = flag('print-sql');

// ---------------------------------------------------------------------------
// Load the migrations.
// ---------------------------------------------------------------------------
if (!existsSync(MIG_DIR)) {
  console.error(`verify: no migrations directory at ${MIG_DIR}`);
  process.exit(2);
}
const files = readdirSync(MIG_DIR).filter((f) => f.endsWith('.sql')).sort();
const sqlOf = Object.fromEntries(files.map((f) => [f, readFileSync(join(MIG_DIR, f), 'utf8')]));

const M_VL = files.find((f) => f.includes('voice_langs'));

// `--` to end of line. Every guard below that must not be satisfied by PROSE
// runs against this, not against the raw text. A constraint proved by its own
// comment is the vacuous-guard failure this project has already found once
// (J26-M3, `[ART-FIGURE]`).
const stripComments = (s) => s.split('\n').map((l) => l.replace(/--.*$/, '')).join('\n');
const CODE = Object.fromEntries(files.map((f) => [f, stripComments(sqlOf[f])]));
const ALL_CODE = files.map((f) => CODE[f]).join('\n');

// The CREATE TABLE body for a given table, code only.
function tableBody(table) {
  const i = ALL_CODE.search(new RegExp(`create\\s+table\\s+public\\.${table}\\s*\\(`, 'i'));
  if (i < 0) return '';
  let depth = 0;
  const start = ALL_CODE.indexOf('(', i);
  for (let j = start; j < ALL_CODE.length; j++) {
    if (ALL_CODE[j] === '(') depth++;
    else if (ALL_CODE[j] === ')') { depth--; if (depth === 0) return ALL_CODE.slice(start + 1, j); }
  }
  return '';
}
const VL_BODY = tableBody('voice_langs');
const V_BODY = tableBody('voices');

const EVIDENCE_COLS = [
  'sync_metric', 'sync_drift_bound_ms', 'sync_pct', 'sync_matched_words',
  'sync_longest_clip_ms', 'sync_measured_at', 'sync_evidence_path',
];
const GRADES = ['unmeasured', 'provisional', 'at_or_above_bar', 'below_bar'];

// ---------------------------------------------------------------------------
// STATIC PROOFS. Each is (id, claim, predicate). The claim text is what gets
// printed, so a passing line states what was actually established.
// ---------------------------------------------------------------------------
const iff = VL_BODY.match(/constraint\s+voice_langs_evidence_iff_measured\s+check\s*\(([\s\S]*?)\n\s*\),/i)?.[1] ?? '';
const floor = VL_BODY.match(/constraint\s+voice_langs_evidence_floor\s+check\s*\(([\s\S]*?)\n\s*\)\s*\n/i)?.[1] ?? '';
const resolver = ALL_CODE.match(/create or replace function public\.voice_lang_sync_grade[\s\S]*?\$fn\$([\s\S]*?)\$fn\$/i)?.[1] ?? '';
const gradeEnum = ALL_CODE.match(/create type public\.sync_grade as enum\s*\(([\s\S]*?)\)/i)?.[1] ?? '';
const metricEnum = ALL_CODE.match(/create type public\.sync_metric as enum\s*\(([\s\S]*?)\)/i)?.[1] ?? '';
// EVERY migration that defines a rule function, not just the first one.
//
// This used to be `files.find(f => f.includes('rls_class_rule'))` — the FIRST
// match in sorted order. The moment the rule was superseded by a later
// migration (20260810000100, J28-minor-a/-b), every static proof below would
// have kept reading the OLD file and reporting PASS on text the database no
// longer runs. A guard that pins itself to the first version of the thing it
// guards is worse than no guard: it goes green precisely when the fix lands.
//
// AND IT WAS STILL A LIST, ONE LEVEL DOWN. The filter used to name the two
// violation functions: `private.rls_(obligated_tables|class_violations)`. A
// migration that replaces ONLY `assert_rls_class_rule` defines neither, so it
// was invisible to this filter, and `fnBody('assert_rls_class_rule')` kept
// returning the SUPERSEDED body — with S16 and S17 both reporting PASS about
// text the database no longer runs. S17's whole claim is "the static guards
// read the definition IN FORCE", and S17 was the guard it failed to hold for.
//
// Reproduced before the fix: 20260810000200 replaces `assert_rls_class_rule`
// to add the residue delegation; the harness reported 21/21 PASS while reading
// 20260810000100's body. Found by running it, not by review — again.
//
// The filter is now a NAMING RULE rather than a list: a `private` function
// whose name begins `rls_`, `align_`, `schema_` or `assert_` IS a rule
// function. `set_updated_at` is deliberately excluded — it is a trigger helper,
// not a rule, and pulling its migration in would only widen `ruleCode` for the
// no-table-names check in S10.
const RULE_FILES = files.filter((f) =>
  /function\s+private\.(rls_|align_|schema_|assert_)\w*\s*\(/i.test(CODE[f]));
const ruleCode = RULE_FILES.map((f) => CODE[f]).join('\n');

// The BODIES of the two rule functions, not the whole file. `COMMENT ON` text
// is a SQL string literal and survives comment-stripping, so a guard run over
// the file can be satisfied by the migration's own description of itself —
// which is J26-M3 (`[ART-FIGURE]` checking nothing) reproduced here. Caught by
// mutation M15 while writing this script; the guard is scoped instead.
//
// LAST definition wins, because `create or replace` means the last one is the
// one Postgres ends up holding. Taking the last match rather than the file also
// keeps this correct if a future migration replaces only ONE of the two.
//
// ANCHORED ON `create ... function`, and that word is load-bearing. The anchor
// used to be the bare name, which also matches every CALL SITE — and a call
// site is followed by a `$fn$ … $fn$` pair too (the *enclosing* function's).
// Reading the first match hid this, because a definition always preceded its
// callers; switching to the last match surfaced it immediately as five static
// proofs reading the body of a DIFFERENT function and failing. Found by running
// it, not by review: the guard was extracting `assert_rls_class_rule`'s body
// and cheerfully asserting things about the violations rule from it.
const fnBody = (name) => {
  const re = new RegExp(
    `create\\s+(?:or\\s+replace\\s+)?function\\s+private\\.${name}\\s*\\(`
    + `[\\s\\S]*?\\$fn\\$([\\s\\S]*?)\\$fn\\$`, 'gi');
  const all = [...ruleCode.matchAll(re)];
  return all.length ? all[all.length - 1][1] : '';
};
const OBLIGATED_FN = fnBody('rls_obligated_tables');
const VIOLATIONS_FN = fnBody('rls_class_violations');
const ASSERT_FN = fnBody('assert_rls_class_rule');
const RESIDUE_FN = fnBody('align_residue_violations');
const RESIDUE_ASSERT_FN = fnBody('assert_align_residue_rule');

// -- H34-C2 / J17-C3, 20260810000200 ----------------------------------------
// Enum bodies come from ALL_CODE, not from `ruleCode`: a CREATE TYPE is not a
// rule function and scoping it to RULE_FILES would silently read nothing.
const enumBody = (name) =>
  ALL_CODE.match(new RegExp(`create type public\\.${name} as enum\\s*\\(([\\s\\S]*?)\\n\\s*\\)`, 'i'))?.[1] ?? '';
const enumVals = (name) => [...enumBody(name).matchAll(/'([a-z_]+)'/g)].map((m) => m[1]);

// §6.3:1499, in the spec's own row order. This array is the SPEC's nine.
const SPEC_ALIGN_REASONS = [
  'unsupported_language', 'low_confidence', 'engine_error', 'transcript_mismatch',
  'no_transcriber', 'transcription_unreliable', 'wrong_match', 'voice_substituted',
  'excessive_drop',
];
// THE DIVERGENCE REGISTER. Values the schema carries that §6.3 does not yet.
// It is pinned, not open-ended: this proof fails if the set grows, and it fails
// if the spec catches up without this line being retired. Writing a value into
// the spec and not the schema is how H34-C2 happened; a register that can grow
// in silence is how it would happen again.
const ALIGN_REASON_DIVERGENCE = ['incomplete_match'];
const GAP_REASONS = ['resync_skipped', 'unmatched_observation'];
const PERMANENCES = ['permanent', 'retryable', 'render_specific'];
const M_AR = files.find((f) => f.includes('align_residue'));

// A permanence classifier's totality comes from having NO `else`/`when null`
// escape: plpgsql raises case_not_found instead of returning a default.
const classifier = (name) =>
  ALL_CODE.match(new RegExp(`create function public\\.${name}\\s*\\([\\s\\S]*?\\$fn\\$([\\s\\S]*?)\\$fn\\$`, 'i'))?.[1] ?? '';
const REASON_PERM_FN = classifier('align_reason_permanence');
const GAP_PERM_FN = classifier('align_gap_permanence');
const PERM_OF_FN = classifier('align_permanence_of');

// The declaration of the violations function that is in force — its RETURN
// signature lives outside the $fn$ body, so it needs its own last-wins slice.
const VIOLATIONS_DECL = (() => {
  const all = [...ruleCode.matchAll(
    /create\s+(?:or\s+replace\s+)?function\s+private\.rls_class_violations\s*\(\s*\)\s*returns\s+table\s*\(([\s\S]*?)\)/gi)];
  return all.length ? all[all.length - 1][1] : '';
})();

// Which migrations create a table — COMPUTED. S12 used to name the two known
// ones, which is the same "list, not rule" defect the RLS migration exists to
// correct, reproduced inside the harness that proves it. A third table-creating
// migration would have been exempt from the ordering rule by never having been
// added to the array.
const TABLE_CREATING = files.filter((f) => /create\s+table\s+public\./i.test(CODE[f]));
const lastStatement = (f) => (CODE[f].trim().split('\n').pop() ?? '').trim();

// Presence is a weak guard when a property has to hold in more than one place.
const count = (re, s) => (s.match(re) ?? []).length;

const STATIC = [
  ['S1', 'migrations are timestamp-ordered and unambiguous',
    () => files.length >= 3
      && files.every((f) => /^\d{14}_[a-z0-9_]+\.sql$/.test(f))
      && new Set(files.map((f) => f.slice(0, 14))).size === files.length],

  ['S2', '`voices` declares NO `lang` column, and drops nothing (first migration)',
    () => !/^\s*lang\b/m.test(V_BODY) && !/drop\s+column/i.test(ALL_CODE)],

  ['S3', `sync_grade is a 4-value enum: ${GRADES.join(', ')}`,
    () => {
      const vals = [...gradeEnum.matchAll(/'([a-z_]+)'/g)].map((m) => m[1]);
      return vals.length === 4 && vals.every((v, i) => v === GRADES[i]);
    }],

  ['S4', 'sync_metric is an enum AND the column uses it (H26-B1: substitution = migration)',
    () => {
      const vals = [...metricEnum.matchAll(/'([a-z_0-9]+)'/g)].map((m) => m[1]);
      return vals.length === 2
        && vals.includes('matched_within_drift_pct')
        && vals.includes('agree_within_250ms_pct')
        // Declaring the type and then typing the column `text` defeats the
        // whole property while leaving the CREATE TYPE in place (mutation M18).
        && /sync_metric\s+public\.sync_metric\b/i.test(VL_BODY);
    }],

  ['S5', 'sync_grade column is NOT NULL DEFAULT \'unmeasured\'',
    () => /sync_grade\s+public\.sync_grade\s+not null\s+default\s+'unmeasured'/i.test(VL_BODY)],

  ['S6', 'primary key is (voice_id, lang) and there is no surrogate id',
    () => /primary key\s*\(\s*voice_id\s*,\s*lang\s*\)/i.test(VL_BODY)
      && !/^\s*id\b/m.test(VL_BODY)],

  ['S7', 'voice_id FK -> voices ON DELETE CASCADE',
    () => /references\s+public\.voices\s*\(\s*id\s*\)\s*on delete cascade/i.test(VL_BODY)],

  ['S8', 'one index on (lang, sync_grade) — what GET /voices?lang= filters on',
    () => /create index\s+\w+\s+on public\.voice_langs\s*\(\s*lang\s*,\s*sync_grade\s*\)/i.test(ALL_CODE)],

  ['P1/P2-static', 'the iff CHECK names ALL SEVEN evidence columns and is two-way',
    () => Boolean(iff)
      && EVIDENCE_COLS.every((c) => iff.includes(c))
      && /num_nulls\s*\(/i.test(iff)
      && /case when sync_grade = 'unmeasured' then 7 else 0 end/i.test(iff)],

  ['P3-static', 'the read path COALESCEs a missing row to `unmeasured`, never NULL',
    () => /returns public\.sync_grade/i.test(ALL_CODE)
      && /coalesce\s*\(/i.test(resolver)
      && /'unmeasured'::public\.sync_grade/i.test(resolver)],

  ['P4-static', 'the evidence floor is ENFORCED: metric, 250 ms bound, 200 words, 300000 ms',
    () => Boolean(floor)
      && /sync_metric\s*=\s*'matched_within_drift_pct'/i.test(floor)
      && /sync_drift_bound_ms\s*=\s*250/i.test(floor)
      && /sync_matched_words\s*>=\s*200/i.test(floor)
      && /sync_longest_clip_ms\s*>=\s*300000/i.test(floor)
      && /coalesce\s*\([\s\S]*?,\s*false\s*\)/i.test(floor)],

  ['P4-deferral', 'the BAR is deferred to the writer, and the migration says which and why',
    () => M_VL && /DEFERRED TO THE WRITER/.test(sqlOf[M_VL])
      && /p95_abs_error_ms/.test(sqlOf[M_VL])
      && /hallucination_rate/.test(sqlOf[M_VL])
      && /Owner: Forge/.test(sqlOf[M_VL])],

  ['S9', 'the store ships EMPTY of grades — no INSERT into voice_langs anywhere',
    () => !/insert\s+into\s+public\.voice_langs/i.test(ALL_CODE)],

  ['S10', 'the RLS exemption is a CLASS RULE — no table name appears in its code',
    () => Boolean(OBLIGATED_FN) && Boolean(VIOLATIONS_FN)
      && !/'voices'/.test(ruleCode) && !/'voice_langs'/.test(ruleCode)
      && /pg_constraint/.test(OBLIGATED_FN)
      && /attname\s*=\s*'user_id'/.test(OBLIGATED_FN)
      && /relrowsecurity/.test(VIOLATIONS_FN)],

  ['S11', 'the class rule reports a renamed user key rather than silently exempting it',
    () => /'unclassifiable'/.test(VIOLATIONS_FN) && /owner\|account/.test(VIOLATIONS_FN)],

  ['S12', 'every table-creating migration ENDS by asserting the class rule (computed, not listed)',
    () => TABLE_CREATING.length >= 2
      // `\s*$` under /m matched the statement ANYWHERE on its own line, so the
      // ordering this rule is entirely about — assert LAST, after the table
      // exists — was never actually checked. It is the last statement or it is
      // not the tripwire it claims to be.
      && TABLE_CREATING.every((f) => lastStatement(f) === 'select private.assert_rls_class_rule();')],

  // -- J28-minor-b -----------------------------------------------------------
  ['S13', 'the obligation covers PARTITIONED parents, not just relkind r (J28-minor-b)',
    () => /relkind\s+in\s*\(\s*'r'\s*,\s*'p'\s*\)/i.test(OBLIGATED_FN)
      // Both legs, or a partitioned table is obligated and then never examined.
      && /relkind\s+in\s*\(\s*'r'\s*,\s*'p'\s*\)/i.test(VIOLATIONS_FN)
      // Leaf partitions stay out of the obligation ON PURPOSE — the parent's
      // policies cover reads through the parent. If this exclusion is ever
      // dropped, the rule starts failing on the CORRECT partitioned layout.
      && /not\s+c?\.?relispartition/i.test(OBLIGATED_FN)],

  ['S14', 'the unclassifiable leg READS relrowsecurity and does not block a protected table (J28-minor-a)',
    () => /'unclassifiable_protected'/.test(VIOLATIONS_FN)
      // The severity must be DERIVED from relrowsecurity, not hard-coded true.
      && /case\s+when\s+c\.relrowsecurity/i.test(VIOLATIONS_FN)
      && /not\s+c\.relrowsecurity/i.test(VIOLATIONS_FN)
      // and it has to be readable off the row rather than inferred elsewhere
      && /blocking\s+boolean/i.test(VIOLATIONS_DECL)],

  ['S15', 'a partition of an obligated parent is checked for a DIRECT grant that no policy covers',
    () => /'partition_directly_granted'/.test(VIOLATIONS_FN)
      && /pg_partition_root\s*\(/i.test(VIOLATIONS_FN)
      // Reachability is computed from the catalog, not from a list of role
      // names — a role list would be defeatable by adding a role.
      //
      // COUNTED, not merely present. `/rolbypassrls/.test(...)` was the first
      // version and mutation M4 walked straight through it: strip the bypass
      // exclusion from ONE of the two ACL branches and the string is still in
      // the file, so the guard stays green while half the rule is gone. Every
      // ACL source must carry its own exclusion, and there are two sources —
      // the table ACL and the column ACLs — so the counts have to agree.
      && count(/aclexplode\s*\(/gi, VIOLATIONS_FN) >= 2
      && count(/aclexplode\s*\(/gi, VIOLATIONS_FN) === count(/rolbypassrls/gi, VIOLATIONS_FN)
      && count(/aclexplode\s*\(/gi, VIOLATIONS_FN) === count(/rolsuper/gi, VIOLATIONS_FN)
      // BOTH acls. A column grant never touches relacl, so a relacl-only test
      // calls a readable partition unreachable.
      && /attacl/.test(VIOLATIONS_FN)],

  ['S16', 'the assert SEPARATES stop from say-so: non-blocking findings are still printed',
    () => /if\s+v\.blocking\s+then/i.test(ASSERT_FN)
      && /raise\s+notice/i.test(ASSERT_FN)
      && /raise\s+exception/i.test(ASSERT_FN)],

  ['S17', 'the static guards read the definition IN FORCE, not the superseded one',
    () => {
      // The whole class of bug this file just had. Anchor the check to a
      // property the OLD definitions cannot satisfy and the new ones must:
      // if `fnBody` ever slides back to a first match, a call site, or the
      // wrong function, one of these three bodies stops being what it says.
      const distinct = new Set([OBLIGATED_FN, VIOLATIONS_FN, ASSERT_FN]);
      return distinct.size === 3
        && /rls_obligated_tables/.test(VIOLATIONS_FN)      // violations calls it
        && !/rls_obligated_tables\s*\(\s*\)/.test(OBLIGATED_FN) // it does not call itself
        && /rls_class_violations/.test(ASSERT_FN)          // assert calls violations
        && !/\$fn\$/.test(OBLIGATED_FN + VIOLATIONS_FN + ASSERT_FN); // no body spans a delimiter
    }],

  // -- H34-C2 + J17-C3, decided jointly (20260810000200) ---------------------

  ['S18', 'align_reason is §6.3\'s nine IN ORDER plus a REGISTERED divergence, and nothing else',
    () => {
      const vals = enumVals('align_reason');
      // The spec's nine, in the spec's order, first.
      const head = vals.slice(0, SPEC_ALIGN_REASONS.length);
      const tail = vals.slice(SPEC_ALIGN_REASONS.length);
      return head.length === SPEC_ALIGN_REASONS.length
        && head.every((v, i) => v === SPEC_ALIGN_REASONS[i])
        // EXACTLY the registered divergence — not a superset, not a subset.
        // Grows -> fails. Spec catches up and the register is not retired ->
        // this stays green, so S19 pins the register text in the migration too.
        && tail.length === ALIGN_REASON_DIVERGENCE.length
        && tail.every((v, i) => v === ALIGN_REASON_DIVERGENCE[i]);
    }],

  ['S19', 'the divergence is REGISTERED in the migration, with the spec section it owes',
    () => Boolean(M_AR)
      && /DIVERGENCE, REGISTERED RATHER THAN DISCOVERED/.test(sqlOf[M_AR])
      && ALIGN_REASON_DIVERGENCE.every((v) => sqlOf[M_AR].includes(v))
      && /§6\.3:1499/.test(sqlOf[M_AR])
      && /Owner Scribe with Forge/.test(sqlOf[M_AR])],

  ['S20', 'align_gap_reason is exactly the two residue sides — one per address half',
    () => {
      const vals = enumVals('align_gap_reason');
      return vals.length === 2 && vals.every((v, i) => v === GAP_REASONS[i]);
    }],

  ['S21', 'align_permanence is §6.3\'s three values',
    () => {
      const vals = enumVals('align_permanence');
      return vals.length === 3 && PERMANENCES.every((p) => vals.includes(p));
    }],

  ['S22', 'both classifiers are TOTAL by construction — no else, no default, every value named',
    () => Boolean(REASON_PERM_FN) && Boolean(GAP_PERM_FN)
      // An `else` branch is the whole defect: it turns "somebody forgot to
      // classify this" into a silent `retryable`, which is the H34-C2 shape
      // (a fact the product emits and the schema quietly absorbs).
      && !/\belse\b/i.test(REASON_PERM_FN.replace(/\belsif\b/gi, ''))
      && !/\belse\b/i.test(GAP_PERM_FN)
      && [...SPEC_ALIGN_REASONS, ...ALIGN_REASON_DIVERGENCE]
           .every((v) => new RegExp(`when\\s+'${v}'`).test(REASON_PERM_FN))
      && GAP_REASONS.every((v) => new RegExp(`when\\s+'${v}'`).test(GAP_PERM_FN))],

  ['S23', 'the residue reasons are render_specific — not permanent, not retryable',
    () => /when\s+'incomplete_match'\s+then\s+'render_specific'/.test(REASON_PERM_FN)
      && GAP_REASONS.every((v) =>
           new RegExp(`when\\s+'${v}'\\s+then\\s+'render_specific'`).test(GAP_PERM_FN))
      // and the classification is argued from the artifact, not from the brief:
      // the two clips that re-sync are REPLICATES of the same voice, which is
      // why the remedy sentence may not promise that another voice fixes it.
      && Boolean(M_AR) && /replicate 1 and 0 at\s*\n--\s*replicate 2/.test(sqlOf[M_AR])
      && /must say RE-RENDER and must NOT promise that/.test(sqlOf[M_AR])],

  ['S24', 'permanence is DERIVED from the SET, permanent > render_specific > retryable (N5-M6)',
    () => Boolean(PERM_OF_FN)
      && /foreach\s+r\s+in\s+array/i.test(PERM_OF_FN)
      && /=\s*'permanent'\s*then\s*\n?\s*return\s+'permanent'/i.test(PERM_OF_FN)
      && /seen_render_specific\s*:=\s*true/i.test(PERM_OF_FN)
      && /return\s+'retryable'/i.test(PERM_OF_FN)
      // An EMPTY set is `align_status: ok` and has no permanence. Returning
      // 'retryable' there would assert a remedy for a rendition with no fault.
      && /array_length\s*\(\s*p_reasons\s*,\s*1\s*\)\s+is\s+null\s*then\s*\n?\s*return\s+null/i.test(PERM_OF_FN)],

  ['S25', 'the residue obligation is a CLASS RULE — no table name appears in its code',
    () => Boolean(RESIDUE_FN)
      && !/'segment_renditions'/.test(RESIDUE_FN)
      && !/'align_gaps'/.test(RESIDUE_FN)
      // Membership is derived from the catalog: a jsonb column named `words`
      // (§7.2a). Renaming the TABLE does not escape it.
      && /pg_attribute/.test(RESIDUE_FN)
      && /typname\s*=\s*'jsonb'/.test(RESIDUE_FN)
      && /attname\s*=\s*'words'/.test(RESIDUE_FN)
      // ...and renaming the COLUMN moves it to "needs a ruling", never
      // "exempt" — the same hole the RLS rule states rather than hides.
      && /'unclassifiable_match_output'/.test(RESIDUE_FN)
      && /word_timings\|/.test(RESIDUE_FN)],

  ['S26', 'the residue store contract is checked on all four properties, not just existence',
    () => /'residue_store_missing'/.test(RESIDUE_FN)
      && /'residue_store_incomplete'/.test(RESIDUE_FN)
      // reason NOT NULL, FK ON DELETE CASCADE, BOTH address halves, XOR check.
      && /attnotnull/.test(RESIDUE_FN)
      && /confdeltype\s*=\s*'c'/.test(RESIDUE_FN)
      && ['display_char_start', 'display_char_end', 'observed_start_ms', 'observed_end_ms']
           .every((c) => RESIDUE_FN.includes(c))
      && /num_nulls/.test(RESIDUE_FN)
      // SINGLE SOURCE. The first version required each test to appear TWICE —
      // once selecting, once explaining — which is exactly what mutations M5
      // and M7 defeated: they deleted the SELECTING copy and the counted guard
      // stayed green on the explaining one. The selection is now derived from
      // the same array as the message, so the count that matters is ONE.
      && /cross join lateral/i.test(RESIDUE_FN)
      && /array_length\s*\(\s*d\.defects\s*,\s*1\s*\)\s+is\s+not\s+null/i.test(RESIDUE_FN)
      && count(/num_nulls/g, RESIDUE_FN) === 2          // the test + its message
      && count(/confdeltype\s*=\s*'c'/g, RESIDUE_FN) === 1
      // The four-column count is EXACT. `< 3` still selects the all-missing
      // probe store, so only pinning the literal catches M7.
      && /\)\s*\)\s*<>\s*4/.test(RESIDUE_FN)
      // ...and the live probes that can actually see a deleted test exist.
      && /G7a-d/.test(readFileSync(join(HERE, 'verify_voice_langs.mjs'), 'utf8'))],

  ['S27', 'the residue rule RIDES ON the one statement CLAUDE.md makes mandatory',
    () => Boolean(ASSERT_FN) && Boolean(RESIDUE_ASSERT_FN)
      // Read off the definition IN FORCE. Before RULE_FILES was widened above,
      // this read 20260810000100's body and could not have seen the delegation.
      && /perform\s+private\.assert_align_residue_rule\s*\(\s*\)/i.test(ASSERT_FN)
      && /if\s+v\.blocking\s+then/i.test(RESIDUE_ASSERT_FN)
      && /raise\s+exception/i.test(RESIDUE_ASSERT_FN)
      // The honest name exists and delegates, so CLAUDE.md's mandated line can
      // be renamed without another migration.
      && /create function private\.assert_schema_obligations/i.test(ALL_CODE)],

  ['S28', 'the residue is NOT admitted to SpanReason, and the migration says why in hashes',
    () => Boolean(M_AR)
      // §7.2: disclosure_fingerprint -> text_hash, and voice_id is
      // deliberately not a text_hash input. A render-dependent SpanReason
      // would make every segment billable on every re-render — and would bill
      // the very remedy `render_specific` recommends.
      && /disclosure_fingerprint/.test(sqlOf[M_AR])
      && /text_hash/.test(sqlOf[M_AR])
      && /SpanReason stays at 16 values/.test(sqlOf[M_AR])
      // Computed, not asserted: enumerate EVERY enum type the migrations
      // create and check that no other one has taken a residue reason as a
      // member. The first version of this clause greped ALL_CODE for the value
      // outside the enum block — which `align_gap_permanence`'s CASE satisfies
      // legitimately, so it failed on correct code. A guard that fires on the
      // right answer is the J28-minor-a shape; this one reads the type system.
      && (() => {
        const types = [...ALL_CODE.matchAll(
          /create type public\.(\w+) as enum\s*\(([\s\S]*?)\n\s*\)\s*;/gi)];
        // Every enum in the schema is accounted for, so a NEW enum carrying a
        // residue reason cannot slip past by not being in a list here.
        if (types.length < 5) return false;
        return types.every(([, name, body]) =>
          name === 'align_gap_reason'
          || !GAP_REASONS.some((v) => body.includes(`'${v}'`)));
      })()],

  ['S29', 'the store that cannot land yet has its contract written out, RLS included',
    () => Boolean(M_AR)
      && /create table public\.align_gaps/i.test(sqlOf[M_AR])
      && /align_gaps_one_address_half/.test(sqlOf[M_AR])
      // Erasure cascades (CLAUDE.md constraint 6) and the verbatim-text column
      // is named for §7.4 rather than assumed covered by it (J17-M4).
      && /on delete cascade/i.test(sqlOf[M_AR])
      && /§7\.4/.test(sqlOf[M_AR])
      // It is a CHILD of a table that does not exist, and the migration says
      // so rather than shipping an FK-less table with verbatim document text
      // and no RLS.
      && /segment_renditions` DOES NOT EXIST|segment_renditions\*\* DOES NOT EXIST|`segment_renditions` DOES NOT EXIST/.test(sqlOf[M_AR])
      && /would ship unprotected/.test(sqlOf[M_AR])],
];

// ---------------------------------------------------------------------------
// LIVE PROOFS. One transaction, rolled back. Every rejection is OBSERVED.
// ---------------------------------------------------------------------------
const VOICE = '00000000-0000-4000-8000-00000000f1f1';
const ABSENT = '00000000-0000-4000-8000-00000000dead';

const cols = '(voice_id, lang, sample_text, sync_grade, sync_metric, sync_drift_bound_ms, '
  + 'sync_pct, sync_matched_words, sync_longest_clip_ms, sync_measured_at, sync_evidence_path)';

const reject = (id, lang, values, err, why) => `
do $probe$
declare fired boolean := false;
begin
  begin
    insert into public.voice_langs ${cols}
    values ('${VOICE}', '${lang}', 'probe', ${values});
  exception when ${err} then fired := true;
  end;
  if not fired then
    raise exception '${id} FAILED — the row was ACCEPTED. Expected: ${why}';
  end if;
  raise notice '${id} ok — ${why}';
end
$probe$;`;

const LIVE_SQL = `
-- ===========================================================================
-- verify_voice_langs — LIVE PROOFS
--
-- THIS WHOLE SCRIPT IS ONE TRANSACTION AND IT ENDS IN ROLLBACK.
-- Nothing below survives. The numbers in the probe rows are CONSTRAINT
-- PROBES, not measurements: no grade, no percentage and no word count here
-- asserts anything about any voice. The store ships empty of grades.
-- ===========================================================================
\\set ON_ERROR_STOP on
begin;

insert into public.voices (id, provider, provider_voice_id, gender, is_clone)
values ('${VOICE}', 'verify', 'verify-fixture-rolled-back', null, false);

${reject('P1', 'aa',
  `'unmeasured', 'matched_within_drift_pct', 250, 99.00, 250, 300000, now(), 'probe://x'`,
  'check_violation', 'unmeasured row carrying evidence is REJECTED')}

${reject('P1b', 'ab',
  `'unmeasured', null, null, 99.00, null, null, null, null`,
  'check_violation', 'unmeasured row carrying PARTIAL evidence is REJECTED')}

${reject('P2', 'ac',
  `'at_or_above_bar', null, null, null, null, null, null, null`,
  'check_violation', 'at_or_above_bar with NULL evidence is REJECTED')}

${reject('P2b', 'ad',
  `'at_or_above_bar', 'matched_within_drift_pct', 250, 99.00, 250, 300000, now(), null`,
  'check_violation', 'at_or_above_bar missing ONE of seven evidence columns is REJECTED')}

-- P3a — the column itself cannot hold NULL.
do $probe$
declare fired boolean := false;
begin
  begin
    insert into public.voice_langs (voice_id, lang, sample_text, sync_grade)
    values ('${VOICE}', 'ae', 'probe', null);
  exception when not_null_violation then fired := true;
  end;
  if not fired then raise exception 'P3a FAILED — a NULL sync_grade was accepted'; end if;
  raise notice 'P3a ok — sync_grade cannot be NULL in a stored row';
end
$probe$;

-- P3b — omitting the grade yields 'unmeasured', not NULL.
insert into public.voice_langs (voice_id, lang, sample_text)
values ('${VOICE}', 'af', 'probe');
do $probe$
declare g public.sync_grade;
begin
  select sync_grade into g from public.voice_langs
   where voice_id = '${VOICE}' and lang = 'af';
  if g is distinct from 'unmeasured' then
    raise exception 'P3b FAILED — omitted grade read as %', coalesce(g::text, 'NULL');
  end if;
  raise notice 'P3b ok — an omitted grade defaults to unmeasured';
end
$probe$;

-- P3c — a pair with NO ROW reads as unmeasured through the read path.
do $probe$
declare g public.sync_grade;
begin
  g := public.voice_lang_sync_grade('${ABSENT}', 'zz');
  if g is null then raise exception 'P3c FAILED — read path returned NULL for a missing row'; end if;
  if g <> 'unmeasured' then raise exception 'P3c FAILED — missing row read as %', g; end if;
  g := public.voice_lang_sync_grade('${VOICE}', 'zz');
  if g is null or g <> 'unmeasured' then
    raise exception 'P3c FAILED — known voice, ungraded language did not read unmeasured';
  end if;
  raise notice 'P3c ok — a missing row reads unmeasured, never NULL and never absent';
end
$probe$;

-- P3d — the guarantee in the catalog, not in a query somebody remembered.
do $probe$
begin
  if not exists (
    select 1 from pg_attribute
     where attrelid = 'public.voice_langs'::regclass
       and attname = 'sync_grade' and attnotnull)
  then raise exception 'P3d FAILED — sync_grade is not NOT NULL in the catalog'; end if;
  raise notice 'P3d ok — sync_grade is NOT NULL in pg_attribute';
end
$probe$;

${reject('P4a', 'ag',
  `'at_or_above_bar', 'matched_within_drift_pct', 250, 99.00, 199, 300000, now(), 'probe://x'`,
  'check_violation', 'at_or_above_bar on 199 matched words is REJECTED (floor 200)')}

${reject('P4b', 'ah',
  `'at_or_above_bar', 'matched_within_drift_pct', 250, 99.00, 200, 299999, now(), 'probe://x'`,
  'check_violation', 'at_or_above_bar on a 299999 ms clip is REJECTED (floor 300000)')}

${reject('P4c', 'ai',
  `'at_or_above_bar', 'agree_within_250ms_pct', 250, 99.00, 200, 300000, now(), 'probe://x'`,
  'check_violation', 'at_or_above_bar on a SUBSTITUTED metric is REJECTED (H26-B1)')}

${reject('P4d', 'aj',
  `'at_or_above_bar', 'matched_within_drift_pct', 500, 99.00, 200, 300000, now(), 'probe://x'`,
  'check_violation', 'at_or_above_bar at a 500 ms drift bound is REJECTED (bound fixed at 250)')}

-- P4e — the floor is a FLOOR, not a wall: exactly at it, the row is accepted.
insert into public.voice_langs ${cols}
values ('${VOICE}', 'ak', 'probe', 'at_or_above_bar', 'matched_within_drift_pct',
        250, 95.00, 200, 300000, now(), 'probe://rolled-back-not-a-measurement');
do $probe$
begin raise notice 'P4e ok — a row exactly at the floor is accepted'; end $probe$;

-- P4f — nothing is discarded: below the floor, stored WITH ITS NUMBERS as provisional.
insert into public.voice_langs ${cols}
values ('${VOICE}', 'al', 'probe', 'provisional', 'agree_within_250ms_pct',
        250, 88.20, 17, 8000, now(), 'probe://rolled-back-not-a-measurement');
do $probe$
begin raise notice 'P4f ok — a below-floor measurement stores as provisional with its numbers'; end $probe$;

-- L1..L5 — structure, read from the catalog rather than from the file.
do $probe$
begin
  if exists (select 1 from pg_attribute
              where attrelid = 'public.voices'::regclass and attname = 'lang' and attnum > 0
                and not attisdropped)
  then raise exception 'L1 FAILED — voices.lang exists (H26-C3)'; end if;
  raise notice 'L1 ok — voices has no lang column';

  if not exists (select 1 from pg_indexes
                  where schemaname = 'public' and tablename = 'voice_langs'
                    and indexdef ~ 'lang, sync_grade')
  then raise exception 'L2 FAILED — no (lang, sync_grade) index'; end if;
  raise notice 'L2 ok — (lang, sync_grade) index present';

  if not exists (select 1 from pg_constraint
                  where conrelid = 'public.voice_langs'::regclass
                    and contype = 'f' and confdeltype = 'c')
  then raise exception 'L3 FAILED — FK is not ON DELETE CASCADE'; end if;
  raise notice 'L3 ok — FK cascades from voices';

  if (select count(*) from unnest(enum_range(null::public.sync_grade))) <> 4
  then raise exception 'L4 FAILED — sync_grade does not have exactly four values'; end if;
  raise notice 'L4 ok — sync_grade has exactly four values';

  if exists (select 1 from private.rls_obligated_tables()
              where relid in ('public.voices'::regclass, 'public.voice_langs'::regclass))
  then raise exception 'L5 FAILED — a catalogue table is inside the RLS obligation'; end if;
  raise notice 'L5 ok — both catalogue tables are outside the obligation BY THE RULE';
end
$probe$;

-- ===========================================================================
-- R1..R9 — THE CLASS RULE ITSELF, EXERCISED AGAINST A REAL CATALOG.
--
-- The static proofs above establish that the rule SAYS these things. These
-- establish that Postgres DOES them, which is a different claim and the one
-- that was missing for three rounds. Every relation and role below is created
-- inside this transaction and dropped again before L6, so the schema L6
-- asserts over is the real one and not a probe fixture.
-- ===========================================================================
create role verify_probe_client nologin;
create role verify_probe_bypass nologin bypassrls;

-- J28-minor-a — a user key under another spelling.
create table public.verify_notes (
  id       uuid primary key default gen_random_uuid(),
  owner_id uuid not null
);

do $probe$
declare fired boolean := false;
begin
  begin perform private.assert_rls_class_rule();
  exception when others then fired := true;
  end;
  if not fired then
    raise exception 'R1 FAILED — an owner_id table with RLS OFF did not block';
  end if;
  raise notice 'R1 ok — a renamed user key with RLS off still BLOCKS (default is not exempt)';
end
$probe$;

alter table public.verify_notes enable row level security;

do $probe$
declare k text; b boolean;
begin
  select kind, blocking into k, b from private.rls_class_violations()
   where relid = 'public.verify_notes'::regclass;
  if k is distinct from 'unclassifiable_protected' or b is distinct from false then
    raise exception 'R2 FAILED — a protected owner_id table reported as % / blocking=%',
      coalesce(k, 'NOTHING'), coalesce(b::text, 'NULL');
  end if;
  perform private.assert_rls_class_rule();
  raise notice 'R2 ok — RLS ON: the rule SEES it, reports it, and does not block (J28-minor-a)';
end
$probe$;

drop table public.verify_notes;

-- J28-minor-b — a partitioned parent is a table.
create table public.verify_events (
  id         uuid not null default gen_random_uuid(),
  user_id    uuid not null,
  created_at timestamptz not null default now(),
  primary key (id, created_at)
) partition by range (created_at);

create table public.verify_events_p1 partition of public.verify_events
  for values from ('2026-08-01') to ('2026-09-01');

do $probe$
declare fired boolean := false;
begin
  if not exists (select 1 from private.rls_obligated_tables()
                  where relid = 'public.verify_events'::regclass) then
    raise exception 'R3 FAILED — a partitioned table carrying user_id is OUTSIDE the obligation';
  end if;
  begin perform private.assert_rls_class_rule();
  exception when others then fired := true;
  end;
  if not fired then
    raise exception 'R3 FAILED — a partitioned table with user_id and RLS OFF did not block';
  end if;
  raise notice 'R3 ok — a partitioned parent carrying user_id with RLS off BLOCKS (J28-minor-b)';
end
$probe$;

alter table public.verify_events enable row level security;

do $probe$
begin
  perform private.assert_rls_class_rule();
  raise notice 'R4 ok — the CORRECT partitioned layout passes: no false positive on the partitions';
end
$probe$;

grant select on public.verify_events_p1 to verify_probe_client;

do $probe$
declare fired boolean := false;
begin
  begin perform private.assert_rls_class_rule();
  exception when others then fired := true;
  end;
  if not fired then
    raise exception 'R5 FAILED — a partition granted directly, with its own RLS off, did not block';
  end if;
  raise notice 'R5 ok — enabling RLS on a parent does NOT reach its partitions, and the rule knows';
end
$probe$;

alter table public.verify_events_p1 enable row level security;

do $probe$
begin
  perform private.assert_rls_class_rule();
  raise notice 'R6 ok — protecting the partition itself clears it';
end
$probe$;

alter table public.verify_events_p1 disable row level security;
revoke select on public.verify_events_p1 from verify_probe_client;
grant select on public.verify_events_p1 to verify_probe_bypass;

do $probe$
begin
  perform private.assert_rls_class_rule();
  raise notice 'R7 ok — a grantee that BYPASSES rls is not a hole, and is not reported as one';
end
$probe$;

grant select on public.verify_events_p1 to public;

do $probe$
declare fired boolean := false;
begin
  begin perform private.assert_rls_class_rule();
  exception when others then fired := true;
  end;
  if not fired then
    raise exception 'R8 FAILED — a partition granted to PUBLIC did not block';
  end if;
  raise notice 'R8 ok — PUBLIC is counted as the worst-case grantee, not skipped as no grantee';
end
$probe$;

drop table public.verify_events;

-- R9 — reached by a FOREIGN KEY rather than by a column of its own.
create table public.verify_owner (
  id      uuid primary key default gen_random_uuid(),
  user_id uuid not null
);
alter table public.verify_owner enable row level security;

create table public.verify_hits (
  id        uuid not null default gen_random_uuid(),
  owner_ref uuid not null references public.verify_owner (id),
  at        timestamptz not null default now(),
  primary key (id, at)
) partition by range (at);

do $probe$
declare fired boolean := false;
begin
  if not exists (select 1 from private.rls_obligated_tables()
                  where relid = 'public.verify_hits'::regclass) then
    raise exception 'R9 FAILED — a partitioned FK child of a user table is outside the obligation';
  end if;
  begin perform private.assert_rls_class_rule();
  exception when others then fired := true;
  end;
  if not fired then raise exception 'R9 FAILED — it did not block'; end if;
  raise notice 'R9 ok — the obligation reaches a PARTITIONED table through a foreign key chain';
end
$probe$;

drop table public.verify_hits;
drop table public.verify_owner;

-- R10 — a COLUMN grant is a grant. It leaves relacl null and lands in
-- pg_attribute.attacl, so a table-level reachability test reports the
-- partition as unreachable while its user column is readable by name.
create table public.verify_cols (
  id      uuid not null default gen_random_uuid(),
  user_id uuid not null,
  at      timestamptz not null default now(),
  primary key (id, at)
) partition by range (at);
create table public.verify_cols_p1 partition of public.verify_cols
  for values from ('2026-08-01') to ('2026-09-01');
alter table public.verify_cols enable row level security;
grant select (user_id) on public.verify_cols_p1 to verify_probe_client;

do $probe$
declare fired boolean := false;
begin
  if (select relacl is not null from pg_class where oid = 'public.verify_cols_p1'::regclass) then
    raise exception 'R10 FAILED — the premise is wrong: a column grant DID write relacl';
  end if;
  begin perform private.assert_rls_class_rule();
  exception when others then fired := true;
  end;
  if not fired then
    raise exception 'R10 FAILED — a COLUMN grant on an unpoliced partition was not seen';
  end if;
  raise notice 'R10 ok — a column grant counts as reachable, though relacl stays null';
end
$probe$;

drop table public.verify_cols;

-- ===========================================================================
-- G1..G11 — H34-C2 + J17-C3: THE ALIGN RESIDUE, EXERCISED AGAINST A REAL
-- CATALOG.
--
-- The static proofs above establish that the migration SAYS these things.
-- These establish that PostgreSQL DOES them — which is the difference H34-C2
-- is entirely about: resync_skipped_display_tokens is SAID by the product,
-- measured at 9 and 25, and enforced by nothing.
-- ===========================================================================

-- G1 — every align_reason value is classified. Read from the CATALOG, so a
-- value added without a classification fails HERE and not in production.
do $probe$
declare r public.align_reason; n integer := 0;
begin
  for r in select unnest(enum_range(null::public.align_reason)) loop
    if public.align_reason_permanence(r) is null then
      raise exception 'G1 FAILED — align_reason % classified as NULL', r;
    end if;
    n := n + 1;
  end loop;
  if n <> 10 then
    raise exception 'G1 FAILED — align_reason has % values, expected 10', n;
  end if;
  raise notice 'G1 ok — all 10 align_reason values classify, enumerated from the catalog';
end
$probe$;

-- G2 — and BOTH residue reasons, from the catalog for the same reason.
do $probe$
declare g public.align_gap_reason; n integer := 0;
begin
  for g in select unnest(enum_range(null::public.align_gap_reason)) loop
    if public.align_gap_permanence(g) <> 'render_specific' then
      raise exception 'G2 FAILED — % is %, not render_specific',
        g, public.align_gap_permanence(g);
    end if;
    n := n + 1;
  end loop;
  if n <> 2 then raise exception 'G2 FAILED — align_gap_reason has % values', n; end if;
  raise notice 'G2 ok — both residue reasons are render_specific: a re-render is a real remedy';
end
$probe$;

-- G3 — the SET derivation (N5-M6): permanent beats render_specific beats
-- retryable, and an empty set has no permanence at all.
do $probe$
begin
  if public.align_permanence_of(array['engine_error','incomplete_match']::public.align_reason[])
     <> 'render_specific' then raise exception 'G3 FAILED — render_specific did not beat retryable'; end if;
  if public.align_permanence_of(array['incomplete_match','excessive_drop']::public.align_reason[])
     <> 'permanent' then raise exception 'G3 FAILED — permanent did not win'; end if;
  if public.align_permanence_of(array['engine_error']::public.align_reason[])
     <> 'retryable' then raise exception 'G3 FAILED — lone engine_error was not retryable'; end if;
  if public.align_permanence_of('{}'::public.align_reason[]) is not null then
    raise exception 'G3 FAILED — an EMPTY reason set produced a permanence'; end if;
  raise notice 'G3 ok — permanence is derived from the SET, and an empty set has none';
end
$probe$;

-- G4 — a NULL element is a producer bug and is refused, not skipped. Skipping
-- it would compute a permanence from a set nobody wrote.
do $probe$
declare fired boolean := false;
begin
  begin
    perform public.align_permanence_of(array['engine_error', null]::public.align_reason[]);
  exception when others then fired := true;
  end;
  if not fired then raise exception 'G4 FAILED — a NULL reason element was silently skipped'; end if;
  raise notice 'G4 ok — a NULL inside the reason array RAISES rather than being skipped';
end
$probe$;

-- G5 — the rule is SILENT on a schema with no match-output store. A rule that
-- fires on the correct configuration is a rule that gets commented out.
do $probe$
begin
  if exists (select 1 from private.align_residue_violations()) then
    raise exception 'G5 FAILED — the residue rule fires on the shipped schema';
  end if;
  raise notice 'G5 ok — the residue rule is silent until a match-output store exists';
end
$probe$;

-- G6 — THE FINDING, IN THE FORM IN WHICH IT WOULD RECUR. A match-output store
-- with no residue store must stop the migration, through the one statement
-- CLAUDE.md makes mandatory.
create table public.verify_rend (
  id    uuid primary key default gen_random_uuid(),
  words jsonb
);

do $probe$
declare fired boolean := false; m text;
begin
  begin perform private.assert_rls_class_rule();
  exception when others then fired := true; m := SQLERRM;
  end;
  if not fired then
    raise exception 'G6 FAILED — a match-output store with no residue store did not block';
  end if;
  if m not like '%residue%' then
    raise exception 'G6 FAILED — it blocked, but not on the residue rule: %', m;
  end if;
  raise notice 'G6 ok — H34-C2 cannot recur silently: the mandated assert refuses the migration';
end
$probe$;

-- G7 — a residue store that is PRESENT but cannot carry the fact. Every
-- missing property is named, not just the first one found: a message that
-- names one of four defects sends an engineer back three more times.
create table public.verify_gaps_bad (
  id             uuid primary key default gen_random_uuid(),
  verify_rend_id uuid references public.verify_rend (id),
  reason         public.align_gap_reason
);

do $probe$
declare k text; r text;
begin
  select kind, reason into k, r from private.align_residue_violations()
   where relid = 'public.verify_gaps_bad'::regclass;
  if k is distinct from 'residue_store_incomplete' then
    raise exception 'G7 FAILED — an unusable residue store reported as %', coalesce(k, 'NOTHING');
  end if;
  if r not like '%nullable%' or r not like '%ON DELETE CASCADE%'
     or r not like '%address columns%' or r not like '%num_nulls%' then
    raise exception 'G7 FAILED — the reason named only some of the four defects: %', r;
  end if;
  raise notice 'G7 ok — an incomplete residue store names EVERY missing property, not the first';
end
$probe$;

drop table public.verify_gaps_bad;

-- G7a..G7d — EACH PROPERTY, ON ITS OWN. G7 above cannot tell WHICH test
-- selected the row: the store is missing all four, so any one surviving test
-- keeps it green. Mutations M5 (delete the num_nulls test) and M7 (weaken the
-- four-column count) both walked straight through G7 AND through the static
-- guard, because the rule listed the four tests twice — once to select, once
-- to explain — and only the explaining copy was checked.
--
-- These four stores are COMPLETE EXCEPT ONE THING each, so a deleted test
-- shows up as a store that is silently accepted. That is the only shape of
-- probe that can see it.
do $probe$
declare
  spec       text;
  variants   text[] := array[
    -- name,           the one property removed,        DDL fragment overrides
    'nullable_reason', 'no_cascade', 'missing_address_col', 'no_xor_check'];
  v          text;
  ddl        text;
  k          text;
  r          text;
  expect     text;
begin
  foreach v in array variants loop
    -- Every variant is the full contract with exactly one property withdrawn.
    ddl := 'create table public.verify_one (
              id uuid primary key default gen_random_uuid(),
              verify_rend_id uuid not null references public.verify_rend (id) '
           || case when v = 'no_cascade' then '' else 'on delete cascade' end || ',
              reason public.align_gap_reason '
           || case when v = 'nullable_reason' then '' else 'not null' end || ',
              display_char_start integer,
              display_char_end integer,
              display_word_count integer,
              observed_start_ms integer,
              '
           || case when v = 'missing_address_col' then '' else 'observed_end_ms integer,' end || '
              observed_word text'
           || case when v = 'no_xor_check' then ''
                   else ', constraint verify_one_xor check (
                           num_nulls(display_char_start, display_char_end) in (0, 2))' end
           || ')';
    execute ddl;

    expect := case v
                when 'nullable_reason'     then '%nullable%'
                when 'no_cascade'          then '%ON DELETE CASCADE%'
                when 'missing_address_col' then '%address columns%'
                when 'no_xor_check'        then '%num_nulls%'
              end;

    select kind, reason into k, r from private.align_residue_violations()
     where relid = 'public.verify_one'::regclass;

    if k is distinct from 'residue_store_incomplete' then
      raise exception 'G7a-d FAILED — a store missing ONLY "%" was ACCEPTED (kind %)',
        v, coalesce(k, 'NOTHING');
    end if;
    if r not like expect then
      raise exception 'G7a-d FAILED — a store missing ONLY "%" was reported as: %', v, r;
    end if;
    -- and it must not invent the other three
    if (select count(*) from unnest(string_to_array(r, '; ')) x) <> 1 then
      raise exception 'G7a-d FAILED — a store missing ONLY "%" reported % defects: %',
        v, (select count(*) from unnest(string_to_array(r, '; ')) x), r;
    end if;

    execute 'drop table public.verify_one';
  end loop;
  raise notice 'G7a-d ok — each of the four store properties is checked ON ITS OWN, and named exactly';
end
$probe$;

-- G8 — the contract as written in 20260810000200 SATISFIES the rule. A
-- contract the rule would still reject is a contract nobody can satisfy.
create table public.verify_gaps (
  id                  uuid primary key default gen_random_uuid(),
  verify_rend_id      uuid not null references public.verify_rend (id) on delete cascade,
  reason              public.align_gap_reason not null,
  display_char_start  integer,
  display_char_end    integer,
  display_word_count  integer,
  observed_start_ms   integer,
  observed_end_ms     integer,
  observed_word       text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  constraint verify_gaps_one_address_half check (
    case reason
      when 'resync_skipped' then
        num_nulls(display_char_start, display_char_end, display_word_count) = 0
        and num_nulls(observed_start_ms, observed_end_ms, observed_word) = 3
      when 'unmatched_observation' then
        num_nulls(display_char_start, display_char_end, display_word_count) = 3
        and num_nulls(observed_start_ms, observed_end_ms, observed_word) = 0
    end
  )
);

select private.assert_rls_class_rule();
do $probe$
begin raise notice 'G8 ok — the contract written in the migration satisfies the rule as written'; end
$probe$;

-- G9 — EXACTLY ONE ADDRESS HALF, and it is a function of the reason. This is
-- the joint decision made executable: both halves is a lie about what was
-- observed, neither half is a tally with a table around it.
insert into public.verify_rend (id, words)
values ('00000000-0000-4000-8000-00000000aaaa', '[]'::jsonb);

do $probe$
declare fired boolean := false;
begin
  begin
    insert into public.verify_gaps
      (verify_rend_id, reason, display_char_start, display_char_end,
       display_word_count, observed_start_ms)
    values ('00000000-0000-4000-8000-00000000aaaa', 'resync_skipped', 10, 40, 7, 1200);
  exception when check_violation then fired := true;
  end;
  if not fired then raise exception 'G9 FAILED — a row carrying BOTH address halves was accepted'; end if;

  fired := false;
  begin
    insert into public.verify_gaps (verify_rend_id, reason)
    values ('00000000-0000-4000-8000-00000000aaaa', 'resync_skipped');
  exception when check_violation then fired := true;
  end;
  if not fired then raise exception 'G9 FAILED — a row carrying NEITHER address half was accepted'; end if;

  fired := false;
  begin
    insert into public.verify_gaps
      (verify_rend_id, reason, display_char_start, display_char_end, display_word_count)
    values ('00000000-0000-4000-8000-00000000aaaa', 'unmatched_observation', 10, 40, 7);
  exception when check_violation then fired := true;
  end;
  if not fired then
    raise exception 'G9 FAILED — an observation-side gap wearing a DISPLAY address was accepted';
  end if;
  raise notice 'G9 ok — exactly one address half, and WHICH half is a function of the reason';
end
$probe$;

-- G10 — both sides of the residue actually store, each with its own half.
-- The values are H34-C2's own measurement shape (a 7-token run at display
-- 446..453) — a CONSTRAINT PROBE, rolled back, asserting nothing about a clip.
insert into public.verify_gaps
  (verify_rend_id, reason, display_char_start, display_char_end, display_word_count)
values ('00000000-0000-4000-8000-00000000aaaa', 'resync_skipped', 2431, 2478, 7);

insert into public.verify_gaps
  (verify_rend_id, reason, observed_start_ms, observed_end_ms, observed_word)
values ('00000000-0000-4000-8000-00000000aaaa', 'unmatched_observation', 41200, 41450, 'probe');

do $probe$
declare n integer;
begin
  select count(*) into n from public.verify_gaps;
  if n <> 2 then raise exception 'G10 FAILED — % rows stored, expected 2', n; end if;
  raise notice 'G10 ok — a skipped display run and an unmatched observation both persist';
end
$probe$;

-- G11 — erasure cascades (CLAUDE.md constraint 6). A takedown that leaves the
-- residue behind leaves verbatim document text behind.
delete from public.verify_rend where id = '00000000-0000-4000-8000-00000000aaaa';
do $probe$
declare n integer;
begin
  select count(*) into n from public.verify_gaps;
  if n <> 0 then raise exception 'G11 FAILED — % residue rows survived the parent delete', n; end if;
  raise notice 'G11 ok — deleting the rendition erases its residue, verbatim text included';
end
$probe$;

drop table public.verify_gaps;

-- G12 — a residue store attached to the WRONG parent does not discharge the
-- obligation. The FK is the link; a table that merely exists is not one.
create table public.verify_other (id uuid primary key default gen_random_uuid());
create table public.verify_gaps_elsewhere (
  id                  uuid primary key default gen_random_uuid(),
  verify_other_id     uuid not null references public.verify_other (id) on delete cascade,
  reason              public.align_gap_reason not null,
  display_char_start  integer,
  display_char_end    integer,
  display_word_count  integer,
  observed_start_ms   integer,
  observed_end_ms     integer,
  observed_word       text,
  constraint verify_gaps_elsewhere_one_half check (
    num_nulls(display_char_start, display_char_end, display_word_count) in (0, 3)
    and num_nulls(observed_start_ms, observed_end_ms, observed_word) in (0, 3)
  )
);

do $probe$
declare k text;
begin
  select kind into k from private.align_residue_violations()
   where relid = 'public.verify_rend'::regclass;
  if k is distinct from 'residue_store_missing' then
    raise exception 'G12 FAILED — a residue store on another parent discharged the obligation (%)',
      coalesce(k, 'NOTHING');
  end if;
  raise notice 'G12 ok — the obligation is discharged by the FOREIGN KEY, not by a table existing';
end
$probe$;

drop table public.verify_gaps_elsewhere;
drop table public.verify_other;

-- G13 — renaming the column moves a table to "needs a ruling", never to
-- "exempt". The same hole the RLS rule states rather than hides.
drop table public.verify_rend;
create table public.verify_rend2 (
  id           uuid primary key default gen_random_uuid(),
  word_timings jsonb
);

do $probe$
declare k text; b boolean;
begin
  select kind, blocking into k, b from private.align_residue_violations()
   where relid = 'public.verify_rend2'::regclass;
  if k is distinct from 'unclassifiable_match_output' or b is distinct from true then
    raise exception 'G13 FAILED — a renamed match-output column reported as % / blocking=%',
      coalesce(k, 'NOTHING'), coalesce(b::text, 'NULL');
  end if;
  raise notice 'G13 ok — a renamed match-output column needs a RULING, and is not auto-exempt';
end
$probe$;

drop table public.verify_rend2;

-- L6 — the rule holds over the whole schema, not just these two tables.
select private.assert_rls_class_rule();
do $probe$ begin raise notice 'L6 ok — RLS class rule holds across public'; end $probe$;

rollback;
`;

// Counted, not asserted: every probe raises exactly one notice on success, so
// the number below cannot drift from the number of probes actually shipped.
const PROBE_COUNT = (LIVE_SQL.match(/raise notice '/g) ?? []).length;

// ---------------------------------------------------------------------------
// Run.
// ---------------------------------------------------------------------------
let failed = 0;
console.log(`verify_voice_langs — ${LIVE ? 'LIVE' : 'DRY RUN'}`);
console.log(`  migrations: ${files.join(', ')}\n`);

for (const [id, claim, fn] of STATIC) {
  let ok = false;
  try { ok = Boolean(fn()); } catch { ok = false; }
  if (!ok) failed++;
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${id.padEnd(13)} ${claim}`);
}

if (!LIVE) {
  console.log('\n  Static proofs establish that each guarantee is DECLARED in the migration.');
  console.log('  They do NOT establish that Postgres enforces it. That needs a database:');
  console.log('    node supabase/tests/verify_voice_langs.mjs --db-url=postgresql://…');
  console.log(`  The live run executes ${PROBE_COUNT} probes in ONE transaction and ROLLS BACK.`);
  if (PRINT_SQL) console.log(`\n${LIVE_SQL}`);
  else console.log('  Re-run with --print-sql to see the exact SQL it would execute.');
} else {
  const host = (() => { try { return new URL(DB_URL.replace(/^postgres(ql)?:/, 'http:')).hostname; } catch { return ''; } })();
  const local = ['localhost', '127.0.0.1', '::1', '[::1]'].includes(host);
  if (!local && !ALLOW_REMOTE) {
    console.error(`\n  REFUSED — ${host || 'that host'} is not loopback.`);
    console.error('  This script rolls back, but a rollback is still a connection to a live');
    console.error('  project. Pass --allow-remote as well if that is genuinely what you want.');
    process.exit(2);
  }
  // `raise notice` goes to STDERR in psql, so both streams are the transcript.
  const r = spawnSync('psql', [DB_URL, '-v', 'ON_ERROR_STOP=1', '-X', '-q', '-f', '-'],
    { input: LIVE_SQL, encoding: 'utf8' });
  if (r.error && /ENOENT/i.test(r.error.code ?? r.error.message)) {
    failed++;
    console.error('\n  `psql` is not on PATH. Install the Postgres client, or run the SQL');
    console.error('  printed by --print-sql through another client.');
  } else {
    const log = `${r.stderr ?? ''}${r.stdout ?? ''}`.trim();
    if (log) console.log(log.split('\n').map((l) => `  ${l}`).join('\n'));
    const ok = (log.match(/\bok —/g) ?? []).length;
    if (r.status !== 0 || ok !== PROBE_COUNT) {
      failed++;
      console.error(`\n  LIVE RUN FAILED — ${ok}/${PROBE_COUNT} probes reported ok, `
        + `psql exit ${r.status}`);
    } else {
      console.log(`\n  ${PROBE_COUNT} live probes passed; transaction rolled back.`);
    }
  }
}

console.log(`\n${failed ? `verify: ${failed} FAILED` : 'verify: clean — all proofs passed'}`);
process.exit(failed ? 1 : 0);
