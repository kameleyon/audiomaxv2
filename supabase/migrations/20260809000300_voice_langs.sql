-- ============================================================================
-- 20260809000300_voice_langs
--
-- One row per (voice, language). Spec §7.1a. Roadmap:521-555.
-- Owner: Atlas. Due 2026-08-15.
--
-- §6.3 said the quote "computes the voice-dependent blocker from SPIKE A's
-- matrix for the (segment.lang, voice_id) pair" and NO TABLE HELD THAT MATRIX.
-- The single pre-payment word-sync disclosure this design offers a blind user
-- terminated in a lookup with nowhere to look, and the `render_specific`
-- remedy -- "choose a different voice" -- cost $1.35-$32 to evaluate. This is
-- that table. It also carries the sample audio that makes the remedy usable at
-- all (R14-M1).
--
-- ---------------------------------------------------------------------------
-- THE STORE SHIPS EMPTY OF GRADES, AND NO SEED ACCOMPANIES THIS MIGRATION
--
-- Every pair is `unmeasured` on day one. On the evidence in aligner/spike-a/
-- out/, nothing has been measured on the bar over the audio that ships: the
-- only per-voice figure this project holds is French, one clip, 15/17 vs 17/18
-- vs 18/18, on `agree_within_250ms_pct` -- cross-engine agreement between two
-- Whisper-family engines, NOT the bar (H26-M3, H26-M4). A seed that wrote a
-- grade would assert a measurement nobody has made. The way to make this store
-- say "established" is to run the measurement, not to write an INSERT.
--
-- The (voice, lang) ROWS themselves -- all `unmeasured` -- are a separate,
-- scheduled item (roadmap:548-555) and require a voice catalogue that does not
-- exist yet. Row presence and `sync_grade` answer two different questions:
-- a missing row means "this voice does not speak this language", a row reading
-- `unmeasured` means "nobody has measured it".
--
-- ---------------------------------------------------------------------------
-- RECONCILIATION GREP, run BEFORE editing
--   grep -rn -F "<ident>" CLAUDE.md README.md resources/specs resources/roadmap
--
--   voice_langs            32 hits  reconciled -- §7.1a is the design; §9:1796
--                                   and §8.2 are read paths (Nexus/Forge)
--   sync_grade             32       reconciled -- §7.1a:1213 (four values),
--                                   §8.2:1670-1694 (quote bucketing),
--                                   §9:1796/1807 (payload + 4 i18n keys)
--   unmeasured             38       reconciled -- default; also the name of the
--                                   quote bucket `word_sync_unmeasured_segments`
--   provisional            17       reconciled -- storable, never "available"
--   at_or_above_bar         9       reconciled -- the only grade the evidence
--                                   floor below constrains
--   below_bar               9       reconciled -- sets `transcription_unreliable`
--                                   at quote time; that is §8.2's job, not a
--                                   column here
--   sync_metric             5       reconciled -- enum, two values (§7.1a:1214)
--   sync_drift_bound_ms     4       reconciled -- 250 fixed BEFORE the run
--   sync_pct                4       reconciled
--   sync_matched_words      8       reconciled -- floor 200
--   sync_longest_clip_ms    4       reconciled -- floor 300000
--   sync_measured_at        7       reconciled -- distinct fact from updated_at
--   sync_evidence_path      4       reconciled -- the artifact, not the claim
--   sample_audio_path       7       reconciled -- nullable = not yet rendered
--   sample_text             6       reconciled -- NOT NULL, chosen text
--   matched_within_drift_pct 10     reconciled -- enum member
--   agree_within_250ms_pct   5      reconciled -- enum member; the metric the
--                                   French figure is on, which is why it is
--                                   storable and can never be at_or_above_bar
--
--   DELIBERATELY UNCHANGED: no document is edited by this migration. Every
--   identifier above already exists in the spec and the roadmap.
--
-- ROLLBACK: forward-only. Reverse with a later migration, never by editing.
-- ============================================================================

-- Enums, not text+CHECK, and the reason is adversarial rather than stylistic:
-- H26-B1 was a METRIC SUBSTITUTION that converted a failing measured result
-- into an unmeasurable one. An enum makes the next substitution a migration
-- somebody has to defend in review, instead of a value somebody types.
create type public.sync_grade as enum (
  'unmeasured',        -- no measurement exists for this pair
  'provisional',       -- measured, but below the evidence floor
  'at_or_above_bar',   -- measured at/above the bar over sufficient evidence
  'below_bar'          -- measured below the bar
);

create type public.sync_metric as enum (
  'matched_within_drift_pct',  -- the roadmap's pass bar (roadmap:295-305)
  'agree_within_250ms_pct'     -- cross-engine agreement. NOT the bar (H26-M3)
);

comment on type public.sync_grade is
  'Spec §7.1a. Four values, and four i18n catalogue keys (§9). `unmeasured` '
  'and `provisional` both count as NOT ESTABLISHED in the §8.2 quote; only '
  '`at_or_above_bar` counts as word-sync available.';


create table public.voice_langs (
  voice_id              uuid        not null
                                    references public.voices (id)
                                    on delete cascade,
  lang                  text        not null,

  -- Heard BEFORE paying (R14-M1). Every degraded-path remedy in this design is
  -- "choose a different voice", and a catalogue that returns nothing audible
  -- names a door the population it was written for cannot open.
  sample_audio_path     text,
  sample_text           text        not null,

  -- SPIKE A's (lang, voice) matrix -- the store §8.2 quotes from.
  sync_grade            public.sync_grade not null default 'unmeasured',
  sync_metric           public.sync_metric,
  sync_drift_bound_ms   integer,
  sync_pct              numeric(5,2),
  sync_matched_words    integer,
  sync_longest_clip_ms  integer,
  sync_measured_at      timestamptz,
  sync_evidence_path    text,

  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),

  -- No surrogate `id`, and that is a deliberate exception to "every table has
  -- an id" (Atlas rule 2). The business identity of a row IS (voice_id, lang);
  -- a surrogate would add a unique constraint on the natural key and buy
  -- nothing, while this composite PK is also the index the §8.2 quote's lookup
  -- needs. `created_at`/`updated_at` are NOT waived: a store whose whole
  -- purpose is holding a dated measurement is the last place to skip them.
  constraint voice_langs_pkey primary key (voice_id, lang),

  -- BCP-47 SHAPE only. Deliberately NOT `lang in ('en','es','fr')`: this column
  -- says which languages a VOICE IS OFFERED IN, which is a provider fact. The
  -- product's language scope is a ROUTING fact and belongs to §3.5, where an
  -- out-of-scope upload is refused with an announced reason rather than being
  -- silently unrepresentable here.
  constraint voice_langs_lang_shape
    check (lang ~ '^[a-z]{2,3}(-[A-Za-z0-9]{1,8})*$'),

  -- Two spellings of "missing" is how a catalogue starts lying.
  constraint voice_langs_sample_audio_path_not_empty
    check (sample_audio_path <> ''),
  constraint voice_langs_sample_text_not_empty
    check (length(sample_text) between 1 and 2000),
  constraint voice_langs_evidence_path_not_empty
    check (sync_evidence_path <> ''),

  -- Domain sanity on the evidence columns. These are not thresholds and not
  -- measurements; they only say a percentage is a percentage.
  constraint voice_langs_sync_pct_range
    check (sync_pct >= 0 and sync_pct <= 100),
  constraint voice_langs_sync_matched_words_nonneg
    check (sync_matched_words >= 0),
  constraint voice_langs_sync_longest_clip_ms_nonneg
    check (sync_longest_clip_ms >= 0),
  constraint voice_langs_sync_drift_bound_ms_positive
    check (sync_drift_bound_ms > 0),

  -- ======================================================================
  -- ONE CHECK, BOTH DIRECTIONS (spec §7.1a "Nullability").
  --
  -- The seven measurement columns are NULL IF AND ONLY IF sync_grade is
  -- `unmeasured`. An unmeasured row may not carry numbers; a graded row may
  -- not omit them. A grade with no `sync_matched_words` is the claim with the
  -- evidence stripped off, which is the shape this table exists to prevent.
  --
  -- `num_nulls()` gives the per-column reading, not a weaker "at least one is
  -- set": all seven, or none of the seven. `sync_grade` is NOT NULL, so the
  -- CASE is never NULL and this constraint can never evaluate to UNKNOWN --
  -- a CHECK that returns NULL PASSES, which is how two-way constraints
  -- usually fail open.
  -- ======================================================================
  constraint voice_langs_evidence_iff_measured check (
    num_nulls(sync_metric, sync_drift_bound_ms, sync_pct, sync_matched_words,
              sync_longest_clip_ms, sync_measured_at, sync_evidence_path)
    = case when sync_grade = 'unmeasured' then 7 else 0 end
  ),

  -- ======================================================================
  -- THE EVIDENCE FLOOR -- ENFORCED HERE, IN THE DATABASE.
  --
  -- Spec §7.1a and roadmap:332-347 fix this floor BEFORE the measurement that
  -- will use it, "movable only publicly with the reason recorded", for the
  -- same reason as the 250 ms drift bound: a floor chosen after the
  -- measurement is a floor chosen to let the result through. Moving any
  -- number below is therefore a migration somebody has to defend.
  --
  --   * sync_metric = matched_within_drift_pct at sync_drift_bound_ms = 250.
  --     Not a substituted metric (H26-B1).
  --   * sync_matched_words >= 200. At today's n of 14-24 one token is 5.6
  --     percentage points, so a bar of 95 cannot be resolved at all.
  --   * sync_longest_clip_ms >= 300000. §6.2's failure is an offset that
  --     ACCUMULATES; on an 8-second clip it cannot appear by construction.
  --
  -- `coalesce(..., false)` so this constraint is self-sufficient: a row with
  -- grade `at_or_above_bar` and all-NULL evidence is rejected HERE as well as
  -- by the iff constraint above, rather than passing on a NULL.
  --
  -- Anything that misses one of these is stored WITH ITS NUMBERS as
  -- `provisional`. Nothing is discarded; it simply does not get to say
  -- established.
  -- ======================================================================
  constraint voice_langs_evidence_floor check (
    sync_grade <> 'at_or_above_bar'
    or coalesce(
         sync_metric = 'matched_within_drift_pct'
         and sync_drift_bound_ms = 250
         and sync_matched_words >= 200
         and sync_longest_clip_ms >= 300000,
       false)
  )

  -- ======================================================================
  -- THE BAR ITSELF IS **DEFERRED TO THE WRITER**, EXPLICITLY, AND HERE IS WHY.
  --
  -- The pass bar is a CONJUNCTION OF THREE metrics (roadmap:313-317):
  --     matched_within_drift_pct >= 95  AND  p95_abs_error_ms <= 300
  --                                     AND  hallucination_rate <= 2
  -- This table holds exactly ONE of them (`sync_pct`). `p95_abs_error_ms` and
  -- `hallucination_rate` have no column in §7.1a, so a CHECK here could
  -- enforce one third of the bar while reading, to anyone who found it, as
  -- the whole bar. Partial enforcement that looks total is worse than none.
  --
  -- The bar is also stated as "Proposed bar, to be confirmed or MOVED by the
  -- measurement and not after it" -- a number the documents expect to change
  -- once, publicly. The evidence FLOOR above is fixed and immovable by the
  -- same paragraph, which is exactly why the floor is a constraint and the bar
  -- is not.
  --
  -- WHO ENFORCES IT: the SPIKE A follow-up writer (Owner: Forge, due
  -- 2026-08-14, roadmap:324-331), which holds all three numbers at the moment
  -- it decides the grade. If the bar is ever to be enforced in the database,
  -- the migration that does it must FIRST add columns for the other two
  -- metrics -- otherwise it re-creates the defect it means to close.
  -- ======================================================================
);

-- `GET /voices?lang=` filters on `lang` ALONE, which the primary key cannot
-- serve (its leading column is voice_id). This also lets the voice picker
-- order by grade without a sort. The PK's leading column serves the FK, so
-- `voice_id` needs no separate index -- the usual "every FK gets an index" is
-- already satisfied.
create index voice_langs_lang_grade_idx
  on public.voice_langs (lang, sync_grade);

comment on table public.voice_langs is
  'One row per (voice, language) the voice is OFFERED in. Spec §7.1a. Carries '
  'NO user data, therefore outside the RLS obligation by the class rule in '
  '20260809000100 -- not by being named. Ships EMPTY of grades: every pair is '
  'unmeasured until a run writes evidence.';

comment on column public.voice_langs.sample_audio_path is
  'Private bucket path, served as a short-TTL signed URL. NULL means NOT YET '
  'RENDERED -- never "this voice has no sample". The seed is not complete '
  'until every row carries one, and Phase 1 asserts zero NULLs after seeding '
  'rather than trusting the word "seeded" (roadmap:564-572).';

comment on column public.voice_langs.sync_grade is
  'NOT NULL, DEFAULT unmeasured. A MISSING ROW also reads as unmeasured, never '
  'as NULL and never as absent -- see public.voice_lang_sync_grade().';

comment on column public.voice_langs.updated_at is
  'When this ROW changed. NOT the same fact as sync_measured_at: a sample can '
  'be re-rendered without a re-measurement, and vice versa.';

comment on column public.voice_langs.sync_evidence_path is
  'The artifact, not the assertion. A grade taken from a file that is '
  'rewritten in place is a grade with no provenance, which is why this is a '
  'column and not a comment.';

create trigger voice_langs_set_updated_at
  before update on public.voice_langs
  for each row execute function private.set_updated_at();


-- ---------------------------------------------------------------------------
-- THE READ PATH, so that "no API ever returns a NULL sync_grade" is a function
-- somebody CALLS rather than a sentence in a spec that every query must
-- remember. Spec §7.1a; roadmap:556-563 (Owner: Nexus, due 2026-08-18) owns
-- the two HTTP readers -- this is the resolver they call.
--
-- A missing row reads as `unmeasured`. A client that must interpret a NULL
-- cannot be relied on to interpret it pessimistically, and the one that does
-- not is the one a blind user is holding.
-- ---------------------------------------------------------------------------
create or replace function public.voice_lang_sync_grade(
  p_voice_id uuid,
  p_lang     text
)
returns public.sync_grade
language sql
stable
parallel safe
as $fn$
  select coalesce(
    (select vl.sync_grade
       from public.voice_langs vl
      where vl.voice_id = p_voice_id
        and vl.lang = p_lang),
    'unmeasured'::public.sync_grade);
$fn$;

comment on function public.voice_lang_sync_grade(uuid, text) is
  'The §8.2 quote''s per-segment lookup for (segments.lang, voice_id). Returns '
  'unmeasured for a pair with no row -- NEVER NULL. coalesce() over a scalar '
  'subquery, so the non-NULL guarantee is structural, not a convention.';

do $grants$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    grant select on public.voice_langs to anon;
    grant execute on function public.voice_lang_sync_grade(uuid, text) to anon;
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    grant select on public.voice_langs to authenticated;
    grant execute on function public.voice_lang_sync_grade(uuid, text)
      to authenticated;
  end if;
end;
$grants$;

select private.assert_rls_class_rule();
