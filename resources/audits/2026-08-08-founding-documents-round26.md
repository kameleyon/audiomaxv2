# Audit Record — Founding Documents, Round 26

- **Date:** 2026-08-09 · **Subject:** SPIKE A's result as recorded in the roadmap and spec, plus `aligner/spike-a/`
- **Reviewer:** Halo · **Response:** v26
- **Authorship provenance:** findings by Halo; **transcribed by the audited party.** States what was true at the ruling; fixes made after it are listed as *open at ruling*.

## Verdict

**FORECLOSES — 2 Blocker · 3 Critical · 8 Major · 4 Minor.** Six items blocking a
commit.

This is the audit that most justifies running Halo at all. The gate was **green**
— `doc-check` exit 0, self-test 54/54 — and **every finding below is invisible to
it**, because no guard reads `aligner/spike-a/out/`. A headline can contradict its
own artifact and exit 0.

## The two Blockers, both the author's

**H26-B1 — a failing measured result was deleted in the same edit that declared
its metric unmeasurable.**

The bar is `matched_within_drift_pct`, fixed at `roadmap:199` before the run, and
the drift it sits inside is defined at `spec:649-651` as *"displacement between a
matched token's timestamp and the position implied by **its neighbours**."*

> *That quantity is **self-referential. It needs no external reference at all.**
> It was measured. It is on disk: **70.8 / 77.3 / 79.2**, `passes_matched_bar:
> false` in all three languages. Round 25's record cites it. **That number now
> appears nowhere in either document.***

What is genuinely hard to score — span overlap against a Whisper reference — is a
metric the **author substituted** (`reference.py:10-13`), not the bar the roadmap
set. Halo:

> *A failing measured result was reclassified as unmeasurable and the failing
> figure removed. That is the exact move `roadmap:186` forbids — "a scope chosen
> after the measurement is a scope chosen to make the result look good" —
> executed on the metric instead of the scope.*

**Four cheaper falsifications were available and none was taken:** score **starts
only**, since §6.1's bound is on a timestamp not a span, and `reference.py`
already computes it; **triangulate** — two mechanisms with uncorrelated error
models agreeing on starts to 1.9 ms *bounds the common error*, and that was
reported as an offset instead of as the bound it is; **construct** ground truth by
synthesizing each word as its own call and concatenating with known silence, ~25
calls and no annotation; or hand-annotate one 12-second clip, ~20 minutes.

> *Calling the bar unmeasurable while the falsification costs half an hour is a
> scheduling decision dressed as an epistemic limit.*

**H26-B2 — the forced-alignment run deleted every token the fixtures exist to
test.** `fa.py`'s `romanize()` stripped non-alpha characters, so `1984`, `3`,
`47`, `52` and `1,250` were removed **before alignment** — 24 display words became
19. `fixtures.json:8-12` states the fixtures' purpose: *"Every one contains at
least one token whose SPOKEN form differs from its DISPLAY form… A fixture of
plain prose would pass trivially and tell us nothing."*

> *`fa.py` converted them into plain prose.* And it corrupts the numbers it did
> report: MMS_FA was handed a transcript missing "nineteen eighty-four" against
> audio containing it, with no skip token, so unmatched audio is absorbed into
> neighbouring spans — *"a plausible mechanical explanation for why a
> frame-accurate method returned a median IoU of only 57.5%, and it means the low
> overlap the 'unmeasurable bar' finding is built on may be the instrument for
> the **fifth** time."*

## The three Criticals

**H26-C1** — *"Match rate 100% all three languages; hallucination 0%"* is
contradicted by the only artifact (`es` 95.5/4.3, `fr` 91.7/9.1) **and that file
predates the corrected `es`/`fr` audio it is credited against.**

**H26-C2** — **§6.1 does not specify forced alignment; it repudiates it.** It
opens *"This section is reversed from v1-v14… **The premise is false**"* and
specifies `synthesize -> transcribe -> match`. The roadmap credited the spec with
a position it took and abandoned. The coherent shape is `ASR -> FA -> match`,
where FA is a **refinement stage, not a replacement** — it cannot be first,
because the only transcript available before ASR is the display text, which is
§6.2's failure verbatim.

**H26-C3** — **no table holds "SPIKE A's matrix."** `spec:1028` says the quote
computes the voice-dependent blocker from it; no migration creates it, and
`voices` (`spec:1115`) has no sync column. *"The single pre-payment word-sync
disclosure currently terminates in a lookup with nowhere to look."*

## Majors of record

`H26-M1` `+2 ms` is a **signed** median set against an **absolute** one — not
comparable, and the two are computed by different files · `H26-M2` `+2 ms` is the
best two of six values; the **held-out** set reads **−18 / −36 / −35 ms** ·
`H26-M3` the calibration that "generalised" was fit and scored against **two
Whisper variants** — agreement, not accuracy · `H26-M4` the voice finding is
**two tokens** on one 8-second clip (15/17 vs 17/18 vs 18/18) and exists only as
prose in a JSON comment · `H26-M5` the holdout **confounds the variable it was
built to control** — `es` was fit on one voice and scored on another · `H26-M6`
the cost claim has **no artifact**; the only timing on disk is 1.3× realtime
including model load, not 0.162× · `H26-M7` **63 seconds of audio total**, 8–12 s
per clip — accumulating drift cannot appear by construction, so nothing speaks to
a 9-hour book · `H26-M8` the comparison excludes short frequent function words,
biasing toward easy tokens, at n = 14–21.

## Forecloses — three, all schema-level

1. **`voices` has no sync-quality field**, so a voice picker cannot disclose, and
   the `render_specific` remedy is reachable only by paying $1.35–$32 to find out.
2. **No store for the matrix** (H26-C3).
3. **`J17-C3` open** — a token matching no display text is excluded from the
   highlight map with disclosure undecided. On a client this becomes **WCAG 2.2
   SC 4.1.3**: a state change conveyed to sighted users by a highlight that stops
   moving, with no programmatic equivalent.

## On `hallucination_rate` — do not retire it

Since FA cannot be first, ASR still invents, and FA then gives the invented token
a **frame-accurate** timestamp — *"removing the timing wobble that might
otherwise have flagged it."* The two halves have opposite symptoms: an invented
word **freezes** the highlight; an unnormalised word makes it **skip**. `fr`'s
9.1% is the second kind counted as the first, and it feeds the pre-payment
disclosure.

## The line the author has to keep

> *The standing lesson — "a defect in the measurement inflates the tail and
> leaves the median alone" — is correct, well-earned, and **was applied
> selectively**. It was used to discount the failing tail. It was **not** applied
> to the median that survived: `+2 ms` is a signed median, on a fitted set, over
> a uniqueness-filtered sample of 16 words, from a transcript with the hard
> tokens deleted, on twelve seconds of audio. Four instruments were wrong before
> one was right. On the evidence in `out/`, **the fifth was wrong too, and it is
> the one the good news came from.**
