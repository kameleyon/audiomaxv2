# Audit Record — Founding Documents, Round 14

- **Date:** 2026-08-08 · **Subject:** spec v15, roadmap v15, `README.md`, `CLAUDE.md`, `tools/doc-check.mjs`
- **Reviewers:** Halo first, then Jury **on synthesis** · **Response:** v15 → v16
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 43/43

> Written late alongside rounds 13 and 15 — see the note in `-round13.md` (J16-M8).

**Process fix applied this round.** Rounds 12–13 dispatched both reviewers in
parallel, so Jury — whose role is *"commit gate, audit **synthesis**"* — ruled
without seeing Halo's findings, and had to vacate a `PASS WITH FIXES` as a
result. From round 14 on, **Halo reports first and Jury rules with Halo's report
in hand.**

## Verdicts

| Reviewer | R13 | R14 |
| --- | --- | --- |
| **Jury** | 0B/2C/3M | **0B/8C/6M — `FAIL`** (highest Critical count since round 1) |
| **Halo** | 0B/3C | **0B/6C/5M — FORECLOSES** |

## `R14-A1` — the owner re-architected word sync, from production evidence

Jo made two corrections, both from code running on this machine:

**1. Haitian Creole was never a launch risk.** The spec had marked `ht`
`UNRESOLVED — Phase 0 blocker` for fourteen revisions. `motionmax`'s
`worker/src/services/audioRouter.ts:10-15, 214-223` routes `ht` and ten other
languages to **Google Gemini Flash 2.5 TTS**, which speaks it natively;
`voiceCatalog.ts:209` lists it first-class. **No code path calls Google Cloud
TTS**, so `providerRates.ts:71`'s contrary claim is a stale comment in a file
already wrong on two rate figures. Evidence:
`resources/research/2026-08-08-spike-b-ht-production-evidence.md`. **SPIKE B
closed at zero cost.** Jury: *"Twelve rounds of argument were settled by reading
`audioRouter.ts:214-223`. I record this as the single best piece of work in
fourteen rounds."*

**2. Word sync is OBSERVED, not predicted.** Every revision through v14 said
*"forced alignment, not ASR"* — which required predicting the spoken form, which
required providers to disable their internal normalization (**SPIKE B2**), the
dependency behind the majority of this project's Criticals across five rounds.
Motionmax instead transcribes the audio it generated (`audioASR.ts:2-5`,
word-level timestamps) and ships. §6.1 reversed: **synthesize → transcribe the
audio we produced → match observed words to display text.** Run on our own
WhisperX sidecar; Hypereal stays rejected on price ($5.40 per 9-hour book, 4× the
synthesis it would time), not on technique. **SPIKE B2 retired — closed by
deleting its dependents, not by measuring it.**

## Jury's ruling on the architecture: **STAND WITH CONDITIONS**

Upheld on three grounds: it is the only architectural decision in fourteen rounds
grounded in Evidence Tier A; it converts an unfalsifiable property into a
falsifiable one (prediction asserted correctness *by construction* and had no
second string to compare against); and the cost objection was preserved rather
than dropped.

On process, Jury dismissed the objection to Jo re-architecting mid-ruling:

> *Jo is the owner. Ruling 4 binds the creator loop; it does not bind Jo. An
> owner may re-architect their product at any time and does not need my leave.
> **Anyone arguing otherwise has confused a quality gate with a chain of
> command.***

## Why it still failed: the ratio, not the size

> **The size of a change is not what generates defects. The ratio of assertion to
> propagation is.**

Six of eight Criticals were pure propagation failure — the same idea written in
one place and not the other eight. `README.md:125` still said, in bold,
**"Forced alignment, not ASR"**; roadmap Phase 6 still said *"Aligner receives
`spoken_text` ONLY"*. Halo: *"The direction is right. The delivery makes a blind
reader worse off today than v14 did"* — because a document set that disagrees
with itself cannot be built at all, whereas v14 could.

| ID | Finding |
| --- | --- |
| **R14-C1** | The re-architecture existed in one section of one document; four artifacts described three products |
| **R14-C2** | `normalization_opaque` declared *"Retired — nothing depends on it"* in a table row naming eleven dependents; 24 live sites, including the guard defending it |
| **R14-C3** | The observed→display match had **no invariant, no floor, no reason code**. Prediction had four invariants; observation had one rule catching tokens matching *nothing*. A token matching the **wrong** word got `align_status: ok` and a healthy score — the *silently wrong* state §1 exists to abolish, re-entered through the door opened to close it |
| **R14-C4** | A hallucinated token was promised a §9.1 span, but every span requires a character address and a hallucinated token has none by definition |
| **R14-C5** | `ht` word sync materially **worse** and undisclosed — Whisper-family WER on Creole is far above `en`/`fr`/`es` and its failure mode is *fluent* hallucination. A new inequity created by the fix, on the population with fewest alternatives |
| **R14-C6** | `spec:373` still routed `ht` to a Phase 0 blocker three lines from where it was marked closed |
| **J14-C1** | The quote still reported `no_normalizer: 41` → *"word sync will not work"* **before payment**. `no_normalizer` blocked *prediction*; it does not block *transcription*. **The product was discouraging its most under-served population from buying the feature the re-architecture had just delivered to them** |
| **J14-C2** | The spike directed adding Google to the subprocessor list; `CLAUDE.md` had zero occurrences of Google or Gemini |

## The pre-payment disclosure question, adjudicated

Halo argued the pre-payment disclosure had become *unimplementable* — transcription
quality is knowable only after synthesis. Jury sustained the finding and disputed
the characterisation:

> *The prediction-era input was never a per-document measurement. It was a
> **static per-language capability fact** — do we own a normalizer for `ht`.
> Observation has an exact analogue: **does transcription meet a stated accuracy
> bar for `(lang, voice)`.** Same arity, same producer stage, same payload slot.
> **No class of disclosure has been lost. One input has been orphaned and its
> replacement has not been named.**

Directive: replace, do not delete; state it as a **prior**, not a guarantee; and
close the loop with money where the delivered render is materially worse than the
disclosed prior.
