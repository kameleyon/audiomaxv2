# Audit Record — Founding Documents, Round 23

- **Date:** 2026-08-08 · **Subject:** the staged commit set, re-verified after round 22
- **Reviewer:** Jury · **Response:** v23
- **Authorship provenance:** ruling by Jury; **transcribed by the audited party.** Recorded because Rule 8 forbids grading one's own work, and a record of a verdict written by the party ruled on needs that stated, not assumed.

## Verdict

**`FAIL` — 0 Blocker · 1 Critical · 5 Major · 2 Minor.**

**J22-C1 and J22-C2 both CLOSED by execution.** Index and worktree reconciled;
all three blobs Jury proved open at round 22 genuinely repaired; 22 records on
disk; `SD-UNWRITTEN` unit-tested in memory against the live README and firing.

## The Critical, and its cause

**J23-C1 — the `ht` scope removal was a blind string substitution, and this
round's fix is what made it false.**

`README:399-404`, rewritten in round 22, established the sharp definition: an
unsupported language *"is refused outright at the §3.5 no-route row, **produces
no audio at all**."* Twelve lines above it, in a row marked **CLOSED** — which
reads as settled fact — sat:

> *an unsupported language **is served natively by a Gemini TTS model, reached
> via OpenRouter**… an unsupported language is **not** a launch blocker.*

The identical false promise as `H21-C2`, graded Critical and repaired that same
round, **surviving twelve lines up in the same file, in the same table.** Eight
further sites: `README:337` put it inside the **privacy disclosure** constraint,
naming processors for a path the design says does not exist.

> *Sharpening what "unsupported" means is what turned the sentences nearby into
> false ones.*

## The three unasked changes — Jury's ruling

**`[STAGED]` check — in scope**, the direct mechanism fix for the round-22 root
cause. **And defective two ways:** documented *"advisory by design"* while
`process.exit(findings.length ? 1 : 0)` treats every finding as blocking — *"a
false self-description inside the section that exists to check what the artifacts
claim about this tool"* — and its filter missed `spike-a-results.json`, **one of
the three blobs it was built for**.

**`SD-ROSTER` scoping — in scope, and the right remedy.** Jury had named
mis-citation as the guard's cheapest fix; restricting completeness to documents
that *maintain* a roster is correct, not blinding. Caution: implemented as a
mid-loop `continue`, so any check appended after it is silently disabled for 8 of
12 documents.

**The `.wav` un-staging — out of scope, and net-negative. This is the pattern.**

> *"Regenerable for ~$0.001" is true and is **not the same claim as
> "reproducible."** TTS output is not deterministic, so a re-run against a frozen
> matcher must run on new audio. `J22-M1` was "audio provenance covers 1 of 3
> languages"; it is still 1 of 3, and the other two are now unrecoverable from
> the repository.*
>
> *It is not laziness; it is **tidying**, and tidying is how evidence goes
> missing.*

## Rule 8 on the round-22 record

Faithful on content — *"and against the writer's interest, which is the
strongest evidence it was written honestly"* — with two dating defects: a
reconciliation line true at write time and not at ruling time, and a subject line
naming *"the staged commit set"* when the Critical was that the staged set did
not contain the work. Jury required **authorship provenance on every record
written this way**, which this record carries.

## `SD-UNWRITTEN`, attacked again

Jury proved it blind on the **severity axis** after round 22 fixed the **prefix
axis**: `[JNHR] × [CMm]` could not see `H23-B1` — *"a guard built to ensure every
cited finding has a written record cannot see a citation of a **Blocker**"* — nor
single-digit rounds (`N8-M8`, `R5-C6`).

> *This is the pattern inside the guard written to close the pattern.*
