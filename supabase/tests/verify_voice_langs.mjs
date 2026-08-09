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

const M_RLS = files.find((f) => f.includes('rls_class_rule'));
const M_VOICES = files.find((f) => f.includes('_voices'));
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
const ruleCode = M_RLS ? CODE[M_RLS] : '';
// The BODIES of the two rule functions, not the whole file. `COMMENT ON` text
// is a SQL string literal and survives comment-stripping, so a guard run over
// the file can be satisfied by the migration's own description of itself —
// which is J26-M3 (`[ART-FIGURE]` checking nothing) reproduced here. Caught by
// mutation M15 while writing this script; the guard is scoped instead.
const fnBody = (name) =>
  ruleCode.match(new RegExp(`function private\\.${name}\\([\\s\\S]*?\\$fn\\$([\\s\\S]*?)\\$fn\\$`, 'i'))?.[1] ?? '';
const OBLIGATED_FN = fnBody('rls_obligated_tables');
const VIOLATIONS_FN = fnBody('rls_class_violations');

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

  ['S12', 'every table-creating migration ends by asserting the class rule',
    () => [M_VOICES, M_VL].every((f) => f && /select private\.assert_rls_class_rule\(\);\s*$/m.test(CODE[f]))],
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
