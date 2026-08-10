-- ============================================================================
-- 20260810000100_rls_class_rule_coverage
--
-- Closes the two coverage holes Jury raised against 20260809000100 and left
-- open for two rounds: J28-minor-a and J28-minor-b.
--
-- Owner: Atlas (schema). Writes no policy; policies remain Vault's.
--
-- ---------------------------------------------------------------------------
-- WHY A NEW MIGRATION AND NOT AN EDIT
--
-- Atlas rule 9 is unconditional: migrations are forward-only, and a reversal is
-- a follow-up forward migration. 20260809000100 has now been APPLIED to a real
-- PostgreSQL 18.1 (this round, finding "migrations remain unvalidated"), so the
-- "never applied anywhere, therefore not shipped" argument for editing it in
-- place is dead on arrival. It is superseded here instead, by CREATE OR REPLACE
-- over the same three functions, which is also the form a reviewer can read as
-- a diff. The older file keeps its own history and is not touched.
--
-- ---------------------------------------------------------------------------
-- J28-minor-a — THE RULE COULD NOT SEE THAT RLS WAS ON
--
-- The `unclassifiable` leg never tested `relrowsecurity`. A table keyed on
-- `owner_id` rather than `user_id` was flagged EVEN WHEN IT WAS CORRECTLY
-- PROTECTED, and because every table-creating migration ends in
-- `assert_rls_class_rule()`, that flag stopped every later migration in the
-- repository. Reproduced on a real server before this fix:
--
--     notes [unclassifiable] ... relrowsecurity = t ... assert RAISED
--
-- A gate that blocks the correct configuration is a gate that gets commented
-- out, which is how the whole rule dies. The classification question and the
-- OBLIGATION question are two different questions, and only the second one is
-- allowed to block:
--
--   * RLS off -> `unclassifiable`, BLOCKING. Nobody knows if this table carries
--     user data and nothing is protecting it. Decide.
--   * RLS on  -> `unclassifiable_protected`, REPORTED AND NOT BLOCKING. The
--     obligation is discharged however the table is finally classified, because
--     the protection is already on. It is still surfaced -- `assert` raises a
--     NOTICE for it -- so "we never looked" cannot be the outcome.
--
-- The default is still NOT exempt: renaming a column moves a table from
-- "obligated" to "needs a ruling", never to "invisible".
--
-- ---------------------------------------------------------------------------
-- J28-minor-b — PARTITIONED TABLES WERE INVISIBLE. THIS IS A MAJOR.
--
-- The rule scanned `relkind = 'r'` only. A partitioned parent is `relkind = 'p'`
-- and was therefore not a table as far as the rule was concerned. Reproduced on
-- a real server before this fix: a partitioned `usage_events` carrying a
-- `user_id`, with row level security OFF, made `rls_obligated_tables()` return
-- ZERO ROWS and `assert_rls_class_rule()` PASS.
--
-- SEVERITY, since the brief asks for a ruling rather than a shrug: this is a
-- MAJOR, not a Minor, and it is not a Critical.
--
--   * Not Critical. No partitioned relation exists in this schema and none is
--     scheduled: `grep -rn -F partition CLAUDE.md README.md resources/specs
--     resources/roadmap` returns two hits and both are about a "group
--     partition" in a determinism check, not about declarative partitioning.
--     There is no live exposure and no work item that would create one.
--
--   * Worse than a Minor. The failure is SILENT AND PERMISSIVE on constraint 5,
--     which CLAUDE.md does not treat as negotiable, and the defect is one
--     `relkind` literal away from a table full of user rows reading green. What
--     settles it is that 20260809000100 carries a section headed "WHERE THE RULE
--     CAN STILL BE DEFEATED, STATED RATHER THAN HIDDEN" which enumerates the
--     rule's holes and does not contain this one. A control whose own stated
--     limits omit a limit it has is this repository's definition of an
--     attestation (J30-M3), and attestations have been scored Major here before.
--
-- ---------------------------------------------------------------------------
-- WHAT ADMITTING `p` FORCES US TO SAY ABOUT PARTITIONS -- MEASURED, NOT RECALLED
--
-- Letting partitioned parents into the obligation is only half an answer, and
-- shipping the half is the exact failure mode of the last five rounds. The other
-- half is what "protected" means for a partitioned table. Three facts, each
-- established by running it on PostgreSQL 18.1 rather than by remembering it:
--
--   1. `ALTER TABLE parent ENABLE ROW LEVEL SECURITY` does NOT recurse.
--      relrowsecurity stayed `f` on the partition -- including on a partition
--      created AFTER the parent was enabled.
--   2. Reads THROUGH the parent do apply the parent's policies to partition
--      rows. A probe role saw 1 of 2 rows through the parent, correctly.
--   3. `GRANT SELECT` on the parent does NOT propagate to the partition either.
--      The partition's relacl stayed null and the direct read was refused with
--      "permission denied", NOT with a policy filter.
--
-- So the default partitioned layout is SAFE, and it is safe by (3) -- by the
-- absence of a grant -- and not by any policy. The moment somebody grants a
-- partition directly, it is an unpoliced door to user rows that can be opened by
-- name. That is the `partition_directly_granted` leg below. It is BLOCKING,
-- because unlike the classification question there is nothing ambiguous about
-- it: the data is reachable and no policy applies.
--
-- "Reachable" is computed, never listed. A grantee counts if it is not the owner
-- and does not bypass RLS -- `rolbypassrls` / `rolsuper` are read from
-- `pg_roles`, so a service role that bypasses RLS everywhere anyway is not a
-- false positive, and PUBLIC (grantee 0, which joins to no role) counts as the
-- worst case rather than being skipped. Reachability reads BOTH the table ACL
-- and the COLUMN ACLs: a column grant leaves `relacl` null and lands in
-- `pg_attribute.attacl`, so a table-level test alone reports "unreachable"
-- about a partition whose `user_id` is readable by name. Measured, after this
-- leg was written and believed done.
--
-- ---------------------------------------------------------------------------
-- STILL NOT COVERED, STATED RATHER THAN HIDDEN
--
--   * A user identifier under a name the regex does not anticipate.
--   * RLS enabled with zero policies -- denies everything; Vault's, not the
--     exemption rule's.
--   * VIEWS AND MATERIALIZED VIEWS OVER OBLIGATED TABLES. A materialized view
--     cannot have RLS at all, and a plain view without `security_invoker` runs
--     as its owner. Either one, granted to a client role, is a full bypass of a
--     protected table. Confirmed on the same server: a matview over an
--     RLS-enabled table reports relrowsecurity `f`, and pg_rewrite/pg_depend
--     traces it back to its base table cleanly, so this IS detectable by the
--     same machinery. It is NOT implemented here: no view or matview exists in
--     this schema and none appears in the specs or the roadmap, and bolting a
--     fourth relation class onto the change that fixes two open findings is how
--     a fix acquires its own defect. Reported to Jury this round as a new
--     finding with the reproduction attached, to be scheduled, not assumed.
--
-- ---------------------------------------------------------------------------
-- RECONCILIATION GREP (CLAUDE.md "The reconciliation pass"), run BEFORE editing
--   grep -rn -F "<ident>" CLAUDE.md README.md resources/specs resources/roadmap
--
--   rls_obligated_tables         0  implementation-only names, as before. No
--   rls_class_violations         0  document names them and none should.
--   assert_rls_class_rule        0
--   unclassifiable               0
--   rls_missing                  0
--   relrowsecurity               0
--   relkind                      0
--   relispartition               0
--   pg_partition_root            0
--   aclexplode                   0
--   unclassifiable_protected     0  NEW
--   partition_directly_granted   0  NEW
--   client_reachable             0  NEW
--   partitioned                  0
--   materialized view            0
--   CITATIONS ARE QUOTATIONS, NOT LINE NUMBERS (J31-M2). This block cited four
--   line numbers and ALL FOUR were wrong by the time the round closed, because
--   peers were reflowing those files as this was written. That is J30-M10
--   reproduced in a new artifact -- the one agent scope the remedy had never
--   been applied to. A quoted string survives a reflow; a line number is only
--   ever true for the version that no longer exists. The rule is now general:
--   cite by quotation in EVERY artifact, including SQL comments.
--
--   partition                       RECONCILED AS DELIBERATELY UNCHANGED --
--                                   the spec and roadmap hits read "group
--                                   partition", about a determinism check. A
--                                   different sense of the word; nothing to
--                                   change. Read, not skipped. (Counts are
--                                   omitted on purpose: the orchestrator's own
--                                   section 7 edit added several in this same
--                                   commit, so any number written here was
--                                   stale before the commit closed.)
--   blocking                        RECONCILED AS DELIBERATELY UNCHANGED --
--                                   the README hits use it for the COMMIT gate
--                                   ("Blocked" / "Permitted"), not for a
--                                   violation row. The collision is in English,
--                                   not in the schema.
--
--   SUPERSEDED, IN THIS FILE **AND IN 20260809000100**: both recorded that
--   CLAUDE.md and README.md "still enumerate the exempt catalogue by name ...
--   out of scope this round". Scribe CLOSED that in the SAME COMMIT -- both now
--   state the exemption as a class with two members, and the roadmap item is
--   marked done. The note in 20260809000100 is NOT edited: that migration has
--   been applied to a real server and migrations are forward-only, so a stale
--   COMMENT in an applied migration is corrected forward, here, rather than
--   rewritten in place. Reading that file, read this paragraph with it.
--
--   The orchestrator's post-round sweep found the 20260809000100 site; Jury's
--   J31-M1 named three and there were four. That is the sweep earning itself on
--   the first run -- and the reason it exists is that the BEFORE-editing grep
--   cannot see a peer who has not edited yet. Recording a peer's scope as unfinished while
--   the peer finishes it is J31-M1, and it happened three times in one round.
--   The reconciliation pass runs BEFORE editing, which is exactly when it
--   cannot see a concurrent author; see CLAUDE.md, "When more than one agent
--   writes in a round".
--
-- ROLLBACK: forward-only. Reverse with a later migration, never by editing.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- J28-minor-b: `relkind in ('r','p')`. One literal, and the reason it is worth
-- a migration is that everything above it was already correct.
--
-- Leaf partitions stay OUT of this set on purpose (`not relispartition`): their
-- protection comes from the parent, measured fact (2) above, and demanding
-- relrowsecurity on every leaf would make the rule fail on the CORRECT
-- partitioned layout. What a leaf owes is handled in the violations function,
-- which is where reachability can be seen.
--
-- Both foreign-key directions were checked on the server before this was
-- written: a table referencing a partitioned parent yields a pg_constraint row
-- whose confrelid IS the parent (plus one per partition, which this set
-- ignores), and a partitioned table referencing a plain one yields a row whose
-- conrelid is the `p` relation. So the recursive reach below now traverses
-- partitioned relations in both directions rather than stopping at them.
-- ---------------------------------------------------------------------------
create or replace function private.rls_obligated_tables()
returns table (relid regclass, reason text)
language sql
stable
as $fn$
  with recursive
  tbl as (
    select c.oid as t_oid
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where c.relkind in ('r', 'p')
      and n.nspname = 'public'
      and not c.relispartition
  ),
  direct as (
    select distinct t.t_oid
    from tbl t
    join pg_attribute a on a.attrelid = t.t_oid
    where a.attname = 'user_id'
      and a.attnum > 0
      and not a.attisdropped
  ),
  -- UNION (not UNION ALL) on a single oid column: the set dedups, so a cycle
  -- of foreign keys terminates instead of recursing forever.
  reach as (
    select d.t_oid from direct d
    union
    select fk.conrelid
    from reach r
    join pg_constraint fk on fk.confrelid = r.t_oid and fk.contype = 'f'
    where fk.conrelid in (select t_oid from tbl)
  )
  select r.t_oid::regclass,
         case when exists (select 1 from direct d where d.t_oid = r.t_oid)
              then 'carries user data directly: has a user_id column'
              else 'reaches user data through a foreign key chain'
         end
  from reach r;
$fn$;

comment on function private.rls_obligated_tables() is
  'Relations in `public` that are INSIDE the RLS obligation, computed from the '
  'catalog: has user_id, or has a foreign key path to a relation that does. '
  'Ordinary tables AND partitioned parents (relkind r and p). Membership is '
  'derived, never listed. Spec §7 preamble.';


-- ---------------------------------------------------------------------------
-- The violations function gains a `blocking` column, so severity is READ OFF
-- THE ROW instead of being inferred from a string somewhere else. The return
-- type changes, so this is a drop and create rather than a replace.
-- ---------------------------------------------------------------------------
drop function if exists private.rls_class_violations();

create function private.rls_class_violations()
returns table (relid regclass, kind text, blocking boolean, reason text)
language sql
stable
as $fn$
  with
  obligated as (
    select o.relid, o.reason from private.rls_obligated_tables() o
  ),
  rel as (
    select c.oid,
           c.relkind,
           c.relispartition,
           c.relrowsecurity,
           -- Reachable by something that RLS would actually constrain. A
           -- grantee that bypasses RLS is not a hole; PUBLIC joins to no role,
           -- so coalesce() counts it, which is the intended worst case.
           --
           -- BOTH ACLS, and the second one is not decoration. `GRANT SELECT
           -- (user_id) ON <partition> TO r` records nothing in relacl -- it
           -- lands in pg_attribute.attacl, and the table-level ACL stays null.
           -- A relacl-only test therefore reports "not reachable" about a
           -- partition whose user column is readable by name. Found by running
           -- the case against the server AFTER this leg was written and
           -- believed finished; it is exactly the shape of hole this leg
           -- exists to catch, reproduced inside the fix for it.
           (exists (
             select 1
             from aclexplode(c.relacl) ae
             left join pg_roles pr on pr.oid = ae.grantee
             where ae.grantee is distinct from c.relowner
               and not coalesce(pr.rolbypassrls, false)
               and not coalesce(pr.rolsuper, false)
           )
           or exists (
             select 1
             from pg_attribute a2
             cross join lateral aclexplode(a2.attacl) ae2
             left join pg_roles pr2 on pr2.oid = ae2.grantee
             where a2.attrelid = c.oid
               and a2.attnum > 0
               and not a2.attisdropped
               and ae2.grantee is distinct from c.relowner
               and not coalesce(pr2.rolbypassrls, false)
               and not coalesce(pr2.rolsuper, false)
           )) as client_reachable
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
  )

  -- (1) Inside the obligation, RLS off. The failure the rule exists to catch.
  select o.relid, 'rls_missing'::text, true, o.reason
  from obligated o
  join rel c on c.oid = o.relid
  where not c.relrowsecurity

  union all

  -- (2) Outside the obligation as computed, but carrying something that looks
  -- like a user key under another name. NOT auto-exempt. Blocking ONLY while
  -- the data is unprotected -- J28-minor-a: the rule now reads relrowsecurity
  -- instead of refusing on a table that is already doing the right thing.
  select c.oid::regclass,
         case when c.relrowsecurity
              then 'unclassifiable_protected' else 'unclassifiable' end::text,
         not c.relrowsecurity,
         case when c.relrowsecurity
              then 'no user_id and no foreign-key path to one, but column "' ||
                   a.attname || '" looks like a user key under another name. '
                   'ROW LEVEL SECURITY IS ENABLED, so the obligation is '
                   'discharged however this table is finally classified: this '
                   'is reported, not blocking. Classify it by hand when '
                   'convenient, and give Vault a policy if it carries a user.'
              else 'no user_id and no foreign-key path to one, but column "' ||
                   a.attname || '" looks like a user key under another name, '
                   'and row level security is OFF. Classify this table by hand '
                   'before treating it as a catalogue.'
         end
  from rel c
  join pg_attribute a
    on a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped
  where c.relkind in ('r', 'p')
    and not c.relispartition
    and a.attname ~ '^(owner|account|profile|customer|member|tenant|org|organization|auth|subject|person|holder)_id$'
    and c.oid not in (select o.relid::oid from obligated o)

  union all

  -- (3) A partition of an obligated parent, with its OWN row level security
  -- off, granted directly to a role that RLS would otherwise constrain.
  -- Enabling RLS on the parent does not reach here (measured), and a direct
  -- grant bypasses the parent entirely, so this is an unpoliced door to user
  -- rows that can be opened by name.
  select c.oid::regclass,
         'partition_directly_granted'::text,
         true,
         'this is a partition of ' || pg_partition_root(c.oid)::text ||
         ', which is inside the RLS obligation. Enabling row level security on '
         'a partitioned parent does NOT set it on the partitions -- the parent '
         'policies cover reads THROUGH the parent. This partition has row level '
         'security off and is granted directly to a role that does not bypass '
         'RLS, so its rows can be read by name with no policy applied. Revoke '
         'the direct grant, or enable row level security here and give Vault a '
         'policy for it.'
  from rel c
  where c.relispartition
    and c.relkind in ('r', 'p')
    and not c.relrowsecurity
    and c.client_reachable
    and pg_partition_root(c.oid)::oid in (select o.relid::oid from obligated o);
$fn$;

comment on function private.rls_class_violations() is
  'No BLOCKING row means the class rule holds. kind=rls_missing: inside the '
  'obligation with RLS off. kind=unclassifiable: the rule cannot see whether '
  'this table carries user data AND nothing is protecting it -- a human '
  'decides, and the default is NOT exempt. kind=unclassifiable_protected: same '
  'ambiguity, but RLS is on, so it is reported and does not block. '
  'kind=partition_directly_granted: a partition of an obligated parent, own RLS '
  'off, reachable by a role that does not bypass RLS.';


-- ---------------------------------------------------------------------------
-- The assert now separates "stop" from "say so". Non-blocking findings are
-- raised as NOTICE: the point of J28-minor-a is that the rule must be able to
-- SEE that RLS is on and SAY so, and a finding that is neither blocked nor
-- printed has not been seen by anybody.
-- ---------------------------------------------------------------------------
create or replace function private.assert_rls_class_rule()
returns void
language plpgsql
stable
as $fn$
declare
  v   record;
  msg text := '';
begin
  for v in select * from private.rls_class_violations() loop
    if v.blocking then
      msg := msg || format(E'\n  %s [%s] %s', v.relid, v.kind, v.reason);
    else
      raise notice 'RLS class rule -- reported, not blocking: % [%] %',
        v.relid, v.kind, v.reason;
    end if;
  end loop;
  if msg <> '' then
    raise exception 'RLS class rule violated:%', msg
      using hint =
        'Spec §7: a table is exempt only when it carries NO user data. '
        'Enable RLS and give Vault a policy, or state why the rule cannot see '
        'the user column. Do not add the table to a list -- there is no list.';
  end if;
end;
$fn$;

comment on function private.assert_rls_class_rule() is
  'Raises if any relation in `public` violates the RLS class rule in a way that '
  'blocks. Non-blocking findings are raised as NOTICE rather than swallowed. '
  'Called at the end of every table-creating migration, and by '
  'supabase/tests/verify_voice_langs.mjs.';

revoke all on function private.rls_obligated_tables() from public;
revoke all on function private.rls_class_violations() from public;
revoke all on function private.assert_rls_class_rule() from public;

-- This migration creates no table, but it changes what the rule MEANS, so it
-- ends the same way every table-creating migration does: by running it.
select private.assert_rls_class_rule();
