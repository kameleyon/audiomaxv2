# Audit Record — Founding Documents, Round 9

- **Date:** 2026-08-08 · **Subject:** spec v8, roadmap v8, `README.md`, `CLAUDE.md`, `tools/doc-check.mjs`
- **Reviewers:** Jury, Halo — read-only · **Response:** spec/roadmap **v9**
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 30/30
  *(run against round 9; `ROUNDS_ON_DISK` is live, so this claim expires with
  the next audit record — bump both rosters in the same change, N9-M1.)*

## Verdicts

| Reviewer | R6 | R7 | R8 | R9 |
| --- | --- | --- | --- | --- |
| **Jury** | 0B/5C | 0B/3C | 0B/3C | **0B/4C/10M** |
| **Halo** | 0B/9C | 0B/11C | 0B/6C | **0B/7C/11M** |

Jury composite **3.6 → 3.4.**

## The finding that matters more than the count

Both reviewers converged on the same diagnosis, and it is the one I had missed
for nine rounds. Jury:

> *Every one of these was created by a v8 remedy, and every one was created the
> same way: **the corrective sentence was inserted and the sentence it corrects
> was left standing.** Nine rounds of answering findings by *adding* argument.
> §6.2 is now ~250 lines of interleaved rule and litigation… **The document is
> at the point where the remedy for the next finding is deletion, not
> addition.**

The proof is the `\p{No}` rule. v8 wrote *"`\p{No}` is the single exception and
is **stated once, here**"* — and then stated it again two bullets down in the
excluding form, which the roadmap copied. A sentence claiming the rule appears
once, falsified by the next paragraph of the same document.

**v9 is the first revision that deletes.** Superseded text removed rather than
argued against: the `\p{N}` floor at spec:761 and roadmap:371, the
"genuinely ambiguous… that is what `render_specific` is for" paragraph that
contradicted the derivation table fifteen lines above it, and the "stated once,
here" claim itself.

## The gate was red, and both headers said it was green

`node tools/doc-check.mjs` → **exit 1**, two `SD-ROSTER` findings, while spec:8
and roadmap:8 asserted exit 0. Cause: writing the round-8 record bumped
`ROUNDS_ON_DISK` to 8 and both rosters still said 7.

This is the live-count guard working exactly as designed — it caught its own
author unprompted — and it is also why the header must record *the round it was
run against*. Fixed first, before anything else, on Halo's instruction:
*"Fix that first, or nothing in this project can be verified at all."*

## Criticals closed

| ID | Finding | v9 |
| --- | --- | --- |
| **N9-C1 (Jury)** | At the **default** `content_narration: full`, a table is spoken **twice** — once as flattened `text` forced into `segments.text` by the never-skip rule, once as linearization. v8's exclusion was scoped to the *suppressed* branch only, leaving the default unsatisfiable | `table` and `math` blocks are excluded from `segments.text` **unconditionally**; narrated only via linearization or withheld. Scheduled in Phase 4, which v8 left empty (N9-M9) |
| **N9-C2 (Jury)** | `align_blocker` — the entire N8-C3 remedy — existed in **one prose sentence**: not in §7.2's column list, not in the §8.2 quote payload it promised, and adding it correctly made `REV` fire | In the `segments` run, in the quote payload with a worked example, allowlisted |
| **N9-C3 (Jury)** | `normalization_opaque` filed as voice-independent, but it is a **provider** fact and §3.5 routes by voice — so it is opaque in one rendition and not another. v8 forbade re-derivation, which would have quoted `align_blocker: null`, taken the money, and disclosed after the render | Split: `segments.align_blocker` for the genuinely text-level reasons, `segment_renditions.align_blocker` from a **pre-quote provider check**, both in the quote |
| **N9-C4 (Jury)** | The `\p{No}` contradiction, textually different and substantively identical to N8-C1 | Deleted at all three sites; a `wholeDoc` guard now fails on `\p{N}` anywhere |
| **N9-C6 (Halo)** | `origin: 'dropped'` had **no `reason` field**, so stage 4.5 could not distinguish a dropped `¹` from a dropped quotation mark and the `dropped_marker` span had no upstream record. And the §9.1 example collapsed **18 markers across 52 blocks into one span, one offset** — the document-level tally §9.1 exists to forbid | `reason` added to the variant; one span per marker at its own offset |

## Tool coverage, measured rather than asserted

Jury measured `PLACE` at **7 of 11** declared placements — blind to any column
§7 writes with a type suffix (`words JSONB`, `align_reason[]`), so `words` could
be moved onto the RLS-exempt `voices` catalogue and the gate stayed green. And
`S2R` harvested only §7 and §9, so `align_blocker` — the Critical that motivated
the class — was invisible to the guard built for the class.

Both widened. The `S2R` widening immediately found **six more** real gaps
including `align_conf_threshold` (Halo N9-M4) and `mean_tokens_per_group`
(Halo N9-M6, R5-C3's anti-weakening instrument). All six now scheduled.

## Still open

`N9-M8` the `kind` ↔ `reason` binding table · `N9-M10` `SCHEMA_ONLY` is a
100-entry hand-maintained allowlist, which is the "remember the site" mechanism
the tool exists to replace · Halo `N9-M2` the catalogue budget counts align keys
only while defining a scope of ~180 strings · Halo `N9-M3` `toc_filler` ·
Halo `N9-M8` `positional`.

Jury's structural recommendation, recorded: **guards need a coverage number, not
a pass/fail.** `PLACE` should print "enforces 7 of 11" and go red when the ratio
drops. Nobody wrote the `PLACE` gap — it emerged from a reasonable pattern
meeting the document's actual formatting.

## Fifth consecutive round, both reviewers

**Run Phase 0's spikes.** All six now dated 2026-08-14 with owners, including
SPIKE B2, which gates word sync and was the last one undated.
