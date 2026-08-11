# Audit Record — SPIKE A Accessibility Review, Round 34

- **Date:** 2026-08-10 · **Subject:** Phase 0 item *"Halo reviews Spike A (alignment engine language coverage)"* — `aligner/spike-a/out/`, `aligner/spike-d/out/`, `docs/architecture/0006`, spec §6.1/§7.1a, `README.md`, `docs/glossary.md`, `20260809000300_voice_langs.sql`, `worker/src/match/`, `worker/src/normalize/`
- **Reviewer:** Halo · **Prior Halo verdict:** round 26 (`FORECLOSES`)
- **Authorship provenance:** findings by Halo; **transcribed by the audited party.** Halo asked that this transcription be verified by ID, noting *"`H34-C1` exists because a finding of mine was faithfully transcribed into an audit record and then never carried into the document that implements it. **A faithful record is not a closed finding.**"*

## Verdict

**`FORECLOSES` — 0 Blocker · 2 Critical · 6 Major · 4 Minor · 1 Polish.**
**Both Criticals block a commit under `CLAUDE.md`'s gate.**

> *Neither is a disputed number: **every figure in the brief reproduced exactly**,
> and I could not break the measurement. What I broke is what reads it.*
>
> *Round 26's line was "the gate was green and every finding was invisible to
> it." That is no longer true of the figures. **It is still true of the
> sentences.***

## Round-26 findings, resolved by ID

**`H26-B1`** *(failing result deleted while its metric declared unmeasurable)* —
**FIXED in the artifacts and the schema · OPEN in spec §6.1** → **`H34-C1`**.
`voice_langs`' `voice_langs_evidence_floor` requires `sync_metric =
'matched_within_drift_pct'` and `sync_drift_bound_ms = 250` before
`at_or_above_bar` may be stored, naming `H26-B1` as its reason.
**`H26-B2`** *(`romanize()` stripped the tokens the fixtures test)* — **FIXED.**
`spokenForms()` emits year forms, digit runs, abbreviations and elision splits;
`groupedDigitForm` explicitly refuses the old digit-concatenation.
**`H26-C1`** **FIXED** · **`H26-C2`** *(§6.1 repudiates FA; the roadmap credits
it)* — **OPEN, and now load-bearing on a cost figure**: SPIKE E's `$0.32–$0.43`
rests on a **1.916** multiplier that exists only if there is an FA stage. Folded
into `H34-C1`. · **`H26-C3`** **FIXED, and well** — `voice_lang_sync_grade()`
coalesces to `unmeasured`, so *"the non-NULL guarantee is structural, not a
convention."* · `H26-M1`/`M2`/`M5` **SUPERSEDED** (FA is in no product path;
live again if `H26-C2` resolves toward FA) · `H26-M3` **FIXED durably** —
`sync_metric` is an enum, so `agree_within_250ms_pct` *"can never be
`at_or_above_bar`"* · `H26-M4` **SUPERSEDED and REVERSED** · `H26-M6` **FIXED** ·
**`H26-M7`** **OPEN** → `H34-M6` · `H26-M8` **SUPERSEDED** ·
**`J17-C3`** **OPEN**, correctly owned and dated *(Atlas · 2026-08-22)* — *"it
now has a **sibling that nobody has noticed** — `H34-C2`."*

**Round-26 foreclosure items 1 and 2 are closed.**

## `H34-C1` — spec §6.1 still declares the bar unmeasurable

§6.1 still reads: *"**SPIKE A (2026-08-09): this bar is not evaluable with the
references available**"* and prescribes *"hand-annotated ground truth on one
short clip, or a second independent forced aligner."*

**Both sentences are false and the artifacts falsify them.** The bar has been
evaluated end-to-end at chapter length in two languages —
`spike-a-english.json` `clips[kind="chapter"].matched_within_drift_pct` = **90.0**
(CI95 88.3–91.6, 1246 words, 453.73 s); `spike-a-voices.json` = **78.4–86.3** on
six 1186-word French clips — **by neither route §6.1 prescribes.** No clip was
hand-annotated; no second aligner was used.

**The same file contradicts itself 950 lines later:** §7.1a carries the correct
result in full. **And the schema enforces a bar the spec says is not
evaluable.**

> *Applied to `CLAUDE.md`'s precedence rule, the spec wins and is **wrong** — and
> the sentence that wins is the one telling an engineer word-sync quality cannot
> be gated on. On the headline feature, for the population `CLAUDE.md` names
> primary.*

*(Owner: **Forge** with **Scribe** · due **2026-08-13**. Grep the claim, not the
identifier: `not evaluable`, `references available`, `hand-annotated`,
`second independent forced aligner`.)*

## `H34-C2` — the re-sync skips display words that have no name anywhere. WCAG 2.2 SC 4.1.3

`ADR-0006` ships a forward-only re-sync **bounded at 200 tokens**. The
implementation returns `skipped_display_tokens` (`worker/src/match/match.ts:92`,
assigned `:420`) — **display tokens the cursor jumped over, which receive no
timestamp and therefore no highlight.**

Measured on committed data (`spike-a-voices.json`):

| clip | `resyncs` | `resync_skipped_display_tokens` |
| --- | --- | --- |
| `fr-long-narrateur-r1` | 2 | **25** |
| `fr-long-feminine-r2` | 1 | **9** |

**The disclosure search is the finding:** `grep -rn "resync" supabase/` → **0**.
It is not a `SpanReason`, not one of the nine `align_reason[]` values, has no
column in `segment_renditions`, no i18n catalogue key, and no build item. Its
seven mentions in the specs and roadmap are **every one a measurement figure,
never an obligation.**

> *Audio continues. The highlight stops for a paragraph, then reappears further
> down. To a screen-reader user that is indistinguishable from the audio having
> drifted, the page having ended, or the app having frozen — **and there is no
> programmatic equivalent of the state change.***

**It inverts constraint 1 in a way the constraint does not anticipate:** the data
**is** captured server-side and is then dropped between the matcher and the
schema. **Constraint 2 is engaged directly** — a degraded path in the primary
flow that is *reasoned* but neither *visible* nor *announceable*.

**Why Critical where round 32 held the camera gap at Major:** that one is named,
owned and dated — a scheduled decision. **This is an unrecognised obligation, and
unrecognised obligations do not acquire owners by the passage of time.** The code
is **already merged** into the product path.

> *`ADR-0006` came within one sentence of catching it — it weighed the user cost
> of the option it **rejected** and did not bound the user cost of the one it
> **accepted**.*

*(Owner: **Atlas** with **Nexus** and **Tongue** · **co-scheduled with `J17-C3`,
not after it** — they are two halves of one question, a display-side gap and an
observation-side gap. Classification: `render_specific` — `narrateur-r1` re-syncs
twice where `-r2` re-syncs zero times on the same text.)*

## Majors — 6

**`H34-M1`** the per-language obligation is discharged unevenly and the two
committed documents a reader reaches first do not say so — one says the
opposite. `asr_coverage_ceiling` exists on **11 clips: 9 `fr`, 2 `en`, zero
`es`.** Spanish's largest bar figure is **68.2 on 22 words**, while
`es-para.wav` (222 words, 74.93 s) **exists, was synthesized and was
transcribed** — the marginal cost is one decode. Disclosed in the gitignored
roadmap and the glossary; **not** in `ADR-0006`, `README` or spec §7.1a.
`ADR-0006` concludes *"Same bar, opposite blocker, and the difference is the
language"* — an enumeration over `{en, fr}` that reads as complete. `README`
states *"Coverage for `en`/`es`/`fr` is now measured, not uncertain"* — **rule 4
violated nine days after it was written.** *(Scribe with Forge · 2026-08-13.)*

**`H34-M2`** **`Access` owns nothing in the roadmap** — one hit, and it is the
word "Accessibility". `CLAUDE.md`: *"Halo audits accessibility; Access builds
it"*, and *"the roadmap is the sole authority for reviewer assignment."*
`J29-m2` was fixed in `CODEOWNERS` — the advisory artifact — and not in the
authoritative one. **`H34-C2`'s announcement, `J17-C3`'s disclosure, the four
`sync_grade` strings and the live region that carries them have no builder
assigned anywhere.** *(Orchestrator with Scribe · 2026-08-13.)*

**`H34-M3`** SPIKE D's disclosure conclusion is stronger than its data. The
recogniser signal is correctly killed (0.9645 vs 0.9603, nested ranges). But
`layout_confidence` — 0.911 correct (min **0.7959**) vs 0.3193 wrong (max
0.8214) — was judged by a **two-sided** criterion when **disclosure needs only
one side**: at 0.7959 there are **zero false positives across all 27
correctly-ordered reads by construction**. The unknown is *recall*, and **the
artifact emits only min/max/mean**, so the number deciding blanket-warning vs
targeted-announcement exists in no committed run. *(Probe for the artifact ·
2026-08-14, so Halo+Comply · 2026-08-17 is decidable. **Declared conflict:**
Halo owns that decision and asks Optic or Access to review the call.)*

**`H34-M4`** `README` and `docs/architecture/README.md` both name round **31** as
Jury's latest; rounds 32 and 33 are committed. **Eighth recurrence.** The
paragraph beneath documents it seven times and announces the durable fix — *"none
of the three may state a verdict without naming the round file"* — which was
obeyed, with a stale round named. *(Scribe · 2026-08-12. Recommend a guard, not
a rule.)*

**`H34-M5`** the en-GB/en-US gap is **both** a correctness and an accessibility
defect, and only the correctness half is measured. `orthography_probe`: 25 absent
→ 11 after respelling, 14 explained, ceiling +1.1 pp. **The probe moves the
ceiling, and the ceiling is not the bar** — nobody has run the fold and re-scored
`matched_within_drift_pct`, so *"the number a British-spelled reader would
actually experience does not exist."* *(Forge · 2026-08-22, plus a re-score.)*

**`H34-M6`** `H26-M7` open — no committed run bounds drift accumulation over a
book; longest ever scored is 453.73 s against nine hours. *(Forge · 2026-08-16;
the record must carry the known understatement.)*

## Minors — 4 · Polish — 1

**`H34-m1`** the glossary's *"measured and below bar for `en`/`es`/`fr`"* sits 62
lines before its own correction *(Scribe · 2026-08-13)* · **`H34-m2`** **the
working tree was not clean during this audit, contrary to the orchestrator's
brief** — `aligner/spike-e/measure.py` and `tests/` appeared mid-audit. Halo
re-hashed the three artifacts its findings rest on and **all three are
byte-identical to HEAD**, so nothing is affected — *"but a brief asserting a
clean tree is a relay claim in `J33-M3`'s exact shape, and a concurrent writer
during an audit is a hazard the process does not currently name."*
*(Orchestrator · immediate)* · **`H34-m3`** `J33-M4` open — the glossary's *"3 of
6 long clips"* still carries no language · **`H34-m4`** `J33-M1` open —
`ADR-0006` is read by no guard, and **`H34-C2` is a direct consequence of that
blind spot** · **Polish `H34-p1`** `docs/help/` does not exist; every disclosure
this audit turns on becomes a sentence a blind user hears, with no home and no
draft *(Guide with Proof · Phase 2)*.

## What Halo credits, and will not soften

**The shipped posture is honest.** `voice_langs` ships every pair `unmeasured`
with **no seed** — *"A seed that wrote a grade would assert a measurement nobody
has made."* `voice_langs_evidence_iff_measured` uses `num_nulls()` and closes the
fail-open hole explicitly. The bar itself is deliberately **not** enforced in a
CHECK: *"partial enforcement that looks total is worse than none."*
**"Nothing in this repository lets a user infer sync works. I looked for it and
it is not there."**

**`ADR-0006` is a strong document and the Critical is not a retraction of that.**
*"Its defect is not carelessness. It is that a decision document reasoned
carefully about the user cost of the option it rejected and not about the user
cost of the one it accepted — a failure mode no amount of care catches, which is
why it needs a reviewer."*

**The English arm did the hard thing** — `supports_chapter_length_claim` computed
and falsifying inside its own artifact, `_length_effect_reading` refusing its own
delta, `_limits` naming *"ONE VOICE, ONE PROVIDER, NO REPLICATE"* first.
**Zero figures moved in the author's favour.**

> **For the owner, plainly.** Nothing passes in any language. English is **90.0**
> against **95**, and **91.6** at the top of its CI95 — it misses at its most
> generous, on one voice, one replicate, one text. French cannot pass on its
> transcript whatever the matcher does. **Spanish has never been measured on
> anything longer than 22 words**, and the two languages measured came back with
> opposite blockers, so nothing known predicts it. **This is not a launch state,
> and English-only is not a rescue.**

## The line the author has to keep

> *Both of my Blockers are closed, and closed in the right places — one in a
> database constraint that names the finding as its reason, one in a normalizer
> whose tests assert the exact tokens that were being deleted. **That is the best
> remediation this project has produced and I want it said before the rest.***
>
> *Then I greped for the sentence instead of the number. **`H26-B1` is closed in
> five documents and open in the one that outranks all five.** And `ADR-0006`,
> the best document in the series, decided a matcher that skips up to two hundred
> display words and weighed the user cost of the option it rejected.*
>
> ***The project has learned that a figure needs an artifact. It has not yet
> learned that an obligation needs one too.** `resync_skipped_display_tokens` is
> emitted by the product, measured at 9 and 25, and named in no spec, no schema,
> no enum and no catalogue — a number with perfect provenance and no owner.*
>
> ***Accessibility is the product. Right now it is the only part of the product
> with no builder in the plan.***

*(Rule 6: `H34-C1`–`H34-M6` close only when Halo re-runs the check —
`grep -F "not evaluable with the references"` over `resources/specs/`, and
`grep -rn "resync" supabase/ resources/specs/ resources/roadmap/` returning a
disclosure rather than a figure.)*
