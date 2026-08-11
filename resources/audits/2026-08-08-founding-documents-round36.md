# Audit Record — Founding Documents, Round 36 (the Phase 0 completion round)

- **Date:** 2026-08-11 · **Subject:** 34 staged files, 8,734 insertions — SPIKE A follow-up, the conformance harness, the SPIKE E container job, the `H34-C2` schema, and the closure of both Halo Criticals. **Six agents.**
- **Reviewer:** Jury · **Response:** v36
- **Authorship provenance:** ruling by Jury; **transcribed by the audited party.**
- **Index/worktree identity verified by the reviewer:** `git diff --name-only` = 0.

## Verdict

**`PASS WITH FIXES` — 0 Blocker · 0 Critical · 3 Major · 2 Minor · 0 Polish.**
**The commit is permitted.** Every Major is owned and dated.

> *Nothing in this diff softens the position: **no language has a measured
> end-to-end pass, Spanish is still 68.2 on 22 words with zero `es` ceiling
> rows, and the FA stage the cost figure prices is not built.** The diff states
> all three harder than the round before it.*

## Verification — all eleven commands run by the reviewer, all reproduce

`doc-check` clean exit 0, 20 abstentions · `--self-test` **94/0**, 68 mutated,
12 named unmutated · `--figure-check --self-test` **14/0** · `secret-scan`
clean, **264 files from the index** · `--self-test` **32/32** · `worker`
**89/89** · `aligner` **9/9** · `verify_voice_langs` **44 live probes, rolled
back** · `a11y --self-test` **69/0** · `a11y` default **47 unestablished, 1
pass, exit 1** · `voices/english/drift` **53 · 44 · 26** · `eslint` exit 0.

Jury additionally ran **15 live `--figure-check` claims: 13 `OK`, and 2
deliberate wrong values returned `FAIL` with exit 1.**

> ***The `J33-M3` remedy has discriminating power.** It caught my dot-path error
> on `clips` and my mis-framing of `pipeline_multiplier` in the same session.*

**Round-33 transcription — FAITHFUL**, all eight IDs present; `J32-m4` not
repeated.

## Nothing is softened — confirmed by grep

The only `true` among the pass flags is `coverage_ceiling_clears_bar` — *"a
**ceiling**, correctly labelled, which is what makes 95 reachable rather than
reached."* `grep '"lang_code": "es"'` over the artifacts returns **nothing**.

## Majors — 3

**`J36-M1` — the round's load-bearing claim excludes a rival its own file could
have tested.** *(Forge · 2026-08-15.)* `verdict._reading` asserts the prosody
residual is *"a property of §6.1's drift DEFINITION, not of the decoder"*. Its
three stated grounds **do not exclude a pause-local decoder error**: `arm_b`
falsifies only a *uniform* shift; the prevalence enrichment is **equally
predicted by both hypotheses**; `arm_c.sign` again addresses only the constant
lead. **The discriminator sits in the same file and was not run** — crossing
`arm_e` with `arm_d`'s re-timed observations separates them in one pass.

> *In fairness: `arm_c.worst_15` **does** carry the discriminating pattern —
> pre-pause tokens negative, post-pause positive. A decoder extending a word
> into silence would push the pre-pause token later; the observed sign is
> negative. **That is the argument that works — and the artifact never makes
> it.** I had to reconstruct it by eye from n=15.*

Major because `README` elevates this to *"an OPEN OWNER DECISION and the only
route to 95 anyone has identified"* — *"an owner decision to move the acceptance
bar may not rest on a hypothesis whose live rival was left untested by an
instrument sitting in the same JSON."*

**`J36-M2` — `XS-8` was reported closed; its load-bearing half is not.**
*(Forge · 2026-08-14, the date already in the artifact.)* `ARTIFACT_DIR` is
**still** `'aligner/spike-a/out'` and `TRACKED` carries **zero SPIKE E keys**, so
`XS-8`'s own sentence *"every SPIKE E figure quoted in prose … is guarded by
nothing"* **is still true after the fix.** The generalisation bought a loud
abstention (`[ART-STALE] aligner/spike-e/out (no tts-manifest.json)`) rather than
a guard — *"abstaining loudly beats being silently blind… but it is not a
guard"* — and now **reads like coverage**, accounting for 1 figure while `1.916`
and `$0.32–$0.43` appear six times unguarded. Fifth occurrence of the shape.

**`J36-M3` — against the orchestrator: editing rank-1 documents after the
auditor ruled.** *(Scribe, then Halo · 2026-08-13.)* **Ruling: not acceptable;
it should have gone back to Scribe.** Four grounds: Jury's charter rule 4
(*"auditors do not edit code… this protects the audit's independence"*); Halo had
**already assigned all three** to Scribe and Forge, dated 2026-08-12; Halo
pre-empted the close (*"`H35-M1`–`H35-M4` close only when Halo re-runs the
check"*); and round 33's own ruling praised Scribe for **flagging** a rank-1
amendment rather than making it routine.

> ***The aggravating fact is that these edits leave no reviewable trace.***
> `git check-ignore` returns `.gitignore:12:/resources/*`, and `git ls-files
> resources/` returns 35 paths, **all of them audits**. *"It is the least
> reviewable change in this repository, made by the one role forbidden to make
> it, on the documents that outrank everything else."*

No evidence the content is wrong — `doc-check` is clean, no figure-check failed.
**Major, not Critical, for that reason — and Major, not Minor, because nobody has
checked them and rule 8 says I may not.** **`H35-M1`/`M2`/`M3` remain OPEN.**

## Minors — 2

**`J36-m1`** `--figure-check` has **no array specimen** among its 14 trials, and
its array error prints `[object Object],[object Object]` where indices belong —
*"the round's four most-relayed numbers all live under `clips[]`, and this is the
message an author meets first."* Fails safe. *(Forge · 2026-08-16.)* ·
**`J36-m2`** `README:474` opens *"Forge shipped the fold"* and still closes
*"(Build item: roadmap Phase 4.5, owner Forge.)"* — a pointer to an item that now
says the opposite. *(Scribe · 2026-08-14.)*

## Every ID resolved

**Round 33** — `J33-M1` **CLOSED** (`adr6` in `DOCS`; `[DOCS-UNGUARDED]` body
read, since the harness correctly lists it among its 12 unmutated) · `J33-M2`
**CLOSED** — *"the fix reproducing the defect inside itself and being caught by
its own test is the control working"* · `J33-M3` **CLOSED**, caveat `J36-m1` ·
`J33-M4` **CLOSED** · `J33-m1` **CLOSED**, computed not hand-listed ·
`J33-m2`, `J33-m3`, `J33-p1` **CARRIED**.
**Round 32** — `J32-M1`, `J32-M2`, `J32-M3` (partial), `J32-m1`–`m3`, `J32-p1`
**CARRIED** · `J32-M4`/`XS-3` **CARRIED, owned and in date** · `J32-M5`
**DISCHARGED by Queue**, confirmed.
**Round 31** — `J31-m1`, `J31-m2`, `A31-1` **CARRIED**.
**Halo** — `H34-M3`, `H34-M5`, `H34-M6` **CARRIED** · `H35-M1`/`M2`/`M3`
**OPEN — do not close** · **`H35-M4` CARRIED and upheld** — *"Halo filing a
zero-discriminating-power `grep -F` against itself, on a check that returned
green, is the highest-value self-report of the round"* · `H35-m1`, `H35-m2`
**CARRIED**.
**Cross-scope** — `XS-8` **OPEN** (`J36-M2`) · `XS-7` **OPEN**, *"correctly
raised in the direction round 31's sweep missed"* · `XS-5` **DISCHARGED as
built, correctly NOT closed as run.**

## What the round got right

> **Queue refusing to check off its own Phase 0 item** — *"Writing a job measures
> nothing"*, with `container_value` verified `null` by figure-check — **is the
> single best act in the round.** **Forge refusing `H17-C3`** and leaving 92.2 as
> an owner decision rather than tuning to pass. **Atlas refusing `SpanReason`**
> on the ground that it would bill the very remedy it recommends — fourth
> sighting of the paywalled-remedy shape, and **the first refused on a hash-input
> argument rather than a taste one.** **Probe's harness finding four defects in
> itself on the first run**, and shipping `UNESTABLISHED` as a third state that
> is never a pass. **Forge disclosing the 6 unrequested Lemonfox calls** when the
> output was byte-identical and nobody would have known.

## The line the author has to keep

> *Three consecutive rounds have now ended with the same shape: a fix reported
> closed that was closed in its **cheap half** — `J33-M2`'s copied predicate,
> `H35-M2`'s roadmap, and now `XS-8`'s enumeration without a `TRACKED` key. In
> every case the artifact that would have caught it was in the same file as the
> fix.*
>
> ***A remedy is closed when the sentence that motivated it stops being true —
> not when the code it named has changed.***
>
> *Read `XS-8`'s `need` aloud after the fix. **It still describes the
> repository.***
