# Audit Record — Founding Documents, Round 12

- **Date:** 2026-08-08 · **Subject:** spec v11, roadmap v11, `README.md`, `CLAUDE.md`, `tools/doc-check.mjs`
- **Reviewers:** Jury, Halo — read-only · **Response:** spec/roadmap **v12**
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → **43/43**
  — both re-run independently by *both* reviewers, not accepted on claim

## Verdicts

| Reviewer | R9 | R10 | R11 | R12 |
| --- | --- | --- | --- | --- |
| **Jury** | 0B/4C | 0B/2C | 0B/2C/7M | **0B/4C/11M — `FAIL`** *(see below)* |
| **Halo** | 0B/7C | 0B/5C | 0B/6C/11M | **0B/7C/14M** |

## The gate opened and was closed again. Read this first.

Jury initially returned **`PASS WITH FIXES`** — 0 Critical, 8 Major — and on that
verdict the founding documents were committed and pushed (`e06006e`).

**That verdict was issued on incomplete input, and it is vacated.** Jury and Halo
were dispatched *in parallel*, so Jury — whose role under `CLAUDE.md` is
"commit gate, **audit synthesis**" — ruled without ever seeing Halo's seven
Criticals. That is a dispatch defect by the coordinator, not a reviewer error.
Re-ruled on synthesis, Jury sustained four of Halo's seven by its own rubric and
**withdrew both the verdict and the score it had awarded:**

> *I closed a Critical last round on the argument that `normalization_opaque` is
> `render_specific` because switching to a Fish voice restores word sync. Every
> remedy this design offers a degraded blind user is "choose a different voice,"
> and no client can present the choice. I corrected a label and called the chain
> end-to-end. **The chain terminates at a remedy with no route.** I scored
> "Service to the blind/low-vision population: 4.0 — first time" on that chain.
> That score was wrong and I am withdrawing it.*

The push was reverted on the owner's standing instruction — **nothing failing
ships, without exception.** Remote `main` was force-replaced with an empty
initial commit; all files remain on disk. Jury argued the commit should stand on
the grounds that it was the root commit and reverting it would erase the README,
the working agreement, `doc-check.mjs` and all twelve audit records from history.
**The owner's rule governs and was applied.** The trail is committed when the
gate is genuinely open.

## The four sustained Criticals

| ID | Defect |
| --- | --- |
| **N12-C3** | **No route returns the `voices` catalogue** while four routes require a `voice_id`. Every degradation remedy in the design is unreachable by any client. Jury: *"the most serious finding in twelve rounds"* — and the one that is **not** self-inflicted |
| **N12-C2** | The quote discloses sync loss and **not speech loss**. A mixed `fr`/`ht` document can contain segments producing no audio at all; the user learns it after paying, as audio stopping |
| **N12-C1** | `GET /quote` inherits `// 402 if insufficient` from the payload it returns — refusing precisely the zero-balance user for whom the disclosure decides everything |
| **N12-C5** | `disclosure_summary` is chapter-scoped audio under a segment-scoped fingerprint; a stale summary is announced as current |

Downgraded to Major by Jury under Rule 7, disagreement recorded rather than
split: `N12-C4` (`409 quote_changed` untranslated), `N12-C6` (trailing-run
`char_offset`), `N12-C7` (`INVARIANTS` are spec-only — Jury's own `J12-M6`,
found independently before it saw Halo's report).

Both round-11 Criticals *were* verified closed by reading and by execution, and
Jury hunted the whole `normalization_opaque` chain across six artifacts: **no
fifth site exists.** That part of the round holds.

## The finding of the round, and it is on me

**Five of Halo's seven Criticals are defects in v11's own fixes.** They did not
exist in v10. Halo:

> *A disclosure was built, and the seam it sits in was not examined. Every one
> of those is at the edge of the thing that was fixed.*

| New Critical | Created by |
| --- | --- |
| `N12-C1` the non-committing quote route inherits `402 if insufficient` | v11's `GET /quote` |
| `N12-C2` the quote discloses sync loss, not speech loss | v11's `GET /quote` |
| `N12-C4` `409 quote_changed` has no error code and no catalogue string | v11's `quote_etag` |
| `N12-C5` `disclosure_summary` is chapter-scoped audio under a segment-scoped fingerprint | v11's `SPOKEN` tuple element |
| `N12-C7` all five `INVARIANTS` are `doc: 'spec'`; the roadmap has zero | v11's `INVARIANTS` |

And the sharper version, from Jury: **the guard built to stop the recurrence
does not stop it.** Round 11's terms were *"this remedy needs a guard instead of
another round of reading."* `INV-OPAQUE-PERM` was written. Jury attacked it by
adding the *wrong* claim to four separate files, one at a time — **green every
time.** The guard asserts the good sentence is **present**; every real leak in
rounds 9, 10 and 11 was a **bad copy added elsewhere**. It guards the one thing
that has never happened. → `J12-M1`.

Then the pattern reproduced in miniature inside the round that fixes it: the
spec header was corrected to name round 11 and **the roadmap header was not** —
it read "round 11" over round 10's numbers. Fixed in the sibling, not in the
pair. That is the founding defect class of this entire audit. → `J12-M2`.

## What the instrumentation proved

Halo re-ran its ten round-11 seam deletions. **Six of ten now go red** — every
red an `INVARIANTS` member, including the two the round-11 record named. Then it
authored eight fresh mutations the author could not have anticipated: **seven of
eight passed at a clean gate**, and three of those seven were deletions from the
**roadmap** of sentences the spec's `INVARIANTS` protect.

> *`S2R` — the widest guard in the tool — cannot detect the deletion of anything
> from the spec. It detects only un-scheduling. `INVARIANTS` is the only guard
> class that detects deletion, it holds five sentences, and it holds them in one
> document.*

Jury independently confirmed the widened `COL` — its round-11 demonstration now
fires on **both** halves of `align_blocker` — and found two `segment_renditions`
columns still absent from `REQUIRED_COLS`.

## Genuinely closed

| ID | v12 |
| --- | --- |
| **J11-C1** `normalization_opaque` mis-classified `permanent` | Closed. Whole chain re-read across six artifacts; **no fifth site** |
| **J11-C2** Phase 4.5 sets a provider fact | Closed. Item deleted, routed to the pre-quote check |
| **N10-C5** `disclosure_verbosity` inert for three rounds | **Closed.** `SPOKEN` moves the hash; Halo worked `full` vs `off` for an undescribed figure and confirmed the tuples now differ. *"Fixed at the right layer rather than by widening the hash."* |
| **J11-M2** `segment_renditions.align_blocker` unguarded | Closed by `(table, column)` pairs |
| **J11-M1 / J11-M3 / J12-M2 / J12-M3** self-description drift | Corrected in v12 — both headers, README revision, phase count |

## The one finding that is not self-inflicted

**`N12-C3` — no route returns the `voices` catalogue**, while `GET /quote`,
`POST /render`, `GET /segments` and `GET /documents/:id` all *require* a
`voice_id`. J11-C1 was closed last round on the argument that
`normalization_opaque` is `render_specific` *because switching to a Fish voice
restores word sync*. `voice_substituted` and `low_confidence` are likewise
`render_specific`. **Every remedy this design offers a blind user on a degraded
path is "choose a different voice", and no client can present the choice** — nor
filter it by `lang`, which is exactly what an `ht` user needs.

> *Eleven rounds of guards missed it because guards check identifiers, and no
> identifier is missing.*

## Standing, twelfth consecutive round, both reviewers

**Run SPIKE B2.** Three of Halo's seven Criticals are arguments about a provider
capability nobody has measured. Jury: *"we have never once called the API."*

The round count is the answer to a choice, not an accident: twelve rounds of
fixing prose with prose, on two 1,500-line documents, **with no version control
and therefore no diffs.** This record accompanies the first commit, which makes
every subsequent change reviewable as a diff rather than as a re-read — and that
is itself a remedy for the defect class above.

**Next round is an experiment, not a revision.**
