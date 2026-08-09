# Audit Record — Founding Documents, Round 4

- **Date:** 2026-08-08
- **Subject:** spec v4, roadmap v4, `README.md`, `CLAUDE.md`, `.gitignore`, `research/`
- **Reviewers:** Jury, Halo — read-only tools
- **Prior:** `-round3.md`, `-round2.md`, `2026-08-08-founding-documents.md`
- **Response:** spec/roadmap v5

## Verdicts

| Reviewer | R1 | R2 | R3 | R4 |
| --- | --- | --- | --- | --- |
| **Jury** | `FAIL` 3B/12C/12M | `FAIL` 0B/3C/6M | `FAIL` 0B/1C/5M | **`FAIL` 0B/2C/4M** |
| **Halo** | `FAIL` 4B/6C/9M | `FAIL` 1B/4C/5M | `FAIL` 0B/3C/12M | **`FAIL` 0B/6C/13M** |

**Jury composite: 2.4 → 3.7 → 3.8 → 3.9.** Evidence discipline held at **5/5**.
Internal consistency held at **2/5** — flat for four rounds, and the sole reason
for every `FAIL` after round 1.

Jury's framing, which is the finding: *"The composite rising while the verdict
stays `FAIL` **is** the finding. These documents are getting materially better on
five of six axes and failing on the sixth, every time, for four rounds."*

## Root causes, not symptoms

Round 4's 8 Criticals reduce to three causes:

1. **`origin` was half-carried.** Round 3's flagship fix was implemented at the
   type level and carried into none of its consumers — no producer, no ordering,
   no anchor, no language, no phase. Four of Halo's six Criticals are downstream
   of this one omission.
2. **The reconciliation was not run.** v4 added a precedence order and a gate
   *claiming* to prevent cross-artifact drift, then drifted in six places — five
   of them **inside a single file**, which precedence does not address at all.
3. **An over-correction.** Removing a wrong constraint without replacing it.

## Critical

| ID | Finding | Disposition (v5) |
| --- | --- | --- |
| **N4-C1 / R4-C2** | `roadmap:230` specified the per-span round-trip test `spec:536` spends a paragraph repudiating. Built as written it fires on correct data, gets weakened until it stops complaining, and the only safeguard on word-sync correctness becomes decorative — the spec *predicts this exact sequence* and the roadmap scheduled it anyway. | **Fixed** — Phase 4.5 tests restated as group-monotonicity, `display ∪ dropped` coverage, and a determinism check explicitly labelled *not* a mapping check. |
| **N4-C2 / R4-M1** | `align_reason` became an array (correct — `ht` produces `voice_substituted` **and** `low_confidence`); the catalogue key stayed single-valued. A client's only options were `reason[0]` — "announcing half the truth", forbidden by NEW-M7 — or concatenation, forbidden by NEW-M8. **Both branches were defects the same revision declared fixed.** | **Fixed** — catalogue keyed on the sorted **reason set** × permanence; every reachable combination ships an authored string; `ht → fr → en` fallback, never a bare enum. |
| **R4-C3** | **The restated invariant was near-vacuous.** `normalize(segments.text)` reproducing `spoken_text` is a self-comparison — `spoken_text` *is* that function's output. It says nothing about `cs`/`ce`. v3's monotonicity was wrong but it was the **only** mapping validator; deleting it left nothing, so `transcript_mismatch` again had nothing to raise it and the "silently wrong" state was unguarded. | **Fixed** — `group_id` on every trace token: monotonic **between** groups, free **within**. `$5` → "five dollars" passes; a scrambled trace fails. Plus `origin: 'dropped'` so "covering" stops being a rule that gets weakened. |
| **R4-C4** | **Inserted speech had an origin tag and no producer.** Stage 4.5's input was display text only, so nothing produced table linearizations, sentinels, or chapter announcements; the table contract sat in Phase 9 — four phases after the text it belongs to had been billed, synthesized and aligned. `spoken_text` and `inserted_speech` were two columns with no ordering, leaving what reaches the provider undetermined. | **Fixed** — stage 4.5 is `utter(blocks[], skip_policy, lang)`, reads blocks (where `TableBlock` / `alt_text` / `mathml` live), emits one ordered stream with `ord`; trace is authoritative, `inserted_speech` derived. Table contract moved to 4.5. |
| **R4-C5** | **The disclosure was spoken in the wrong language by the wrong voice.** The sentinel was specified as "spoken from the catalogue in the user's locale" while synthesis routes on `segments.lang` — so an English sentinel in a Creole segment is voiced by the Creole voice, violating the never-cross-a-language invariant and making the announcement a blind user most needs the least intelligible. **A defect v4 created:** in v3 the sentinel had no language and so could not be wrong. | **Fixed** — inserted tokens carry `lang = segments.lang`; `ui_locale` governs displayed text only, never synthesized speech. |
| **R4-C6** | **The reconciliation gate had a hole shaped exactly like v4's misses** — scoped to §3.2 + §7.2/§7.2a, one-directional, excluding §7.1, and scheduled inside Phase 1. Every field v4 dropped (`ui_locale`, document-level skip manifest, `figures_total`, `math_total`, `epub_a11y_metadata`, `skip_policy`) landed in the excluded region. | **Fixed** — gate is bidirectional, covers all of §7, and moves into the document revision loop. The manual half is now a **grep whose output is pasted into the revision header**. |
| **N4-M1 / R4-C1** | The N3-R3 relocation was applied to the column lists and **nothing else** — `roadmap:143` still scheduled `segments.status`, sixteen lines below the bullet moving it. Plus five stale statements in the spec. | **Fixed** — all seven sites reconciled by grep. |

## Major

| ID | Finding | Disposition |
| --- | --- | --- |
| **N4-M2 / R4-M8** | Metering fix landed in §8.2 only; `spec:73` still said `char_count` "is what the provider bills"; schema had two counters where the quote serves four; `roadmap:146` still said "characters and bytes". | **Fixed** — `display_char_count` renamed at source; four counters persisted; Phase 4 records display only. |
| **R4-M2** | `align_degraded_ratio` stayed on `documents`/`chapters` while `align_status` moved to renditions. A book in two voices has two true ratios and one column — and H-M2's purpose was *one honest announcement at the top*, so a wrong-voice ratio is worse than flicker because it is believed. | **Fixed** — `document_align_rollup` / `chapter_align_rollup` keyed by voice. |
| **R4-M3** | `listening_progress` carried no voice key while `duration_ms` became per-rendition. After a voice change the time anchor is wrong and the block anchor is unusable on degraded paths — the NEW-M3 failure, recreated by the N3-R3 fix. | **Fixed** — `voice_id` added. |
| **R4-M4** | Inserted tokens had no address, so a client could not position them; and three of five `InsertedReason` values had no manifest representation despite §6.2 claiming all were enumerated. | **Fixed** — `block_ord`/`char_offset` on the token; `kind: inserted` spans. |
| **R4-M5** | NEW-M4's arity (one entry per ordinal in range) and NEW-M5a's resolution (cross-chapter skips outside the range) contradicted; end-of-chapter skip runs — the commonest contiguous skip — got no `char_offset`. | **Fixed** — arity is `range ∪ skipped_block_ords`; the tiling test restated. |
| **R4-M6** | Inserted speech was mandatory and billed, so a user paid extra **because their source document was inaccessible**, with no control. Screen-reader users control verbosity as a matter of course. | **Fixed** — `disclosure_verbosity` (`full｜positional｜summary｜off`); `inserted_characters` quoted separately. |
| **R4-M7** | `text_hash` covered `segments.text` only, so a lexicon or locale change altered the audio while the hash matched — the system would serve a stale pronunciation and judge it current. | **Fixed** — hash includes normalizer version, lexicon version, lang. |
| **R4-M9** | Halo absent from Phase 0 and 0.5 — the phases choosing the alignment engine, the OCR engine, and the `ht` go/no-go, i.e. the three decisions most able to foreclose accessibility. | **Fixed** — Halo added to both. |
| **R4-M10** | The AT acceptance test targets "the reference client", an artifact no phase builds and no spec defines. | **Fixed as a decision, not a task** — Jo owns an explicit choice: add a client spec/phase, or defer the gate and ship this backend **unsigned-off on accessibility**. |
| **R4-M11** | `GET /documents/:id` returned blocks *and* a paginated blocks route existed — an implementer following the first defeats time-to-first-text on textbook-sized documents. | **Fixed** — blocks removed from the document payload. |
| **R4-M12** | Over-length spoken segments had a check and no remedy; the failure mode was a segment that never synthesizes, with no reason code. | **Fixed** — split at a group boundary, recorded. |
| **R4-M13** | The mispronunciation remedy was **paywalled by construction**: correcting it forced a billable re-render, and §7.3's "set it before first render" mitigation is unavailable because a mispronunciation cannot be known until the book has been heard. | **Fixed** — `lexicon_version` in `text_hash` makes affected segments computable; only those re-render and only those are charged. |
| **N3-R11** | No rendition selector on `GET /segments`; absolute RLS claim contradicted by the schema. | **Fixed** — `voice_id` param; RLS mechanism stated (join through `documents`; `voices` exempt as a global catalogue). |

## Minor

`N4-m1` README state-table contradiction — **fixed** · `N4-m2`/`R4-m8` citations
pointed at the round-1 record while quoting round-3 IDs — **fixed**, all four
rounds now cited with their ID prefixes · `N4-m4`/`R4-m6` owner/date format —
**fixed** · `N4-m5` stale changelog row — **fixed** · `N4-m6` trajectory series
mislabelled — **fixed** · `R4-m1` duplicate time invariant — **fixed** ·
`R4-m2` nullability phrased against a moved column — **fixed** · `R4-m3`
`DELETE /me/lexicon` had no entry key — **fixed** · `R4-m4` catalogue locale
fallback — **fixed** · `R4-m5` AT matrix omitted TalkBack, VoiceOver/iOS and a
keyboard pass — **fixed** · `N4-p1`/`J-p3` README task unchecked — **fixed**.

### R4-m7 / N4-m3 — retroactive definitions

Round 3's record listed `NEW-m3`, `NEW-m6`, `NEW-m7`, `NEW-m8` without
definitions, making them unre-auditable — a violation of the rule that record
itself established. Defined here so they can be closed:

| ID | Definition | Status |
| --- | --- | --- |
| `NEW-m3` | Clients are asked to "highlight confident spans and skip the rest" but the confidence threshold is server-side and served nowhere | **Fixed** — threshold served with `align_status` |
| `NEW-m6` | "A client can detect its set was superseded" with no mechanism, and no retention rule for superseded renditions' audio | **Open** — Minor |
| `NEW-m7` | `POST /documents/:id/progress` has no body shape now that the anchor changed | **Open** — Minor |
| `NEW-m8` | `documents.skip_policy` vs `user_preferences.skip_policy` precedence unstated | **Open** — Minor |

## Method change

Rounds 2–4 fixed findings by editing prose from memory. Measured miss rate:
roughly one third of sites per identifier. `align_reason` had **12 mentions**;
round 4 updated 3 and treated the job as done.

**v5 was grep-driven.** Identifiers swept across all four documents *before*
editing: `align_reason` (12), `segments.status` (2), `char_count` (6),
`words JSONB` (2), `duration_ms` (6), `spoken_text` (12), `inserted_speech` (3),
`normalize` (12). The sweep caught two stale sites the author had already
believed reconciled — which is the argument for the method.

## Preserve

Both reviewers, repeatedly: `research/`'s self-demotion of its own Tier A
evidence · §7.3's honest statement of the re-segmentation bill · *"v2 diagnosed
the disease and added a thermometer"* · the behavioural `degraded` vs
`unavailable` definition · 99.5% · §3.2's willingness to state that a skipped run
lives outside its own segment's range · §6.2's account of how a check gets
weakened until it catches nothing — **which diagnosed R4-C3 correctly and then
fell to it.**

## Rule 8 disclosure

`N4-m2`, `N4-m3`, `N4-m6`, `R4-m7`, `N3-R9` and both reviewers' assessments of
the precedence order and reconciliation gate concern the audit layer grading its
own scaffolding. `jury.md:83` routes these to BigBrain or Jo.
