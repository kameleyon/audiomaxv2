-- ============================================================================
-- 20260809000200_voices
--
-- The voice catalogue. Spec §7.1, row `voices`.
-- Owner: Atlas. Due 2026-08-15 (roadmap:464-467).
--
-- ---------------------------------------------------------------------------
-- `lang` IS NOT HERE, AND "DROPPED" IS THE WRONG VERB FOR A FIRST MIGRATION
--
-- Spec §7.1 and roadmap:533-535 both say `voices.lang` is DROPPED "in the same
-- migration". Both sentences were written against a schema that already
-- existed. This repository has no shipped schema: this is the first migration
-- in it. There is nothing to drop, so the column is simply NEVER CREATED, and
-- no `ALTER TABLE ... DROP COLUMN` appears below.
--
-- The design fact is unchanged and is the reason: a scalar `lang` can describe
-- one language per voice and is silently wrong for every other. Fish `s2-pro`
-- is multilingual, and SPIKE A generated Spanish on an ENGLISH Fish voice for
-- exactly this reason (aligner/spike-a/fixtures.json:17) before the owner
-- caught it. The (voice, language) pairing lives in `voice_langs`
-- (20260809000300), which is the only place `GET /voices?lang=` can honestly
-- filter. H26-C3.
--
-- ---------------------------------------------------------------------------
-- RECONCILIATION GREP, run BEFORE editing
--   grep -rn -F "<ident>" CLAUDE.md README.md resources/specs resources/roadmap
--
--   voices             48 hits  reconciled -- §7.1:1158 is the column run this
--                               table implements; §9:1796 is the read route
--                               (Nexus, not built here); README:335 and
--                               CLAUDE.md:224 are the RLS sentences, left to
--                               Scribe per roadmap:689 (due 2026-08-15)
--   provider_voice_id   1 hit   reconciled -- §7.1:1158, sole mention
--   is_clone            3 hits  reconciled -- §7.1:1158, §9:1796 payload,
--                               roadmap read-route item
--   provider           many     reconciled -- appears on `api_call_logs` and
--                               `segment_renditions` too (§7.2a:1476); those
--                               are different columns on different tables and
--                               are NOT built here
--   gender              -       reconciled -- §7.1:1158 and §9:1796 name it and
--                               NEITHER states a value domain. No CHECK is
--                               invented below; see the column comment.
--
--   DELIBERATELY UNCHANGED: nothing in the documents. This migration adds no
--   identifier the spec does not already carry.
--
-- ROLLBACK: forward-only. Reverse with a later migration, never by editing.
-- ============================================================================

create table public.voices (
  id                 uuid        primary key default gen_random_uuid(),

  provider           text        not null,
  provider_voice_id  text        not null,

  -- NULLABLE, with the `sample_audio_path` / `observed_words` discipline:
  -- NULL means THE PROVIDER PUBLISHES NO GENDER FOR THIS VOICE. It never means
  -- "we did not look". The CHECK forbids '' so that empty string and NULL
  -- cannot both come to mean absence -- two spellings of missing is how a
  -- catalogue starts lying.
  --
  -- NO value-domain CHECK. Spec §7.1 and §9 both name this column and neither
  -- states its domain, and inventing one here would push a vocabulary onto
  -- Tongue and onto the voice picker that no document has agreed. A CHECK is a
  -- later migration, once the catalogue seed shows what providers actually
  -- publish.
  gender             text        check (gender <> ''),

  is_clone           boolean     not null default false,

  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),

  constraint voices_provider_not_empty
    check (length(provider) between 1 and 64),
  constraint voices_provider_voice_id_not_empty
    check (length(provider_voice_id) between 1 and 256),

  -- Business identity. One row per voice per provider; a second is a bug, and
  -- a duplicate would give `voice_langs` two parents for one real voice.
  constraint voices_provider_identity_key
    unique (provider, provider_voice_id)
);

comment on table public.voices is
  'Global voice catalogue. Spec §7.1. Carries NO user data, therefore outside '
  'the RLS obligation by the class rule in 20260809000100 -- not by being '
  'named. Deliberately has no `lang` column (H26-C3): see `voice_langs`.';

comment on column public.voices.id is
  'Surrogate PK. UUID v4 via gen_random_uuid(), not v7: no v7 generator is '
  'available without an extension this project has not adopted, and the '
  'time-sortability v7 buys is worthless on a catalogue of tens of rows that '
  'is read by key and never scanned in insert order. `created_at` carries the '
  'time. Revisit if this table ever grows or is range-scanned.';

comment on column public.voices.gender is
  'NULL = the provider publishes no gender for this voice. Never "unknown to '
  'us". No value domain is fixed by any document; do not add one here without '
  'a spec change and a Tongue string budget.';

create trigger voices_set_updated_at
  before update on public.voices
  for each row execute function private.set_updated_at();

-- `GET /voices?lang=` is documented Public and cacheable (roadmap:1030). Read
-- only; every write path is the worker, which connects as the owning role.
-- Any change to these grants is Vault's (CODEOWNERS:72).
do $grants$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    grant select on public.voices to anon;
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    grant select on public.voices to authenticated;
  end if;
end;
$grants$;

-- Tripwire, not decoration: if this table had been given a user column, the
-- migration that created it would fail here rather than shipping an
-- unprotected table and waiting for an audit to notice.
select private.assert_rls_class_rule();
