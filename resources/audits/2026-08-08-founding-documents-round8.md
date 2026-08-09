# Audit Record — Founding Documents, Round 8

- **Date:** 2026-08-08 · **Subject:** spec v7, roadmap v7, `README.md`, `CLAUDE.md`, `tools/doc-check.mjs`
- **Reviewers:** Jury, Halo — read-only · **Response:** spec/roadmap **v8**
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 28/28
- **ID namespace:** round-7 IDs collided between reviewers (`N7-C1`, `N7-C3`
  each denote two findings). Disambiguated below as `(Jury)` / `(Halo)`; future
  rounds namespace at issue (N8-M9).

## Verdicts

| Reviewer | R5 | R6 | R7 | R8 |
| --- | --- | --- | --- | --- |
| **Jury** | 0B/4C | 0B/5C | 0B/3C | **0B/3C/10M** |
| **Halo** | 0B/8C | 0B/9C | 0B/11C | **0B/6C/9M** |

Jury composite **3.5 → 3.6 — the decline stops.** Tooling **2.6 → 4.3**:
*"Last round the self-test was the defect. This round it is the best artifact in
the project."* Halo Criticals **11 → 6**, its first real decline in four rounds.

Countervailing, and it is the finding that matters most this round: Jury's
*internal consistency within the spec* fell to a new low of **3.2** — *"for the
first time the spec is contradicting itself more than it contradicts the
roadmap."* Eight rounds of answering findings by **adding** argument has made
the document harder to build from.

## What the reviewers proved by execution

Both loaded the shipped `runChecks` and drove it against hand-built mutations
rather than reading the code.

| Claim | Reality |
| --- | --- |
| "Bidirectional … covers all of §7", ticked `[x]` | Moving `align_status` onto `segments`, and `text_hash` onto the global `voices` catalogue, produced **0 findings**. Whole-§7 membership is table-agnostic; no field↔table binding existed |
| `--self-test` "proves each guard fires" | 9 of 36 check IDs had no mutation, `SD-ENUM` matched **zero** occurrences of the live corpus, and the `CTL` hash branch was unreachable from every trial |
| `MIG-H` guards the missing-column finding | Scoped to the whole roadmap, not Phase 1 — strip the columns from Phase 1, leave one mention elsewhere, **0 findings**. The guard written for the finding did not test the finding |
| Structural mutation is "below threshold, not deletion" | True for 2 of 7 guards; the other five have `min: 1`, where below-threshold **is** deletion |

Halo additionally reproduced eight round-7 defects in the live documents and
watched every one pass a green gate — *"the self-test now proves the guards are
alive. It cannot prove there is a guard."*

## Response: guard the class, not the instance

Halo's one thing was *"you now have a specimen for every guard — build a guard
for every remedy"*, noting seven of the eight missed defects shared one shape:
**the fix is in the spec and the roadmap does not know about it.**

**`S2R`** — every identifier the spec introduces (union members, §7 columns,
§9 error codes, span kinds) must appear in a roadmap item. It found **31** on
its first run, including every one Halo had located by hand. All 31 now have
build items with owners and dates.

**`PLACE`** — column↔table binding, the property `CLAUDE.md` names first and
three artifacts falsely claimed. It caught a false positive on its first run
(a *reference* to `duration_ms` in explanatory prose read as a declaration), so
declarations now require list context. Then the self-test caught that the guard
had **zero data through two separate bugs** — a `$`-under-`/m` lookahead that
captured empty bodies, and a `\n**` cut that truncated the wrapped column run.
It would have reported clean forever.

Also: `MIG-H` rescoped to Phase 1 · trial matcher exact-ID only (`REV` was
passing on `SD-REV`) · union members harvested from every ts block, fixing an
overlapping-match bug that hid `table_cell_header` · `SD-ENUM` now catches the
"every" evasion that emptied it · `ROUNDS_ON_DISK` counted from the filesystem
so the roster guard cannot pin itself stale · `SD-ROSTER` reads the roadmap's
filename list, which the range form structurally could not see.

## Product Criticals closed

| ID | Finding | v8 |
| --- | --- | --- |
| **N8-C1 (Jury)** | §6.2 forbade dropping `\p{N}` in one bullet and required dropping `\p{No}` three bullets later — a contradiction inside the section defining the floor, and the roadmap implemented only the forbidding half | Floor restated once over `\p{L}`/`\p{Nd}`/`\p{Nl}`; `\p{No}` drops **only** with a disclosure span; both halves in the roadmap |
| **N8-C1 (Halo)** | `dropped_marker` had no `kind` that admits it, so a client filtering on `kind` lost it — and the marker is the only channel telling a listener a footnote exists | `kind: dropped` added; worked example in §9.1 |
| **N8-C2 (Jury)** | Wrong-table placement undetectable | `PLACE` check, self-tested |
| **N8-C2 (Halo)** | `SpanReason`, `dropped_marker`, `suppressed_narration` in no roadmap item — the N7-C3/N7-C4 remedies unbuildable as scheduled | Producers scheduled in Phase 4.5 with owner and date |
| **N8-C3 (Jury)** | Stage 4.5 wrote `align_status`/`align_reason` to a row Phase 5 creates. Both conditions are **voice-independent and knowable before a character reaches a provider**, so a blind user paid for a full render to learn word sync was never going to work | `segments.align_blocker`, set at 4.5 and **reported in the preflight quote** |
| **N8-C3 (Halo)** | NFC on `user_lexicon.surface_form` spec-only | Phase 1 item, dated |
| **N8-C4** | The catalogue key gained `align_status` and the count stayed 15 | **17 keys, 68 strings**; roadmap item updated |
| **N8-C5** | `disclosure_fingerprint` keyed on `InsertedReason`, so after `suppressed_narration` moved out, content suppression became invisible to the hash — a header-less table hashes identically under `summary` and `full` | Keyed on `SpanReason`, covering emitted *and* suppressed |
| **N8-C6** | The table narration contract and §6.2's coverage invariants were jointly unsatisfiable — a table body could be neither a `display` nor a `dropped` span | Suppressed blocks are excluded from `segments.text`, which now contains only what is spoken |

Majors closed: `N8-M1` rosters · `N8-M2` headers substantively stale ·
`N8-M3` catalogue arithmetic · `N8-M4` `low_confidence` derived two ways ·
`N8-M5` `transcript_mismatch` mis-classed `render_specific` when it never
touches audio · `N8-M6` trial false-green · `N8-M7` three spellings of
`figure_no_description` · `N8-M8` narrated math and table cell values had no
`InsertedReason` · `N8-M9` ID collision · `N8-M10` coverage over-claim ·
`N8-m1` mutation tautology · `N8-m3` README staleness · `N8-m4` undated spikes.

## Both reviewers, fourth consecutive round

**Run Phase 0's spikes.** Jury: *"You are paying for eight rounds of audit on a
design whose riskiest assumptions have never been touched by a real system."*
Now dated 2026-08-14 with owners. Not blocked by any finding.
