# Audit Record — Founding Documents, Round 2

- **Date:** 2026-08-08
- **Subject:** spec v2, roadmap v2, `CLAUDE.md`, `.gitignore`, `research/`, `README.md`
- **Prior round:** `2026-08-08-founding-documents.md`
- **Reviewers:** Jury, Halo — both re-audited with **read-only tools**, enforcing
  `jury.md:79` by tool scope rather than instruction.

## Verdicts

| Reviewer | Round 1 | Round 2 |
| --- | --- | --- |
| **Jury** | `FAIL` — 3 Blocker, 12 Critical, 12 Major | **`FAIL`** — 0 Blocker, 3 Critical, 6 Major |
| **Halo** | `FAIL` — 4 Blocker, 6 Critical, 9 Major | **`FAIL`** — 1 Blocker, 4 Critical, 5 Major |

**Jury composite: 2.4 → 3.7 / 5.** Risk sequencing 2→5, legal 1→4,
accessibility 2→4, commercial 2→4, evidence 3→4. Documentation 4→3 (the README).

**Of 35 Jury findings, 30 verified fixed** — by re-running the original
verification commands, not by accepting claims. All Blockers closed.

## Round-2 findings and disposition

All fixed in v3 unless noted. Owner and date carried per `CLAUDE.md:22`.

### Critical

| ID | Finding | Disposition |
| --- | --- | --- |
| **J-N1** | `README.md` documented the **old** commit gate verbatim, including the "there is no middle state" phrasing `CLAUDE.md` was rewritten to remove. Two committed root documents giving opposite instructions on the one rule the project calls MANDATORY. | **Fixed** — README mirrors `CLAUDE.md` and names it the single source of truth. |
| **J-N2** | `README.md:30`, `:322`, `:325` stated audit reports are gitignored, while `git status` showed one staged for this commit. A contributor "correcting" `.gitignore` to match would delete the governance trail the comment begs them not to touch. | **Fixed** — README states the exception and explains the `/resources/*` construction. |
| **J-N3 / H-B2/R** | `segments.spoken_text` had **no producer**. A forced aligner cannot emit offsets into display text; and if providers normalize internally their transcript is unreadable. The spec asserted a safety property it had not established. | **Fixed** — new pipeline stage 4.5 Normalize with a token-level provenance trace; provider normalization disabled (Spike B2 capability question); `normalization_opaque` reason; and the `normalize(text[cs:ce]) == w` invariant that finally gives `transcript_mismatch` something able to raise it. |
| **H-N1** | Addressability broken at the last link — no `block → character-within-segment` map. | **Fixed** — `segments.block_start_offsets int[]`. |
| **H-N2** | Skip-coverage gap: blocks skipped *between* segments belonged to no range, and contiguous skip runs are the common case. | **Fixed** — block ranges tile the document gaplessly, with a test that every skipped block appears in exactly one `skipped_block_ords[]`. |
| **H-N3** | `figure` and `caption` un-skipped but never linked. | **Fixed** — `describes_ord` / `described_by_ord`. |
| **H-B3/R** | A figure with no alt *and* no caption was kept, empty, and absent from every disclosure channel. | **Fixed** — stable sentinel + `figures_without_description` count. |
| **H-C5/R** | Append-only versioning asserted with no version key; `listening_progress` unchanged, so the remap was not computable. | **Fixed** — `segment_set_id`, `superseded_by`, and `listening_progress` re-anchored on `{block_ord, char_offset_in_block}`. Billing consequence stated honestly rather than elided. |

### Major

| ID | Finding | Disposition | Owner |
| --- | --- | --- | --- |
| **J-N4** | The file's only Tier A datum failed its own Tier A definition. | **Fixed** — relabelled Tier B, with the correction shown rather than silently edited. Zero Tier A evidence now stated explicitly. | Forge |
| **J-N5** | The `PASS WITH FIXES` branch requires owner + date; no artifact carried either. | **Fixed** — this table and roadmap item owners. | Jo |
| **J-N6 / H-N5** | Two of three J-C12 deliverables **silently dropped** between v1 and v2 — no mention, no dispute. A governance failure: the resolve-by-ID rule must bind the revision, not only the re-audit. | **Fixed** — §3.8 adds pronunciation lexicon and table narration contract. | Forge |
| **J-N7** | Halo missing from Phase 8 while two documents claimed otherwise; also absent from 5 and 7, where her own findings are implemented. | **Fixed** — Halo added to 4.5, 5, 7, 8. | Jury |
| **J-N8** | `segments` kept one `voice_id`/`audio_path`, so a re-render orphaned paid audio. | **Fixed** — `segment_renditions` child table. | Atlas |
| **J-N9** | README omitted constraints 6 and 7 — the Blocker and Critical legal findings — and never mentioned DMCA or subprocessors. | **Fixed** | Scribe |
| **H-N4** | No backend-owned message catalogue for enums the revision created; `ht` strings owned by nobody. | **Fixed** — §3.8, Phase 9. | Tongue |
| **H-N6** | No math/formula handling and no way to disclose its absence, in a product whose first named audience is students with textbooks. | **Fixed** — `math` kind, MathML/OMML capture, `math_unnarratable` count. Narration may stay out of scope; silence does not. | Forge |
| **H-N8** | `ocr_conf` measures recognition and cannot detect the column-interleaving failure §3.2 spends a paragraph condemning. | **Fixed** — `reading_order_conf` as a separate signal. | Forge |

### Minor / Polish

`J-n1` recall floor now **99.5%**, never-skip threshold **200 chars** ·
`J-n2` EPUB limits made coherent (100 MB archive / 500 MB decompressed / 20:1) ·
`J-n3` "Verified rate" header corrected · `J-n4` full path to `captionBuilder.ts` ·
`J-n5`/`H-m1` `documents.status` enumerated · `J-n6` `.ssh`/`.claude.json`/
`id_rsa*` added as defence in depth · `J-n7`–`J-n10` README corrections ·
`H-m2` `lang_conf` added · `H-N9` `blocked_quota` · `H-N10` caption never-skip
disambiguated (binds the classifier, not the user) · `H-N11` `header_cols` +
per-cell `scope` · `H-N12` heading-level contiguity · `H-N13`
`epub_a11y_metadata` now served · `H-M2` `chapters.align_degraded_ratio` ·
`H-M8` `encoder_padding`.

## Open, deliberately

**Halo cannot issue `PASS` before implementation.** Its rules require a keyboard
pass and a screen-reader transcript, and there is no artifact to run NVDA
against. No accessibility `PASS` exists until Phase 10. The question this gate
answers is narrower and was answered: *does the design foreclose or enable
accessible clients?* Round 1: foreclosed. Round 2: enabled except in three named
dimensions, all now addressed in v3.

**Rule 8 disclosure.** `J-C1`, `J-C10`, `J-C12`, `J-M9`, `J-N1`, `J-N2`, `J-N5`
and `J-N7` concern the audit layer grading its own governance scaffolding.
`jury.md:83` routes these to BigBrain or Jo rather than self-action. Flagged.

## Process note carried forward

Jury's own framing, worth keeping: *"The research file's willingness to write
'this is the weakest evidence here and the most important claim' about its own
Fish Audio number, and then block the schema on it — that is the single most
trustworthy paragraph in the whole set. Do not let anyone tidy that honesty
away."*
