# Audit Record — Founding Documents

- **Date:** 2026-08-08
- **Subject:** backend design spec, build roadmap, `CLAUDE.md`, `.gitignore`
- **Reviewers:** Jury (audit orchestrator), Halo (accessibility)
- **Audience rubric:** students; commuting professionals; **blind and low-vision
  users as a primary population**; casual readers. `en` / `es` / `fr` / `ht`.
  Consumer risk profile, user-uploaded copyrighted documents, paid credits.

## Verdicts

| Reviewer | Verdict |
| --- | --- |
| **Jury** | **`FAIL`** — 3 Blocker, 12 Critical, 12 Major, 6 Minor, 2 Polish |
| **Halo** | **`FAIL`** — 4 Blocker, 6 Critical, 9 Major, 3 Minor |

**Commit status: BLOCKED.** No commit or push until a re-audit returns `PASS`.

> Format note: this is a findings register rather than the reviewers' verbatim
> prose. It preserves finding IDs, severities, evidence locations, and required
> fixes so a re-audit can resolve each finding by ID — which is what Jury
> finding M9 asks for. Verbatim reports are not reproduced here.

---

## Credited as correct — preserve through revision

Both reviewers independently asked that these decisions survive the rework:

- **Segment as the universal unit** (`spec:57`) — solves five problems at once.
- **Forced alignment over ASR** (`spec:236`) — correct on cost *and* correctness.
- **Refusing estimated timings** (`spec:252-258`) — a confidently wrong highlight
  harms a user tracking their place more than an absent one.
- **Text before audio** (`spec:22-24`) — serves the low-vision case directly.
- **Asymmetric test severity** (`spec:343`, `spec:349-352`) — false skip is a
  Blocker, false keep is Minor, reasoned from "a user who cannot see the page."
- **Append-only credit ledger with derived balance** (`spec:288`).
- **Citation accuracy** — Jury verified every `file:line` reference into
  motionmax and `jury.md`; all resolved except M4. All 16 agent personas exist.
- **Arithmetic** — Jury independently re-derived the cost model; sound.

---

## BLOCKER

| ID | Finding | Evidence | Fix | Status |
| --- | --- | --- | --- | --- |
| **J-B1** | Repo topology exposes private keys. `git rev-parse --show-toplevel` returned `C:/Users/Administrator`; no `.git` in audioMax; `.ssh` and `.claude.json` not ignored. First `git add -A` stages them. | `.gitignore` (whole file), `roadmap:14` | `git init` inside audioMax; add as roadmap item 0.1 | **FIXED 2026-08-08** — repo initialized at `C:/Users/Administrator/audioMax`, branch `main`, remote `origin` set. Home repo reverted to `master`, remote removed. Host-level hazard escalated to Jo. |
| **J-B2** | Copyright/DMCA posture absent from the entire build plan. Core loop creates and stores derivative works from copyrighted uploads. No DMCA agent, takedown endpoint, repeat-infringer policy, or ToS. | `spec:364`, `roadmap:12-158` | Add Phase 0.5 "Legal foundation" gate, must `PASS` before any ingest endpoint ships | Open |
| **J-B3** | No deletion, retention, or erasure path. `CLAUDE.md:64` presupposes an account-deletion surface that is nowhere designed. Cannot honour a takedown without a delete path. | `spec:319-330`, `CLAUDE.md:64` | `DELETE /documents/:id` cascading to storage + segments; account deletion; retention policy. Phase 1 and 8. | Open |
| **H-B1** | `segments` has no back-pointer to `blocks`. `chapters` has `start_block`/`end_block`; segments do not. Since segments are built only from non-skipped blocks, **no client can compute what was skipped** between segment N and N+1. Also blocks page position, footnote-on-demand, and re-segmentation anchoring. | `spec:277-280` vs `spec:270`, `spec:138` | `segments.start_block_ord`, `end_block_ord`, `skipped_block_ords int[]`. Phase 1 migration. | Open |
| **H-B2** | `words[]` has no character offsets. TTS normalizes before speaking (`Dr.`→"doctor", `1984`→"nineteen eighty-four"), so alignment matches the *spoken* form and `words[i]` does not correspond to display token *i*. Drift accumulates. **`overall_conf` stays healthy while the mapping is wrong**, so §6 degradation cannot catch it — a third state the spec never models: *silently wrong*. | `spec:165`, `spec:280`, `spec:246`, contradicts `spec:25-26` | Store `{w,s,e,conf,cs,ce}` with char offsets into `segments.text`. Persist normalized spoken transcript separately. Aligner takes both. Prior art: EPUB Media Overlays. | Open |
| **H-B3** | Figures 100% invisible to blind users. No `alt_text`, no `figure` block kind, captions skipped by default. WCAG 1.1.1 **Level A**. Source data is discarded, not absent: DOCX `wp:docPr/@descr`, EPUB `@alt`, tagged PDF `/Alt`. | `spec:90-98`, `spec:95`, `spec:122` | Add `kind:'figure'`, `blocks.alt_text`, extract from every adapter, make skip defaults audience-conditional | Open |
| **H-B4** | The only accessibility gate sits in Phase 6, after every decision it must influence. Phases 1–4 freeze schema and extraction under a `PASS` first. | `roadmap:107` | Move an a11y gate to Phase 1 *before migrations are written*; add to Phases 2 and 3 | Open |

---

## CRITICAL

| ID | Finding | Evidence | Fix |
| --- | --- | --- | --- |
| **J-C1** | Commit gate wording invites a deadlock reading. See "Disputed" below. | `CLAUDE.md:18-24` vs `jury.md:71-76` | Redefine: `PASS` = zero open Blocker/Critical/Major; `PASS WITH FIXES` = zero Blocker/Critical, Majors tracked → commit permitted; `FAIL` = any open Blocker/Critical |
| **J-C2** | "Credits are the abuse ceiling" contradicts "import/parsing/OCR are free" two paragraphs above. 1,000 free uploads = $150+ LLM spend, unbounded OCR, 200 GB storage, zero credits. | `spec:297` vs `spec:314`, `spec:211`, `spec:75` | Meter import or add per-user rate limits + storage quotas |
| **J-C3** | SSRF built Phase 2, tested Phase 9 — in the only process holding provider keys, on a network with reachable metadata endpoints. Credential exfiltration, not nuisance. | `roadmap:49` vs `roadmap:139`, `CLAUDE.md:132` | Egress control into Phase 2 acceptance: DNS pinning, post-resolution RFC1918/link-local/metadata denylist, redirect re-validation, size/type/timeout limits |
| **J-C4** | Roadmap defers the spike the spec calls design-invalidating to Phase 6 — after the segment size it feeds back into is already built on. | `spec:363-366` vs `roadmap:95-98`, `spec:57`, `spec:64` | Promote alignment spike **and** the `ht` TTS verification to Phase 0. Add explicit go/no-go: if `ht` fails both, launch degraded or not at all? |
| **J-C5** | Figure captions default-skipped — for a blind user the caption *is* the figure. Violates the spec's own asymmetry argument one section earlier. | `spec:121` vs `spec:349` | Remove `caption` from default skips entirely; footnote body → user preference defaulted by document type; Halo signs off on the default set in Phase 3 |
| **J-C6 / H-C2** | No per-segment `lang`. Router keys on language; every segment inherits one document language. `ht`↔`fr` code-switching is constant. Wrong provider, wrong phonology, then wrong or failed alignment. WCAG **3.1.2 (AA)**. | `spec:268`, `spec:277-280`, `spec:151-157` | `blocks.lang` + `segments.lang` (BCP-47) as a 4th output of the existing structure pass; "never cross a language boundary" segmenter invariant |
| **J-C7 / H-C4** | OCR reading order asserted, not designed. `bbox` exists; no algorithm consumes it. Wrong order is *locally fluent*, so a blind user gets scrambled meaning narrated confidently. No OCR confidence anywhere. **§6 builds rigorous confidence discipline where failure costs a highlight; §3.2 builds none where failure costs the words.** | `spec:108`, `spec:96`, `spec:342` | Name the algorithm/engine; add `blocks.ocr_conf` + `documents.scan_quality` (mean conf, page coverage, edge truncation); flag low confidence visibly; add two-column and sidebar fixtures |
| **J-C8** | Payments is one table row. No PSP, webhook idempotency, SCA/3DS, tax, receipts, chargebacks. No refund/reversal row semantics — **there is currently no legal way to refund a user**. | `spec:330`, `spec:288`, `roadmap:124` | Own phase, own gate. Extend ledger `reason` enum with `refund`/`chargeback`/`expiry`. Note Phase 9 reconciliation passes trivially today because no refund can occur. |
| **J-C9** | §5 titled "CORRECTED" with a "Verified current" column, but `resources/research/` **does not exist**. No probe log, no dated capture. The load-bearing "Fish bills per UTF-8 byte" claim (`spec:224`) backs `byte_count` through schema, preflight, segmenter and Phase 1. Arithmetic verified; inputs not. | `spec:190-201`, `spec:224`, `CLAUDE.md:78` | Create `resources/research/2026-08-08-provider-rates.md` with dated capture per rate; one real billed call per provider; confirm Fish byte-billing against an invoice line for accented French before cementing `byte_count` |
| **J-C10** | The audit trail is gitignored. `resources/` ignored in full, yet `CLAUDE.md:41` and `roadmap:153` require every report stored there. `git clean -xdf` destroys the compliance record. Rule 6 re-audit depends on a prior report that may not exist. | `.gitignore:5` vs `CLAUDE.md:41` | See "Disputed" below — conflicts with a direct user instruction |
| **J-C11** | Users' documents go to four third parties (LLM + 3 TTS vendors) with no subprocessor list, DPA posture, disclosure, or opt-out. Medical/legal/manuscript uploads are plausible. | `spec:116`, `spec:151-157` | Subprocessor list + processing disclosure in the Phase 0.5 legal gate; confirm zero-retention/no-training terms per provider |
| **J-C12** | `CLAUDE.md:121` commits Halo to signing off on any shipping surface; the roadmap invokes Halo **once**, narrowly. Phases 3, 8, 9 have no Halo. Backend has no pronunciation/lexicon control, no table-narration contract, no skip announcement. Mitigations delegate to clients declared out of scope (`spec:376`) — the backend cannot claim a property it has delegated. | `CLAUDE.md:121` vs `roadmap:107` | Halo named in Phases 2, 3, 8, 9. Three reviewable backend deliverables: table-narration contract, pronunciation-lexicon hook on the segment, skip-manifest in `GET /documents/:id` |
| **H-C1** | No structural navigation. `heading` has no level; `chapters` is flat; EPUB nav document and PDF outline are never read (spine ≠ TOC). Screen-reader users navigate by structure or not at all. WCAG **1.3.1 (A)**, **2.4.6 (AA)**, **2.4.5 (AA)**. | `spec:95`, `spec:270`, `spec:102-104` | `blocks.heading_level`; `chapters.parent_id` + `depth`; read EPUB nav + PDF outline; expose hierarchy on `GET /documents/:id` |
| **H-C3 / J-p1** | `align_degraded` is both a `status` value and an API error code. A degraded segment **is ready and plays**, so status overloading makes the state unrenderable, and a client built from §9 will refuse to play good audio. No reason code, so nothing can be announced — WCAG **4.1.3 (AA)**, caused by the backend. | `spec:279`, `spec:334`, `spec:252-254` | Remove from `status`. Add `segments.align_status`, `align_reason` (`unsupported_language`/`low_confidence`/`engine_error`/`transcript_mismatch`), `align_conf`. Remove from error list. Reason must be a stable client-translatable enum. |
| **H-C5** | Skip override is per-block only — a blind graduate student needs hundreds of PATCH calls per book, forever. No policy layer exists in the schema. Re-segmentation after override is **undefined**: doing nothing makes the override silently inert; re-segmenting shifts every `ord`, breaking `listening_progress`, orphaning offline downloads, with undefined credit consequences. | `spec:325`, `spec:268-275`, `spec:138`, `spec:131` | `user_preferences` / `documents.skip_policy` keyed on `skip_reason`, applied at segmentation. Append-only segment versioning — never mutate `ord`. Define credit behaviour for re-render. |
| **H-C6** | Tables are opaque text blobs — payload is `text: string` only. A table's meaning is the header↔cell association. WCAG **1.3.1 (A)**. Same for `list_item`: no nesting or ordinal. | `spec:95`, `spec:92-96` | Structured payload (rows, header_rows, cells with row/col index) alongside linear `text` |

---

## MAJOR (summary)

| ID | Finding |
| --- | --- |
| **J-M1** | Structure pass cannot deliver chapter detection or speaker attribution from stateless 100-block batches — both are book-scoped. Split into two passes with carried-forward state. |
| **J-M2** | "False skip is a Blocker" demands a deterministic guarantee from an LLM. Needs a numeric recall floor + a fixed never-skip list with the LLM choosing only from a bounded candidate set. |
| **J-M3** | Audio path has no voice component and `segments` has one `audio_path` — changing voice overwrites paid audio, and retry-vs-re-render billing is undefined. |
| **J-M4** | **The one inaccurate citation, on the no-fallback decision.** `audioASR.ts:231` is a `console.warn`, not the fallback. The estimator is `captionBuilder.ts:88`, called at `:459`. An engineer told "don't port line 231" deletes a log line and ports the estimator. |
| **J-M5** | `.gitignore` patterns unanchored: `models/` matches `worker/src/models/` at any depth and will silently swallow source. Same for `dist/`, `build/`. Missing: `*.pem`, `*.key`, `.vercel/`, `.railway/`, `coverage/`, `.turbo/`. |
| **J-M6** | Golden-file fixtures mean committing copyrighted books in a project whose central legal risk is copyright. Public-domain only; store `Block[]` snapshots + hashes otherwise. |
| **J-M7** | EPUB unzip built Phase 2, zip bombs tested Phase 9. No decompression ratio limit, entry count, path-traversal guard, or AV scanning. |
| **J-M8** | Aligner sidecar never sized. "Stateless" is misleading — no request state, but multi-GB resident model state per language. Four languages co-resident is an architecture question, not a deployment detail. |
| **J-M9** | Rule 6 ("the originating reviewer re-runs the check") is unimplementable — a re-spawned agent is not the originating reviewer. Substitute artifact continuity: version reports, resolve findings by ID, re-run the original verification command. |
| **J-M10** | Open question #1 is a live motionmax financial defect (COGS mis-reported up to 32×) parked in an audiomax table with no date. Escalate as a motionmax incident. |
| **J-M11** | Size limits defined for 1 of 6 sources. `document_too_large` exists with no threshold behind it. |
| **J-M12** | No cancel endpoint. A user who starts a 540-segment render cannot stop it while debits land — contradicts "no surprise debits" (`CLAUDE.md:130`). |
| **H-M1** | Per-word `conf` is returned by the aligner and dropped at persistence, forcing all-or-nothing degradation instead of skipping an uncertain run. |
| **H-M2** | No document/chapter degradation rollup — highlighting will flicker on a ~60s cadence for nine hours on marginal documents. Worse than consistently off. |
| **H-M3** | Credit exhaustion mid-listen is indistinguishable from "not rendered yet" — both read `pending`. WCAG **4.1.3 (AA)**, **3.3.1 (A)**. Needs terminal reasoned blocked states. |
| **H-M4** | No record of voice substitution. If `ht` degrades to a French voice, nothing records it and no client can disclose it. Add `requested_lang` / `spoken_lang`. |
| **H-M5** | Footnotes have no anchor back to their reference point — un-skipping inserts page-bottom bodies mid-narration, producing incoherent audio for the academic user the feature exists to serve. |
| **H-M6** | EPUB accessibility metadata (`schema:accessibilityFeature`, `accessMode`, `accessibilitySummary`, `accessibilityHazard`) discarded. Free authoritative signal, and EAA-relevant. Use `pageBreakMarkers` for real printed page numbers. |
| **H-M7** | No `user_preferences` table despite a cross-device continuity promise. Voice-per-language and skip policy are consumed by the **worker** at render time, so they cannot live client-side. |
| **H-M8** | MP3 per segment produces an audible seam every ~60s (~540 per book) from encoder delay/padding, and risks `duration_ms` drift. Use a gapless container or persist delay/padding; measure duration from the decoded stream. |
| **H-M9** | No accessibility criteria in the test strategy. No assertion that heading level, alt text, language, table structure, or reading order survive extraction. |

---

## MINOR / POLISH

`J-m1` two contradictory persona-invocation mechanisms (`CLAUDE.md:29-31` vs `:90`) ·
`J-m2` structure-pass cost quoted twice ($0.50 vs $0.15) ·
`J-m3` the $8.10 Fish figure is an unmarked floor; accented Latin is 2–4× under byte billing ·
`J-m4` "~10,000 credits / $2.07" rounds inconsistently — state the actual ~9,400 ·
`J-m5` `CLAUDE.md:142`'s sample commit names a real bug class (word boundaries exceeding segment duration) that §6 defines no invariant against ·
`J-m6` two report templates (`jury.md:109` vs `CLAUDE.md:41`) ·
`J-p2` `.gitignore:2-4` comment becomes wrong once C10 is resolved ·
`H-m1` `documents.status` unenumerated while `segments.status` is ·
`H-m2` no language detection or confidence on `documents.lang` ·
`H-m3` heading-level prosody would give real audio-only navigation

---

## Disputed / requires Jo's decision

**J-C1 — the deadlock claim is overstated, the fix is still right.**
Jury argues the gate can never open because any Polish nit yields
`PASS WITH FIXES`. But `jury.md:43` already defines the transition: it forbids
promoting to `PASS` *until every Critical and Blocker is fixed* — implying that
once they are, promotion is permitted with Minors open. So it is not a true
livelock. My `CLAUDE.md:18-24` wording invited the reading by saying "no middle
state," and Jury's proposed severity-explicit definition is clearer regardless.
Adopting it.

**J-C10 — conflicts with a direct instruction.** Jo asked that `resources/`
never be committed. Jury requires the audit trail be durable and diffable.
Both cannot hold as written. Options: (a) un-ignore `resources/audits/` only —
audit reports contain no secrets; (b) keep everything ignored and accept that
the compliance record is untracked and destroyable. **Jo decides.** Not changed
pending that decision.

**J-C12 / Rule 8.** Jury notes that findings C1, C10, C12 and M9 are Jury
grading Jury's own governance scaffolding, which `jury.md:83` says must route
through BigBrain or Jo. Flagged, not auto-actioned.

---

## Halo's "one thing"

> Make the document addressable end to end — `block → segment → word → character`
> — and decide it before the Phase 1 migration is written.

Chosen over the starker alt-text failure for one reason: it is the only finding
that cannot be retrofitted at all. Alt text needs a re-extract. Provenance needs
a re-extract, re-structure, re-segment **and** re-align, and silently corrupts
`listening_progress` and every offline download on the way. Roughly two orders of
magnitude cheaper now than after Phase 4.

## Jury's scorecard

| Dimension | Score |
| --- | --- |
| Architectural soundness | 4 / 5 |
| Internal consistency | 2 / 5 |
| Evidence discipline | 3 / 5 |
| Accessibility (audience-relative) | 2 / 5 |
| Risk sequencing | 2 / 5 |
| Legal & compliance completeness | **1 / 5** |
| Commercial completeness | 2 / 5 |
| Process workability (the gate) | 2 / 5 |
| Documentation quality | 4 / 5 |
| **Composite** | **2.4 / 5** |
