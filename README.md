<p align="center">
  <img src="assets/amlogo.png" alt="audiomax.ai" width="320">
</p>

# audiomax.ai

Turn any document into narrated audio with word-level text↔audio sync.

Six sources — PDF, EPUB, DOCX/TXT, article URL, camera scan, pasted text — become
studio-quality speech with a highlight that tracks the word currently being
spoken. Web (React + Vite) and mobile (Expo), backed by a Node/TypeScript worker,
a Python transcription + word-alignment sidecar (WhisperX), and Supabase.

---

## Status: design phase — no implementation exists yet

**Read this section before anything else.** This repository has **no
implementation code.** There is nothing to install, build, or run. Any
instruction elsewhere that tells you to `npm install` this project is wrong.
What is committed is the working agreement, this README, the documentation gate
(`tools/doc-check.mjs`) and the review trail — see the table below.

| What | State |
| --- | --- |
| Implementation code | **None.** Not started. |
| `tools/doc-check.mjs` | Present and running. The documentation consistency gate — bidirectional field coverage, migration coverage, 17 prose-regression guards, and an end-to-end control-chain trace. `node tools/doc-check.mjs` must exit 0 before a commit; `--self-test` mutates the live documents and runs the shipped checks, proving that **the check IDs with a mutation** fire on their own defect. Six check families are verified by hand, not by the harness — it reports which. Exits 2 on a fresh clone, because the documents it checks live in the gitignored `resources/`. |
| Commits on `main` | The founding documents, the working agreement, the gate tool and **17 audit records**. The design itself is **not** in the repository — `resources/specs` and `resources/roadmap` are gitignored — and Jury's most recent ruling on it is `FAIL`, which you can read in `resources/audits/`. The commit gate governs the file set under review; the trail is committed so it cannot go missing again. |
| `docs/` (public documentation) | **Does not exist yet.** Created in Phase 0. |
| `assets/` | Present — brand assets. Contents are managed by the design tooling, not by this repo's authors; do not assume a fixed file list. |
| `CLAUDE.md` | Present — the working agreement. Authoritative. |
| `.gitignore` | Present. |
| `resources/specs`, `roadmap`, `research` | Present on disk, **gitignored** — never committed. |
| `resources/audits/` | Present, and **tracked rather than ignored** — the governance trail is versioned and will be in the first commit. |
| Backend design spec | **Draft, under revision.** See [Design status](#design-status-the-spec-is-not-settled). |
| Backend roadmap | v18. Phase 0 open; `git init` and the README are done. |

What a new contributor can do today is **understand the design and the review
gate**, then pick up a Phase 0 item. See [Orientation](#orientation-what-to-read-and-in-what-order).

> **Why the README exists before the code.** The working agreement requires
> documentation to be written in the same change as the behaviour it describes,
> never retrofitted. Root `README.md` is itself a Phase 0 deliverable
> (`resources/roadmap/2026-08-08-backend-roadmap.md`). This file will be rewritten
> — not appended to — the moment there is a local environment to spin up.

---

## Who this is built for

The audience rubric is fixed and every review is graded against it.

| Audience | What they need from the product |
| --- | --- |
| Students | Textbooks and papers as audio; citations and footnotes skippable but recoverable |
| Commuting professionals | A reading backlog cleared hands-free; offline downloads |
| **Blind and low-vision users** | **Reliable TTS they can depend on.** Not a convenience feature — the product |
| Casual readers | Ebooks and long articles, low friction |

**Languages:** English, Spanish, French, Haitian Creole.

Accessibility is not a workstream that runs alongside the product; it *is* the
product. WCAG 2.2 AA is a floor, not a target, and **Halo** (the accessibility
auditor) signs off on any surface that ships.

---

## How it is meant to work

### The pipeline

Eight stages. Each hands off through the database, so any stage can be retried
independently.

```mermaid
flowchart LR
  I["1 · Ingest<br/>raw bytes → private bucket"]
  E["2 · Extract<br/>per-source adapters"]
  S["3 · Structure<br/>two LLM passes"]
  G["4 · Segment<br/>merge into TTS units"]
  N["4.5 · Normalize<br/>inserted speech + billing"]
  Y["5 · Synthesize<br/>provider router"]
  A["6 · Transcribe + Match<br/>WhisperX to display text"]
  V["7 · Serve<br/>ranges + signed URLs"]

  I --> E --> S --> G --> N --> Y --> A --> V

  E -. "text is readable from here on" .-> V
  Y -. "audio is what gets transcribed" .-> A

  classDef gate fill:#0f766e,stroke:#0f766e,color:#ffffff;
  class E gate;
  classDef key fill:#7c2d12,stroke:#7c2d12,color:#ffffff;
  class A key;
```

| # | Stage | Does | Emits |
| --- | --- | --- | --- |
| 1 | **Ingest** | Persists raw bytes to a private bucket, creates the document row | `documents` row |
| 2 | **Extract** | Per-source adapters normalise everything to one `Block[]` shape | `blocks` |
| 3 | **Structure** | Pass A: chapters, per-block language, skip candidacy. Pass B: speaker attribution | `chapters`, block flags |
| 4 | **Segment** | Merges non-skipped blocks into TTS units on sentence boundaries | `segments` |
| **4.5** | **Normalize** | Produces inserted speech (table preambles, sentinels) and the **billing** estimate of what will be spoken. It no longer places highlights (`R14-A1`) | inserted text, quote basis |
| 5 | **Synthesize** | Routes each segment to a TTS provider by language, voice, and clone status | `segment_renditions` |
| 6 | **Transcribe + Match** | WhisperX transcribes the audio we generated, returning word-level timestamps; the match step maps observed words onto display-text offsets under a monotonicity rule and a drift bound | word timings, `asr_conf`, `match_conf` |
| 7 | **Serve** | Segment ranges with state, short-lived signed URLs, word timings | API responses |

**Stage 6 is why word-level sync works.** Transcription knows what was *said*;
the page shows something different. The match step connects them, and it is the
component the whole feature rests on — which is why it carries explicit
invariants rather than a confidence score alone. A highlight that lands on the
wrong word looks exactly like one that lands on the right word.

### Three decisions that shape everything

**The segment is the universal unit** — of work, billing, caching, retry,
playback, and sync. Roughly 1,000 characters, roughly 60 seconds of audio. One
choice resolves alignment accuracy (short clips align well and in parallel),
billing precision (the spoken-character count, produced at normalization, is
what the provider bills), lazy generation
(a queue walk over ordinals), retry granularity (a failure costs one segment, not
one book), and offline download ("fetch segments N..M").

**Text before audio.** Extraction finishes in seconds; synthesis takes minutes to
hours. Reading must never wait on TTS — the dashed edge in the diagram above is a
hard requirement, not an optimisation.

**Observe what was spoken; do not predict it** (`R14-A1`, spec §6.1). Earlier
revisions said *"forced alignment, not ASR"*, on the reasoning that we know what
text we sent. We know what we **sent**; we do not know what was **said** — every
TTS provider normalizes internally (`Dr.` → "doctor", `1984` → "nineteen
eighty-four") and whether any of them can be told not to was an open question for
thirteen review rounds. So we stopped asking: we **transcribe the audio we
generated** and read the spoken form off the result. Provider normalization
becomes something we observe rather than something we must predict or negotiate.

Transcription runs on our own WhisperX sidecar, not a per-minute vendor —
Hypereal's $0.01/min is $5.40 for a 9-hour book, four times the synthesis it
would be timing.

For a user tracking their place visually, a highlight on the wrong word is a
correctness bug, not a glitch. Two failure modes, handled differently:

- **A transcribed word that matches nothing on the page** — recognition invented
  it. Excluded from the highlight map and recorded, never silently placed.
- **A transcribed word that matches the *wrong* place** — the dangerous one,
  because it looks correct. Guarded by a monotonicity rule and a drift bound over
  display offsets, and by `match_conf` — *"we know where this goes on the page"*
  — which is a **different number** from `asr_conf`, *"the engine was sure it
  heard this."* Highlighting keys on `match_conf`.

**Two degradation states, and a client must tell them apart** (H17-C2). They are
not interchangeable, and the message catalogue spends two extra keys and eight
extra strings letting a user distinguish them:

- **`degraded`** — partial coverage. Timings exist; some runs are below
  `match_conf_threshold`. The client **highlights the confident spans and skips
  the rest**, while audio plays normally.
- **`unavailable`** — no usable mapping at all. **Highlighting is off** for the
  segment; audio still plays.

The per-word decision keys on `match_conf`; the segment-level `degraded` /
`unavailable` decision keys on `align_conf_threshold`. Neither ever falls back to
estimated timings — a highlight on the wrong word is a correctness bug, and a
guessed one is indistinguishable from a real one.

### Topology

```mermaid
flowchart TB
  subgraph clients["Clients"]
    W["web/ — React + Vite<br/>library · import · player · reader"]
    M["apps/mobile/ — Expo<br/>+ camera scan · offline"]
  end

  subgraph rail["Railway"]
    K["worker/ — Node + TypeScript<br/>the pipeline, long-running jobs"]
    P["aligner/ — Python sidecar<br/>POST /align, stateless"]
  end

  subgraph sb["Supabase"]
    D[("Postgres + RLS")]
    ST[("Private Storage")]
    AU["Auth"]
  end

  T["TTS providers"]

  W --> AU
  M --> AU
  W --> K
  M --> K
  K --> P
  K --> D
  K --> ST
  K --> T
  W -. "short-lived signed URLs" .-> ST
  M -. "short-lived signed URLs" .-> ST
```

**Why one Python service in an otherwise TypeScript stack.** Transcription and word alignment have
no credible Node implementation. This is the single exception. The sidecar
exposes one endpoint and holds no state, so the seam is narrow — and the worker
codes against an `Aligner` interface, so the backend is swappable without
touching the pipeline.

---

## Repository layout

Only `assets/`, `CLAUDE.md`, `README.md`, `.gitignore` and `resources/` exist
today. Everything else is the planned shape, established in Phase 0.

```
audioMax/
├── web/               React + Vite — library, import, player, reader   ── planned
├── apps/mobile/       Expo React Native — + camera scan, offline       ── planned
├── worker/            Node/TS on Railway — the pipeline                ── planned
├── aligner/           Python sidecar — WhisperX transcribe + match     ── planned
├── supabase/          Migrations, RLS policies, thin edge functions    ── planned
├── docs/              Public technical documentation (Scribe)          ── planned
│   └── help/          Public user documentation (Guide)                ── planned
├── tools/             doc-check.mjs — the documentation consistency gate ── present
├── assets/            Brand assets (managed by design tooling)         ── present
├── resources/         Internal working documents                       ── present
│   ├── specs/ roadmap/ research/                                       ── GITIGNORED
│   └── audits/        Jury verdicts                                    ── COMMITTED
├── CLAUDE.md          Working agreement — authoritative                ── present
└── README.md          This file                                        ── present
```

Root build is a no-op; each service builds independently. Model weights for the
aligner are fetched at build time and never committed — ignored as
**`/aligner/models/`**, deliberately anchored. A bare `models/` pattern would
match `worker/src/models/` at any depth and silently swallow source files.

---

## The commit gate — read this before you write anything

> **No commit. No push. Not code, not config, not markdown. Nothing.**
>
> Every commit MUST be preceded by a review from **Jury**, the Studio Zero audit
> orchestrator. This is not advisory and there is no override.

You are meant to learn this here, not by having a commit rejected.

**`CLAUDE.md` is the single source of truth for this gate.** The table below
mirrors it; if they ever diverge, `CLAUDE.md` wins.

| Jury verdict | Condition | Commit |
| --- | --- | --- |
| `PASS` | Zero open Blocker, Critical, or Major | **Permitted** |
| `PASS WITH FIXES` | Zero open Blocker or Critical. Majors open, each with a named owner and a date | **Permitted** |
| `FAIL` | Any open Blocker or Critical | **Blocked** |

Minor and Polish findings never block a commit. They are tracked and fixed when
convenient, per Jury's own rubric.

A `FAIL` is not negotiable — rework and re-audit. *"I'll fix it in the next
commit"* is explicitly rejected by Jury's rules.

### Running the gate

Spawn a subagent whose system context is the full contents of
`studio-zero/agents/audit/jury.md`, and hand it three things:

1. **The file set under review** — paths, not summaries.
2. **The audience rubric** — Jury refuses to audit without one. For audiomax:
   students, commuting professionals, blind / low-vision users relying on TTS,
   and casual readers, across `en` / `es` / `fr` / `ht`.
3. **The relevant spec** from `resources/specs/`.

Jury returns a **Verdict**, a severity-sorted **Punch List** with owners, and a
**Scorecard**. Every report is stored under `resources/audits/<date>-<subject>.md`
— **including passes.** Silent passes are forbidden.

### Rules inherited from Jury

- **Evidence or it didn't happen.** Findings cite `file:line`, a capture, or tool
  output. Never an opinion.
- **Re-audit, don't trust.** Self-attested fixes do not close findings. Since a
  re-spawned agent is not literally the originating reviewer, **artifact
  continuity substitutes**: every finding carries a stable ID, reports are
  committed and diffable, and a re-audit resolves each ID explicitly
  (`fixed` / `open` / `disputed` — never silence) by **re-running the original
  verification command**, not by accepting a claim.
- **Reviewers get read-only tools.** Jury's "auditors do not edit" is enforced
  by tool scope, not by instructions.
- **Auditors do not edit code.** Jury flags; we implement.

### Specialist reviewers

Jury synthesises; specialists find. Each phase of the roadmap names its
reviewers. The ones this project leans on most:

| Concern | Agent | Persona |
| --- | --- | --- |
| Commit gate, audit synthesis | **Jury** | `audit/jury.md` |
| Accessibility (WCAG 2.2 AA) | **Halo** | `audit/halo.md` |
| User-facing copy | **Proof** | `audit/proof.md` |
| Backend architecture | **Forge** | `backend/forge.md` |
| API contracts | **Nexus** | `backend/nexus.md` |
| Job queues / pipeline | **Queue** | `backend/queue.md` |
| Secrets, keys, RLS | **Vault** | `backend/vault.md` |
| Schema design | **Atlas** | `data/atlas.md` |
| Security | **Shield** / **Cipher** | `security/` |
| AI eval, cost-per-interaction | **Oracle** | `ai/oracle.md` |
| i18n (`en`/`es`/`fr`/`ht`) | **Tongue** / **Locale** | `platform/` |
| Test strategy | **Probe** | `quality/probe.md` |

Personas live at `C:\Users\Administrator\studio-zero\agents\<layer>\<name>.md`.
Before proposing any tool, framework, or dependency, consult
`studio-zero/CAPABILITIES.md` — it is the source of truth for what this host can
actually run.

---

## Constraints that bind engineering

These are not preferences. A change that violates one does not pass the gate.

| # | Constraint | Consequence if broken |
| --- | --- | --- |
| 1 | **Accessibility is the product.** WCAG 2.2 AA is a floor. | A primary audience cannot use the product at all. |
| 2 | **No fallback launch.** A primary path never depends on a fallback. Degraded paths are emergency-only and must be *visible* when they engage. | A silently wrong word-sync is worse than a visibly absent one. |
| 3 | **Text before audio.** Extracted text is served the moment parsing finishes. | Reading waits hours on synthesis. |
| 4 | **Credits are characters** (1 credit = 1,000 characters synthesised). Providers bill **spoken** characters — counted after normalization, since `1984` is four characters and twenty spoken — and every render is preflighted with an exact quote before a single character reaches a provider. | Surprise debits. Partial renders. |
| 5 | **Provider keys never leave the worker.** Clients get short-lived signed URLs. RLS on every table carrying user data — by `user_id` where the column exists, by join through `documents` otherwise; `voices` is a global catalogue and is exempt. URL fetching is egress-controlled. | Key exfiltration; cross-tenant reads; SSRF. |
| 6 | **Users can delete their data.** Every document and account has a real erasure path that cascades to storage. | A DMCA takedown you cannot honour. Legal liability, not backlog. |
| 7 | **Users are told where their documents go.** A subprocessor list is maintained and disclosed — uploads reach an LLM and up to three TTS vendors — **including Google (Gemini Flash 2.5 TTS), the Haitian Creole path**; generated audio also reaches our own first-party transcription sidecar. | Undisclosed processing of medical, legal, and unpublished material. |

**A legal gate blocks all ingest.** Roadmap Phase 0.5 — DMCA agent registration,
takedown endpoint, repeat-infringer policy, ToS/AUP, retention policy,
subprocessor list — must clear before any upload endpoint ships. The product's
core loop creates and stores a derivative work from a copyrighted upload; this is
the item most likely to end the project.

Two of these have teeth in the test strategy. **A false skip — dropping real
content from the narration — is a Blocker**, because it is silent data loss for a
user who cannot see the page. A false keep (reading an extra footnote) is Minor.
The asymmetry is deliberate.

---

## Design status: the spec is not settled

**Both reviewers returned `FAIL` on the design documents.** The backend design
spec is **under revision** following accessibility review (Halo) and audit review
(Jury).

What that means for you:

- The **architecture and the principles above are the current design intent** —
  segments as the universal unit, text before audio, observation over prediction,
  visible degradation. These are what the revision is being built on.
- The **specifics are not final.** Do not treat the spec's schema columns, status
  enums, thresholds, size limits, credit ratios, or cost figures as settled, and
  do not quote them as decided. They are draft inputs to a revision, and the
  numbers in particular were derived from a rate card the spec itself flags as
  materially stale.
- **Nothing in the spec has passed the gate.** No part of it is implementable as
  written until a revision returns `PASS`.

### Known open questions

Carried in the spec and not yet closed:

All **open** rows are Phase 0 spikes, and nothing downstream is built until they
return. Struck-through rows are closed; they are kept so a reader can see what was
asked and how it was answered. **SPIKE A is now the only one gating word sync.**

| Question | Why it matters |
| --- | --- |
| **Which transcription + word-alignment engine (WhisperX or equivalent), and does it cover `es` / `fr` / `ht`?** | **Highest risk in the design**, and now the only Phase 0 spike gating word sync. Haitian Creole coverage is genuinely uncertain. |
| ~~**Can provider text-normalization be disabled?**~~ | **RETIRED (`R14-A1`).** We transcribe the audio we generated, so provider normalization is observed rather than predicted and nothing depends on the answer. |
| **Is transcription accurate enough per language — especially `ht`?** | Word sync now rests on recognition quality, which is materially weaker in Haitian Creole than in `en`/`fr`/`es`, and whose failure mode is *fluent* hallucination. **SPIKE A** must return a per-language accuracy matrix with a numeric pass bar. Until it does, `ht` word-sync quality is unknown and the quote must say so rather than guess. |
| ~~Which provider actually serves Haitian Creole TTS~~ | **CLOSED 2026-08-08, zero API calls.** Resolved from production code in the reference stack: `ht` routes to **Google Gemini Flash 2.5 TTS**, which speaks it natively; no code path calls Google Cloud TTS, so the comment claiming otherwise is stale. `ht` is **not** a launch blocker. What remains open is the row above — whether *transcription* is accurate enough in Creole, which is a different question with a different answer shape (a WER number against a bar, not a yes/no). |
| Does Fish Audio bill per UTF-8 byte? | Unverified, and it backs a schema column. One real billed call on accented French gates it. |
| Which layout-aware OCR engine | Multi-column reading order. Wrong order is *locally fluent*, so a blind user gets scrambled meaning narrated confidently. |
| Aligner container sizing | Multi-gigabyte acoustic models per language. If four cannot co-reside, the topology changes. |

The alignment-engine question is the one that can invalidate the design. The
mitigation is structural: the `Aligner` interface plus *visible, reasoned*
degradation means an unsupported language loses word highlighting but still
narrates correctly, and the user is **told**. The product degrades on one axis
rather than failing.

The inherited provider rate card question is **closed** — it was stale by
6.7–32× and is now an escalated production incident against the reference stack,
owned by Jo. See `resources/research/`.

---

## Where documentation lives

The split is strict and there is no third place. There is no wiki.

| Path | Contents | Git | Owner |
| --- | --- | --- | --- |
| `docs/` | Public technical documentation — ADRs, schema docs, API reference, runbooks | **Committed** | Scribe |
| `docs/help/` | Public user documentation — help centre, onboarding, error copy | **Committed** | Guide |
| `resources/specs/` | Design specs | **Ignored** | — |
| `resources/roadmap/` | Build checklists | **Ignored** | — |
| `resources/audits/` | Jury verdicts and punch lists | **Committed** | Jury |
| `resources/research/` | Provider pricing probes, dated evidence | **Ignored** | — |

Internal working documents never reach the repository — **with one deliberate
exception.** `resources/audits/` **is committed.** The commit gate is enforced by
those reports, and a governance trail that `git clean -xdf` can destroy is not a
trail. `.gitignore` implements this as `/resources/*` followed by
`!/resources/audits/` — note it excludes the *contents*, not the directory,
because git will not re-include a file whose parent directory is excluded. **Do
not "simplify" that back to `resources/`**; it silently un-does the exception.

Guide reports to Scribe and drafts
user-facing copy; **Proof** grades it independently before it ships on critical
surfaces — onboarding, errors, paid flows, account deletion.

**Documentation is written as features are built, never retrofitted.** A change
that alters behaviour updates its documentation in the same change. Outdated
documentation is worse than missing documentation: missing docs make you search,
wrong docs make you ship bugs.

---

## Orientation: what to read, and in what order

There is no local environment to spin up yet, so onboarding today means being
able to *participate* — understand the design, know the gate, pick up a task.
Budget about 15 minutes.

| # | Read | Minutes | You will know |
| --- | --- | --- | --- |
| 1 | This README | 5 | What the product is, what exists, what the rules are |
| 2 | `CLAUDE.md` | 4 | The working agreement and the commit gate, authoritative |
| 3 | `resources/specs/2026-08-08-audiomax-backend-design.md` | 5 | The full design — **read it as a draft under revision** |
| 4 | `resources/roadmap/2026-08-08-backend-roadmap.md` | 2 | The thirteen phases (0, 0.5, 1–4, 4.5, 5–10) and which reviewers gate each one |
| 5 | `resources/audits/` | 4 | Prior verdicts and open punch lists — **committed and diffable**. Start with the most recent; it tells you what is currently blocking a commit |

Then: the roadmap's **Phase 0 — Foundations** is the only phase currently open.
It covers the monorepo scaffold, the package-manager pin and lockfile sync that
Railway's Nixpacks requires, `/health` endpoints with correct `PORT` binding, a
complete `.env.example` with no real values, Supabase provisioning, and CI running
typecheck, lint, and test on every push. Phase 0 ends — like every phase — with a
Jury audit that must clear the gate above: no open Blocker or Critical.

---

## Conventions

**Commits.** Short conventional-commit subject. No narrated body. No AI
co-author trailer.

```
feat(worker): add EPUB spine extractor
fix(align): clamp word boundaries to segment duration
docs(help): add offline download guide
```

**Branch.** `main`, remote `origin`. The repository root is `audioMax/` itself —
verify with `git rev-parse --show-toplevel` before your first commit and stop if
it returns anything else.

**Cross-cutting rules, every phase:** documentation lands in the same change as
the behaviour · no fallback path is load-bearing on any primary flow · text is
available before audio, always · every Jury report is stored, including passes.

---

## Licence

**Undetermined.** No licence has been chosen or applied to this repository. Until
one is, default copyright applies and no usage rights are granted. Choosing a
licence is an open item, not an oversight to be resolved by assumption.
