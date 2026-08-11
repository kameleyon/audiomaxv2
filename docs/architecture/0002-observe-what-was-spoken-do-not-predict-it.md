# ADR-0002 — Observe what was spoken; do not predict it

## Status

**Accepted 2026-08-08.** Decided by **Jo**, the product owner, from production
evidence, mid-audit. Finding ID **`R14-A1`**; entered the design as spec v15 and
is current in v19.

**Supersedes the decision recorded as *"forced alignment, not ASR"***, which
stood unchallenged in spec v1 through v14. That decision has no ADR of its own —
this directory did not exist — which is a large part of why it survived thirteen
review rounds while breaking everything downstream of it.

Design intent, not gate approval — see [the status note](README.md#what-accepted-means-here-and-what-it-does-not).

> Jury, on the process objection: *"Jo is the owner. Ruling 4 binds the creator
> loop; it does not bind Jo. An owner may re-architect their product at any time
> and does not need my leave. Anyone arguing otherwise has confused a quality
> gate with a chain of command."* (`-round14.md`)

## Context

### The requirement

Word-level text↔audio sync is the headline feature. A highlight that lands on
the **wrong** word is a correctness bug, not a glitch — and for a reader tracking
their place, a confidently wrong highlight is indistinguishable from a correct
one. The spec's first section states the requirement as: *word-level sync must be
correct, or absent and announced* (§1).

### The superseded decision, and why it was reasonable

Every revision through v14 said **"forced alignment, not ASR."** The reasoning
was sound on its face and deserves to be recorded properly rather than
caricatured:

- We generated the audio ourselves, so **we know what text we sent.**
- Solving for time boundaries against a known transcript is a strictly easier
  problem than open recognition.
- A forced aligner **cannot hallucinate a word that is not in the document** — it
  has no vocabulary to invent from. Under prediction, the "transcript contains a
  word that isn't on the page" failure mode does not exist at all.
- Open recognition costs money per minute; alignment against a known transcript
  is cheap.

Under that architecture, our own **normalizer** (pipeline stage 4.5) predicted
the spoken form and emitted a token-level **provenance trace**, mapping each
spoken token back to the `[cs, ce)` display span it came from. The aligner timed
the predicted transcript; the trace projected those times onto display offsets.

### What falsified it

**We know what we *sent*. We do not know what was *said*.**

Every TTS provider normalizes internally before speaking: `Dr.` → "doctor",
`1984` → "nineteen eighty-four", `§3` → "section three", `p. 47` → "page
forty-seven" (§6.2). A forced aligner aligns against the **spoken** form, so the
*i*-th aligned word does not correspond to the *i*-th display token, and **the
offset accumulates**. Worse, the failure is silent: the aligner's confidence
stays healthy because the alignment *succeeded* — it is the text↔word mapping
that is wrong.

Prediction therefore had a hard dependency: our normalizer had to reproduce each
provider's internal normalization **exactly**, which in turn required each
provider to let us **disable** its internal normalization so we could send
pre-normalized text. Whether Fish, Lemonfox and Google would allow that was
**SPIKE B2**.

That single unanswered vendor question:

- was the **highest-priority open item for thirteen consecutive rounds**;
- was, by Jury's count, the **single largest source of Critical findings in the
  project's history** — the majority of Criticals across five rounds
  (`-round14.md`);
- was **unverifiable even in principle** on the correctness side: "our normalizer
  matches theirs" is a claim about a black box, asserted by construction, with no
  second string to compare against;
- made the headline feature contingent on **vendor cooperation** we had no
  leverage to obtain.

### The evidence that ended it

Not an argument — running code, on the same machine, in a sibling project:

| Evidence | What it shows |
| --- | --- |
| `motionmax/worker/src/services/audioASR.ts:2-5` | Transcribes **generated** audio and returns `words: [{ word, start, end }]` — word-level timestamps taken from the audio that actually exists |
| `motionmax/worker/src/services/exportVideo.ts:674` | Fires it in parallel with encoding |
| `motionmax/worker/src/services/captionBuilder.ts` | Burns the result into video |

It ships. Evidence Tier **A** — a shipping code path on this host, not a vendor
claim.

> Jury, upholding the reversal (**STAND WITH CONDITIONS**): it is the only
> architectural decision in fourteen rounds grounded in Tier A evidence; it
> **converts an unfalsifiable property into a falsifiable one** — prediction
> asserted correctness *by construction* and had no second string to compare
> against, whereas observation has both strings; and the cost objection was
> preserved rather than dropped. (`-round14.md`)

## Decision

**Synthesize → transcribe the audio we produced → match observed words to
display text.**

Word timings come from **transcribing our own generated audio** on our own
Python sidecar (WhisperX, which performs recognition **and** word-level alignment
in one pass), and a **match step** maps the observed words onto display-text
character offsets.

Provider normalization becomes something we **hear**, not something we must
predict or negotiate.

| | Predict (v1–v14) | Observe (v15+) |
| --- | --- | --- |
| Can providers disable normalization? | **Must know** — gates the headline feature | **Do not care** |
| Our normalizer must match theirs exactly | Yes, and unverifiable | No |
| `normalization_opaque` | Central | Removed as an `align_reason` and as a blocker |
| SPIKE B2 | Blocks word sync | **Retired** |
| Residual work | Normalizer + provenance trace + vendor cooperation | One matching step — local, testable, no vendor cooperation |

### The cost reasoning: the vendor was rejected, not the technique

v14 rejected **Hypereal** ASR at **$0.01/min** — **$5.40 for a nine-hour book**,
roughly **4× the $1.35 Lemonfox synthesis it would be timing.** That arithmetic
still holds and the rejection stands.

**What was wrong was concluding from "Hypereal is too expensive" that
*prediction* was the answer.** Transcription runs on the **Python sidecar this
design already provisions**, at compute cost rather than per-minute price. The
sibling project pays a per-minute vendor because its sidecar is a video encoder,
not an aligner; ours exists for exactly this purpose. Jo's architectural
correction and the cost objection were never in conflict.

> **Note on a figure that disagrees with itself.** Spec §5 states the Hypereal
> alternative as *"$6.00 per book, ~4.4×"*. Spec §6.1, the roadmap and the
> `README` all state **$5.40 per 9-hour book, ~4×**, which is what
> $0.01/min × 540 min gives. Three artifacts against one; the ADR uses $5.40 and
> the §5 figure is reported as a spec-internal contradiction rather than
> silently reconciled here.

## Consequences

### Retired

- **`normalization_opaque`** — removed as an `align_reason` value and as a
  pre-payment blocker. Nothing observes it.
- **`no_normalizer`** — removed from both `align_blocker` columns and from the
  quote payload. Left standing it told a blind user on an unsupported-language document, *before
  paying*, that word sync would fail on 41 of 42 segments — for a feature this
  re-architecture may have just delivered to them (`J14-C1`).
- **SPIKE B2** — retired **unrun**. Closed by deleting its dependents, not by
  measuring it. Its pronunciation-lexicon half (does each provider accept SSML
  `<phoneme>`?) is **not** retired: it is a `user_lexicon` question and moves to
  Phase 5/6.
- **Stage 4.5 Normalize no longer owns the headline feature.** It survives as the
  producer of **inserted speech** (table linearization, sentinels, chapter
  announcements) and of the **billing estimate** the preflight quote meters —
  that is its only remaining role.

### Created: the match contract

The match step is now the **sole placer of highlights**, so it carries the
invariants the normalization trace used to. All four are load-bearing; a
violation is a defect, not a quality signal (§6.1, `R14-C3`):

1. **Monotonicity** — matched display offsets are non-decreasing across a
   segment's observed words. A book contains "the" four thousand times; without
   this, an unconstrained fuzzy match produces a highlight that jumps backwards.
2. **A drift bound — 250 ms.** The maximum permitted displacement between a
   matched token's timestamp and the position implied by its neighbours. **The
   number is fixed *before* SPIKE A runs**, and may be moved by the measurement
   only publicly, with the reason recorded (`H17-C3`). It is stated first
   because SPIKE A's pass bar is *"share of words matched inside the drift
   bound"* — a bound chosen afterwards would set its own pass rate, with nobody
   to defend the choice to.
3. **A coverage floor** — how many display characters may go unmatched before the
   segment is `degraded`. Silence here is how "mostly worked" becomes "shipped".
4. **Two confidences, two fields** — `asr_conf` (*the engine was sure it heard
   this word*) and `match_conf` (*we are sure this word goes **here** on the
   page*). These are **different quantities**, and a transcriber is routinely
   confident and wrong. **Per-word highlighting keys on `match_conf` only.**
   `align_conf` is retained as `min(asr_conf, match_conf)` for the *segment*-level
   `degraded` threshold and clients must not use it to decide a word.

Both thresholds are **served to clients** on `GET /documents/:id/segments` —
`match_conf_threshold` for the per-word decision and `align_conf_threshold` for
the segment-level one. A client told to "highlight the confident spans and skip
the rest" cannot apply a threshold it is never given (`J15-C4`, `J16-M3`).

### Created: failure has names

| Reason | Meaning | Permanence | Lives on | In the quote? |
| --- | --- | --- | --- | --- |
| `no_transcriber` | No transcriber covers this language at all | `permanent` | `segments.align_blocker` — voice-independent, set at stage 4.5 before any voice exists | **Yes** |
| `transcription_unreliable` | Transcription is **below SPIKE A's bar** for this `(lang, voice)` | `render_specific` — another voice genuinely can change it | `segment_renditions.align_blocker`; computed at quote time from the matrix, persisted once a render exists | **Yes** |
| `wrong_match` | The match invariants were violated | `render_specific` | `segment_renditions.align_blocker` | **No** — raised after payment, by the match step |

The first two are **static `(lang, voice)` lookups**, which is what preserves the
pre-payment disclosure. Under prediction the pre-quote fact was *"do we own a
normalizer for this language"*; under observation it is *"does transcription meet
the bar for this `(lang, voice)`"*. Same arity, same producer stage, same payload
slot — as Jury put it, *"no class of disclosure has been lost. One input has been
orphaned and its replacement has not been named."*

**It is a prior, not a guarantee**, and the catalogue strings must read that way:
*"word sync is unreliable in a low-resource language"* is honest; *"word sync will not
work"* is not; and neither is silence.

### Created: a new failure mode that prediction did not have

Open recognition **can emit a word that is not in the document.** Such a token is
**excluded from the highlight map** and recorded — that half is settled and is
the half a reader experiences.

**How it is disclosed is OPEN** (`J17-C3` · Owner **Atlas** · due
**2026-08-22**). A hallucinated token has no display address by definition, and
every §9.1 disclosure span requires one. It resolves as either a new span `kind`
with a null-address rule, or a per-segment tally with a stated reason it is not
positional. `transcript_mismatch` **may not be reused** — it is classified
`permanent` expressly because it never touches audio, and reusing it would tell a
blind user a mishearing is unfixable when another voice or re-transcription
genuinely fixes it.

### Created: an inequity, on the population with fewest alternatives

Recognition quality in **a low-resource language** is materially weaker than in `en`, `fr`
or `es`, and its failure mode is **fluent hallucination** — a token timed to
50 ms and mapped confidently to the wrong word (`R14-C5`). Under prediction, a low-resource language
word sync failed for a normalizer reason; under observation it may fail for a
recognition reason, and the *fluent* variety is the dangerous one.

Two mitigations are in the plan, neither of them optional:

- SPIKE A returns **`hallucination_rate`** per language — *"the only one of the
  metrics that distinguishes a low-resource language from `en`"*, because `p95_abs_error_ms` is a
  timing bound and cannot see a perfectly timed wrong word (`H17-C3`).
- `segment_renditions.observed_words JSONB` persists **the transcript as heard**,
  one row per `(segment, voice)`. Without it a wrong match is unauditable after
  the fact, because the only surviving artifact would be the match's own output
  (`J16-C3`). It contains verbatim document text, so it is **named explicitly**
  in the §7.4 deletion cascade and retention lifecycle, not merely covered by it
  (`J17-M4`).

### Consequences elsewhere

- **SPIKE A is rescoped** and is now the only Phase 0 spike gating word sync:
  WhisperX (or equivalent) on the sidecar, plus a language-coverage matrix over
  **the three supported languages — `en`, `es`, `fr`** — fixed before the
  measurement (`J18-M4`). *(Corrected 2026-08-10. This read "all eleven
  languages §3.5 routes — not the four product languages". **Both numbers are
  wrong now.** Eleven is the reference stack's routing table, which is not our
  language scope; four was `en`/`es`/`fr`/`ht`, and `ht` left scope on
  2026-08-08 — ADR-0005 records that the matrix "covers the three supported
  languages instead of the eleven the reference stack routes — and the scope
  question that `J18-M4` opened closes with it." The identical `J18-M4` claim
  lived in three places: the roadmap said **three**, the spec header said
  **eleven**, and this ADR said **eleven**. One claim, three homes, one right.)*
  Four numbers per language:
  `median_abs_error_ms`, `p95_abs_error_ms`, `matched_within_drift_pct` (the pass
  bar), `hallucination_rate`, plus `compute_cost_per_audio_hour_usd`. Proposed
  bar: `matched_within_drift_pct >= 95` and `p95_abs_error_ms <= 300`, confirmed
  or moved **by** the measurement and not **after** it.
  *(Owner: Forge · due 2026-08-14.)*
- **The `align_*` half of the message catalogue was recounted** to **22 keys /
  66 strings** across the three languages. *That is the `align_*` budget only*
  (`H20-C1`) — the catalogue's total is **~56 keys / ~168 strings** (spec §9,
  recounted for `H26-C3`, recounted again 2026-08-11 for `H34-C2`), and quoting
  22/66 as the whole catalogue is precisely the defect `H20-C1` was filed for.
  *(This ADR recorded **20 / 60** and **~54 / ~162** until 2026-08-11.
  `H34-C2` added `incomplete_match` as a ninth `align_reason` cause, which adds
  two reason sets and therefore two keys. **The numbers are updated rather than
  annotated because they are a live budget Tongue scopes against, not a record
  of what was decided** — spec §9 is the authority and this line mirrors it.)* `no_transcriber`, `transcription_unreliable` and `wrong_match`
  are the three states this architecture introduces and initially had **no string
  in any language**; `align_status: pending` is a state every rendition now
  passes through and had no key (`J15-C6`, `J17-M5`).
- Pipeline stage 6 changed name and job: **Transcribe + Match**, fed **audio**
  rather than a predicted transcript.

### The lesson the reversal itself taught

Round 14 still returned `FAIL` — eight Criticals, the highest count since round
one — and six of the eight were pure **propagation** failures: the same idea
written in one place and not the other eight. `README.md` still said, in bold,
*"Forced alignment, not ASR"*; roadmap Phase 6 still said *"Aligner receives
`spoken_text` ONLY"*.

> **The size of a change is not what generates defects. The ratio of assertion to
> propagation is.** (`-round14.md`)

That is the reason this ADR exists rather than a paragraph in one document.

## References

- Spec §6.1 (the reversal and the match contract), §6.2 (the normalization
  problem, retained as the *why*), §6.3 (`align_status`, reasons, permanence,
  the two `align_blocker` columns), §7.2a (`observed_words`, `asr_conf`,
  `match_conf`), §8.2 (the quote), §12 (open questions 1 and 3b)
- Roadmap Phase 0 (SPIKE A, SPIKE B2 retired), Phase 4.5 (what Normalize still
  owns), Phase 6 (transcription + match sidecar)
- Audits: `-round14.md` (`R14-A1`, `R14-C2`–`C5`, `J14-C1`),
  `-round19.md` (`J17-C2`, `J17-C3`, `H17-C3`)
- Evidence: `motionmax/worker/src/services/audioASR.ts:2-5`,
  `exportVideo.ts:674`, `captionBuilder.ts`
