# Audit Record — SPIKE A Accessibility, Round 35 (Halo, Rule 6 re-run)

- **Date:** 2026-08-11 · **Subject:** the Rule 6 re-run of round 34's foreclosure — spec §6.1/§6.3/§7.1a, `ADR-0006`, `ADR-0001`, `docs/glossary.md`, `README.md`, roadmap, `20260810000200_align_residue.sql`, `worker/src/normalize/`, `tools/doc-check.mjs`
- **Reviewer:** Halo · **Prior:** round 34 (`FORECLOSES`, 2 Critical)
- **Authorship provenance:** ruling by Halo; **transcribed by the audited party.** Halo verified the round-34 transcription itself before ruling and found it faithful *"including the ones that cost the author (`H34-m2`), transcribed against the transcriber's own interest."*

## Verdict

**`FORECLOSURE LIFTED` — 0 Blocker · 0 Critical · 4 Major · 2 Minor.**

> *Both round-34 Criticals are CLOSED. **The commit is unblocked.** The Majors
> below do not gate under `CLAUDE.md` and every one of them is a
> documentation-integrity defect, not a disclosure defect. I say that first
> because I foreclosed and only I can lift it, and I will not make the lift
> conditional on findings my own rubric rates Major.*

*(The `CLAUDE.md` gate is **Jury's**. Halo lifting its foreclosure removes the
accessibility block; it does not authorise a commit.)*

## Check 1 — Halo's ruling on its own criterion

`grep -F "not evaluable with the references" resources/specs/` → **1 hit.**
**RULING: the ledger quotation SATISFIES the check.** Three reasons, the third
decisive: **(a)** the hit is a *disposition* whose grammatical subject is *"this
text was deleted"* — `J31-m1`'s quoting-vs-defect distinction; **(b)** §6.1 is
genuinely repaired, verified by reading the section, not the grep; **(c)** *"the
repair explains **why**, and that is what converts a deletion into a closure."*

> *"**This section already defines the reference, in the words immediately
> above** … local three-point neighbour interpolation … **The old prescription
> was not too expensive; it was measuring the wrong thing to begin with.**"*

Halo verified the claim rather than accepting it — `contract.ts:89` defines
`localDriftMs`, called at `:112` over `(prev, cur, next)`. *"That is the correct
answer to my finding and it is **a better answer than the one I asked for**."*
The roadmap twin was corrected too, findable only by grepping the claim.

**Check 2** — `resync` now returns an **enum value**, a type comment defining it,
a **classification**, §6.3's row, and three build items. *"A disclosure, not a
figure."*

## `H34-C1` · `H34-C2` · `H26-C2` — all CLOSED

**`H34-C2` closes on RECOGNITION**, and Halo grounds that in its own filing:
*"the defect I filed was recognition, not persistence."* All four homes it said
were empty are filled — enum, spec, catalogue (8→9 causes, 20→22 keys, 60→66
strings, reconciled across spec §9, roadmap, `ADR-0002`, `ADR-0005` and
`tests/a11y/contract.mjs`, which Halo **ran**: rc=0), and three dated build items
including **the live region, owned by Access**.

> *`segment_renditions` does not exist, so the entire disclosure surface is
> unbuilt. **`incomplete_match` is now exactly as built as `excessive_drop` and
> `wrong_match`.** The Critical was that it was *less* built than its peers.
> **That asymmetry is gone.***

**Condition stated:** *"If the class rule is ever weakened or exempted by list,
that is a new Critical and I will file it as one."*

**`H26-C2`** — §6.1 now states `synthesize → ASR → forced alignment → match`,
**and the half nobody had written down is written down**: the FA stage is **not
built** (Halo verified: no FA sidecar in `worker/src/`), so *"every word-sync
figure was measured without it while the cost figure was measured with it …
neither may be quoted as if it characterised the other."*
*"Nobody had written this down before; **Scribe wrote it against the author's own
interest.** That is the single best thing in this round."*

## Figures — verified with `--figure-check`, not taken from the brief

`chapter_best_measured_pct` **92.2** · `constant_offset_recoverable_pp` **0** ·
gap **2.8 pp** · fold predicted ceiling **99.1** = observed **99.1**, predicted
absent **11** = observed **11** · interior **96.1%** vs boundary **63.8%** ·
FA **+1.3** chapter / **−5.0** paragraph, n=2 · `clears_bar_with_fa_refinement:
false`.

> ***Every figure reproduces. I could not break the measurement — again.** Zero
> figures moved in the author's favour, for the second round running.*

## New Majors — 4

**`H35-M1`** the pre-fold marking reached four documents and **skipped the one
that outranks all four** — spec §7.1a carried the stale table unmarked while
§6.1, 950 lines away, says *"the verdict lives in §7.1a … so the two cannot drift
apart."* **`H34-C1`'s exact geometry with the polarity reversed.** Second site:
`ADR-0001`, *"on no handover list — the same failure it documents about
itself."* *(Scribe · 2026-08-12 — **fixed after ruling**.)*

**`H35-M2`** the en-GB/en-US fold **has shipped** and the roadmap still carries
building it, open, due 2026-08-22 — **and `roadmap:383` repeats the false
property, which is the derivation of `coverage_ceiling_pct_any_matcher`.** *"The
relaxation set has grown; the definition of a figure quoted in five documents has
not."* One document, two answers, ~1,260 lines apart — **seventh consecutive
round, at the repair's own boundary.** *(Forge with Scribe · 2026-08-12 —
**fixed after ruling**.)*

**`H35-M3`** the `render_specific` warrant reaches the glossary and **stops one
rank short** — spec §6.3 still read *"a different voice can genuinely change"*
twenty-five lines below its own correction, and **the spec is what Tongue reads
when writing 66 strings.** *(Scribe · 2026-08-12 — **fixed after ruling**.)*

**`H35-M4` — filed by Halo against itself.** Its closing criterion has **zero
discriminating power**: `grep -F` is line-based and §6.1's copy spans a wrap, so
the check returns `1` *"whether §6.1 was repaired or merely re-wrapped. **The
answer would have been identical had the defect survived — I would have closed a
live Critical on a green check.**"* `J30-M10`'s doctrine hitting its own limit:
*"a quoted string survives a reflow — **unless the quotation spans the
reflow**."* *(Halo · replace with a whitespace-tolerant pattern or a `[BANNED]`
entry with a mutation specimen.)*

## Minors — 2

**`H35-m1`** `[SD-UNWRITTEN]`'s predicate was rewritten this round and ships with
**no mutation specimen** — the guard that emitted seven false findings is the one
that did not get one. Mitigated: the self-test computes its uncovered set from
source, so it names itself every run. *(Forge · 2026-08-13.)* ·
**`H35-m2`** the repaired constants read the **disk** in a file whose doctrine
eight lines below is *"the index, not the disk (`J29-m4`)"* — and the round-34
record is untracked. Covered indirectly by `[STAGED]`. *(Forge · 2026-08-13.)*

## Ruling on the cross-scope edits to `tools/doc-check.mjs`

**The guard defect was Major-grade and Scribe's characterisation is correct:**

> *"A guard that says a written report was never written, in the run that gates
> the commit closing it … **the cheapest way to silence it is to delete the
> citation rather than write the record. A guard whose cheapest fix is worse
> than the defect is a guard that will be worked around.**"*

Halo: *"exactly right, and it is the accessibility lesson in miniature — **a
control that makes the honest path more expensive than the dishonest one is an
anti-control.**"*

**The cross-scope edit: APPROVED**, because Scribe flagged both in-file with
dated rationale, confined them to a predicate, argued monotonicity, and routed
*"Forge reviews."* *"That is how a cross-scope edit should be made."* One
reservation — monotonicity was **asserted**, and `H35-m1` says assertion without
a specimen is how guards go inert.

## For the owner, plainly

> **The gate is open. It should be.** … **Nothing about the product has
> improved.** English is **92.2** against 95 at its best measured. The cheap
> hypothesis is dead at **0.0 pp**. Forced alignment gives **+1.3 / −5.0**, n=2,
> opposite signs, for 91.6% more compute — **and the stage is not built.**
> Spanish has still never been measured beyond 22 words. What is left in English
> is prosody, and it is a property of the bar's own definition, which `H17-C3`
> forbids moving to make a measurement pass. **This is still not a launch
> state.**

> **Six rounds running, the next defect lives at the repair's own boundary — and
> it did again.** Three of my four Majors are the same species. **The
> reconciliation grep found seven kinds of site and missed the sentence
> twenty-five lines below its own correction.** And the fourth Major is mine.

> ***The project has learned that a figure needs an artifact, and this round it
> learned that an obligation needs one too. What is still unlearned is that a
> check needs a specimen*** — *and the two things that most needed one this round
> were a guard the author rewrote and a criterion the auditor wrote. Both were
> trusted; neither had been tested against the defect it exists to catch.*

*(Rule 6: `H35-M1`–`H35-M4` close only when Halo re-runs the check.)*
