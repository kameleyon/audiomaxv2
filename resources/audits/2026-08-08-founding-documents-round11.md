# Audit Record — Founding Documents, Round 11

- **Date:** 2026-08-08 · **Subject:** spec v10, roadmap v10, `README.md`, `CLAUDE.md`, `tools/doc-check.mjs`
- **Reviewers:** Jury, Halo — read-only · **Response:** spec/roadmap **v11**
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → **43/43**
  *(run against round 11)*

## Verdicts

| Reviewer | R8 | R9 | R10 | R11 |
| --- | --- | --- | --- | --- |
| **Jury** | 0B/3C | 0B/4C | 0B/2C | **0B/2C/7M** |
| **Halo** | 0B/6C | 0B/7C | 0B/5C | **0B/6C/11M** |

**Both round-10 Criticals verified closed** — Jury checked all four parts of
J10-C1 by hand and by execution, and read §6.3 end to end for J10-C2. Jury
composite 3.6 → 3.5; instrumentation **3.6 → 3.9, its highest.**

## The credit, then the correction

Halo, on the seven acceptance mutations it had supplied in round 9 and seen read
rather than executed for three rounds:

> **7 of 7 go red. All seven. None passes.** *That is the first unqualified
> credit I have given this instrumentation.*

It then authored **eight fresh mutations with different literals** so a guard
that had memorised the installed specimen would go green. All eight fired,
including a *rename* rather than a deletion. Jury independently attacked the
three new guards and defeated one.

Then Halo ran ten more deletions at the seams, and **nine passed silently**:

> *38/38 measures the guards that exist. It does not yet measure the surface
> that matters.*
>
> **Every one of the 15 `BANNED` guards protects a sentence that was
> *previously* wrong. Not one protects a sentence that is currently right and
> load-bearing. That is a guard set shaped by history rather than by risk.**

That is the finding of the round. I had built a regression suite and called it a
specification test. *"Never cross a language boundary"* — the invariant stopping
a Creole passage being spoken by a French voice — could be **deleted** at a green
gate. R5-C7's no-cross-language-fallback rule could be **inverted** to its
repudiated form: clean.

## Response

**`INVARIANTS`** — a new guard class that asserts a load-bearing sentence is
**present**, the half that never existed. Five to start, each with a trial:
the §8.2 `align_blocker` disclosure, the language-boundary rule, the
no-cross-language-fallback rule, the `block_start_offsets` length invariant, and
the `normalization_opaque` permanence classification.

**§8 was sectioned by nothing.** The payment section. The entire pre-payment
disclosure block could be deleted with the gate clean. And the harvest required
a **closing backtick**, so `` `progress_resolution: exact｜block_approximate` ``
was invisible — Halo: *"four disclosure channels for blind users fell through a
punctuation mark."* All four now harvested and scheduled:
`word_sync_available_segments`, `progress_resolution`,
`blocked_language_unsupported`, `spoken_chars`.

## Criticals closed

| ID | Finding | v11 |
| --- | --- | --- |
| **J11-C1** | `normalization_opaque` classified **`permanent`** by the same section that proves it is a *provider* fact and that §3.5 routes by voice. A blind user on a Lemonfox voice was told word sync was gone for good when switching to a Fish voice would restore it — the headline feature withdrawn **and** the remedy hidden, through the field whose purpose is to surface remedies. Phase 10's AT criterion would have certified the wrong permanence being announced correctly | Reclassified `render_specific`, **and guarded** by `INV-OPAQUE-PERM` |
| **J11-C2** | Phase 4.5 still scheduled stage 4.5 setting the provider fact — 200 lines below the schema item J10-C1 corrected. Stage 4.5 runs before any voice exists | Deleted. The authoritative pre-quote item already existed with an owner and a date |
| **N10-C3 (Halo)** | No non-committing quote route: the disclosure that must arrive *before* payment was delivered by the call that takes it | `GET /documents/:id/quote` + `quote_etag`, `409 quote_changed` |
| **N10-C4 (Halo)** | `block_start_offsets` had no arity rule for an excluded-not-skipped block; spec said two terms, roadmap said three | Three-term form in both; excluded blocks carry the next retained character's offset |
| **N10-C5 (Halo)** | `disclosure_verbosity` **inert** — `full`, `positional` and `off` produced byte-identical tuple sets, so a user who rendered on `off` and later wanted sentinels was told the audio was current. Third consecutive round | `SPOKEN` added as the fourth tuple element — the emission decision the heading always claimed was keyed and the tuple had no field for |
| **N11-C3 (Halo)** | The roadmap's `\p{No}` rule was blanket, against the spec's fraction carve-out: *"add ½ cup"* → *"add cup"*, announced as a footnote marker | Carve-out and discriminator stated in the roadmap |

Majors closed: `J11-M1` spec header claimed it answered round 8 with both
trajectories two rounds stale · `J11-M2` **`segment_renditions.align_blocker`
had no guard at all** — Jury proved it by execution; `COL` is now `(table,
column)` pairs · `J11-M3` README a revision behind for the third round.

## Jury's terms

> *Fix the two lines. Re-run. Then this is `PASS WITH FIXES` and you commit.
> I will hold to that again — and if I find a third copy next round, the honest
> conclusion won't be that the fixes are bad, it will be that this remedy needs
> a guard instead of another round of reading.*

Both lines are fixed **and** the remedy now has a guard, so a fifth leak fails
the build rather than waiting for a reviewer.

## Ninth consecutive round, both reviewers

**Run SPIKE B2.** Jury: *"We have now spent three audit rounds fixing
documentation about the behaviour of a setting we have never once tested. One
afternoon of API calls would settle it, and would probably delete half of §6.3."*
