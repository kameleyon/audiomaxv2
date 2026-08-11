-- ============================================================================
-- 20260810000200_align_residue
--
-- H34-C2 (Critical, Halo round 34) and J17-C3 (open, Owner Atlas, due
-- 2026-08-22), DECIDED TOGETHER. Owner: Atlas.
--
-- Halo: "deciding them apart is how one gets a span `kind` and the other gets a
-- bare tally." This migration is the joint decision, and the paragraph below is
-- the reason the two cannot be separated.
--
-- ---------------------------------------------------------------------------
-- THE FINDING, REPRODUCED RATHER THAN RELAYED
--
-- Verified against aligner/spike-a/out/spike-a-voices.json at HEAD 51b0f3b,
-- reading clips[] by (reference_id, voice, replicate) rather than by the label
-- in the brief:
--
--   voice=narrateur replicate=1 lang=fr kind=long  resyncs=2  skipped=25
--   voice=feminine  replicate=2 lang=fr kind=long  resyncs=1  skipped= 9
--   the other seven clips                          resyncs=0  skipped= 0
--
-- Both figures reproduce EXACTLY. `grep -rn "resync" supabase/` returned 0
-- lines before this file. Over resources/specs + resources/roadmap, `resync`
-- and `re-sync` together occupy SEVEN distinct lines -- spec:2072 and
-- roadmap:285, 459, 469, 471, 474, 2183 -- and Halo's characterisation holds on
-- every one: five are measurement figures, one is an ablation delta, one is a
-- container-memory consideration. NONE is an obligation.
--
-- ---------------------------------------------------------------------------
-- THE JOINT DECISION: THEY ARE ONE OBJECT SEEN FROM TWO SIDES
--
-- The match step (ADR-0002, ADR-0006) tries to connect two streams: the
-- OBSERVED words heard in our own generated audio, and the DISPLAY words on the
-- page. It succeeds on most tokens and leaves a residue on BOTH sides:
--
--   H34-C2  a DISPLAY word that received no observation -- the re-sync cursor
--           jumped over it. It has (cs, ce). It has NO (start_ms, end_ms), so
--           it is never highlighted.
--
--   J17-C3  an OBSERVED word that matched no display text -- recognition can
--           emit a word that is not in the document. It has (start_ms, end_ms).
--           It has NO (cs, ce), so it is excluded from the highlight map.
--
-- **The addresses are exactly complementary.** That is the whole reason the two
-- must be decided together, and it is invisible if either is taken alone:
--
--   * J17-C3 alone reads as "this thing has no address, therefore it cannot be
--     positional, therefore a tally." That reading is precisely the "bare
--     tally" Halo predicted -- and it is WRONG, because the token does have an
--     address; it is a TIME address rather than a character address.
--   * H34-C2 alone reads as "this thing has a character address, therefore it
--     is an ordinary positional span with a NOT NULL char offset" -- a shape
--     with no room for J17-C3 at all.
--
-- Decided jointly, the roadmap:1794-1804 fork ("either a new span `kind` with a
-- null-address rule, or a per-segment tally with a stated reason it is not
-- positional") resolves to the FIRST branch, and the null-address rule is not
-- "null address" but "THE OTHER ADDRESS":
--
--     Exactly one address half is present, and WHICH half is a function of the
--     reason. Never both. Never neither.
--
-- One store, one reason enum, one XOR constraint. A tally is refused: a
-- document-level count at minute 47 does nothing for someone who needs to know
-- that THIS paragraph is the one whose highlight stopped (spec §9.1, "`spans`
-- is the part that matters for a blind user").
--
-- ---------------------------------------------------------------------------
-- WHY THIS IS **NOT** A `SpanReason` / §9.1 SKIP-MANIFEST SPAN
--
-- The obvious home is §9.1's `spans[]`, and it is wrong, for a reason that is
-- checkable rather than aesthetic:
--
--     spec §7.2: disclosure_fingerprint = H( sorted (SpanReason, block_ord,
--                                            char_offset, SPOKEN) ... )
--     spec §7.2: text_hash = H(text, normalizer_version, lexicon_fingerprint,
--                              lang, disclosure_fingerprint)
--     spec §7.2: "`skip_policy` and `voice_id` are deliberately NOT hash
--                 inputs ... Re-render identity is hash equality at a given
--                 voice."
--
-- A re-sync gap is VOICE- AND RENDER-dependent -- measured above: the same
-- reference text at the same voice produced 2 re-syncs at replicate 1 and 0 at
-- replicate 2. Admitting it to `SpanReason` therefore injects a render-
-- dependent term into `text_hash`, which is the key that makes "only genuinely
-- new segments are charged" (§7.3) decidable. Every segment's hash would move
-- on every re-render, and the whole book would become billable.
--
-- And it would bill the remedy it recommends: this reason is classified
-- `render_specific` below, whose entire meaning is "a different render can
-- change it". That is the H6-C1 / R4-M6 / N7-M1 paywalled-remedy shape, aimed
-- again at the population §9.1 exists for. **SpanReason stays at 16 values.**
--
-- The residue is a fact about a (segment, voice) RENDER, so it lives under
-- `segment_renditions` (§7.2a), which is where "nothing per-voice lives on the
-- segment" (§7.2, N3-R3) already puts every other alignment fact.
--
-- ---------------------------------------------------------------------------
-- PERMANENCE: `render_specific`, AND THE BRIEF'S JUSTIFICATION IS NOT THE
-- ARTIFACT'S
--
-- The brief and the audit both say `render_specific` because "narrateur-r1
-- re-syncs twice where -r2 re-syncs zero times on the same text -- so a
-- DIFFERENT VOICE genuinely re-syncs differently, and the remedy 'try another
-- voice' is real."
--
-- **The artifact does not show that.** `narrateur` r1 and r2 are two REPLICATES
-- OF THE SAME VOICE over the same `reference_id`; likewise `feminine` r1/r2.
-- The measured contrast is between RENDERS, not between voices. Three
-- consequences, and the middle one is a correction to the remedy sentence a
-- blind user will hear:
--
--   1. `render_specific` is MORE strongly warranted, not less. §6.3 defines it
--      as "a different voice genuinely can change it"; here even the SAME voice
--      re-rendered changes it. The classification is a fortiori.
--   2. The catalogue string must say RE-RENDER and must NOT promise that
--      another voice fixes it. No committed run compares re-sync counts ACROSS
--      voices at fixed replicate, so "try another voice" is unmeasured. Routed
--      to Tongue and Proof; recorded here because the schema is what will
--      outlive the audit report.
--   3. Not `permanent`: the same text produced zero gaps at another render, so
--      it is not a function of text x normalizer (the N7-M1 test).
--      Not `retryable`: re-transcribing the SAME audio is deterministic
--      (ADR-0006, "two independent runs producing identical figures"), so the
--      only thing that changes the outcome is NEW AUDIO, which is billable.
--      `retryable` would promise a free automatic retry that cannot work.
--
-- `unmatched_observation` is `render_specific` on ADR-0002's own words:
-- "reusing [`transcript_mismatch`] would tell a blind user a mishearing is
-- unfixable when another voice or re-transcription genuinely fixes it."
--
-- ---------------------------------------------------------------------------
-- WHAT LANDS HERE, AND WHAT CANNOT YET
--
-- `segment_renditions` DOES NOT EXIST. This schema holds `voices` and
-- `voice_langs` only; the rendition table is Phase 1 (roadmap:1187) and is a
-- 25-column table whose design is §7.2a's, not this migration's. A child table
-- cannot precede its parent, and the two ways to fake it are both worse than
-- waiting:
--
--   * an FK-less `align_gaps` would carry VERBATIM DOCUMENT TEXT (the observed
--     word) with no `user_id` and no foreign-key path to one -- so the class
--     rule in 20260809000100 would compute it OUTSIDE the RLS obligation and it
--     would ship unprotected. That breaks CLAUDE.md constraint 5 to close a
--     finding about constraint 2.
--   * a stub `segment_renditions` would freeze half of §7.2a's design in a
--     forward-only migration, to be ALTERed by the migration that actually owns
--     it.
--
-- So what lands is the part that CAN land, and it is deliberately more than a
-- plan:
--
--   1. THE VOCABULARY -- `align_reason` (with the new value), `align_gap_reason`
--      and `align_permanence` as enum types. H26-B1's lesson applies verbatim:
--      an enum makes the next silent substitution a migration somebody has to
--      defend in review, instead of a value somebody types.
--   2. THE CLASSIFICATION, EXECUTABLE -- §6.3's permanence table and its
--      "derived, not authored" rule (N5-M6) are prose today. They become
--      functions that are TOTAL over the enum: a value added without being
--      classified raises `case_not_found` instead of silently reading
--      `retryable`.
--   3. THE OBLIGATION, EXECUTABLE -- a class rule, in the exact shape of
--      20260809000100's, that makes it IMPOSSIBLE to create the match-output
--      store without the residue store. It is silent on today's schema and it
--      halts the Phase 1 migration that would otherwise drop the fact again.
--
-- Halo's finding is that an obligation with no artifact does not acquire an
-- owner by the passage of time. (3) is that artifact. It is not persistence,
-- and this file does not claim to be; it is the thing that makes the omission
-- of persistence a hard failure rather than an oversight.
--
-- ---------------------------------------------------------------------------
-- RECONCILIATION GREP (CLAUDE.md, "The reconciliation pass"), run BEFORE
-- editing:
--   grep -rn -F "<ident>" CLAUDE.md README.md resources/specs resources/roadmap
--
--   resync                    5 hits  DELIBERATELY UNCHANGED -- every hit is a
--                                     measurement figure (README:458,
--                                     spec:2072, roadmap:459/469/474). None is
--                                     an obligation; that IS H34-C2. The
--                                     obligation-side text is Scribe's and
--                                     Forge's, routed in the report.
--   re-sync                   5       DELIBERATELY UNCHANGED -- roadmap:285
--                                     (ablation delta), :471, :2183 (memory
--                                     sizing), spec:2072. Same reading.
--   skipped_display_tokens    0       NEW to the documents. The producer emits
--                                     it (worker/src/match/match.ts:92,:420);
--                                     no document names it. Routed to Scribe.
--   align_reason             28       RECONCILED -- §6.3:1499 is the nine-value
--                                     row and §9:2598 is the catalogue key
--                                     derivation. The type created below has
--                                     TEN. See "DIVERGENCE" immediately after
--                                     this list; it is registered, not silent.
--   align_permanence         10       RECONCILED -- §6.3:1500 fixes the three
--                                     values and the derivation rule; both are
--                                     implemented verbatim below.
--   wrong_match              13       RECONCILED -- and NOT reused. Halo: "a
--                                     re-sync is not a violation, it is the
--                                     design working." §6.3 defines it as "the
--                                     match invariants were violated".
--   transcript_mismatch       7       RECONCILED -- explicitly not reused
--                                     (roadmap:1799, ADR-0002).
--   render_specific          12       RECONCILED -- §6.3's definition is the
--                                     one applied above.
--   SpanReason               17       DELIBERATELY UNCHANGED, and that is a
--                                     DECISION, not an omission -- see "WHY
--                                     THIS IS NOT A SpanReason" above. Stays
--                                     at 16 values.
--   disclosure_fingerprint    6       RECONCILED -- §7.2:2177 is the reason
--                                     SpanReason is left alone.
--   text_hash                14       RECONCILED -- §7.2:2159, same reason.
--   segment_renditions       24       RECONCILED -- §7.2a is the parent this
--                                     store hangs from; roadmap:1187 schedules
--                                     it in Phase 1. Not created here.
--   align_gaps                0       NEW, and it is a schema identifier, not a
--   align_gap_reason          0       design fact the documents already carry.
--   incomplete_match          0       The §6.3 row and the §9 budget that must
--   unmatched_observation     0       name them are routed in the report.
--   resync_skipped            0
--
--   DIVERGENCE, REGISTERED RATHER THAN DISCOVERED: `public.align_reason` below
--   carries TEN values; spec §6.3:1499 enumerates NINE. The extra value is
--   `incomplete_match` and it is the whole of H34-C2. The spec edit is one row
--   plus one permanence clause and it is NOT this migration's to make (scope:
--   supabase/** only, three agents live in the document paths) -- exact text is
--   in the report, Owner Scribe with Forge. `verify_voice_langs.mjs` proof S18
--   pins the divergence set to exactly {incomplete_match}, so it cannot grow in
--   silence and it fails the moment the spec catches up without the register
--   being updated. Writing the value ONLY into the spec and not the schema is
--   how H34-C2 happened; writing it into neither is how it stays happened.
--
-- ROLLBACK: forward-only (Atlas rule 9). Reverse with a later migration.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- §6.3's three permanence values, exactly.
-- ---------------------------------------------------------------------------
create type public.align_permanence as enum (
  'permanent',        -- no re-render and no retry changes it
  'retryable',        -- the same operation repeated may succeed, at no cost
  'render_specific'   -- a different RENDER genuinely can change it
);

comment on type public.align_permanence is
  'Spec §6.3. DERIVED from the align_reason set, never authored (N5-M6) -- see '
  'public.align_permanence_of(). `render_specific` is the value that carries a '
  'remedy; classifying something `permanent` that a re-render fixes withdraws '
  'the headline feature AND hides the remedy (J11-C1).';


-- ---------------------------------------------------------------------------
-- §6.3's align_reason enum, PLUS `incomplete_match`.
--
-- The value is last because enum order is the sort order and the nine before it
-- are the spec's own row order; appending keeps a future `\dT+` diff readable.
-- ---------------------------------------------------------------------------
create type public.align_reason as enum (
  'unsupported_language',
  'low_confidence',
  'engine_error',
  'transcript_mismatch',
  'no_transcriber',
  'transcription_unreliable',
  'wrong_match',
  'voice_substituted',
  'excessive_drop',
  -- H34-C2 + J17-C3. The SEGMENT-LEVEL name for "the match ran correctly and
  -- left part of this segment unconnected". It is one cause covering both
  -- sides of the residue ON PURPOSE: §9:2598 bounds the catalogue key space at
  -- "at most one CAUSE plus at most one CONTEXT", and the two sides CAN co-
  -- occur in a single segment, so two causes would make {display, observation}
  -- a reachable reason set with no key -- reintroducing the power-set problem
  -- N5-M6 closed. WHICH side, and WHERE, is the positional record's job
  -- (public.align_gap_reason), exactly as `excessive_drop` is the segment-level
  -- cause whose positional detail is `dropped_marker`.
  --
  -- NOT `wrong_match`: that is "the match invariants were violated" (§6.3) --
  -- a defect. A bounded forward re-sync is ADR-0006's accepted design working
  -- as specified, and conflating them would tell a reader a correct matcher is
  -- broken while giving a broken one nowhere to be reported.
  'incomplete_match'
);

comment on type public.align_reason is
  'Spec §6.3. TEN values: the nine §6.3 enumerates, plus `incomplete_match` '
  '(H34-C2 + J17-C3), which §6.3 does not yet carry. That divergence is '
  'registered in this migration''s header and pinned by proof S18 in '
  'supabase/tests/verify_voice_langs.mjs -- it is one row of spec text owed by '
  'Scribe with Forge, not a schema that invented a value.';


-- ---------------------------------------------------------------------------
-- The residue's own reason vocabulary. TWO values, and the split is the
-- address, not the taxonomy.
-- ---------------------------------------------------------------------------
create type public.align_gap_reason as enum (
  -- H34-C2. Display words the forward re-sync cursor jumped over (ADR-0006,
  -- bounded at 200 tokens). They carry (cs, ce) and NO timestamp, so they are
  -- never highlighted: audio continues, the highlight stops for a paragraph
  -- and reappears further down. Producer: worker/src/match/match.ts's
  -- `skipped_display_tokens`, one row per contiguous run.
  'resync_skipped',

  -- J17-C3. An observed word that matched no display text. Open recognition
  -- can emit a word that is not in the document -- prediction could not
  -- (ADR-0002). It carries (start_ms, end_ms) and NO display address, and it
  -- is excluded from the highlight map.
  'unmatched_observation'
);

comment on type public.align_gap_reason is
  'The residue of the match step, one value per side. `resync_skipped` is a '
  'DISPLAY word with no observation (has cs/ce, no time). '
  '`unmatched_observation` is an OBSERVED word with no display text (has time, '
  'no cs/ce). Deliberately NOT a SpanReason: §9.1 spans feed '
  'disclosure_fingerprint -> text_hash, and voice_id is deliberately not a '
  'text_hash input (§7.2), so a render-dependent span would make every segment '
  'billable on every re-render.';


-- ---------------------------------------------------------------------------
-- §6.3's permanence TABLE, executed.
--
-- TOTAL OVER THE ENUM BY CONSTRUCTION. There is no ELSE branch: plpgsql raises
-- `case_not_found` on an unclassified value. That is the same property
-- voice_lang_sync_grade() gets from coalesce() -- structural, not a
-- convention -- and it is the specific thing H34-C2 needed and did not have.
-- A tenth value added by a future migration without a classification here
-- FAILS LOUDLY; it does not quietly read `retryable`.
-- ---------------------------------------------------------------------------
create function public.align_reason_permanence(p_reason public.align_reason)
returns public.align_permanence
language plpgsql
immutable
parallel safe
as $fn$
begin
  if p_reason is null then
    raise exception 'align_reason_permanence: NULL is not an align_reason'
      using hint = 'A reason set may be EMPTY. It may not contain a NULL.';
  end if;

  return case p_reason
    -- permanent: never touches audio, or is a function of text x normalizer.
    when 'unsupported_language'     then 'permanent'
    when 'no_transcriber'           then 'permanent'
    when 'excessive_drop'           then 'permanent'   -- N7-M1
    when 'transcript_mismatch'      then 'permanent'   -- N8-M5

    -- retryable: the same operation repeated may succeed, at no cost.
    when 'engine_error'             then 'retryable'

    -- render_specific: a different render genuinely can change it.
    when 'voice_substituted'        then 'render_specific'
    when 'low_confidence'           then 'render_specific'  -- N8-M4
    when 'transcription_unreliable' then 'render_specific'
    when 'wrong_match'              then 'render_specific'
    when 'incomplete_match'         then 'render_specific'  -- H34-C2, J17-C3
  end;
end;
$fn$;

comment on function public.align_reason_permanence(public.align_reason) is
  'Spec §6.3''s permanence table, executed. NO ELSE BRANCH: an unclassified '
  'enum value raises case_not_found rather than defaulting. Adding a reason '
  'without classifying it is therefore a hard failure, not a silent '
  '`retryable`.';


-- ---------------------------------------------------------------------------
-- §6.3's DERIVATION rule (N5-M6), executed:
--
--   "if any reason in the set is `permanent` the result is `permanent`; else if
--    any is `render_specific` the result is `render_specific`; else
--    `retryable`."
--
-- NULL return, deliberately and narrowly: an EMPTY reason set is the ordinary
-- state of a healthy rendition (`align_status: ok`), and a segment with no
-- reason has no permanence. NULL here means "there is no such fact", never
-- "unknown" -- the caller's CHECK is `(align_reason = '{}') = (align_permanence
-- is null)`. A NULL *element* is a different thing and is refused above.
-- ---------------------------------------------------------------------------
create function public.align_permanence_of(p_reasons public.align_reason[])
returns public.align_permanence
language plpgsql
immutable
parallel safe
as $fn$
declare
  r public.align_reason;
  seen_render_specific boolean := false;
begin
  if p_reasons is null or array_length(p_reasons, 1) is null then
    return null;
  end if;

  foreach r in array p_reasons loop
    -- Raises on a NULL element rather than skipping it: a reason array with a
    -- hole in it is a producer bug, and swallowing it would compute a
    -- permanence from a set nobody wrote.
    if public.align_reason_permanence(r) = 'permanent' then
      return 'permanent';
    elsif public.align_reason_permanence(r) = 'render_specific' then
      seen_render_specific := true;
    end if;
  end loop;

  if seen_render_specific then
    return 'render_specific';
  end if;
  return 'retryable';
end;
$fn$;

comment on function public.align_permanence_of(public.align_reason[]) is
  'Spec §6.3: permanence is DERIVED from the reason SET, not authored (N5-M6). '
  'permanent > render_specific > retryable. Returns NULL for an empty or NULL '
  'set -- a rendition with no reason has no permanence -- and RAISES on a NULL '
  'element. Without a single-valued derivation, a reason ARRAY (NEW-M7) has no '
  'computable permanence at all.';


create function public.align_gap_permanence(p_reason public.align_gap_reason)
returns public.align_permanence
language plpgsql
immutable
parallel safe
as $fn$
begin
  if p_reason is null then
    raise exception 'align_gap_permanence: NULL is not an align_gap_reason';
  end if;

  return case p_reason
    -- Measured, not asserted: spike-a-voices.json shows the SAME voice over the
    -- SAME reference text producing 2 re-syncs at replicate 1 and 0 at
    -- replicate 2. A different RENDER changes it, which is §6.3's own test for
    -- render_specific, met a fortiori.
    when 'resync_skipped'        then 'render_specific'
    -- ADR-0002: "another voice or re-transcription genuinely fixes it" -- the
    -- stated reason transcript_mismatch may not be reused for this.
    when 'unmatched_observation' then 'render_specific'
  end;
end;
$fn$;

comment on function public.align_gap_permanence(public.align_gap_reason) is
  'Both residue reasons are render_specific, and neither is permanent or '
  'retryable. NO ELSE BRANCH, same property as align_reason_permanence.';


-- ============================================================================
-- THE OBLIGATION, AS A CLASS RULE.
--
-- Same species as 20260809000100's RLS rule, and for the same reason: a LIST is
-- defeatable by addition, and the failure mode this closes is precisely that
-- somebody builds the match-output store and nobody remembers the residue.
--
--     A table that persists MATCH OUTPUT is obligated to have a RESIDUE STORE
--     hanging off it -- a child table, FK ON DELETE CASCADE, carrying an
--     `align_gap_reason` column, both address halves, and an XOR constraint.
--
-- "Persists match output" is DERIVED from the catalog: §7.2a names the column
-- `words JSONB`, so a jsonb column named `words` is the signal. That is not
-- table-name matching -- renaming `segment_renditions` does not escape it.
--
-- WHERE IT CAN STILL BE DEFEATED, STATED RATHER THAN HIDDEN: renaming the
-- COLUMN. So, exactly as the RLS rule does with a renamed user key, a jsonb
-- column whose name looks like word timings under another spelling is not
-- auto-exempted -- it is FLAGGED, blocking, for a human ruling. Not covered:
-- a spelling this regex does not anticipate, and match output stored somewhere
-- other than a jsonb column.
--
-- IT IS SILENT ON TODAY'S SCHEMA. No relation in `public` has a jsonb column
-- at all, so this rule reports nothing until the Phase 1 migration that creates
-- the store -- at which point it stops that migration until the residue store
-- exists in it. That is the point: it blocks only the configuration that
-- reintroduces H34-C2, never a correct one (the J28-minor-a lesson -- a gate
-- that blocks the correct configuration is a gate that gets commented out).
-- ============================================================================
create function private.align_residue_violations()
returns table (relid regclass, kind text, blocking boolean, reason text)
language sql
stable
as $fn$
  with
  rel as (
    select c.oid, c.relkind, c.relispartition
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relkind in ('r', 'p')
      and not c.relispartition
  ),
  -- Match-output stores, canonical spelling (§7.2a: `words JSONB`).
  canonical as (
    select distinct r.oid
    from rel r
    join pg_attribute a
      on a.attrelid = r.oid and a.attnum > 0 and not a.attisdropped
    join pg_type t on t.oid = a.atttypid
    where t.typname = 'jsonb' and a.attname = 'words'
  ),
  -- Match-output stores under another spelling. The rule cannot be sure, so it
  -- asks rather than exempting.
  renamed as (
    select distinct r.oid, a.attname
    from rel r
    join pg_attribute a
      on a.attrelid = r.oid and a.attnum > 0 and not a.attisdropped
    join pg_type t on t.oid = a.atttypid
    where t.typname = 'jsonb'
      and a.attname ~ '^(word_timings|word_times|aligned_words|match_output|word_map|timings|matched_words)$'
      and r.oid not in (select oid from canonical)
  ),
  -- A residue store is any table carrying an `align_gap_reason` column.
  gap_store as (
    select distinct r.oid
    from rel r
    join pg_attribute a
      on a.attrelid = r.oid and a.attnum > 0 and not a.attisdropped
    where a.atttypid = 'public.align_gap_reason'::regtype
  ),
  -- ...that is a CHILD of the store in question, by foreign key.
  linked as (
    select fk.confrelid as parent_oid, fk.conrelid as child_oid, fk.confdeltype
    from pg_constraint fk
    where fk.contype = 'f'
      and fk.conrelid in (select oid from gap_store)
  )

  -- (1) A match-output store with no residue store hanging off it. This is
  --     H34-C2 and J17-C3, in the form in which they would recur.
  select m.oid::regclass, 'residue_store_missing'::text, true,
         'this table persists match output (jsonb column "words", spec §7.2a) '
         'and NO table carries an align_gap_reason column with a foreign key '
         'to it. The match step leaves a residue on BOTH sides -- display '
         'words the re-sync cursor skipped (H34-C2, measured at 9 and 25 in '
         'aligner/spike-a/out/spike-a-voices.json) and observed words that '
         'matched no display text (J17-C3). Neither receives a highlight and '
         'neither has a programmatic equivalent without this store: WCAG 2.2 '
         'SC 4.1.3. Create the residue store in THIS migration -- its contract '
         'is written out in full in 20260810000200_align_residue.sql.'
  from canonical m
  where not exists (
    select 1 from linked l where l.parent_oid = m.oid
  )

  union all

  -- (2) Same obligation, reached through a column name the rule had to guess
  --     at. Never auto-exempt; the default is a ruling, not silence.
  select m.oid::regclass, 'unclassifiable_match_output'::text, true,
         'this table has a jsonb column "' || m.attname || '" whose name looks '
         'like match output under a spelling other than §7.2a''s `words`, and '
         'no residue store hangs off it. The rule cannot tell whether this is '
         'the match-output store. Classify it by hand: either give it a residue '
         'store, or state why it holds no word timings. Renaming a column moves '
         'a table from "obligated" to "needs a ruling", never to "exempt".'
  from renamed m
  where not exists (
    select 1 from linked l where l.parent_oid = m.oid
  )

  union all

  -- (3) A residue store exists but does not carry what makes it usable. Each
  --     clause is a way the store could be present and still lose the fact.
  --
  --     THE DEFECT LIST IS COMPUTED ONCE AND DRIVES BOTH THE SELECTION AND THE
  --     MESSAGE. The first version of this leg had the four tests written twice
  --     -- once in a WHERE and once in the reason text -- and mutations M5 and
  --     M7 walked straight through it: delete a test from the WHERE and the
  --     message still names it, so a store missing that property is ACCEPTED
  --     while every guard stays green. That is the J26-M3 vacuous-guard shape
  --     and it is the second time this project has found it in a counted guard
  --     (the first was `rolbypassrls` in 20260810000100). Deleting a case from
  --     the array below now removes it from the message AND from the
  --     selection, so the live probes in verify_voice_langs.mjs -- one store
  --     per property, each missing exactly one -- can see it.
  select g.oid::regclass, 'residue_store_incomplete'::text, true,
         'this table carries an align_gap_reason column but ' ||
         array_to_string(d.defects, '; ')
  from gap_store g
  cross join lateral (
    select array_remove(array[
           case when not exists (
             select 1 from pg_attribute a
              where a.attrelid = g.oid and a.attnum > 0 and not a.attisdropped
                and a.atttypid = 'public.align_gap_reason'::regtype
                and a.attnotnull)
           then 'its reason column is nullable (a gap with no reason has no '
                'catalogue string, so it cannot be announced)' end,
           case when not exists (
             select 1 from linked l
              where l.child_oid = g.oid and l.confdeltype = 'c')
           then 'it has no foreign key ON DELETE CASCADE to a match-output '
                'store (CLAUDE.md constraint 6: erasure must cascade)' end,
           case when (
             select count(*) from pg_attribute a
              where a.attrelid = g.oid and a.attnum > 0 and not a.attisdropped
                and a.attname in ('display_char_start', 'display_char_end',
                                  'observed_start_ms', 'observed_end_ms')
             ) <> 4
           then 'it is missing one of the four address columns '
                '(display_char_start, display_char_end, observed_start_ms, '
                'observed_end_ms) -- BOTH halves are required, because the two '
                'residue reasons carry opposite halves' end,
           case when not exists (
             select 1 from pg_constraint ck
              where ck.conrelid = g.oid and ck.contype = 'c'
                and pg_get_constraintdef(ck.oid) ilike '%num_nulls%')
           then 'it has no num_nulls() CHECK pinning exactly one address half '
                'per reason -- without it a row can carry both halves, or '
                'neither, and a gap with neither is a tally with a table '
                'around it' end
    ], null) as defects
  ) d
  where array_length(d.defects, 1) is not null;
$fn$;

comment on function private.align_residue_violations() is
  'No BLOCKING row means the residue obligation holds. kind='
  'residue_store_missing: a match-output store with no residue store -- H34-C2 '
  'and J17-C3 in the form in which they recur. kind='
  'unclassifiable_match_output: a jsonb column that looks like match output '
  'under another spelling; a human decides, and the default is NOT exempt. '
  'kind=residue_store_incomplete: the store exists but cannot carry the fact.';


-- ---------------------------------------------------------------------------
-- The two class rules, under one raiser.
-- ---------------------------------------------------------------------------
create function private.schema_obligation_violations()
returns table (relid regclass, rule text, kind text, blocking boolean, reason text)
language sql
stable
as $fn$
  select v.relid, 'rls_class'::text, v.kind, v.blocking, v.reason
  from private.rls_class_violations() v
  union all
  select v.relid, 'align_residue'::text, v.kind, v.blocking, v.reason
  from private.align_residue_violations() v;
$fn$;

comment on function private.schema_obligation_violations() is
  'Every computed schema obligation in one relation, tagged by rule. Adding an '
  'obligation means adding a leg here -- not remembering to call a new assert.';


create function private.assert_align_residue_rule()
returns void
language plpgsql
stable
as $fn$
declare
  v   record;
  msg text := '';
begin
  for v in select * from private.align_residue_violations() loop
    if v.blocking then
      msg := msg || format(E'\n  %s [%s] %s', v.relid, v.kind, v.reason);
    else
      raise notice 'align residue rule -- reported, not blocking: % [%] %',
        v.relid, v.kind, v.reason;
    end if;
  end loop;
  if msg <> '' then
    raise exception 'align residue rule violated:%', msg
      using hint =
        'H34-C2 / J17-C3. The match step leaves a residue on both sides and '
        'neither side has a programmatic equivalent without a store. The '
        'contract for the residue store is written out in full in '
        'supabase/migrations/20260810000200_align_residue.sql. Do not add the '
        'table to a list -- there is no list.';
  end if;
end;
$fn$;

comment on function private.assert_align_residue_rule() is
  'Raises if any relation in `public` violates the align residue obligation. '
  'Reached from private.assert_rls_class_rule(), because CLAUDE.md names that '
  'ONE statement as the mandatory terminal line of every table-creating '
  'migration -- see the note on the delegation there.';


-- ---------------------------------------------------------------------------
-- THE DELEGATION, AND WHY IT RIDES ON A FUNCTION WHOSE NAME SAYS "RLS".
--
-- CLAUDE.md: "Every table-creating migration ends with `select
-- private.assert_rls_class_rule();`" -- ONE statement, and it is the only line
-- a future migration is REQUIRED to contain. An obligation that rides on a line
-- nobody is required to write is exactly the shape of H34-C2, so the residue
-- rule rides on the line that is.
--
-- The RLS body is UNCHANGED, deliberately: this is a replace that ADDS a
-- delegation, not a rewrite. The RLS findings still raise with the RLS hint and
-- the residue findings raise with theirs, so a failure names the rule that
-- failed rather than an umbrella.
--
-- The name is now narrower than the function. That is a real wart and the fix
-- is one line of CLAUDE.md -- rename the mandated statement to
-- `select private.assert_schema_obligations();`, which is created below and is
-- already correct. Routed in the report; NOT done here, because CLAUDE.md is a
-- document and three agents are live in the document paths this round.
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

  -- The delegation. RLS first: an unprotected table is the worse finding, and
  -- a residue store that is missing on a table nobody may read is the lesser
  -- of the two problems that migration has.
  perform private.assert_align_residue_rule();
end;
$fn$;

comment on function private.assert_rls_class_rule() is
  'Raises if any relation in `public` violates the RLS class rule in a way that '
  'blocks, then delegates to private.assert_align_residue_rule(). Non-blocking '
  'findings are raised as NOTICE rather than swallowed. Named for the RLS rule '
  'because CLAUDE.md names THIS statement as the mandatory terminal line of '
  'every table-creating migration; private.assert_schema_obligations() is the '
  'honest name and is the one to migrate CLAUDE.md to.';


create function private.assert_schema_obligations()
returns void
language plpgsql
stable
as $fn$
begin
  -- Delegates rather than re-implementing, so there is exactly one raiser per
  -- rule and the hints stay attached to the rule that produced them.
  perform private.assert_rls_class_rule();
end;
$fn$;

comment on function private.assert_schema_obligations() is
  'The honest name for the mandatory terminal statement of a table-creating '
  'migration: asserts EVERY computed schema obligation. Identical behaviour to '
  'private.assert_rls_class_rule() today, and it stays identical because that '
  'function delegates. Exists so CLAUDE.md''s mandated line can be renamed '
  'without a migration.';


-- ============================================================================
-- THE RESIDUE STORE'S CONTRACT, WRITTEN OUT SO PHASE 1 INVENTS NOTHING.
--
-- This is NOT created here: `public.segment_renditions` does not exist, and a
-- child cannot precede its parent. It belongs in the SAME migration that
-- creates the rendition store (roadmap:1187, Phase 1), because the rule above
-- will refuse that migration until it is there.
--
--   create table public.align_gaps (
--     id                    uuid  primary key default gen_random_uuid(),
--     segment_rendition_id  uuid  not null
--                                 references public.segment_renditions (id)
--                                 on delete cascade,
--     reason                public.align_gap_reason not null,
--
--     -- The DISPLAY half. Character offsets INTO segments.text, the same
--     -- coordinate system as the trace's cs/ce (§6.2) and §9.1's char_offset.
--     display_char_start    integer,
--     display_char_end      integer,
--     -- How many display WORDS the run covers. `skipped_display_tokens` is the
--     -- number Halo measured at 9 and 25; without it the store holds a range
--     -- and not the quantity the finding is about.
--     display_word_count    integer,
--
--     -- The OBSERVED half. Milliseconds into THIS rendition's audio.
--     observed_start_ms     integer,
--     observed_end_ms       integer,
--     -- The word as heard. Verbatim recognizer output, so §7.4's deletion
--     -- cascade and retention lifecycle must NAME this column alongside
--     -- observed_words (J17-M4), not merely cover it.
--     observed_word         text,
--
--     created_at            timestamptz not null default now(),
--     updated_at            timestamptz not null default now(),
--
--     -- EXACTLY ONE ADDRESS HALF, AND WHICH ONE IS A FUNCTION OF THE REASON.
--     -- num_nulls() gives the per-column reading rather than a weaker "at
--     -- least one is set", and `reason` is NOT NULL so the CASE is never NULL
--     -- and this CHECK can never evaluate to UNKNOWN -- a CHECK that returns
--     -- NULL PASSES, which is how two-way constraints usually fail open
--     -- (voice_langs_evidence_iff_measured, same reasoning).
--     constraint align_gaps_one_address_half check (
--       case reason
--         when 'resync_skipped' then
--           num_nulls(display_char_start, display_char_end, display_word_count) = 0
--           and num_nulls(observed_start_ms, observed_end_ms, observed_word) = 3
--         when 'unmatched_observation' then
--           num_nulls(display_char_start, display_char_end, display_word_count) = 3
--           and num_nulls(observed_start_ms, observed_end_ms, observed_word) = 0
--       end
--     ),
--     constraint align_gaps_display_range
--       check (display_char_end >= display_char_start),
--     constraint align_gaps_observed_range
--       check (observed_end_ms >= observed_start_ms),
--     constraint align_gaps_display_word_count_positive
--       check (display_word_count > 0),
--     constraint align_gaps_observed_word_not_empty
--       check (observed_word <> '')
--   );
--
--   -- ONE ROW PER CONTIGUOUS RUN, at its own address -- N9-C6's rule, which
--   -- was filed against a manifest that aggregated 18 markers across 52 blocks
--   -- into a single address. `narrateur-r1`'s 25 skipped tokens are TWO runs
--   -- (7 at display 446-453, 18 at display 872-890), and one row saying 25
--   -- would be the same defect.
--
--   create index align_gaps_rendition_idx
--     on public.align_gaps (segment_rendition_id, reason);
--
--   -- RLS: NOT exempt, and it does not need to be listed anywhere. The class
--   -- rule in 20260809000100 reaches it automatically --
--   -- align_gaps -> segment_renditions -> segments -> documents(user_id) --
--   -- and it MUST, because observed_word is verbatim document text.
--   -- assert_rls_class_rule() will refuse the migration until Vault's policies
--   -- and `alter table ... enable row level security` are in place.
--
-- WHAT MUST LAND WITH IT, AND IS NOT SCHEMA:
--   * Nexus -- `align_gaps` served on GET /documents/:id/segments, keyed to the
--     rendition, with the segment-level `align_reason` including
--     `incomplete_match`. A store nobody can read is not a disclosure.
--   * Tongue + Proof -- catalogue strings. Budget in the report.
--   * Access -- the live region that announces it. H34-M2: nobody is assigned.
-- ============================================================================


revoke all on function public.align_reason_permanence(public.align_reason) from public;
revoke all on function public.align_permanence_of(public.align_reason[]) from public;
revoke all on function public.align_gap_permanence(public.align_gap_reason) from public;
revoke all on function private.align_residue_violations() from public;
revoke all on function private.schema_obligation_violations() from public;
revoke all on function private.assert_align_residue_rule() from public;
revoke all on function private.assert_schema_obligations() from public;
revoke all on function private.assert_rls_class_rule() from public;

-- The three classifiers are pure functions over enums and hold no data, but a
-- client that renders a permanence needs the same derivation the backend used
-- -- §6.3's whole point is that "permanent" and "transient" must not arrive as
-- the same token. Granted on the voice_lang_sync_grade precedent.
do $grants$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    grant execute on function public.align_reason_permanence(public.align_reason) to anon;
    grant execute on function public.align_permanence_of(public.align_reason[]) to anon;
    grant execute on function public.align_gap_permanence(public.align_gap_reason) to anon;
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    grant execute on function public.align_reason_permanence(public.align_reason) to authenticated;
    grant execute on function public.align_permanence_of(public.align_reason[]) to authenticated;
    grant execute on function public.align_gap_permanence(public.align_gap_reason) to authenticated;
  end if;
end;
$grants$;

-- This migration creates no table, but it changes what the mandatory terminal
-- assert MEANS, so it ends the same way every table-creating migration does:
-- by running it. 20260810000100 set that precedent for the same reason.
select private.assert_rls_class_rule();
