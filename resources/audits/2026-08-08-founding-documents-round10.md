# Audit Record — Founding Documents, Round 10

- **Date:** 2026-08-08 · **Subject:** spec v9, roadmap v9, `README.md`, `CLAUDE.md`, `tools/doc-check.mjs`
- **Reviewers:** Jury, Halo — read-only · **Response:** spec/roadmap **v10**
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → **38/38**,
  including all seven of Halo's round-9 acceptance mutations *(run against round 10)*

## Verdicts

| Reviewer | R7 | R8 | R9 | R10 |
| --- | --- | --- | --- | --- |
| **Jury** | 0B/3C | 0B/3C | 0B/4C | **0B/2C/10M** |
| **Halo** | 0B/11C | 0B/6C | 0B/7C | **0B/5C/9M** |

Jury composite **3.4 → 3.6.** Verification instrumentation **4.0 — the highest
it has been**, earned: `PLACE` went 7/11 → **11/11** under Jury's own attack,
`S2R` gained §6 with **zero substring false-greens**, and the live roster caught
its own author.

## The finding of the round, and it is on me

Halo, having supplied seven concrete acceptance mutations in round 9:

> **2 of 7 go red.** *Three rounds running I have handed over a specimen set,
> and three rounds running it has been read rather than executed. A specimen
> that lives in an audit report protects nothing; a specimen that lives in
> `results.push` cannot be forgotten and fails the build.*

Correct. I treated a test suite as prose. **All seven are now first-class
trials**, and making them go red forced the four `S2R` repairs I had agreed to
and not made:

| Repair | Forced by |
| --- | --- |
| Word-boundary matching | `table_cell` was satisfied by `table_cell_header` |
| **Phase** scope, not document scope | `content_narration` could leave the phase that builds it |
| Full union harvest | `chapter_announcement` and `toc_filler` sat mid-line and were invisible |
| Producer-signature parity | the roadmap's `utter(` may not drift from the spec's |
| New `COL` guard | a declared `segments` column could silently vanish |
| New `KIND` guard | a §9.1 span kind could be renamed and lose a disclosure channel |

## Did intra-spec contradictions fall?

Jury counted: **8 → 7. No.** But the composition is the answer:

> *The deletion strategy worked where it was applied. Every contradiction v9
> deleted is gone and stayed gone… four sites, four closures, zero regressions.
> That is the first round in ten where a remedy class closed completely.*

The insert-and-leave-standing class fell from three instances to **one** — and
that one was inside a Critical remedy, which is why it still blocked.

## The two Criticals

**J10-C1 — the N9-C3 remedy reached spec prose and nothing else.** `normalization_opaque`
is a **provider** fact (§3.5 routes by voice: Fish vs Lemonfox), not a text
fact. v9 corrected the spec and left `roadmap:169` scheduling the repudiated
per-segment design, `§7.2a` without the column, and no build item for the
pre-quote provider check. Under `CLAUDE.md:112-115` that is Critical by the
project's own rule — the roadmap is what gets built. And the tool **fired
against the correct fix**, because `PLACEMENT` still encoded the round-8
position.

Closed: `normalization_opaque` removed from the segment column in the roadmap;
`segment_renditions.align_blocker` added to §7.2a and to Phase 1; the
**pre-quote `(segment, provider)` check** scheduled with owner and date; the
`PLACEMENT` row retired with the reason recorded, since the column now
legitimately lives on both tables.

**J10-C2 — the paragraph ended on the sentence it overturns.** Five lines after
*"the rendition is set by the pre-quote provider check"* stood *"Renditions
inherit it; they never re-derive it"* — the exact v8 rule N9-C3 was raised
against. An engineer reading top to bottom ended on the wrong one, and the wrong
one bills the user before disclosing.

Closed by **deletion**, per round 9's prescription: both that sentence and the
v7-history paragraph above it are gone.

## Also closed

`toc_filler` (Halo N9-M3) scheduled · README version and self-test count
corrected — the only file a stranger can read said v8 and 28 · the allowlist now
exempts `Block.kind` members and nested payload fields **as a class with a
stated reason**, answering Jury's M3 that judgement was *"stored in a list with
no rationale field."*

## Open, tracked with owners and dates

Jury M1 `PLACE` needs a coverage number rather than pass/fail, and is blind to
`listening_progress`'s `+`-delimited run · M2 the `kind`↔`reason` binding is
still six examples, not a table · M3 150 allowlist entries · M4
`block_start_offsets` undefined for excluded-not-skipped blocks · M5 §9.1's
`null` rule for `start_ms` is falsified by its own example · M8 `dropped.reason`
has four values and no mapping to `SpanReason` · M9 `display_char_count` no
longer means what §8.2's annotation says · M10 the `N9-C4` guard watches the
spec while the defect was copied into the roadmap.

Halo: `positional` has no producer · catalogue budget 68 against a declared
scope of ~180 · `table_cell` cannot be highlighted (N9-C3, its standing
foreclosure) · no non-committing quote route.

## Jury's assessment of where this stands

> *Delete one paragraph, correct one line in the build checklist, add two build
> tasks with an owner and a date, add one column name to one list, and fix two
> numbers in the README… the moment those two Criticals are closed, this goes to
> `PASS WITH FIXES` and you can commit.*

All five are done. Sixth consecutive round, both reviewers: **run Phase 0's
spikes.** SPIKE B2 gates `normalization_opaque`, the subject of both Criticals
this round — a value nobody has measured.
