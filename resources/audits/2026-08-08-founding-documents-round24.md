# Audit Record — Founding Documents, Round 24

- **Date:** 2026-08-08 · **Subject:** the staged commit set, re-verified after round 23
- **Reviewer:** Jury · **Response:** v24
- **Authorship provenance:** ruling by Jury; **transcribed by the audited party**, per the standing rule adopted this round.

## Verdict

**`FAIL` — 0 Blocker · 0 Critical · 8 Major · 2 Minor.**

**J23-C1 closed at Critical.** Ruled from `git show :README.md`, not the
worktree: no false technical claim survives in any staged blob.

## Why it still failed, and it is not the finding count

> *It fails on one thing: **J23-M1 and J23-M2 were reported to me as fixed and
> are not fixed — not partially, not started.** The staged `README.md` blob
> contains zero occurrences of the string `22`. I disproved both claims with one
> grep each.*

The author reported two closures from a script's success message without
grepping the result. Under Rule 6 Jury cannot certify a closure it has just
refuted — and passing would have made the round-24 record *"the fourth document
in this repository asserting something the commit carrying it contradicts, which
is the exact defect class under review."*

## The finding that matters most: 54 passed measures the wrong thing

**J24-M4 — the single most recurrent defect in this repository has no check.**
`J18-M3` → `J19-M1` → `J23-M1` → `J24-M2`: **four recurrences** of a document
misstating how many audit records exist. `SD-ROSTER` matches the range form
`rounds 1–N` and the filename form `-roundN.md`. **Nothing reads
`**18 audit records**`.**

> *The gate is green and the gate is wrong… The checker reports 54 tests passing,
> which sounds reassuring, but it is counting **the tests that exist, not the
> mistakes that keep happening.***

Closed in v24 by `SD-COUNT-AUDITS`, which derives the count from disk.

## The rest

`J24-M1` substitution residue at three sites, one incoherent (an answer about
low-resource coverage under a question asking about `en`/`es`/`fr`) · `J24-M2`/
`J24-M3` the two false closures · `J24-M5` **the ADR index's own fix for
`J22-M8` was a fresh mis-citation** — one replaced with another, same paragraph,
one round later · `J24-M6` `SD-UNWRITTEN`'s widening covered alphabets and digit
counts — *"the axis of my round-23 attack"* — and left the **plural** blind:
`rounds 18-19`, the sentence added to the README that round, matched nothing ·
`J24-M7` `[STAGED]`'s allowlist **did not contain the file it lives in**, so an
unstaged edit to the gate tool was invisible to the check built to catch unstaged
edits · `J24-M8` constraint 7 drifted between `README` and `CLAUDE.md`, and the
narrowing dropped `en` from a **subprocessor disclosure** — the wrong direction
of error for a privacy constraint.

## The `.wav` reversal — upheld, with the test stated

Jury verified all three SHA-256 values against the **staged blobs**, not the
worktree. `J22-M1` closed.

> *The test for reversing-under-audit is not "did the auditor ask for it" — it is
> **"does the reversal have a reason that survives the auditor leaving the room,
> and is it falsifiable."** Both hold… a cosmetic capitulation does not produce
> three hashes that check out.*

One caution: `.gitignore` attributed the reasoning to Jury. *"A rationale held
because Jury said so is one auditor away from being reversed again."*

## Ruling on sequencing — adopted as standing

> **Jury rules from artifacts. Jury writes the record immediately after, before
> any other document cites the round. The record ships in the same commit as the
> fixes it certifies.**

Three reasons: Rule 6 (*"self-attested fixes do not close findings"* — a record
written before the verdict makes the reviewer a co-signer on the audited party's
account of their own work); Rule 2 (with no record to cite, the ruling **must**
cite artifacts); Rule 8 (the record of a ruling is the reviewer's work, not the
fixer's).

> **This round is the proof of the sequencing rule, not just an instance of it —
> the two findings I overturned were overturned precisely because there was no
> record standing between me and the blob.**

*(Transcription note: this record and `-round23.md` are written by the audited
party because no reviewer-authored transcription mechanism exists yet. The
provenance line at the top is the interim honesty measure; building the real
thing is open work.)*

## Phase 0, on a pass

Monorepo scaffold · `packageManager` pin + lockfile sync · `/health` endpoints ·
`.env.example` with no real values · Supabase provisioning · CI with a secret
scan. **Not** anything downstream of word sync — SPIKE A returned **70–79%
against a 95% bar** and remains the open question that can invalidate the design.
