# Audit Record — Founding Documents, Round 33 (the English measurement round)

- **Date:** 2026-08-10 · **Subject:** 13 staged files — English measured end-to-end at chapter length; per-language scoping of the ASR-ceiling finding
- **Reviewer:** Jury · **Response:** v33
- **Authorship provenance:** ruling by Jury; **transcribed by the audited party.**
- **Index/worktree identity verified by the reviewer:** `git diff --name-only` = 0.

## Verdict

**`PASS WITH FIXES` — 0 Blocker · 0 Critical · 4 Major · 3 Minor · 1 Polish.**
**The commit is permitted.**

> *The measurement is the best artifact this project has produced and I could not
> break it. Then I looked at what reads it. **The ADR that carries this round's
> entire finding is in no guard at all** — `doc-check`'s `DOCS` map stops at
> `adr5` — and the only mention of `ADR-0006` in that file is a comment claiming
> it quotes the key being tracked. **The fix for `J32-M3` was justified by naming
> a document the checker cannot open.** The round measured honestly and then
> reported into a blind spot.*

## Verification — all nine commands run by the reviewer, all reproduce

`doc-check` clean, exit 0, **17 abstentions** · `--self-test` **94 passed, 0
failed** · `secret-scan` clean, **248 files FROM THE INDEX**, exit 0 (243 → 248
= exactly the five newly staged files) · `--self-test` **32/32** ·
`voices.py --self-test` **53 controls** · `english.py --self-test` **39
controls** · `worker` **80/80** · `aligner` **OK** · `eslint` exit 0.

## The result — recomputed by the reviewer from the raw data, not from summary fields

- **chapter end-to-end 90.0** = `sum(_outcome)/len(_outcome)` = **1122/1246**;
  `_outcome` length equals `display_words`, its sum equals `in_bound_tokens`.
  CI95 [88.3, 91.6], `passes_matched_bar: false`.
- **ceiling 98.0** = 100·(1246−25)/1246, `coverage_ceiling_clears_bar: true`.
- **headroom 8.0 pp**, `chapter_bound_by: "drift"`, `resyncs: 0`, 1246 words /
  453.73 s. Paragraph checks the same way: 209/224 = 93.3 against 99.1.
- **Bound ordering holds on real data:** 98.0 ≥ `match_rate_pct` 97.8 ≥ 90.0.

**`supports_chapter_length_claim` is COMPUTED, not asserted**, and falsifies
inside the same artifact — the paragraph row is `false`. **The ceiling is the
same strict upper bound verified in round 32, by identity rather than
inspection:** `CTL-IMPORT` asserts `V.score.__module__ == "voices"` and that the
bound and bar are imported from `measure`, never restated.

**French reproduces byte-for-byte** — 95/92.0, 103/91.3, 105/91.1, 114/90.4,
119/90.0, 121/89.8 — and `spike-a-voices.json`'s `clips[].lang_code` is `fr` in
all nine rows. **Same bar, opposite blocker, and English still fails.**

> **For the owner, plainly: English-only does not rescue the launch.** 90.0 with
> a CI95 upper bound of 91.6 misses 95 by 3.4 pp **even at its most generous**.
> *"What the round buys is the **owner** of the remaining gap: drift is Forge's
> to close, recognition would have been a vendor decision."*

## Majors — 4

**`J33-M1` — ADR-0006 is read by no guard, and the `J32-M3` fix was justified by
naming it.** `DOCS` enumerates `adr1`…`adr5`; ADR-0006 is **absent**.
`grep -n "0006" tools/doc-check.mjs` returns **one hit, inside a comment** —
written this round as the rationale for adding `coverage_ceiling_pct_any_matcher`
to `TRACKED`. The abstention breakdown proves it: there is no `adr6` key to
abstain on. The file's own recorded history repeats three lines above: *"H20-M4 —
J19-M2 extended DOCS from four files to seven and left the MOST damaged files
outside it. Halo found four Criticals in that blind region while the gate exited
0."* Major and not Critical because Jury hand-checked every figure in ADR-0006
and **all are correct** — the defect is the unguarded surface, on the newest and
most load-bearing ADR. *(Forge · 2026-08-13.)*

**`J33-M2` — `CTL-LENGTH` guards a copy of the predicate, not the predicate.**
`english.py:840` redefines the threshold expression **inside the test**; the
shipped expression at `:515` is never invoked by `self_test()`. **Change the
shipped threshold to 100 and `CTL-LENGTH` still reports 2/2.** This is what
`CTL-IMPORT` forbids, in the same file, seventy lines earlier. It guards the one
field certifying a paragraph did not stand in for a chapter — `J29-C1`'s shape.
*(Forge · 2026-08-14.)*

**`J33-M3` — the relay rule is unenforced, and a written rule is now measurably
not a control.** Five relay errors this session; **agents caught 5, the author
caught 0**; **two occurred after the control was written, by its author.**
Prevention rate **0/5**. The rule's *content* is correct — had it been obeyed,
error 1 was unwritable. **It is not unenforceable:** every one of the five dies
at a key-existence-and-value check over `aligner/spike-a/out/`, using machinery
`doc-check.mjs` already has. Required: a `figure-check` entry point taking
`file#keypath=value`, and routing messages carrying a line it can consume.
*(Orchestrator, tool by Forge · 2026-08-13.)*

**`J33-M4` — a missed site of rule 4, in the file edited for rule 4.**
`docs/glossary.md:102`: *"monotonic greedy with a six-token lookahead desynced
**3 of 6** long clips"* — no language, in a **committed** document, the same
quantity the orchestrator relayed wrongly. All six are French, and the only
non-French long clip now reports `matcher_desynced: false` — so "long clips" as
an unqualified population is **falsified by this round's own measurement**.
*(Scribe · 2026-08-13.)*

## Minors — 3 · Polish — 1

**`J33-m1`** both Python harnesses **overstate their own coverage** — `english.py`
prints *"Each control is asserted in BOTH directions"* while 9 of 39 assertions
have no `/mut` line; in `voices.py` it is 12 of 14 families. The honest form
ships in the same repo (`doc-check --self-test` names its 11 unmutated IDs).
**Jury records this against itself: it passed `voices.py` in round 32 without
reading the footer against the ID table.** *(Forge · 2026-08-16.)* ·
**`J33-m2`** `chapter_bound_by` is a **dichotomy, not a measurement** — any
shortfall under a passing ceiling is labelled `"drift"`. Correct here only
because `match_rate_pct` 97.8 independently clears 95, **which the formula never
consults.** *"The label is what the owner is buying."* *(Forge · 2026-08-16.)* ·
**`J33-m3`** `CTL-CEILING-BOUNDS` claims it is checked on the real committed clip;
both operands are synthetic *(Forge · 2026-08-16)*. ·
**Polish `J33-p1`** Scribe's *"92.3 = a `true_s` timestamp"* is **generous to the
orchestrator**: 92.3 appears nowhere on disk as a value.

## Scribe's three unbriefed findings — each verified

**1. The index precondition was REAL**, confirmed from the code rather than the
throwaway index: with the JSON staged and `en-long.wav` untracked, the manifest
loop emits `[ART-STALE]` **by construction**. Not a guess.
**2. Both relay errors confirmed against disk.** `asr_coverage_ceiling` appears
on exactly **11 clips — 9 `fr`, 2 `en`** — and no `-para` row carries one. `89.8`
is `fr-long-feminine-r1`'s ceiling; `95.9` is `en-para`'s CI95 upper bound.
Re-syncs: **2 of 6**, **0 desynced**. *"Scribe was right to refuse publication."*
**3. `ADR-0001` confirmed wrong twice** — **93 is produced by no artifact**, and
the sentence carried no language over nine French rows. *A site no handover
listed, found by grepping the claim.*

## Rulings requested

**Round-32 transcription — FAITHFUL**, all 10 findings by ID; `J32-m4` **not
repeated**. · **`CLAUDE.md` rule 4 — UPHELD and necessary:** rules 1–3 each bind
a *figure*; **none binds a sentence**, so the defect passed them *by
construction*. *"Scribe flagging a rank-1 amendment for explicit review rather
than letting it pass as routine is exactly right and I want that behaviour
repeated."* One reservation — **its enforcement is another written rule**, and
Jury found a site the grep missed (`J33-M4`). · **Keeping the verdict verbatim —
CORRECT; rewording would have been the error.** Replacing evidence and
attribution while preserving the sentence is the right separation. ·
**Phase 4.5 date — keep 2026-08-22; do NOT gate the 08-16 re-score on it.**
Gating an overdue measurement on an unbuilt fold would move matcher and
normaliser at once — the confound this project files monthly. **Condition of
closing `J30-m1`/`H26-M7`: the 08-16 record must carry the known understatement.**

## Carried findings — every ID resolved

`J32-M1` **OPEN** — `grep -rniE "ablat"` over `aligner/` still returns nothing ·
`J32-M2` **OPEN** — `spike-a-groundtruth.json` still carries neither interval key ·
`J32-M3` **PARTIAL, and the unfixed half is the half that failed this round** —
`display_tokens_absent_from_transcript` and `resyncs` are still untracked, and
**those two keys produced both of this round's published errors** ·
`J32-M4`, `J32-M5` **OPEN** (no Rule 6 re-run, which is what closes them) ·
`J32-m1`, `J32-m2` (**now doubled** — the English arm is confounded the same
way), `J32-m3`, `J32-p1` **OPEN** · `J32-m4` **CLOSED, verified** ·
`J31-m1`, `J31-m2` **OPEN, not due** · `A31-1` **OPEN** *(Atlas · 2026-08-17)* ·
**the accessibility Major remains the one load-bearing deadline** — Critical on
sight if 2026-08-17 passes with ingest work started.

## The line the author has to keep

> *You measured the thing you were afraid of, on a fixture that qualifies, with
> an instrument you imported rather than rebuilt, and published a result that
> fails. **Zero of the seventeen figures I recomputed moved in your favour.**
> That is the hard half and it is now three rounds of doing it well.*
>
> *And the relay rule you wrote was broken by you, in your next message, twice —
> and the fix for `J32-M3` was argued in a comment that names a document
> `doc-check` has never opened. **Both are the same failure: a control addressed
> to attention rather than to execution.***
>
> ***Stop writing rules for yourself and start writing checks. `J33-M1` and
> `J33-M3` are one finding wearing two hats, and `J33-M2` is that hat a third
> time — a control that tests a copy is a rule addressed to whoever remembers to
> keep the copy in step.***

*(Rule 6: `J33-M1`–`J33-M4` close only when the originating reviewer re-runs the
check. Rule 8: `J33-m1` is recorded as Jury's own miss from round 32; the
round-31 arithmetic on `J30-m1` remains referred to BigBrain.)*
