# Glossary

The vocabulary of audiomax.ai that a newcomer cannot infer from the names.
Every entry names the section that **owns** it — that section, not this page, is
the authority. Spec references are to
`resources/specs/2026-08-08-audiomax-backend-design.md` (gitignored; see
[CONTRIBUTING](../CONTRIBUTING.md)).

Where something is genuinely undecided, this page says so and names the owner and
date from the roadmap.

---

## The units

### Block
The smallest extracted unit — one heading, paragraph, footnote, caption, figure,
table, list item or equation, in reading order. Every adapter (PDF, EPUB, DOCX,
URL, OCR, pasted text) normalizes its source into the same `Block[]` shape, so
nothing downstream knows where a document came from. *Owner: §3.2.*

### Segment
**The universal unit** — of work, billing, caching, retry, playback and sync.
Roughly **1,000 characters ≈ 60 seconds of audio**, hard ceiling 2,000. Cut so it
never splits a sentence, never crosses a chapter, and **never crosses a language
boundary**. Ordinals are permanent addresses and are never renumbered.
*Owner: §3.4; see [ADR-0001](architecture/0001-the-segment-is-the-universal-unit.md).*

### Segment set (`segment_set_id`)
One complete segmentation of a document. Changing skip policy, or splitting an
over-length segment, produces a **new set** rather than mutating existing
ordinals; `superseded_by` links the old set forward and its audio is retained for
30 days with the expiry disclosed. A client holding an offline copy can detect
that its set was superseded instead of continuing from stale data.
*Owner: §7.2b.*

### Rendition
One row per **(segment, voice)** — the audio for a given segment in a given
voice, plus everything that varies with the voice: `audio_path`, `duration_ms`,
encoder delay/padding, word timings, and all alignment state. A book rendered in
two voices has two renditions per segment, and both remain reachable: a re-render
must never orphan audio the user has already paid for. *Owner: §7.2a.*

---

## Text, speech, and the gap between them

### Display text (`segments.text`)
What the reader shows. Also the coordinate system every highlight is expressed
in — word records carry `cs`/`ce` character offsets into it, so the client never
re-tokenizes and cannot drift. A `table` or `math` block's flat text **never**
enters it, at any setting; structured blocks are narrated only through
linearization. *Owner: §3.4, §9.1.*

### `spoken_text`
What stage 4.5 predicts will be **uttered**, produced by our normalizer plus any
inserted speech. `1984` is four display characters and twenty spoken ones.

**Since `R14-A1` its only remaining role is billing** — it is the estimate the
preflight quote meters, because providers bill spoken characters. It is **not**
an input to word sync any more; word timings come from transcribing the audio.
*Owner: §6.2, §8.2; see [ADR-0002](architecture/0002-observe-what-was-spoken-do-not-predict-it.md).*

### Inserted speech
Text that is **spoken but never displayed**: table preambles ("Table, 4 columns,
12 rows"), the undescribed-figure sentinel ("image, no description available"),
math sentinels, chapter announcements, per-chapter disclosure summaries. Billed
(the provider charges for it), reported separately in the quote as
`inserted_characters`, and **never highlighted** — it has no display address.
Always spoken in `segments.lang`, never in the user's UI locale. *Owner: §6.2.*

### Normalization trace
The token-level provenance map produced by stage 4.5: every token in the
utterance carries its origin — `display` (with the `[cs, ce)` span it came from),
`inserted` (with a block ordinal, character offset and language), or `dropped` (a
glyph that produces no speech). Contains verbatim document text, so it is named
explicitly in the deletion cascade. *Owner: §6.2.*

### `group_id`
Tokens emitted by one rewrite rule share a group. `$5` → "five dollars" is one
group whose display spans are inverted, and must pass; a scrambled mapping must
fail. The rule is stated over display offsets — for groups A before B,
`max(ce) over A ≤ min(cs) over B` — because "monotonic" without a named ordering
domain validates nothing. *Owner: §6.2.*

---

## Word sync

### The match step
The step that maps **observed** words (what transcription heard) onto **display
text** offsets. It is the **sole placer of highlights** and the component the
headline feature rests on. It runs after synthesis and after transcription, and
it enforces four things: monotonicity, a **250 ms** drift bound, a coverage
floor, and two separate confidences. A highlight on the wrong word looks exactly
like a highlight on the right word, which is why these are invariants and not
quality signals.

**It re-synchronises, forward only** — trigger 3 consecutive unmatched tokens,
anchor 3 consecutive matches, bounded at 200. Without that path a single
mismatch cost the *rest of the clip*: monotonic greedy with a six-token
lookahead desynced **3 of 6** long clips. Backward re-sync is refused — a
highlight moving backwards through the page is worse than a missing one, and it
breaks monotonicity. Diacritic and elision folds are **ranked strictly below the
exact fold**, so a loose fold can never steal a token that had an exact match
available.

**It lives in `worker/src/match/`, and that is the point.** It used to be
`measure.match`, a function *inside the measurement script* — which is why its
defect could be diagnosed in a comment and never fixed. A component that exists
only inside the instrument measuring it cannot be repaired without contaminating
the measurement. *Owner: §6.1, roadmap Phase 6; see
[ADR-0006](architecture/0006-the-matcher-re-synchronises-and-lives-in-the-product.md).*

### Drift, and the 250 ms drift bound
**Drift** is the gap between when a word is *highlighted* and when it is
*spoken* — the absolute error between a word's timestamp and its true position
in the audio. The **drift bound** is the largest gap the product will accept:
**250 ms**, stored as `sync_drift_bound_ms`.

**The bound was fixed *before* the measurement that scores against it, and that
ordering is the point** (`H17-C3`). As first written the metric was circular:
§6.1 deferred the bound to the match step, the match step is gated by SPIKE A,
and SPIKE A's pass metric was defined *in terms of* the bound — so whoever chose
the bound chose the pass rate, after seeing the data, without having to defend
it. It may still move, but only **publicly and with the reason recorded**; it
may not be moved to make a language pass. The same discipline governs the
evidence floor and the language scope.

Drift is not the same as *accumulating* drift. A constant lead of 400 ms is a
bad highlight everywhere; a drift that grows at 1 ms per second is fine for a
minute and **tens of seconds off** across a 9-hour book. Whether accumulation
exists is **open** (`H26-M7`) — SPIKE A's slopes are near zero but its
confidence intervals are wide on 137–143 seconds of audio, and the artifact says
so itself: *"no accumulation was detected, which on this n is not the same as
none existing."* *Owner: §6.1, roadmap Phase 0 (SPIKE A).*

### Match rate vs `matched_within_drift_pct` — two numbers, both percentages, different questions
These are routinely confused, they are both reported per language, and they can
even take **the same value on the same run** — SPIKE A produced `95.8` for both,
for different things, in adjacent clauses. **Always carry the metric name.**

| | **Match rate** | **`matched_within_drift_pct`** |
| --- | --- | --- |
| Question | *Did an observed word find a display token at all?* | *Was the word placed within **250 ms** of where it is actually spoken?* |
| Failure it detects | Recognition invented a word, or the text moved under it | The highlight is on the right word at the wrong **time** |
| Ignores | Timing entirely | Words that never matched |
| Role | Diagnostic | **The pass bar** — `>= 95` |

A run can score 100% match rate and fail badly on drift: every word found its
place on the page, and every highlight fires a third of a second early. The
reverse is rarer but worse, because a confidently misplaced word looks exactly
like a correct one.

The companion metrics are `median_abs_error_ms`, **`p95_abs_error_ms`** (bar:
`<= 300`; the tail is what a listener notices) and **`hallucination_rate`**
(bar: `<= 2`) — observed tokens matching no display text. Hallucination has its
own bar because a timing bound cannot see it: a fluently invented token can be
timed to 50 ms and mapped to the wrong word, and `p95` will look excellent.
*Owner: §6.1, roadmap Phase 0.*

### `asr_conf`
**"The engine was sure it heard this word."** Recognition confidence, per word,
persisted. *Owner: §6.3, §7.2a.*

### `match_conf`
**"We are sure this word goes *here* on the page."** Placement confidence — a
**different quantity** from `asr_conf`, because a transcriber is routinely
confident and wrong. **Per-word highlighting keys on `match_conf` only**, against
`match_conf_threshold`, which the API serves to clients. *Owner: §6.3, §7.2a.*

### `align_conf`
`min(asr_conf, match_conf)`, retained for the **segment-level** `degraded`
decision against `align_conf_threshold`. **Clients must not use it to decide
whether to highlight a word.** *Owner: §6.3.*

### `sync_grade`
**What we know about word sync for one `(language, voice)` pair — asked and
answered *before* the user pays.** It is a column on `voice_langs` (§7.1a), it
is **NOT NULL with DEFAULT `unmeasured`**, and the read path coalesces, so **no
API ever returns a NULL `sync_grade`**. Four values:

| Value | Meaning | Effect on the quote |
| --- | --- | --- |
| **`unmeasured`** | No measurement exists for this pair | Counts as **not established** |
| **`provisional`** | Measured, but **below the evidence floor** | Counts as **not established** |
| **`at_or_above_bar`** | Measured at or above the SPIKE A bar, on sufficient evidence | Counts as **word-sync available** |
| **`below_bar`** | Measured below the bar | Sets `transcription_unreliable` |

**Do not confuse a missing row with `unmeasured`.** A row's *presence* says the
voice can speak the language at all; `sync_grade` says whether that pair has
been *measured*. A voice with no row for a language is not returned by
`GET /voices?lang=` at all.

**`provisional` exists because three grades would force a lie.** The French
voice result — 88.2% / 94.4% / 100% across three voices — is `15/17` vs `17/18`
vs `18/18` **on one 8-second clip**. With three grades the only options are to
call the 100% voice *established* on the strength of two tokens, or to discard a
real signal. Both are wrong. The direction is plausible, the mechanism is sound,
and **the number is two tokens** — the schema has to say all three at once.

**The evidence floor is fixed BEFORE the measurement that will use it**, for the
same reason as the drift bound. `at_or_above_bar` requires **all** of:
`sync_metric` = `matched_within_drift_pct` at 250 ms (a *substituted* metric is
how `H26-B1` turned a failing result into an unmeasurable one, so the column is
an enum and the next substitution is a migration somebody has to defend);
`sync_matched_words >= 200` (at today's `n` of 14–24 one token is 5.6 points, so
a bar of 95 is unresolvable — the nearest reachable values are 94.4 and 100);
and `sync_longest_clip_ms >= 300000` (an offset that *accumulates* cannot appear
on an 8-second clip by construction, and all of SPIKE A is 63 seconds of audio).

The store **ships empty** — `sync_grade` is not seeded from SPIKE A, because
SPIKE A clears none of those three conditions. *Owner: §7.1a; grades reach the
user through `GET /voices?lang=` with their evidence (`sync_pct`,
`sync_matched_words`, `sync_measured_at`) so a client can say "measured on 18
words, one clip" instead of presenting a bare verdict.*

### `align_status`
Per **rendition** (not per segment — timings belong to a specific voice's audio).
One of:

| Value | Meaning for the reader |
| --- | --- |
| `pending` | Not transcribed yet. Every rendition passes through it |
| `ok` | Word sync works |
| `degraded` | **Partial** coverage — timings exist, some runs are below threshold. The client highlights the confident spans and **skips the rest**; audio plays normally |
| `unavailable` | **No usable mapping at all.** Highlighting is **off** for the segment; audio still plays |

`degraded` and `unavailable` are behaviourally different and a client must be
able to tell them apart — the message catalogue spends extra keys on exactly
that. Neither ever falls back to estimated timings. *Owner: §6.3.*

### `align_reason[]`
**An array**, because states co-occur: a Creole segment spoken by a substituted
French voice raises `voice_substituted` **and** `low_confidence` simultaneously,
and a single-valued field announces half the truth. It is a stable, translatable
enum, because a client cannot announce a state change it has no string for.
Reachable values: `unsupported_language`, `low_confidence`, `engine_error`,
`transcript_mismatch`, `no_transcriber`, `transcription_unreliable`,
`wrong_match`, `voice_substituted`, `excessive_drop`. *Owner: §6.3.*

### `align_permanence`
**Derived from the reason set, never authored.** If any reason is `permanent` the
result is `permanent`; else if any is `render_specific`, `render_specific`; else
`retryable`.

- **`permanent`** — *"Word sync isn't available for this voice."*
- **`render_specific`** — a **different voice** genuinely can fix it. This is the
  field that surfaces the remedy, so misclassifying something as `permanent`
  withdraws the feature *and* hides the fix.
- **`retryable`** — try again, same voice.

It exists as a column so that no client has to hardcode which reasons are
terminal. *Owner: §6.3.*

### `align_blocker` — and why it lives on two tables
The **pre-payment** word-sync disclosure: what we can tell a user *before* they
spend credits. It is split across two tables because it holds two different
**kinds of fact**:

| Column | Values | Why here |
| --- | --- | --- |
| `segments.align_blocker` | `null｜no_transcriber｜excessive_drop` | **Voice-independent.** Whether a transcriber covers the language at all, and whether the dropped-span floor was breached, are properties of language × text. Set at stage 4.5, **before any voice exists** |
| `segment_renditions.align_blocker` | `null｜transcription_unreliable｜wrong_match` | **Voice-dependent.** Accuracy varies with the audio, and the audio varies with the voice — which is exactly why another voice is a real remedy |

Both still reach the quote before payment: `GET /documents/:id/quote` takes
`voice_id` as a **parameter**, so the voice-dependent blocker is *computed* at
quote time from SPIKE A's matrix and *persisted* on the rendition once a render
exists. `wrong_match` is the one value **not** in the quote — it is raised by the
match step, which runs after payment.

Storing a `(lang, voice)` fact on `segments`, a table with no `voice_id`, would
be right for one voice and wrong for every other, and the user would find out
after paying. This column produced a Critical in three consecutive rounds, always
by writing the new enum without deleting the old. *Owner: §6.3, §7.2, §7.2a.*

### `no_transcriber` vs `transcription_unreliable` vs `wrong_match`
Three failures that a reader experiences differently and must not be told about
in the same words:

| Value | Plain meaning | Known before payment? | Permanence | Remedy |
| --- | --- | --- | --- | --- |
| **`no_transcriber`** | No transcription engine covers this language at all | **Yes** — a static per-language lookup | `permanent` | None. Telling a user to retry would invite a $1.35–$32 charge that cannot succeed |
| **`transcription_unreliable`** | Transcription is **below SPIKE A's numeric bar** for this `(lang, voice)`. A **probability, not a verdict** — the catalogue string must read that way | **Yes** — a static `(lang, voice)` lookup, computed at quote time | `render_specific` | **A different voice** |
| **`wrong_match`** | The match invariants were violated — the word was placed against the wrong display text. The dangerous failure, because it looks correct | **No** — raised after payment by the match step | `render_specific` | A different voice, or re-transcription |

*Owner: §6.1, §6.3.*

---

## Disclosure — telling the user what they are not hearing

### Disclosure span
A positioned record in the skip manifest of something the pipeline removed,
withheld, inserted, or could not describe. **Positioned** is the whole point: a
document-level tally does nothing for someone at minute 47 who needs to hear
*"three footnotes skipped here."* Each span carries a `kind`
(`skipped｜undescribed｜inserted｜suppressed｜dropped`), a `reason`
(a `SpanReason`), a block range, `segment_ord` + `char_offset`, and
`start_ms`/`end_ms` where timings exist.

The times matter for cost, not just navigation: with them a client can skip a
20-second table preamble **locally**, instead of paying for a re-render to be rid
of it. **No verbosity setting may remove the positional record** — a user must
always be able to learn that something is there, even when they chose not to hear
it. That is the difference between a preference and silent data loss.
*Owner: §9.1.*

### Skip manifest
The document's complete disclosure record: `totals` keyed on `SpanReason`, a
`by_chapter` breakdown, and the `spans` array above. Served on
`GET /documents/:id` **and** on `GET /documents/:id/segments`, because a
disclosure delivered only at import arrives at the wrong moment in the session.
When a document produces no segments at all, `documents.skip_manifest` is
authoritative. *Owner: §9.1, §3.4.*

### Sentinel
A short stable utterance standing in for content that has no text: *"image, no
description available"* for a figure with neither alt text nor a caption, and its
equivalent for unnarratable math. Spoken from the message catalogue **in
`segments.lang`** — an English sentinel voiced by a Creole voice is the
announcement a blind user most needs, rendered least intelligible. Emitted as an
`inserted` trace token, and recorded as a disclosure span **whether or not it is
spoken**. *Owner: §3.2, §9.1.*

### `disclosure_verbosity` and `content_narration`
**Two axes, deliberately not one.** `disclosure_verbosity`
(`full｜positional｜summary｜off`) governs **sentinels and announcements only**.
`content_narration` (`full｜summary｜off`) governs **table and math narration** —
content, not chatter.

They were split because a single switch advertised as "less chatter" would also
have deleted every table in the book, silently, for the population that cannot
see the table on the page. *Owner: §9.1.*

### `disclosure_fingerprint`
A **per-segment** hash of the disclosures that segment would emit or suppress at
the current settings — a sorted list of
`(SpanReason, block_ord, char_offset, SPOKEN)` tuples, where `SPOKEN` is the
boolean *"was this actually uttered"*.

It is an input to `text_hash`, which decides what counts as a genuinely new
segment and therefore what is billable. It is per-segment and not a global
counter for one reason: hashing the raw settings re-hashes all ~540 segments on
one preference change — including the ~500 whose audio is byte-identical either
way — so a blind user turning **off** announcements they were being charged for
would be billed **$1.35–$32 to do it**. `SPOKEN` is the element that makes the
control work at all; without it three of the four verbosity levels hash
identically.

On a chapter's first segment the `disclosure_summary` tuple carries a fifth
element, `CHAPTER_DIGEST`, because that token's audio summarises the **whole
chapter** while the fingerprint is otherwise scoped to one segment.
*Owner: §7.2.*

---

## Money and metering

### Credit
**1 credit = 1,000 characters synthesized.** Providers bill the **spoken**
count, produced at stage 4.5 — not the display count recorded at segmentation.
*Owner: §8.*

### Preflight quote
`GET /documents/:id/quote?scope=&voice_id=` — the exact price and the honest
warnings, **without committing anything**. It debits nothing, enqueues nothing,
and returns **`200` at any balance, including zero and negative**, because the
user who cannot pay is precisely the user for whom *"is this book worth topping
up for?"* is the decision. It carries `display_characters`, `spoken_characters`,
`inserted_characters`, `spoken_bytes`, `align_blocker`, `speech_blocker`,
`word_sync_available_segments`, `speech_available_segments`, and a `quote_etag`
that `POST /render` checks — a stale token gets `409 quote_changed`, so the
number agreed is the number charged. *Owner: §8.2, §9.*

### `speech_blocker` vs `align_blocker`
`align_blocker` answers *"will highlighting work?"*. `speech_blocker` answers
*"will I hear all of it?"* — it counts segments whose language has **no provider
route at all** and which therefore produce **no audio**. Two different questions;
both must be answerable before payment. *Owner: §8.2.*

### `text_hash`
`H(text, normalizer_version, lexicon_fingerprint, lang, disclosure_fingerprint)`
— every input per-segment. It is what makes *"only genuinely new segments are
charged"* decidable rather than an unwritten comparison. Audio is a function of
text × normalizer × lexicon × language × disclosure settings, so hashing the
display text alone would serve a stale pronunciation and call it current.
*Owner: §7.2.*

---

## Terms you will meet in the review trail

### Halo, Jury, and the rest
Studio Zero review agents. **Jury** owns the commit gate and synthesises;
**Halo** is the accessibility auditor and reviews every phase. Others
(Atlas · schema, Nexus · API contracts, Forge · backend, Tongue · i18n,
Comply · legal, Probe · test strategy) are listed in `CLAUDE.md`, and the
**roadmap is the sole authority for which agent reviews which phase**.
See [CODEOWNERS](../CODEOWNERS).

### Finding ID
A stable identifier for one audit finding — `J-B1`, `R14-A1`, `H17-C3`,
`J17-C2`. The prefix names the round and reviewer; a re-audit resolves each ID
explicitly as `fixed`, `open` or `disputed` — **never silence**. Reports live in
`resources/audits/` and are committed.

### Severity — five tiers, and the three verdicts they produce
Newcomers reliably conflate the **severity** of a finding with the **verdict**
of an audit. They are different vocabularies and only one of them opens the
gate.

**Severity** grades a single finding. Jury's rubric is fixed and every finding is
exactly one of five:

| Tier | Meaning | Blocks a commit? |
| --- | --- | --- |
| **Blocker** | Ships nothing until fixed — legal, security, a broken core flow | **Yes** |
| **Critical** | Fix before launch — significant audience exclusion, data loss | **Yes** |
| **Major** | Fix before next release — clear friction, comprehension failure | **No, if owned and dated** |
| **Minor** | Fix when convenient — polish, edge cases, micro-copy | No |
| **Polish** | Optional improvement — taste, parity with best-in-class | No |

**Verdict** grades the whole audit, and it is *computable* from the severities
rather than a judgement call:

| Verdict | Condition | Commit |
| --- | --- | --- |
| `PASS` | Zero open Blocker, Critical **or Major** | Permitted |
| `PASS WITH FIXES` | Zero open Blocker or Critical. Majors open, **each with a named owner and a date** | Permitted |
| `FAIL` | Any open Blocker or Critical | **Blocked** |

Two things a newcomer gets wrong. **`PASS WITH FIXES` is the normal healthy
state, not a near-miss** — any single Polish nit makes `PASS` unreachable by
definition, so a rule that only `PASS` permits a commit is a gate that never
opens, which is worse than a loose one. And **a Major's owner and date are what
make it non-blocking**; an unowned or undated Major is not a Major that waits,
it is a gate that stays shut.

**Severity is the reviewer's, never the author's** — grading your own defect is
what Jury's Rule 8, *"Never grade your own work"*, forbids. `CLAUDE.md` is
authoritative for the gate table; this entry mirrors it.

### SPIKE A
The one Phase 0 experiment still gating word sync: transcription accuracy per
language, over **the three supported languages**, returning
`median_abs_error_ms`, `p95_abs_error_ms`, `matched_within_drift_pct` (the pass
bar), `hallucination_rate`, and compute cost per audio-hour. Proposed bar:
`matched_within_drift_pct >= 95` and `p95_abs_error_ms <= 300`, confirmable or
movable **by** the measurement and not after it. *(Owner: Forge · due
2026-08-14.)* Until it returns, `transcription_unreliable` has no producer rule
and word-sync quality is **measured and below bar** for `en`/`es`/`fr` (SPIKE A).

**And since 2026-08-10 we know what the bar is bound by.** The matcher was
repaired ([ADR-0006](architecture/0006-the-matcher-re-synchronises-and-lives-in-the-product.md))
and the long French clips moved from 20.9–71.4 to **78.4–86.3**, with the three
desynced clips recovered and **inadmissible clips 3 → 0**. **Nothing clears 95** —
and the reason is no longer the matcher:

> On the best long clip, **95 of 1186 display tokens appear in the transcript in
> no form the matcher could accept**, so the ceiling for *any* matcher is
> **92.0%**. Across all six long clips: **89.8%–92.0%, i.e. 3.0–5.2 pp below the
> 95 bar.**

**On chapter-length audio the remaining gap is recognition, not matching** — even
a perfect matcher cannot clear 95 with faster-whisper `base`, so the open
question is the ASR configuration itself.

**But the constraint is length-dependent, and that is the part to remember.** On
the 8–10 s control clips, two of three ceilings are **95.8% — above the bar** —
while those clips score 70.8 and 75.0, so there the loss is **drift, not
recognition**. *(The third short clip's ceiling is 91.7%, below the bar; it
scores 66.7, so drift still dominates.)* **The ceiling is a property of clip
length, not a constant of the corpus.**

The figure is `coverage_ceiling_pct_any_matcher` in
`aligner/spike-a/out/spike-a-voices.json`. It is a **strict upper bound** — the
derivation is deliberately order-free and one-to-many-free, so a real matcher can
only do worse, and it is **not** a prediction of what a better matcher would
score. **Do not confuse it with `match_rate_pct`** (coverage this matcher
achieved) or `matched_within_drift_pct` (what survived the 250 ms bound); the
artifact deliberately does not restate either inside the ceiling block, because
copying them is exactly what produced an earlier mislabelling.
