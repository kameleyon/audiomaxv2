# audiomax.ai — Working Agreement

Convert books, PDFs, EPUBs, DOCX, articles, camera scans and pasted text into
studio-quality audio with word-level text↔audio sync. Web + mobile.

---

## MANDATORY RULE: Jury approves before anything is committed

**No commit. No push. Not code, not config, not markdown. Nothing.**

Every commit MUST be preceded by a review from **Jury** (the Studio Zero audit
orchestrator, persona at `C:\Users\Administrator\studio-zero\agents\audit\jury.md`).

### The gate

Severity-explicit, so the verdict is computable rather than a judgement call:

| Jury verdict | Condition | Commit |
| --- | --- | --- |
| `PASS` | Zero open Blocker, Critical, or Major | **Permitted** |
| `PASS WITH FIXES` | Zero open Blocker or Critical. Majors open, each with a named owner and a date | **Permitted** |
| `FAIL` | Any open Blocker or Critical | **Blocked** |

Minor and Polish findings never block a commit. They are tracked and fixed
when convenient, per Jury's own rubric (`jury.md:71-76`).

> **Why this wording** (Jury finding J-C1). The previous version said only
> `PASS` permits a commit and "there is no middle state." Since any single
> Polish nit produces `PASS WITH FIXES` by definition, that reading blocks
> every commit forever — and a gate that can never open is a gate that gets
> quietly ignored, which is worse than a loose one. The rubric has five
> severities precisely because the middle states are the useful ones.

**A `FAIL` is not negotiable.** Rework and re-audit. "We'll fix it in the next
commit" is rejected by Jury's own rules (`jury.md:13`).

### How to run the gate

Spawn a subagent whose system context is the full contents of
`studio-zero/agents/audit/jury.md`, and hand it:

1. The diff or file set under review — **paths, not summaries**.
2. The audience rubric (below). Jury refuses to audit without one (`jury.md:22`).
3. The relevant spec from `resources/specs/`.
4. **The prior audit report**, if one exists, so findings are resolved by ID.

**Grant reviewers read tools only.** They must not hold Write, Edit, or
destructive Bash. Jury's Rule 4 (`jury.md:79`) says auditors do not edit code;
enforce that with tool scope, not just instructions.

### Audience rubric

Students converting textbooks and papers · professionals clearing a reading
backlog on commutes · **blind and low-vision users who depend on reliable TTS,
treated as a primary population** · casual readers converting ebooks and
articles. Languages: **English, Spanish, French.** *(Haitian Creole was removed
from scope by the owner on 2026-08-08 — see `docs/architecture/0005`. It is not
deferred; it is out. `ht` uploads are refused by the §3.5 no-route row with an
announced `blocked_language_unsupported`, not silently mishandled.)* Consumer risk
profile, user-uploaded copyrighted documents, paid credits.

### Re-audit by finding ID

Jury Rule 6 says the *originating reviewer* re-runs the check. A re-spawned
agent is not the originating reviewer, so that property cannot hold literally
(finding J-M9). **Artifact continuity substitutes for reviewer continuity:**

1. Every finding carries a stable ID (`J-B1`, `H-C3`, …).
2. Audit reports are committed under `resources/audits/` and are diffable.
3. A re-audit opens by loading the prior report and resolving **each finding by
   ID** — `fixed` / `open` / `disputed`, never silence.
4. A re-audit re-runs the original verification command. It does not accept a
   claim that something was fixed.

### Storage

Every report — including passes — is stored at
`resources/audits/<date>-<subject>.md`. Jury Rule 5 forbids silent passes. This
project overrides the studio default template location (`jury.md:109`); that is
deliberate, not drift (finding J-m6).

---

## Documentation duty

Documentation is written **as features are built**, never retrofitted.

| Owner | Persona | Scope | Committed? |
| --- | --- | --- | --- |
| **Scribe** | `agents/docs/scribe.md` | READMEs, ADRs (`docs/architecture/`), OpenAPI, runbooks, schema docs, `CONTRIBUTING.md`, `CODEOWNERS`, glossary | Yes — `docs/` |
| **Guide** | `agents/docs/guide.md` | Help centre, microcopy, onboarding, error copy, changelog framing | Yes — `docs/help/` |

Guide reports to Scribe. **Proof** grades user-facing copy independently before
it ships on critical surfaces (onboarding, errors, paid flows, account deletion).

Scribe Rule 1: **outdated docs are worse than no docs.** A change in behaviour
updates its documentation in the same change.

---

## Document precedence

Three audits in a row found the same defect: a fix landed in the artifact where
it was raised and not in the artifact that implements it. There is now an
explicit order, so a contradiction has a resolution instead of a coin flip.

| Question | Authority |
| --- | --- |
| The commit gate, constraints, agent roster | `CLAUDE.md` |
| Design — schema, contracts, invariants, API | `resources/specs/` |
| Sequence, phase contents, reviewer assignment, owners and dates | `resources/roadmap/` |
| Orientation for newcomers | `README.md` — **mirrors, never originates** |

**A contradiction is a finding, not a judgement call.** When the spec says a
component cannot do X and the roadmap schedules building X, the spec wins and
the roadmap is defective — because the roadmap is what gets built, that defect
is Critical, not cosmetic.

## The reconciliation pass — mechanical, not remembered

Four consecutive audits found the same defect: a fix landed where it was raised
and not where it is implemented. v4 answered with a precedence order and a
narrow gate, and round 4 found six more — five of them **inside a single file**,
which precedence does not address at all. The rule was written and not run.

**The pass is a grep, and its output is pasted into the revision header.**

1. List every identifier the edit changes — column, enum, endpoint, invariant.
2. `grep -rn -F "<identifier>" CLAUDE.md README.md resources/specs resources/roadmap`
3. Paste the hit list into the revision header, and mark each line reconciled or
   deliberately unchanged. **A hit you did not look at is an unreconciled hit.**
4. Only then edit.

Doing this *after* editing is what failed four times: you patch where you
remember the concept living, and memory misses roughly a third of the sites.
`align_reason` had twelve mentions; three were updated and the author believed
the job done.

**The automated half must be bidirectional and cover every table.** v4's test
checked interface field → column, scoped to §3.2 and §7.2/§7.2a. That cannot
detect a field on the **wrong table**, a **spurious** column, or a table in §7.1
— and every field v4 then dropped landed in the excluded region. Required:

- every field in a spec interface has a column, **and** every column traces to a
  spec field (both directions);
- scope is **all of §7**, not a subset;
- it runs in the **document revision loop**, not inside Phase 1. The defect lives
  in the documents today; a gate scheduled for the migration cannot catch it.

---

## Where documents live

| Path | Contents | Git |
| --- | --- | --- |
| `resources/specs/` | Design specs | Ignored |
| `resources/roadmap/` | Build checklists | Ignored |
| `resources/research/` | Provider pricing probes, dated evidence | Ignored |
| `resources/audits/` | Jury verdicts and punch lists | **Committed** |
| `docs/` | Public technical documentation (Scribe) | Committed |
| `docs/help/` | Public user documentation (Guide) | Committed |
| `docs/architecture/` | ADRs | Committed |

---

## Studio Zero agents

Personas live at `C:\Users\Administrator\studio-zero\agents\<layer>\<name>.md`.

**Invocation (normative):** spawn a subagent with the persona file as its system
context. `task-claude.js` + `catalog.json` is the Studio Zero host mechanism and
is *not* used from this project — one mechanism only (finding J-m1).

| Need | Agent | Path |
| --- | --- | --- |
| Commit gate, audit synthesis | **Jury** | `audit/jury.md` |
| Accessibility (WCAG 2.2 AA) | **Halo** | `audit/halo.md` |
| User-facing copy review | **Proof** | `audit/proof.md` |
| UX review | **Optic** | `audit/optic.md` |
| Backend architecture | **Forge** | `backend/forge.md` |
| API contracts | **Nexus** | `backend/nexus.md` |
| Job queues / pipeline | **Queue** | `backend/queue.md` |
| Secrets, keys, RLS | **Vault** | `backend/vault.md` |
| Schema design | **Atlas** | `data/atlas.md` |
| Security / SSRF / uploads | **Shield**, **Cipher** | `security/` |
| AI eval, cost-per-interaction | **Oracle** | `ai/oracle.md` |
| Legal, DMCA, privacy | **Comply** | `operations/comply.md` |
| Billing, ledger, refunds | **Ledger** | `operations/ledger.md` |
| i18n (en / es / fr) | **Tongue**, **Locale** | `platform/` |
| Test strategy | **Probe** | `quality/probe.md` |

**Halo reviews every phase — 0, 0.5, 1, 2, 3, 4, 4.5, 5, 6, 7, 8, 9, 10.**
This list has been wrong in **five consecutive audits**, most recently by
omitting the two phases that had just been added (R5-M10). It is not maintained
here any more: **the roadmap is the sole authority for reviewer assignment**,
and this sentence is descriptive, not normative. (v6 claimed
`tools/doc-check.mjs` enforced agreement between the two. **No such check
existed** — an attestation to a fiction, in the document this file declares
authoritative, about a roster wrong in five consecutive audits. N6-C3.)
"Accessibility is the product" cannot be a claim the plan contradicts.

Consult `studio-zero/CAPABILITIES.md` before proposing any tool or dependency.

---

## Product constraints that bind engineering

1. **Accessibility is the product, not a feature.** WCAG 2.2 AA is a floor.
   The backend may not discharge an accessibility obligation onto a client that
   is out of scope — if the data isn't captured server-side, no client can
   invent it.
2. **No fallback launch.** A primary path must never depend on a fallback.
   Degraded paths are emergency-only and must be *visible, reasoned, and
   announceable* when they engage.
3. **Text before audio.** Extracted text is served the moment parsing finishes.
   Reading never waits on TTS.
4. **Credits are denominated in characters**, every render is preflighted with
   an exact quote, and **no path is unmetered** — free operations still carry
   rate limits and quotas (finding J-C2).
5. **Provider keys never leave the worker.** Clients get short-lived signed
   URLs. **RLS on every table carrying user data** — by `user_id` where the
   column exists, by join through `documents` otherwise; `voices` is a global
   catalogue and is exempt. URL fetching is egress-controlled.
6. **Users can delete their data.** Every document and account has a real
   erasure path that cascades to storage. A takedown you cannot honour is a
   legal liability, not a backlog item.
7. **Users are told where their documents go.** A subprocessor list is
   maintained and disclosed. Uploads reach an LLM and up to three TTS vendors —
   **including OpenRouter and Google** on the Gemini path. Gemini TTS is reached via OpenRouter
   (`google/gemini-3.1-flash-tts-preview`) with direct Google as the fallback
   chain, so a document reaches **both** parties — J19-M3, and the routing fact
   is established at the call site, not in a comment (`docs/architecture/0003`)
   (J14-C2). Generated audio additionally reaches our own transcription sidecar;
   that one is first-party and is disclosed as such, not as a subprocessor.

---

## Commit conventions

Short conventional-commit subject. No narrated body. No AI co-author trailer.

```
feat(worker): add EPUB spine extractor
fix(align): clamp word boundaries to segment duration
docs(help): add offline download guide
```
