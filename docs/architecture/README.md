# Architecture Decision Records

An ADR records **why** a decision was made, by whom, and what it costs — for the
engineer who joins six months from now and has read none of the audit trail.

Until this directory existed, the decisions below lived only as prose inside
36 audit records and a design spec that is gitignored. That is tribal
knowledge with a filename. These 6 ADRs are the first correction.

## Index

| # | Decision | Status | Spec |
| --- | --- | --- | --- |
| [0001](0001-the-segment-is-the-universal-unit.md) | The segment is the universal unit | Accepted | §3, §3.4 |
| [0002](0002-observe-what-was-spoken-do-not-predict-it.md) | Observe what was spoken; do not predict it | Accepted — **supersedes "forced alignment, not ASR"** | §6.1 |
| [0003](0003-haitian-creole-tts-routing.md) | Gemini TTS is reached via OpenRouter, not directly | **Superseded in part by 0005** (language scope) and **fully superseded for routing** (J29-C3). Accepted as a record of *method*, not of routing. Its `CLAUDE.md` constraint-2 conflict is **closed by removal** — audiomax has no Gemini path to fall back through | §3.5 |
| [0004](0004-the-accessibility-gate-is-an-api-conformance-harness.md) | The accessibility gate is an API conformance harness | Accepted — **obligation not discharged** | roadmap Phase 0 |
| [0005](0005-haitian-creole-is-removed-from-scope.md) | Haitian Creole is removed from scope | Accepted — owner decision, 2026-08-08. **Removed the day it was proven to work**, so this is product scope, not a technical limit | §3.5, §9 |
| [0006](0006-the-matcher-re-synchronises-and-lives-in-the-product.md) | The matcher re-synchronises, and it lives in the product | Accepted, 2026-08-10 — **completes 0002**, whose "match step" had no implementation. Supersedes `J30-M8`'s bound. **Read the ceiling, not the improvement — and read it per language: the 95 bar is ASR-bound in FRENCH and DRIFT-bound in ENGLISH. Nothing passes; the blockers are opposite** | §6.1, §7.1a |

## What "Accepted" means here, and what it does not

**"Accepted" means the decision is the current design intent. It does not mean
the design passed the gate.**

The most recent *recorded* Jury verdict on the design documents is
**`PASS WITH FIXES`** — **round 33** (`…-round33.md`), zero Blocker, zero
Critical, **four Majors** tracked under an owner and a date. Round 32
(`…-round32.md`) and rounds 18, 19, 25, 28, 30 and 31 also returned
`PASS WITH FIXES`; the `FAIL`s of rounds 17, 22, 27 and 29 are superseded.

**Halo cannot issue `PASS` before implementation and has not. Its most recent
verdict is `FORECLOSES` — round 34
(`2026-08-10-spike-a-accessibility-round34.md`): 0 Blocker · **2 Critical** ·
6 Major · 4 Minor · 1 Polish, and both Criticals block a commit.** That is the
standing accessibility verdict, and it is **newer** than Jury's — so nothing on
this page is gate-approved and the gate is currently **shut**. A Jury
`PASS WITH FIXES` says nothing about accessibility foreclosure, and reading it
that way is how "accessibility is the product" becomes a sentence nobody checks.
Read the ADRs as current design intent under an open Majors list **and an open
Halo foreclosure**, not as a certificate.

*(**`H34-M4`, corrected 2026-08-11 — the eighth recurrence of this defect.** The
Jury line was two rounds out of date and the Halo line eight, in the *optimistic*
direction, in the document a newcomer reads to learn whether the design is
approved. The 2026-08-10 remedy below — *"every verdict claim here now names its
round file"* — **was obeyed, and it named a stale round file**, which is the
argument that this needs a check rather than a further rule. Recommended and
referred to Forge with the `README.md` twin: a guard that resolves the newest
audit record per reviewer from the index and fails any `round <N>` verdict claim
that does not name it *(Forge · due 2026-08-13)*.)*

*(Corrected 2026-08-10. Two errors, both in the optimistic direction, which is
the direction that matters. The Jury line was **six rounds** out of date. The
Halo line said **`ENABLES` (round 21)** — Halo's *superseded* verdict — while
`README.md`, in the same repository, correctly recorded round 26's `FORECLOSES`;
two committed documents contradicting each other on governance state is `J24-M3`
verbatim, and `J22-M8` said of this same paragraph that being wrong "in the
conservative direction … is still wrong". This time it was wrong in the other
one. **Every verdict claim here now names its round file**, so a reader
disproves it with one `ls`.)*

An ADR that recorded a decision as approved when it was merely made would be
exactly the kind of confident-and-wrong artifact this project has spent
seventeen rounds deleting.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| `Proposed` | Written down, not yet decided |
| `Accepted` | Decided, and it is what the spec now says |
| `Superseded by NNNN` | Reversed. **The record stays.** A reversal without its history is a decision nobody can re-examine |
| `Rejected` | Considered and declined, with the reason kept |

A superseded ADR is never deleted or quietly rewritten. ADR-0002 exists because
the decision it reverses was never written down, so five rounds of reviewers
re-derived it from scratch every time it broke.

## Format

Every ADR uses the same five headings, in this order:

1. **Status** — one of the four above, with a date and a named decider.
2. **Context** — the forces. What was true when the decision was made.
3. **Decision** — one sentence in the active voice, then the specifics.
4. **Consequences** — what this now costs us, including the bad parts and the
   obligations it creates. An ADR with only good consequences is marketing.
5. **References** — spec section, roadmap phase, audit record, finding ID.

## Rules

1. **Every claim traces, and it traces by quotation.** Spec section, roadmap
   item, audit finding ID, or a **quoted string plus its file path**. No claim
   rests on recollection — and since `J31-M2`, **no claim rests on a line
   number**: a quoted string survives a reflow and is re-findable with
   `grep -F`; a line number is true only for the version of the file that no
   longer exists. Where an ADR cites the frozen `motionmax` reference stack, the
   `file:line` locators are kept — that code is external and unedited — but the
   quotation is what carries the claim, and the locator rides behind it.
2. **The spec is the design authority, not this directory.** Per `CLAUDE.md`
   document precedence: `CLAUDE.md` > `resources/specs/` > `resources/roadmap/` >
   `README.md`. An ADR *explains* a decision the spec *states*. If an ADR and
   the spec disagree, the spec wins and the ADR is defective — file it as a
   finding rather than editing the spec to match.
3. **Record the loser.** What was considered and rejected, and on what evidence.
4. **Number monotonically.** Four digits, never reused, never renumbered.
5. **Open questions stay open in writing**, with the owner and date the roadmap
   assigns. "Undecided" is a legitimate thing for a document to say; a confident
   guess is not.
