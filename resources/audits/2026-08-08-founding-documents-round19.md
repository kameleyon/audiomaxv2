# Audit Record — Founding Documents, Round 19

- **Date:** 2026-08-08 · **Subject:** the **documentation commit** — `.gitattributes`, `CODEOWNERS`, `CONTRIBUTING.md`, `README.md`, `docs/architecture/` (4 ADRs + index), `docs/glossary.md`, `resources/audits/…-round18.md`, `tools/doc-check.mjs`
- **Reviewer:** Jury · **Author of the docs:** Scribe · **Response:** v20
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 54/54

**This record exists because the guard written in response to it demanded it.**
`SD-UNWRITTEN` — added in v20 to close `J19-M2` — fired on its first real run
against `CLAUDE.md`, which cites `J19-M3` while only 18 records existed. That is
the fourth occurrence of `J16-M8` and **the first caught by the gate rather than
by a human**.

## Verdict

**`PASS WITH FIXES` — 0 Blocker · 0 Critical · 3 Major · 3 Minor.** Not a full
pass. The commit was held.

## Why Scribe was dispatched at all

Jo asked: *"do you make sure you are writing the docs section with scribe as you
go"*. The answer was no. `docs/` did not exist. `CONTRIBUTING.md`, `CODEOWNERS`
and the glossary did not exist. Scribe wrote the README around round 4 and **the
author then edited it directly for eighteen rounds without it** — violating
Scribe's own Rule 1 and `CLAUDE.md`'s "written as features are built, never
retrofitted".

The concrete cost: `R14-A1`, a full architecture reversal, existed only as §6.1
prose and audit-trail narrative. A new engineer would have found the *decision*
nowhere.

## What Jury verified

**The ADRs are accurate.** Jury checked every number against the spec and every
quote against the audit records.

On **ADR-0002** — the one most likely to be self-serving, since it records a
reversal the author got wrong for thirteen rounds:

> *This was the one to distrust and it survives the attack.* It **steelmans the
> decision it supersedes**, stating outright that it *"deserves to be recorded
> properly rather than caricatured"*, and lists four genuine merits — including
> the one the reversal **loses**: a forced aligner cannot hallucinate a word that
> is not in the document. It then files that loss as a new failure mode the
> reversal created, marked OPEN with owner and date. *Self-serving documents do
> not do this.*

On **ADR-0004**, the accessibility gate: the limitation carries a **top-level
heading**, the same rank as *Decision*, and is forward-referenced from the
Status block — *"Read the limitation before citing this ADR as accessibility
sign-off. **It is not one.**"* All three required statements present and
unhedged.

**The five guards are real, not decorative.** Four are faithful semantic
inversions at unique sites. `INV-NO-ROUTE` reproduces Jury's own round-18 attack
verbatim: *"`spec:381` is no longer the least protected line in the document."*

**Rule 8 — the round-18 record does not flatter Jury's own ruling.** Jury
checked it against artifacts rather than recollection, and noted that its
strongest evidence against flattery is the opening block, which records that the
record was written late, was caught by *Scribe rather than by the gate*, and that
`SD-ROSTER` is structurally blind to that class — *"which is the finding I would
otherwise have had to make myself."*

## The three Majors

| ID | Finding |
| --- | --- |
| **J19-M1** | Three committed documents claimed **17 audit records**; the commit made 18. Two cited the design's most recent verdict as `FAIL` (round 17) while round 18's `PASS WITH FIXES` travelled in the same commit. **J18-M3 recurring in the very next commit** — a self-description falsified by the commit carrying it |
| **J19-M2** | **The gate read four files while the commit added seven that make claims about the project.** Every `J19-M1` site but one sat in that blind region. And `SD-ROSTER` fires only when a roster claim is *less than* `ROUNDS_ON_DISK`, which is counted from the same directory the roster describes — so it catches a roster that undercounts and is **structurally blind to a cited round whose record was never written** |
| **J19-M3** | `README.md` named **OpenRouter and Google** as subprocessors; `CLAUDE.md` still named Google alone. The README is precedence rank 4 and *"mirrors, never originates"*; the authoritative list omitted a party that actually receives document text. An artifact of Scribe's write-scope, not a Scribe error |

## Closed in v20

`J19-M1` — all counts reconciled from disk. `J19-M2` — **`DOCS` extended from
four files to seven**, which caught a stale roster in the ADR index on its first
run; and **`SD-UNWRITTEN` added**, the missing direction, which caught this
record's own absence. `J19-M3` — fixed at rank 1 in `CLAUDE.md`, where it
belonged.

**A note on how `SD-UNWRITTEN` was built, because it is the round's other
lesson.** The guard silently matched nothing through four debugging rounds: a
Python heredoc had written `\\d` into a JavaScript regex, where it means *a
literal backslash*, not a digit. `Read` displayed it as `\d`; only dumping the
raw bytes with `JSON.stringify` revealed it. **A guard that matches nothing
passes**, which is precisely the `[HARVEST]` failure class this tool exists to
prevent — this time in the tool's own source. It was proven by execution, not by
reading, before being accepted.

## Scribe's contradiction report — the more valuable half

1. **The round-18 record did not exist** while three artifacts cited its findings.
2. **Hypereal costed at `$6.00`/`~4.4×` in §5** and `$5.40`/`~4×` in three other
   places. $0.01/min × 540 min = **$5.40**; §5 was wrong.
3. **`spec:711` still read "Provider normalization must be disabled"** as
   normative bolded prose — *at the very section `R14-A1` reversed* — with a
   retirement note appended two sentences later instead of the rule being
   deleted. Fixed by **deletion, not amendment**.
4. `forced alignment` vocabulary survived in §2 and the §6 title.
5. `README` claimed *"Both reviewers returned `FAIL`"*; Halo returned **`ENABLES`**.
6. **`core.autocrlf=true` with no `.gitattributes`** — the root cause of the CRLF
   corruption that hit twice. `[HARVEST]` was the detector; `.gitattributes` is
   the prevention. The project had one and not the other.

## What Scribe declined to write, and why it was right

`docs/help/` (Guide's, and Proof grades it) · OpenAPI (no API exists) · runbooks
(nothing runs) · **schema docs**:

> *Writing them today means copying a gitignored design that has **not passed the
> gate** into a committed file, where it would become the most
> authoritative-looking wrong document in the repo.*
