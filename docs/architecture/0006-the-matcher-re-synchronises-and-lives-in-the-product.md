# ADR-0006 — The matcher re-synchronises, and it lives in the product

## Status

**Accepted 2026-08-10.** Implemented by Forge; measured on the SPIKE A long
corpus. Supersedes no ADR — it **completes** [ADR-0002](0002-observe-what-was-spoken-do-not-predict-it.md),
which decided that word sync is *observed* and named a "match step" that then
existed only inside a measurement script.

Design intent, not gate approval — see [the status note](README.md#what-accepted-means-here-and-what-it-does-not).

> **Read the headline before the improvement.** The matcher got substantially
> better and **the bar did not move**:
>
> **Even a perfect matcher cannot clear 95 on chapter-length FRENCH audio with
> faster-whisper `base` — the ceiling is 3.0–5.2 pp below the bar on all six
> long clips — while the same measurement puts short French clip ceilings above
> the bar, so within French the constraint is length-dependent.**

> **SCOPED 2026-08-10, THE SAME DAY, BY `spike-a-english.json` — read this
> before the sections below.** For one revision the banner above and three
> passages in this ADR said *"chapter-length audio"* with **no language on
> them**, and `README.md`, `docs/glossary.md`, spec §7.1a and `ADR-0001` copied
> them that way. **Every ceiling quoted in this ADR is correct. The scope of the
> sentences around them was not.** All nine clips it rests on are French —
> `spike-a-voices.json`'s `clips[].lang_code` is `fr` in every row.
>
> **English is DRIFT-bound. French is ASR-bound. Same bar, opposite blocker.**
> The English recogniser emits **98.0%** of display tokens in a form the matcher
> could accept — **above** the bar — and this matcher converts only **90.0%**
> into placements inside 250 ms. **English still fails; nothing passes.** What
> changes is *why*, and the *why* is the product decision.
>
> **Nothing in this ADR is withdrawn.** The decisions it records — forward-only
> re-sync, ranked folds, the matcher living in `worker/src/match/` — are
> unaffected, and so are the French figures. What is corrected is a
> generalisation that was never measured. See
> [the per-language reading](#the-blocker-is-per-language-and-english-is-drift-bound).

## Context

### The failure: three of six long clips desynced, and the diagnosis sat in a comment

The shipped matcher was **monotonic greedy with a six-token lookahead and no
re-sync path**. Its design admits no recovery: once the cursor advances past a
mismatch, every later token is scored against the wrong region and the clip is
lost from that point on. That is not a tuning weakness, it is the algorithm.

On six long French clips it produced two populations rather than a spread:

| clip | `matched_within_drift_pct` before |
| --- | --- |
| `fr-long-locked-r1` / `-r2` | 71.4 / 71.3 |
| `fr-long-narrateur-r2` | 69.5 |
| **`fr-long-feminine-r2`** | **20.9** — desynced |
| **`fr-long-narrateur-r1`** | **25.5** — desynced |
| **`fr-long-feminine-r1`** | **29.1** — desynced |

**Three of six clips were inadmissible.** `J30-M8` recorded the consequence and
`round 31` accepted Forge's recommendation to *state the coverage rather than
re-measure*, on the grounds that fixing it *"is ADR-0002 territory that moves
every published figure at once."* This ADR is that territory, entered
deliberately.

### The architectural cause, which is the part worth remembering

**The matcher was `measure.match` — a function inside a measurement script.**
That is why the defect could be diagnosed in a comment and never fixed: the
component the headline feature rests on had no home in the product, so
"improving the matcher" meant editing a spike, and editing a spike to make its
own numbers better is the one thing a spike may not do.

A component that only exists inside the instrument that measures it cannot be
fixed without contaminating the measurement.

## Decision

**1. The matcher re-synchronises, forward only.** When the cursor loses the
text, it searches ahead for an anchor and resumes, rather than degrading for the
remainder of the clip.

- **Trigger: 3 consecutive unmatched tokens.** Anchor: **3 consecutive matching
  tokens.** Symmetric by intent — the evidence required to declare desync is the
  evidence required to declare recovery.
- **Bounded at 200 tokens.** A re-sync that may scan arbitrarily far is a
  matcher with no monotonicity guarantee at all; the bound is what keeps the
  invariant.
- **Forward only.** Backward re-sync would let a highlight move *backwards*
  through the page, which is a worse user experience than a missing highlight
  and breaks the monotonicity rule §6.1 states.

**2. Fallback folds are RANKED, strictly below the exact fold.** An exact match
always wins; a diacritic-folded match is considered only when no exact match
exists; elision forms below that. Ranking rather than merging is what stops a
loose fold from stealing a token that had a correct exact match available.

**3. The matcher moves to `worker/src/match/`, and `measure.py` delegates to it
over a CLI.** The product owns the component; the spike calls the product. The
measurement now scores *the thing that ships*, which is the only arrangement in
which SPIKE A's numbers mean anything.

## Consequences

### It works, and the improvement is large

Same audio, same decode, **two independent runs producing identical figures**:

| clip | before | after | matched of 1186 |
| --- | --- | --- | --- |
| `fr-long-locked-r2` | 71.3 | **86.3** | 887 → 1061 |
| `fr-long-locked-r1` | 71.4 | 85.5 | 891 → 1056 |
| `fr-long-narrateur-r2` | 69.5 | 83.0 | 896 → 1055 |
| `fr-long-feminine-r2` | **20.9** | **80.2** | 284 → 1026 |
| `fr-long-narrateur-r1` | **25.5** | 78.7 | 357 → 1025 |
| `fr-long-feminine-r1` | **29.1** | 78.4 | 400 → 1006 |

**Inadmissible clips: 3 → 0.** Ablated separately, each by reversible patch with
state `A0` reproducing the committed artifact exactly: **re-sync +23.9 pp mean
(range 0 … +45.1)**, **diacritic fold +10.8 pp**, **elision forms +3.5 pp**.

**The control matters as much as the result.** The short `en`/`es`/`fr` figures
— **62.5 / 68.2 / 75.0** — **reproduce byte-identically.** The change is inert
where nothing diverges, which is the evidence that it repairs desync rather than
loosening matching generally.

### And it does not reach the bar — because on long FRENCH audio the bar is not matcher-bound

The measurement is `clips[].asr_coverage_ceiling.coverage_ceiling_pct_any_matcher`
in `aligner/spike-a/out/spike-a-voices.json`, emitted for **all nine clips** —
**all nine of which are French.** That file's `clips[].lang_code` is `fr` in
every row, and it is the whole reason the section below exists.

> **On the best long French clip, 95 of 1186 display tokens appear in the
> transcript in no form the matcher could accept** — so the ceiling for **any**
> matcher is **92.0%.**

| clip | absent | ceiling | vs the 95 bar |
| --- | --- | --- | --- |
| `fr-long-locked-r2` | 95 | **92.0%** | −3.0 |
| `fr-long-narrateur-r2` | 103 | 91.3% | −3.7 |
| `fr-long-locked-r1` | 105 | 91.1% | −3.9 |
| `fr-long-feminine-r2` | 114 | 90.4% | −4.6 |
| `fr-long-narrateur-r1` | 119 | 90.0% | −5.0 |
| `fr-long-feminine-r1` | 121 | 89.8% | −5.2 |

**Below the bar on every long clip, by 3.0–5.2 pp.** `sync_grade` stays
`unmeasured`.

### Within French the constraint is length-dependent, and the control is what shows it

**Quoting only the long clips would make this a claim about the corpus. It is
not — it is a claim about clip length *within French*.** The same measurement on
the 8–10 s clips, 24 display words each:

| clip | ceiling | achieved (`matched_within_drift_pct`) | the gap is |
| --- | --- | --- | --- |
| `fr-short-locked` | **95.8%** — above the bar | 75.0 | **drift** |
| `fr-short-feminine` | **95.8%** — above the bar | 70.8 | **drift** |
| `fr-short-narrateur` | 91.7% — below the bar | 66.7 | drift dominates |

**On 8-second French audio the recogniser emits nearly everything and the loss is
drift; on chapter-length French audio the loss is recognition.**

*(Stated precisely because a control quoted only where it agrees is not a
control: **two of the three** short ceilings clear the bar, not all three. The
third sits at 91.7% — still 25 pp above what that clip actually scored, so drift
remains the binding constraint there and the length contrast holds.)*

**So within French the ceiling is not a constant of the corpus; it is a property
of clip length.** That reframes Phase 6 **for chapter-length French audio
specifically**: the open question there is the ASR configuration — model size,
decode parameters, or a different engine — and further matcher work cannot answer
it. **It does not reframe Phase 6 for English**, where the ceiling clears the bar
and matching and timing are exactly what is left.

### The blocker is per-language, and English is drift-bound

**This section was added 2026-08-10, hours after the rest of this ADR, and it
exists because the sections above were read as general.** They are French. The
generalisation was not measured, and when it was measured it did not hold.

`aligner/spike-a/out/spike-a-english.json` scores English end to end at chapter
length — **1246** display words, **453.73** s of Lemonfox audio, one voice
(`Adam`), `supports_chapter_length_claim` computed by the artifact rather than
asserted by the author.

| quantity | key | value |
| --- | --- | --- |
| end to end | `clips[].matched_within_drift_pct` | **90.0**, CI95 **88.3**–**91.6**, `passes_matched_bar: false` |
| ASR ceiling | `clips[].asr_coverage_ceiling.coverage_ceiling_pct_any_matcher` | **98.0**, `coverage_ceiling_clears_bar: true` |
| what binds it | `verdict.chapter_bound_by` | **`"drift"`**, headroom **8.0** pp |
| re-syncs fired | `clips[].resyncs` | **0** |

**English fails and English is not ASR-bound.** The recogniser emits 98.0% of
display tokens in a form the matcher could accept — **3.0 pp above the bar** —
and the matcher places only 90.0% inside the 250 ms bound. French's ceiling is
**89.8–92.0**, below the bar, so **no matcher can pass French on that
transcript.** Only English's blocker is one that better matching and timing could
remove. **Same bar, opposite blocker, and the difference is the language.**

**The re-sync path never fired on English.** `clips[].resyncs` is 0 — the clip
never lost the text. Under the same matcher **2 of the 6** French long clips fire
re-syncs; the **3 of 6** figure in the Context above is the *pre-repair*
inadmissible count and is a different quantity. Both are true and they are not
interchangeable.

**Read it with its limits, which are larger than the French arm's.** **One voice,
one provider, one replicate.** The French arm needed six clips before it could
say anything about voice at all. **There is no characterised English noise
floor** — the 4.3 pp within-voice figure is Fish at temperature 0.8, and
Lemonfox's sampling behaviour is unmeasured. The 224-word `en-para` clip scores
**93.3** against a **99.1** ceiling and carries
`clips[].supports_chapter_length_claim: false`; the **93.3 → 90.0 difference is
not a length effect**, because `verdict._length_effect_reading` records that the
two clips are **different texts**.

**And the run surfaced a product defect, running in the conservative direction.**
`clips[].orthography_probe` recomputes the ceiling after respelling the **display
text** from en-GB to en-US against the **same observations from the same decode**:
**98.0 → 99.1**, because **14 of the 25** absent tokens were British spellings the
recogniser wrote in American form. Those words were **recognised correctly and
failed to match** — a `worker/src/normalize/spokenForms` gap, not an ASR limit,
and it costs coverage on most English published outside the United States. It is
a **probe, not a result**: no audio was re-synthesized, so **98.0 is if anything
understated.** *(Build item: roadmap Phase 4.5, owner Forge.)*

### The derivation is a strict upper bound, and it is falsified rather than asserted

A display token counts as absent only when **no contiguous run of 1–3 observed
tokens** equals any sequence in that token's `forms` or `looseForms` from
`worker/src/normalize/spokenForms`, and no grouped-digit form covers it — *"exactly
the relaxations `worker/src/match/matchTokens` can apply, so a token absent here
is one the recogniser did not emit in any form the matcher could accept, and NO
matcher can place it."* The window is **3** because that is the longest sequence
`spokenForms` emits (`mille neuf cent`).

**What `spokenForms` does NOT fold is now measured, not assumed:** it folds
diacritics and elisions and **does not fold en-GB against en-US**, which costs
**14 of 25** absent tokens on the English chapter clip. Because the ceiling is
computed with the product's own tables, **every ceiling in this ADR inherits that
gap and is therefore understated, never overstated** — the bound stays strict.

It is **order-free and one-to-many-free on purpose** — it ignores monotonicity
and lets one observation serve several display tokens — *"so it is a STRICT
UPPER BOUND and a real matcher can only do worse. It is NOT a prediction of what
a better matcher would score."*

And it is checked: **`CTL-CEILING`, three controls**, including *halve the
transcript and the ceiling must fall.* *"A 'ceiling' that ignored its own input
would be a constant wearing a derivation."*

**Two keys, no collisions, deliberately.** `coverage_ceiling_pct_any_matcher` and
`display_tokens_absent_from_transcript` **name no other quantity anywhere in the
repository**, and the block **refuses to restate** `match_rate_pct` or
`matched_within_drift_pct` — it names them instead, *"so they cannot drift out of
agreement with themselves."*

*(Corrected 2026-08-10. This read *"appear **nowhere else** in the
repository"* — a stronger claim than the one that matters, and already false when
written: the same commit added `coverage_ceiling_pct_any_matcher` to
`doc-check.mjs`'s `[ART-FIGURE]` `TRACKED`, which is the guard that makes the key
load-bearing, and `spike-a-english.json` now emits it as well. **The property
worth having is that no OTHER quantity wears these names**, which survives every
new site; a literal claim a `grep` disproves does not, and this ADR is the wrong
document to leave one in.)*

> **A withdrawn figure, recorded because the withdrawal is the lesson.**
> An earlier draft of this ADR carried *"~89.5% after drift"* as the ceiling.
> **89.5 is `match_rate_pct`** — the coverage this matcher *achieved*, before the
> drift bound — not a ceiling of any kind. **No post-drift ceiling has ever been
> measured**; the measured post-drift figure is `matched_within_drift_pct` =
> **86.3**. Restating an existing key as a new derived quantity is the `J29-M1`
> shape, and it reached a draft of the very ADR that documents the fix for it.
> Caught before publication, by the artifact rather than by review — which is
> the argument for emitting figures into artifacts instead of computing them
> ad hoc.

### `J30-M8` is superseded, and its finding reverses

The old bound — *"at most 1.9 pp between voices, over 2 voices"* — **was an
artifact of the desync.** With all six clips admissible:

- **Maximum between-voice difference: 7.9 pp** (was 1.9).
- **10 of 12 pairs significant** (was 0 of 2).
- **`feminine` is covered for the first time** — it previously had zero
  admissible long clips.

**Voice choice is a real word-sync variable.** But it must be read against the
noise floor this measurement finally has:

> *"READ IT AGAINST THE NOISE FLOOR, NOT ZERO: the same voice re-sampled differs
> by up to 4.3 pp, and 1 of 3 within-voice replicate pairs is itself significant
> at .05. A between-voice difference smaller than 4.3 pp is not evidence of a
> voice effect."*

This is what makes `voice_langs.sync_grade` a per-`(lang, voice)` column rather
than a per-language one, and it is the first evidence that actually supports
that shape — the original 12-pp claim never had a noise floor at all.

### Every published SPIKE A figure moves

That was the accepted cost of entering this territory, and it is why round 31
declined to do it inside a documentation finding. The roadmap's handover section
lists the sites; the drift intervals in particular are **not final** — see below.

### An obligation this creates: the drift intervals must be re-scored

`J30-m1` is closed at the *derivation*: `groundtruth.py` now emits
`slope_ci95_ms_per_s`, `slope_se_ms_per_s`, and names its method —
`"OLS t interval, b ± t(0.975, n-2)·se(b)"`. Recomputed on the **same** data as
the published table, it **confirms `J30-m1`: none of the published intervals
reproduce.**

| corpus | recomputed | published |
| --- | --- | --- |
| `en-gtlong` | **[−0.896, +0.641]** | −0.900 / +0.650 |
| `es-gtlong` | **[−2.793, +1.477]** | −2.746 / +1.465 |
| `fr-gtlong` | **[−2.016, +0.425]** | −1.966 / +0.427 |

**These numbers are not final and must not be presented as such.** They will
move again when `groundtruth.py --score` is re-run under this matcher, and
**that re-score has not been run.** *(Owner: Forge · due 2026-08-16.)*

### A stale route was reachable in code, and is now gone

`J29-C3` was closed in the documents on 2026-08-09. It was **not** closed in
code: `tts.py`'s provider dispatch ended in a **bare `else` that sent any
unrecognised provider string to Gemini-via-OpenRouter**. A retired route was
**reachable by default** — constraint 2 and constraint 7 in executable form.

**No wrong audio exists** (`fixtures.json` records `fish`), so no measurement is
affected. `synth_openrouter` is deleted and the dispatch now refuses an unknown
provider and names the two §3.5 routes. **Recorded as closed in code, distinct
from the documentation closure** — a fix that lands in prose and not in the
dispatch is the defect this project has filed under four separate IDs.

### What we accepted, stated plainly

- **The diacritic fold's +10.8 pp is inflated relative to production.** The long
  fixture is written in **flat ASCII** while `fixtures.json` is properly
  accented; on a correctly-spelled document most of those tokens would match
  **exactly**, and the fold would contribute far less. The ablation measures the
  fixture's spelling as much as the fold's value.
- **The fold merges `ou`/`où` and `ano`/`año`.** Accepted as better than dropping
  the token — a highlight on the right word with the wrong diacritic is a
  correct highlight; a dropped token is a gap — but it is a real collision and
  it is ranked below the exact fold so it can only ever act where nothing exact
  was available.
- **Re-sync cannot repair what was never recognised.** It closes the desync class
  and leaves the recognition class untouched, which is precisely why the ceiling
  above is where it is.

## Alternatives considered

**Do nothing; state the coverage instead** — Forge's own round-31
recommendation, and correct *at that time*: fixing the matcher moves every
published figure, and smuggling that into a documentation finding would have
been worse than the finding. Superseded by this ADR because it was entered
deliberately, with ablations, a control, and a re-score obligation recorded.

**Backward re-sync.** Rejected: a highlight that moves backwards through the page
is worse for a reader tracking audio against text than a missing highlight, and
it breaks the monotonicity invariant §6.1 states.

**Unbounded re-sync search.** Rejected: without the 200-token bound there is no
monotonicity guarantee left to enforce.

**Merging the folds instead of ranking them.** Rejected: a loose fold that can
outrank an available exact match will steal tokens, and the failure would be
invisible — a wrong highlight looks exactly like a right one.

**Leaving the matcher in `measure.py`.** Rejected as the root cause. See Context.

## References

- Supersedes the bound in `J30-M8`; closes `J30-m1` at the derivation; closes
  `J29-C3` **in code**.
- Completes [ADR-0002](0002-observe-what-was-spoken-do-not-predict-it.md) — the
  "match step" it named now has an implementation in `worker/src/match/`.
- Spec §6.1 (the match step, monotonicity, the 250 ms drift bound), §7.1a
  (`sync_grade` and its evidence floor).
- Roadmap Phase 0 (SPIKE A), Phase 6 (transcription + match sidecar), and the
  handover section listing every figure this moves.
- Audit records: `resources/audits/` — `J30-M8`, `J30-m1`, `J29-C3`, `J31-M5`.
