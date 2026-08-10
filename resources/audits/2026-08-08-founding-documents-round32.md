# Audit Record — Founding Documents, Round 32 (the Phase 0 spike round)

- **Date:** 2026-08-10 · **Subject:** 67 staged files — SPIKES A, C, D, E closed by **five agents in parallel** (Forge, Oracle, Probe, Queue, Scribe), orchestrator owning the seams
- **Reviewer:** Jury · **Response:** v32
- **Authorship provenance:** ruling by Jury; **transcribed by the audited party.**
- **Index/worktree identity verified by the reviewer:** `git diff --name-only` = 0.

## Verdict

**`PASS WITH FIXES` — 0 Blocker · 0 Critical · 5 Major · 4 Minor · 1 Polish.**
**The commit is permitted.**

> *The second sweep works and it is not sufficient. It caught two of the
> orchestrator's three relay errors and the fourth `J31-M1` site. It did not
> catch that **three separate blocks of figures published this round exist in no
> artifact**, that the round's single load-bearing number is guarded by nothing,
> or that an artifact shipped asking a peer to do what the same commit did.
> **Four of five new Majors are seams. The clause changed the failure rate, not
> the failure mode.***

## Verification — all nine commands run by the reviewer, all reproduce

`doc-check` clean exit 0 · `--self-test` **94 passed, 0 failed** · `secret-scan`
clean, **243 files FROM THE INDEX**, exit 0 · `--self-test` **32/32** ·
`voices.py --self-test` **53 controls, all passed** · `verify_voice_langs`
**30 live probes, rolled back** · `worker` **80/80** · `aligner` **9/9** ·
`eslint` exit 0.

## The ASR ceiling holds — the round's load-bearing claim, verified

Every figure in ADR-0006's table reproduces byte-for-byte from
`spike-a-voices.json`: ceilings **92.0 / 91.3 / 91.1 / 90.4 / 90.0 / 89.8** on
95 / 103 / 105 / 114 / 119 / 121 absent tokens.

**The construction is a genuine strict upper bound.** Jury read `asr_absence`
against `placeAt` and `matchTokens`: it relaxes monotonicity, relaxes the
six-token window, and permits one observation to serve several display tokens —
**every relaxation in the ceiling's favour.** So
`matched_within_drift_pct ≤ match_rate_pct ≤ ceiling`, and it bounds the bar
metric too. `CTL-CEILING`'s third leg — halve the transcript, the ceiling must
fall — fires under mutation.

**The orchestrator's self-correction is upheld in full:** `95` absent (not 93),
`92.0%` (not 92.2), and *"~89.5% after drift"* correctly **withdrawn** — `89.5`
is `match_rate_pct` for the very clip the ceiling was quoted from.

## Word sync — nothing softens it

`any_clip_passes_bar: false`; best **86.3**; all six long clips carry
`below_bar`; `S9` green statically **and live**. *"The round raised the best
figure by 14.9 pp and moved the verdict not at all. That is the correct
behaviour."*

## Majors — 5

**`J32-M1`** — three ablation deltas (+23.9 / +10.8 / +3.5 pp), a range, and the
`A0` reproduction state are published in three documents and exist in **no
artifact and no code**. `grep -rniE "ablat"` returns only the three documents;
`"A0"` appears nowhere. This is the defect **SPIKE E filed in the same commit**,
reproduced by the agent that read it — and forbidden in terms by Forge's own
`voices.py` comment. *(Forge · 2026-08-14.)*

**`J32-M2`** — `J30-m1` is declared closed "at the derivation", and the
derivation has **never been run into an artifact**. `spike-a-groundtruth.json`
contains one slope key and **no interval at all**; it is not among the staged
modified artifacts. *"Writing the route into code that was never run does not
close it. **`J30-m1` is not closed. It is re-committed with a better excuse.**"*
*(Forge · 2026-08-16.)*

**`J32-M3`** — the round's load-bearing number is guarded by nothing, and
`[ART-FIGURE]` **does not even abstain** on it. `coverage_ceiling_pct_any_matcher`,
`display_tokens_absent_from_transcript`, `resyncs` are untracked, so the
summary's *"abstained on 14"* **understates** the unguarded surface rather than
bounding it — ADR-0006 and README contribute **zero** abstentions.
*(Forge · 2026-08-13, with `J31-M5`.)*

**`J32-M4`** — `compute_cost_per_audio_hour_usd` still claims the pipeline and
still times one stage of three. SPIKE E routed it to Forge by name; Forge edited
four files in that scope and not `harness.py`. **And `[ART-METRIC]` now pins the
name** — *"the misnomer has acquired a defender."* *(Forge · 2026-08-14.)*

**`J32-M5`** — a stale peer-scope assertion shipped **inside an artifact**,
asking Scribe to fix what the same commit fixed. `J31-M1` verbatim, one round
later, in the round whose new clause exists to catch it — and step 3 of that
clause enumerates the exact phrase. *(Queue with the orchestrator · 2026-08-13.)*

## Minors — 4 · Polish — 1

**`J32-m1`** the ceiling's 3-token window is asserted by comment, not control;
`digitRuns` is unbounded, so a 4-element grouped-digit form would understate the
ceiling — empirically harmless here (max form length 3) *(Forge · 2026-08-14)* ·
**`J32-m2`** the length contrast is confounded — short and long corpora are
different texts, and the short ceilings carry no interval at n=24
*(Forge · 2026-08-16)* · **`J32-m3`** `spike-d-results.json`'s only
verdict-shaped field is `verdict_gate: "PASS"`, which is the **instrument's**
gate, in the spike where nothing passes on an image; the roadmap disclaims it,
the artifact does not *(Probe · 2026-08-14)* · **`J32-m4`** the round-31 record
carries a finding **without an ID** *(Jury · with this record — **fixed**)* ·
**Polish `J32-p1`** the Fish range endpoint is the `by_language` max, not the
EPUB-typography max ($8.45).

## Carried findings — every ID resolved

`J31-M1` **NOT CLOSED — recurs as `J32-M5`** · `J31-M2` **CLOSED** ·
`J31-M3` **CLOSED** · `J31-M4` **CLOSED, and closed correctly** — *"Deleting a
number nobody could keep right is a better fix than correcting it a fifth
time"* · `J31-M5` **PARTIAL — reproduced as `J32-M3`** · `J31-M6` **CLOSED** ·
`J30-m1` **NOT CLOSED — restated as `J32-M2`** · `J30-M8` **CLOSED and
superseded**, 1.9 → **7.9 pp**, 0 of 2 → **10 of 12 significant** ·
`J30-m5` **CLOSED** · `J31-m1`, `J31-m2` **OPEN, not due** ·
Postgres version **CLOSED** · `A31-1` **OPEN, correctly** *(Atlas · 2026-08-17)*.

## Accessibility — Major, and the deadline is load-bearing

Jury considered Critical. Held at Major because **nothing ships** (Phase 2 is
unbuilt), the degradation is **measured** and the disclosure signal **falsified
rather than assumed** — *"Probe falsified its own preferred signal"* — and it is
owned at the right layer *(Halo with Comply · 2026-08-17)*.

> **It does not become Critical unless a camera path is built before
> 2026-08-17. If that date passes with the item open and any ingest work has
> started, it escalates to Critical on sight** — the one finding in the round
> where the deadline is load-bearing rather than administrative.

## The relay ruling — against the orchestrator

**"Adequate as a recovery. Not adequate as a control."** Two of three relay
errors were caught by the receiving agent; the third reached four documents for
a revision.

> *The asymmetry is the point: **the writing rule demands an artifact and the
> routing rule demands nothing**, so a routing message is the only place in this
> process where a number may travel without provenance. That is not a smaller
> version of the round-29 defect — it is the **upstream** version, because a bad
> relay contaminates every scope it reaches at once, while a bad paragraph
> contaminates one.*

Jury's requirement, now in `CLAUDE.md`: a routing message carrying a figure
carries its artifact path and key, or says *"unverified"* in terms. And:
*"Scribe's 'a control quoted only where it agrees is not a control' is the
sentence of the round and it was earned correcting **you**; the process should
not depend on an agent being that good."*

## Seams attacked directly

**The scanner/OCR collision — exclusion upheld, no finding.** *"Narrowing the
scanner would have been the wrong answer and I would have filed it as a Major.
A `SKIP` for OCR output is a `SKIP` for the shape a leaked key most
resembles."* Jury verified `spike-d-results.json` **is** in the index, **is**
scanned, and **is** clean. **The forward correction** of the fourth `J31-M1`
site — upheld; an applied migration's checksum is tracked and forward-only is
worth more than a tidier comment.

## What Jury verified and accepted

**ADR-0006 is the best document this series has produced**, *"and its best
passages are the ones that cost it something"* — it records the withdrawn figure
inside the ADR documenting the fix for that same class, and discounts its own
headline improvement as *"inflated relative to production."*

**SPIKE E is the strongest refusal in the series** — `container_value: null`,
`_no_substitute_offered`, the blocker documented to the vendor's error string,
and its own working assumption falsified in public. *"Refusing to reboot a host
running four other agents to finish a sizing spike was also correct."*

**SPIKE C's second finding is the one that counts** — that the project's own
round-1 audit was wrong in the **opposite** direction. **SPIKE D falsified its
own disclosure signal**, and its `_limits` include two **measured** limits that
make its own pass worth less.

## The line the author has to keep

> *The round is honest about everything it measured and careless about
> everything it computed. Four spikes moved four published numbers the
> unfavourable way and not one was softened. **That is the hard half and it was
> done well.***
>
> *And then three blocks of figures were published by the route this project has
> now filed under six IDs. `J32-M1`, `J32-M2` and `J32-M3` are one defect
> wearing three hats: **a number is not measured because you computed it, it is
> measured because a committed run emitted it.** Forge wrote that sentence into
> `voices.py` this round, obeyed it for the ceiling, and broke it three times in
> the document that reports the ceiling.*
>
> ***A sweep that unions identifiers cannot see a figure that was never given
> one.** Add the artifact-first rule to relaying and to publishing, or the next
> round will pass in every scope, pass the sweep, and still ship six numbers
> nobody can falsify.*

*(Rule 6: `J32-M1`–`J32-M5` close only when the originating reviewer re-runs the
check. Rule 8: Jury's round-31 arithmetic on `J30-m1` remains referred to
BigBrain; `J32-M2` does not discharge it.)*
