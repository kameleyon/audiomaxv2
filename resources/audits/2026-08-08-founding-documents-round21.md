# Audit Record — Founding Documents, Round 21

- **Date:** 2026-08-08 · **Subject:** the round-20 repairs, plus **SPIKE A's first run**
- **Reviewer:** Halo · **Response:** v21
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 54/54

> Written late alongside `-round20.md` — see the note there (J22-C2).

## Verdict

**ENABLES — 0 Blocker · 3 Critical · 15 Major · 4 Minor.**

**The foreclosure is closed.** Halo returned FORECLOSES in round 20 on exactly
one defect and traced it link by link this round:

> *`§3.5 → segment_renditions.status → §8.2 → catalogue key → en/es/fr string`,
> every link present and owned. **The refusal now produces a sentence.** Say that
> plainly.*

## The three Criticals

| ID | Finding |
| --- | --- |
| **H21-C1** | The accessibility gate's **own ADR** still specified an unconditional failure — a specimen requiring the harness to fail on *"an `align_reason` with no string in an unsupported language"*, which every `align_reason` satisfies by design. The document defining conformance specified a gate that could never go green. `H20-C2` alive in the artifact that defines the gate |
| **H21-C2** | `README:398` told a blind reader an unsupported language *"loses word highlighting but still narrates correctly."* It narrates **not at all** — refused at the no-route row, no audio. The public artifact promised degraded-but-audible where the design refuses outright. **The most damaging of the three for the primary population** |
| **H21-C3** | **SPIKE A measured no drift.** `DRIFT_MS = 250` was defined and never applied; `matched_within_drift_pct` was `len(matched)/len(display)` — *"a plain match rate wearing the name of a bounded quantity"* — while `p95` was emitted `null` and `passes_matched_bar: true` was asserted anyway |

## The finding about the measurement, which is the round's real content

**H21-M14 — the matcher was amended after a below-bar result.** First run
91.7/90.9/91.7; a spoken-form normaliser was added; second run 100/100/100. The
drift bound and the language scope are fixed and dated *before* a run precisely
so neither can be chosen to make a language pass. **Nothing fixes the matcher.**

And the harness had predicted it. `fixtures.json`, written hours earlier:

> *"If a run reports 100% matched and these were not resolved by the normalizer
> path, the harness is measuring the wrong thing."*

The tripwire was written and never wired up — `expect_hard` appears in no code
(J22-M2).

## The guard findings

- **`SD-UNWRITTEN` is blind to `H\d\d-`** — its own reviewer's prefix. *"The
  guard was written after `J19-M3` fired on `CLAUDE.md` and it was shaped to the
  ID that fired, not to the class."*
- **`SD-ROSTER` produced a false positive whose cheapest fix is mis-citation** —
  it cannot tell a roster from a citation, so three ADRs now cite `-round19.md`
  for findings recorded in `-round18.md`. **The extension's three catches are
  three new wrong citations.**
- **`DOCS` extended 7 → 13; no check extended with it.** *"Thirteen files read,
  two files checked."*

## SPIKE A — Halo's accessibility reading

1. **`transcription_unreliable` is now reachable on all three supported
   languages**, while every artifact writes it as a property of *unsupported*
   ones. As dictated, the string *"word sync is unreliable in an unsupported
   language"* **would tell a French user their French is unsupported** — and is
   unreachable where it is true, since an unsupported language is refused before
   synthesis.
2. **A sub-95% match rate is not a reason to withhold the feature; it is a reason
   to change what the user is told before paying.** §8.2 offers one binary lever.
   A 92% document is neither available nor blocked, and §6.3's promised sentence
   — *"word sync will not work for this document"* — is **materially false at
   92%. That sentence is more harmful than the 8% gap.**
3. **The misses are systematically the highest-information tokens** — dosages,
   page references, sample sizes, years, honorifics. *"A sighted user tracking a
   highlight past `1,250` loses nothing; a blind user relying on sync to hold
   position loses the number the sentence exists to deliver."*
4. `hallucination_rate` conflating *engine invented a word* with *matcher failed
   to normalise* is an accessibility defect as well as a metric defect: it is the
   only metric that can see the fluent-hallucination failure mode, and conflated
   it reports 12% on clean English.

**None of this forecloses. All of it changes the copy.**

## Halo's closing line

> *Sixth round running, the defects are at the seam of the previous round's fix.
> This round the seam is visible in one sentence: **every Critical I found is in
> an artifact `DOCS` now reads and no check inspects.** Extending the file list
> was the right instinct and half the remedy. The other half is a guard —
> because five rounds of evidence say that anything protected only by an author's
> memory of where a number lives will be wrong again next round.*
