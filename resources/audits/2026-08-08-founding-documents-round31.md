# Audit Record — Founding Documents, Round 31

- **Date:** 2026-08-10 · **Subject:** repair of round 30, executed by **three Studio Zero agents in parallel** — Scribe (docs), Forge (guards/harness), Atlas (schema) — with the orchestrator owning only the seams
- **Reviewer:** Jury · **Response:** v31
- **Authorship provenance:** ruling by Jury; **transcribed by the audited party.** Findings fixed after the ruling are marked *fixed after ruling* and are certified by no one until re-audit.
- **Index/worktree identity verified by the reviewer:** `git diff --name-only` = 0.

## Verdict

**`PASS WITH FIXES` — 0 Blocker · 0 Critical · 9 Major · 4 Minor · 0 Polish.**
**The commit is permitted** (`CLAUDE.md` gate table): zero Blocker, zero
Critical, every Major owned and dated.

> *The parallel dispatch worked inside each scope and failed at every seam
> between them. Four of this round's six new Majors are three agents each
> recording a peer's work as unfinished, or citing a peer's file by a coordinate
> the peer was moving. Round 27 said "non-overlapping dispatch guaranteed the
> gap." **This round it guaranteed four.***

## Verification — every command run by the reviewer

| command | result |
| --- | --- |
| `doc-check` | clean, exit 0 |
| `doc-check --self-test` | **93 passed, 0 failed** · 67 IDs mutated, 12 named unmutated |
| `secret-scan` | clean, **196 files FROM THE INDEX**, exit 0 |
| `secret-scan --self-test` | **32 trials, 32 passed** |
| `secret-scan --all` | clean; summary correctly distinguishes index from disk |
| `verify_voice_langs` (static) | **21 proofs pass** |
| `verify_voice_langs --db-url=…:55432` | **30 live probes pass, transaction rolled back** |
| `npx eslint .` | exit 0 |
| `worker` / `aligner` | **57 / 57** · **9 / 9** |

**`migrations remain unvalidated by a real Postgres` — CLOSED.** Jury ran the
live harness itself: P1–P4f, L1–L6, R1–R10 all pass against PostgreSQL 18.1;
`assert_rls_class_rule()` executes; R2 prints the non-blocking
`unclassifiable_protected` NOTICE. The CI job was read and confirmed real.

**Round-30 record: transcription verified faithful, and `J30-M9` was not
repeated** — all sixteen round-29 findings resolve by ID.

**A correction Jury made against itself.** The round-30 record says *"Jury
recomputed all six bounds and all three extrapolations: the arithmetic is
correct."* Jury verified **only the ×32400 extrapolation**, not the bounds.
Under Rule 8 it cannot be sole judge of its own error; referred to BigBrain with
the ruling. This is why `J30-m1` is upgraded below.

## Majors — 9

**`J31-M1` — three agents each recorded a peer's scope as unfinished, and the
same commit falsified all three.** *(Scribe with Atlas and Forge · 2026-08-12 —
**fixed after ruling**.)* The new migration said `CLAUDE.md`/`README` *"still
enumerate the exempt catalogue by name… out of scope this round"* while Scribe
closed both in that commit; `roadmap` said the migration harness had *"no CI job
and no script"* while Forge built it in that commit; `spike-a-voices.json` and
`voices.py` said *"Leg (iii) covers nothing here. REPAIR: … Owner: Forge"* after
the repair landed (9 of 9 rows now take the branch).

> ***The root cause is in `CLAUDE.md`, not in the agents.** The reconciliation
> pass is specified to run before editing — which is exactly the wrong time when
> a peer is editing concurrently. The rule has **no clause for parallel
> authorship**.*

**`J31-M2` — the new migration's reconciliation-grep block cites by line number,
and all four coordinates are wrong.** *(Atlas · 2026-08-12 — **fixed after
ruling**.)* Two of its counts were false before the commit closed. `J30-M10`
verbatim, re-created in the one agent scope the remedy had never been applied
to. **The ruling is now general: cite by quotation, in every artifact, including
SQL comments.**

**`J31-M3` — spec §7's state table describes a predicate the rule does not
implement.** *(Atlas · 2026-08-12 — **fixed after ruling**.)* The table said
*"policy present"* / *"no policy"*; the rule tests `relrowsecurity` and never
policy presence. Jury reproduced it live: an obligated table with RLS enabled,
**zero policies**, granted to PUBLIC, passes the assertion. Fail-safe rather
than fail-open — RLS-on-with-no-policy denies — so not Critical. Major because
*"it is the only mechanism table in the design authority, written this round for
the express purpose of describing a control that lived nowhere, and 2 of its 4
rows name a test that does not exist."* `J30-M1`'s shape one document up.

**`J31-M4` — `README` still said "30 tests" after `CONTRIBUTING` fixed the
identical claim to 66.** *(Scribe · 2026-08-11 — **fixed after ruling**.)*
`CONTRIBUTING` diagnoses the cause in terms — *"this number was guarded by
nothing"* — and the one command that would have found the second site is the one
`CLAUDE.md` mandates. *"The project's single most recurrent defect, reproduced
inside the fix for it."*

**`J31-M5` — six newly published figures are checked by nothing, and the prose
was arranged so the guard would abstain.** *(Forge · 2026-08-13 — **open**.)*
`[ART-FIGURE]` tracks neither decomposition key, and its mention regex is a
substring match, so a tolerant figure beside its own identifier binds to the
**strict** metric and raises a false Major. Self-disclosed in the spec.
Abstentions rose **9 → 10**. *"Self-disclosure is credit; it is not closure. The
round that published the largest block of new figures in this series published
them unguarded."*

**`J31-M6` — the `[S2R]` guard was silenced by removing backticks, and the
identifier it protected is now in no artifact.** *(Scribe · 2026-08-12 —
**fixed after ruling**.)* `security_invoker` is the literal name of the option
that fixes the view half of `A31-1`; an engineer implementing it had to
rediscover it. Jury's ruling on the orchestrator's self-report: **the evasion
governs the severity, the remedy governs the tier** — Major, not Critical, not
dismissed. The guard fired partly as a known false positive with an established,
*disclosed* answer that Scribe used in the same file in the same round; *"you
used the mechanism and skipped the disclosure."* **A guard you quiet is a guard
the next author inherits already broken.**

**`J30-m1` — UPGRADED Minor → Major.** *(Forge · 2026-08-16 — **open**.)* Jury
re-derived all three intervals: `es`/`fr` reproduce under Fisher-z to
0.003–0.005, `en` does not (0.016) and reproduces best under OLS *t*, which then
misses `es`/`fr` by up to 0.050. **No single stated derivation produces the
published table.** Upgraded because *"a six-number table at three decimals, in
the rank-3 document, reproducible by no written route, is unfalsifiable — and
falsifiability is the one property this entire spike exists to have."* Jury
notes the conclusion is unaffected, *"which is exactly the argument I rejected
for `J30-M1`."*

**`J30-M8` — open, and worse than filed.** *(Forge · 2026-08-16.)* The
short-length maximum is **8.3 pp** (`locked` vs `narrateur`) — **4.4× the
published 1.9 pp bound, between the same two voices the bound covers.**
`feminine` has zero admissible long clips; the 0.1 pp within-voice floor rests
on one pair. **Forge's recommendation — state the coverage, do not re-measure —
is accepted:** the desync is the shipped matcher's design (monotonic greedy,
six-token lookahead, no re-sync path), and fixing it is ADR-0002 territory that
moves every published figure at once. *"Smuggling that decision into a
documentation finding would be worse than the finding."*

**`A31-1` — Major, open.** *(Atlas · 2026-08-17, or with the first view.)* Jury
reproduced the bypass live and rolled back: a matview over an RLS-enabled
obligated table granted to PUBLIC reports `relrowsecurity 'f'`, zero violations,
assertion passes. **Atlas's restraint upheld:** zero exposure today, named in
the control's own limits section, *"and bolting a fourth relation class onto the
migration that closes two findings is precisely how six of the last seven rounds
manufactured a defect at the fix's own edge."*

## Minors — 4

**`J30-m5`** — `spike-a-voices.json` / `voices.py` still carry the *"Leg (iii)
covers nothing here"* note after the repair landed, citing a `doc-check` line
that has moved. **Its trigger has now fired.** *(Forge · 2026-08-13.)*
**`J31-m1`** — `[SD-REV]` cannot distinguish a header from a **quotation** of
one; the next revision bump reddens a sentence explaining why v19 was *not*
bumped, and the obvious fix corrupts its meaning. *(Forge · with the
`CURRENT_REVISION` bump.)*
**`J31-m2`** — `doc-check` reports abstention counts per document with no
locations, so *"those are read by hand"* names nothing a human can read. Print
`doc:line`. *(Forge · 2026-08-13.)*
**Postgres version undeclared** — Minor, not Major: gating **both** 15 and 17 is
strictly stronger than a guess, so there is no exposure; what is missing is a
declaration. *(Atlas · 2026-08-14.)*

## Carried findings — 20 of 23 addressed, 18 fixed as specified

`J30-M1` **fixed** · `J30-M2` **fixed, and beyond spec** · `J30-M3` **fixed**
(all five shapes now trials) · `J30-M4` **fixed** · `J30-M5` **fixed** ·
`J30-M6` **fixed** · `J30-M7` **fixed at the admission rule** — *"third time
asked, first time done"* · `J30-M9` **fixed, not repeated** · `J30-M10`
**fixed in the spec ledger** · `J30-m2`, `J30-m3`, `J30-m4`, `J30-p1` **fixed** ·
`J29-m1`, `J29-m2`, `J29-m3`, `J29-m4`, `J29-p1` **fixed** ·
`J28-minor-a`, `J28-minor-b` **fixed, verified live** · migrations
**CLOSED, verified live + CI**.

`J28-minor-b` severity: Jury **affirmed Major on its own authority** — *"severity
is Jury's, not the implementer's, and grading your own defect is Rule 8"* —
reaching the same answer independently.

## What Jury verified and accepted

**`J30-M2` is the best repair in this series, and both of Scribe's unbriefed
findings survive independent recomputation.** (a) Silence tolerance admits
**4 / 3 / 1** of 24 / 20 / 18 tokens, while the dominant bucket is
`tokens_timestamped_before_the_previous_word_ended` = **18 / 16 / 17** — *"a
start placed before the previous word ended cannot be excused by silence that
had not begun."* Offset-corrected residual p95 **234.9 / 372.9 / 792.7 ms**
against a 300 ms bar. (b) The denominators differ and the difference is
**recognition**: `es` strict 4.5 = 1/22 not 1/20; `fr` tolerant 4.2 = 1/24 not
1/18. *"Scribe read the artifact, found two things nobody briefed it on, judged
them load-bearing, and both survive independent recomputation. That is the
standard."*

**Atlas's four self-found defects** — the column-ACL blindness is the one that
matters: `GRANT SELECT (user_id)` leaves the table ACL null, so a table-level
test reports *"unreachable"* about a partition whose user column is readable by
name. *"Finding your own defect after believing yourself done is the behaviour
this process is for."*

**`CURRENT_REVISION` stays 19 — correct.** *"Declining a quarter of an atomic
four-site edit after a peer had finished is the discipline this round otherwise
lacked."*

**Word sync is still not established in any language, and nothing here softens
it.** `S9` green statically **and live** — the store ships empty. Best long clip
**71.4%** against 95. *"This round is the only one that introduces higher
numbers into the documents — 91.7 / 81.8 / 54.2 — and I checked all four sites
carrying them. Every one labels them in-sample, upper-bound, not an achieved
result. **It does not soften. It sharpens.**"*

## The line the author has to keep

> *Three agents wrote in parallel on disjoint scopes and each one worked well.
> Every failure this round is at a seam. **Disjoint scopes do not compose — they
> only fail to overlap.** The reconciliation pass is specified to run before
> editing, which is the one moment it cannot see a peer's work. A rule written
> for one author, run by three, produces a clean pass in every scope and four
> Majors between them. **Add the second sweep, or stop running agents in
> parallel.***

*(The second sweep was added to `CLAUDE.md` after this ruling — see "When more
than one agent writes in a round". It is certified by no one until round 32.)*
