# Audit Record — Founding Documents, Round 3

- **Date:** 2026-08-08
- **Subject:** spec v3, roadmap v3, `README.md`, `CLAUDE.md`, `.gitignore`, `research/`
- **Reviewers:** Jury, Halo — read-only tools
- **Prior:** `-round2.md`, `2026-08-08-founding-documents.md`

## Verdicts

| Reviewer | R1 | R2 | R3 |
| --- | --- | --- | --- |
| **Jury** | `FAIL` 3B/12C/12M | `FAIL` 0B/3C/6M | **`FAIL` 0B/1C/5M** |
| **Halo** | `FAIL` 4B/6C/9M | `FAIL` 1B/4C/5M | **`FAIL` 0B/3C/12M** |

**Jury composite: 2.4 → 3.7 → 3.8.** Evidence discipline reached **5/5** — the
strongest dimension in the set, credited to the research file demoting its own
Tier A datum and stating the consequence out loud. Internal consistency
regressed 3 → 2, which is the entire reason for the `FAIL`.

**All Blockers closed.** Word-level sync now has a producer, a stage, an owner,
and a validity invariant — the thing that could not be retrofitted.

## The dominant pattern, named by both reviewers

> *v3 fixes findings in the artifact where they were raised and not in the
> artifact that implements them.*

Four of the most serious findings are the same governance defect: interface
fixed / schema not (NEW-C1), spec fixed / roadmap not (NEW-C3), roadmap fixed /
`CLAUDE.md` not (N-7), §7.2b fixed / §7.1 not (NEW-M3).

**Structural fix, not a patch:** `CLAUDE.md` now carries a **document precedence
order** and a **reconciliation gate** — every field in a spec interface must
have a column in a migration, enforced by a test, run before Phase 1 writes any
migration.

## Round-3 findings and disposition

### Critical

| ID | Finding | Disposition |
| --- | --- | --- |
| **NEW-C2** | **The §6.2 invariant and the §3.8 narration contracts were mutually exclusive.** `normalize(text[cs:ce]) == w` requires every spoken token to have a display origin — but table linearization, the figure sentinel, and math narration are all spoken-and-not-displayed, with no field to live in. Build either literally and the other breaks. The invariant was *over-strong*, not insufficient. | **Fixed** — trace tokens carry `origin: 'display' \| 'inserted'`; `segments.inserted_speech` holds synthesized-not-displayed text; the round-trip binds display tokens only; inserted tokens are never highlighted and are enumerated as disclosure spans. **This one field unblocks five findings across three rounds.** |
| **NEW-C1 / N3-R4** | Six accessibility fields added to the `Block` interface in v3 appear in **no schema table and no migration** — `lang_conf`, `describes_ord`, `described_by_ord`, `ref_target_offset`, `mathml`, `reading_order_conf`. Alone this defeated N-3, and the persistence half of N-6, N-8, H-m2, H-M5. | **Fixed** — §7.1 `blocks` row now defers to §3.2 field-for-field; roadmap Phase 1 lists the six explicitly and opens with a reconciliation gate plus an automated test. |
| **NEW-C3 / N3-R1** | `roadmap:226` still specified the aligner contract `spec:445` explicitly repudiates, and the **projection step had no owner in either document**. The roadmap is the executable artifact. | **Fixed** — Phase 6 now reads "aligner receives `spoken_text` ONLY"; a discrete projection step is added with owner and date; precedence rule added so the next contradiction resolves instead of coin-flipping. |

### Major — Jury

| ID | Finding | Disposition |
| --- | --- | --- |
| **N3-R2 / NEW-M3** | `listening_progress` defined two contradictory ways in one file; and the v3 anchor **cannot resolve to a playback time without alignment**, so resume collapses to "start of segment" on exactly the degraded paths. The v3 fix was subtractive where it needed to be additive. | **Fixed** — both anchors stored. |
| **N3-R3** | Alignment state and `words JSONB` stayed on `segments` while audio moved to renditions. Timings are computed against a *specific rendition's* audio, so a voice change destroys sync data for audio the user paid for — identical to the defect `segment_renditions` was created to fix. | **Fixed** — `align_*`, `words`, and `status` moved to `segment_renditions`. |
| **N3-R5** | Canonical pipeline line still read seven stages; README never mentioned normalization at all. | **Fixed** — eight stages in spec, roadmap, README prose, table and mermaid. |
| **N3-R6 / J-N5** | The roadmap **claimed** every item carried an owner and gating items carried dates. Two of ~120 had an owner; none had a date. | **Fixed** — false claim withdrawn explicitly; gating items now carry `(Owner · due)`. Routine items in unstarted phases deliberately carry neither. |
| **N3-R7** | `README:397` still stated the old gate. | **Fixed** |
| **N3-R11** | No rendition/voice selector on `GET /segments`; `user_id` absent from `segments`/`renditions` against an absolute RLS claim. | **Partially fixed** — selector added via `segment_set_id`; RLS-by-join is noted as the enforcement mechanism. Open. |

### Major — Halo

| ID | Finding | Disposition |
| --- | --- | --- |
| **NEW-M1** | The decisive invariant was **not evaluable**: (a) normalization is context-dependent, so checking isolated spans produces spurious mismatches on correct data — and the predictable response is to weaken the check until it catches nothing; (b) monotonic spans **reject correct normalizations** (`$5` → "five dollars" inverts order), silently costing highlighting on numeric-dense documents, i.e. textbooks. | **Fixed** — whole-text round-trip; spans must cover and not overlap, order unconstrained. |
| **NEW-M2** | The preflight quote metered display text; the provider bills spoken text. `1984` (4 chars) → "nineteen eighty-four" (20). Understated quotes land as `blocked_credits` mid-listen. | **Fixed** — quote meters `spoken_text` and reports display/spoken/inserted separately; normalization precedes the quote. |
| **NEW-M4** | `block_start_offsets[]` arity unspecified — the same criticism v3 correctly levelled at v2's manifest. | **Fixed** — one entry per ordinal including skipped blocks, with a length invariant. |
| **NEW-M5** | Gapless tiling collides with the never-cross-chapter rule; and a zero-segment document has no manifest carrier. | **Fixed** — chapters own ranges, segments tile within; document-level manifest is authoritative when there are no segments. |
| **NEW-M6** | "Only genuinely new segments are charged" had no identity mechanism. Whether a user pays $0 or $32 rested on an unwritten comparison. | **Fixed** — `segments.text_hash`. |
| **NEW-M7** | `align_reason` single-valued while the `ht` path produces two reasons at once; and no code for "we have no normalizer for this language" — the likeliest `ht` outcome. | **Fixed** — array, plus `no_normalizer`. |
| **NEW-M8** | Message catalogue had no transport, no locale selector, and is not translatable by concatenation (`reason` × `permanence` produces ungrammatical `fr`/`es`/`ht`). Tongue absent from the phase that builds it. | **Fixed** — `GET /i18n/messages`, `ui_locale` preference, keyed on the combination; Tongue added to Phase 9. |
| **NEW-M9** | `user_lexicon` had no write path — the N-5 fix was inert. | **Fixed** — `/me/lexicon`, with the re-render consequence stated. |
| **NEW-M10** | Undescribed figures and unnarratable math appeared only as document tallies, never positioned — the exact thing §9.1 argues against. | **Fixed** — `spans` generalised to disclosure spans. |
| **NEW-M11** | Neither sentinel specified: no field, value, language, or billing treatment. | **Fixed** — routed through `origin: 'inserted'` + catalogue; depended on NEW-C2. |
| **NEW-M12** | Phase 10's accessibility acceptance was a one-line stub with no AT named, no criterion, no owner — the only artifact between the build and a `PASS`. | **Fixed** — NVDA/Firefox + VoiceOver/Safari, recorded transcripts, six named criteria, zero-AA-failure bar. |

### Minor

`N3-R8` Halo phase list under-claimed in `CLAUDE.md` — **fixed**, roadmap made
authoritative · `N3-R10` README listed an answered question — **fixed** ·
`NEW-m1` `scan_quality` definition omitted reading order — **fixed** ·
`NEW-m2` roadmap never-skip list lacked the user carve-out — **fixed** ·
`NEW-m4` no pagination on the reader path — **fixed** ·
`NEW-m5` deletion cascade omitted `normalization_trace`, which contains verbatim
document text — **fixed** · `NEW-m3`, `NEW-m6`, `NEW-m7`, `NEW-m8` — **open**,
Minor.

### N3-R9 — the governance finding, and the reason this section exists

Round 2's record collapsed four findings into *"J-n7–J-n10 README corrections"*
and never defined `J-p3`, making them **unverifiable by construction**. That
violates this project's own resolve-by-ID rule, applied to the audit layer's own
output. For the record, retroactively:

| ID | What it was | Status |
| --- | --- | --- |
| `J-n7` | README claimed `assets/` holds "logo, hero image"; contents differ | Fixed — README no longer enumerates asset filenames |
| `J-n8` | README listed the stale rate card as open; it had been escalated | Fixed |
| `J-n9` | README stated `main` has no commits — self-invalidating | Fixed |
| `J-n10` | README described bare `models/` as ignored; the fix anchors it | Fixed |
| `J-p3` | Roadmap marked the README task `[ ]` though it exists | Open — Polish |

**Rule going forward: every finding gets a one-line definition in the record,
even Minors.** A finding with no written definition cannot be re-audited.

## Rule 8 disclosure

`J-C1`, `J-C10`, `J-C12`, `J-M9`, `J-N1`, `J-N2`, `J-N5`, `J-N7`, `N3-R9` and
this round's process findings concern the audit layer grading its own
scaffolding. `jury.md:83` routes these to BigBrain or Jo. Flagged, not
self-actioned.

## Preserve through the next revision

Both reviewers asked that these survive untouched:

- `spec` §7.3's honest statement of the re-segmentation billing cost — it states
  a cost the product would rather not state.
- The `reading_order_conf` rationale: *"v2 diagnosed the disease and added a
  thermometer."*
- The behavioural definition of `degraded` vs `unavailable`.
- 99.5% — a real number attached to a severity claim.
- `research/`'s self-demotion of its own Tier A evidence. Jury: *"the single
  most trustworthy paragraph in the whole set. Do not let anyone tidy that
  honesty away."*

## Unresolvable before implementation

Halo cannot issue `PASS` at any design gate — its rules require a keyboard pass
and a screen-reader transcript, and no artifact exists to run NVDA against. The
question it answers instead: **does the design foreclose or enable accessible
clients?** R1: foreclosed. R2: enabled except in three dimensions. R3: enabled
except NEW-C2, now closed.
