# Architecture Decision Records

An ADR records **why** a decision was made, by whom, and what it costs — for the
engineer who joins six months from now and has read none of the audit trail.

Until this directory existed, the decisions below lived only as prose inside
27 audit records and a design spec that is gitignored. That is tribal
knowledge with a filename. These 5 ADRs are the first correction.

## Index

| # | Decision | Status | Spec |
| --- | --- | --- | --- |
| [0001](0001-the-segment-is-the-universal-unit.md) | The segment is the universal unit | Accepted | §3, §3.4 |
| [0002](0002-observe-what-was-spoken-do-not-predict-it.md) | Observe what was spoken; do not predict it | Accepted — **supersedes "forced alignment, not ASR"** | §6.1 |
| [0003](0003-haitian-creole-tts-routing.md) | Gemini TTS is reached via OpenRouter, not directly | **Superseded in part by 0005** — routing finding stands; language scope does not. Accepted — carries an **open** conflict with `CLAUDE.md` constraint 2 | §3.5 |
| [0004](0004-the-accessibility-gate-is-an-api-conformance-harness.md) | The accessibility gate is an API conformance harness | Accepted — **obligation not discharged** | roadmap Phase 0 |
| [0005](0005-haitian-creole-is-removed-from-scope.md) | Haitian Creole is removed from scope | Accepted — owner decision, 2026-08-08. **Removed the day it was proven to work**, so this is product scope, not a technical limit | §3.5, §9 |

## What "Accepted" means here, and what it does not

**"Accepted" means the decision is the current design intent. It does not mean
the design passed the gate.**

The most recent *recorded* Jury verdict on the design documents is
**`PASS WITH FIXES`** — **round 25** (`…-round25.md`), zero Blocker, zero
Critical, five Majors tracked under an owner and a date. Rounds 18
(`…-round18.md`) and 19 (`…-round19.md`) also returned `PASS WITH FIXES`;
round 22 (`…-round22.md`) was `FAIL` on two Criticals, both since closed.
**Round 17's `FAIL` is superseded.**

*(J22-M8: this paragraph said `FAIL` (round 17) and cited the round-**21** file
for it, while both `PASS WITH FIXES` records travelled in the same commit. It is
the orientation document, and it was wrong about the project's audit status in
the conservative direction — which is still wrong.)*

Halo cannot issue `PASS` before implementation and has not; its most recent
verdict is **ENABLES** (round 21) — no foreclosure found. Read the ADRs as
current design intent under an open Majors list, not as a certificate.

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

1. **Every claim traces.** Spec section, roadmap item, audit finding ID, or a
   `file:line` in the evidence. No claim rests on recollection.
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
