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

### When more than one agent writes in a round — the second sweep

The pass above runs **before** editing. That is the right time for one author
and the **one moment it cannot work for several**, because a peer's edit does
not exist yet when you grep for it. Round 31 dispatched three agents on disjoint
scopes; each was clean inside its own scope, and **four of the round's six new
Majors were between them** — a migration recording a file as unfixed while the
commit fixed it, a grep block whose coordinates a peer was moving as it was
written, a roadmap item declaring a CI job absent that a peer was building, a
test count corrected in one of its two homes.

> **Disjoint scopes do not compose. They only fail to overlap.**

So when N > 1 agents write in one round, the orchestrator runs a **second sweep
after all agents report and before the gate**, and it is not the same grep:

1. **Union the identifiers** every agent touched — not just your own.
2. Grep each across **all four precedence documents plus every agent's files**,
   including SQL, JSON artifacts and CI YAML. A stale claim in a migration
   comment is a stale claim.
3. **Grep for peer-scope assertions specifically** — the phrases that describe
   another agent's work as pending: `out of scope`, `no CI job`, `still`,
   `due 20`, `Owner:`, `REPAIR:`, `not yet`. Every hit is checked against what
   the round actually did, because these are the sentences that go stale by
   someone else's success.
4. **Cite by quotation, never by line number** — in every artifact, including
   SQL comments. A peer reflows the file you are citing while you cite it.

**The seams belong to the orchestrator.** No agent owns the sentence that spans
two scopes, so if the orchestrator does not run this sweep, nobody does — and
the round passes cleanly in every scope while failing between them.

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
| Frontend structure | **Arch** | `frontend/arch.md` |
| UI components | **Vega** | `frontend/vega.md` |
| Mobile / PWA | **Touch** | `frontend/touch.md` |
| Accessibility *engineering* (distinct from Halo's *audit*) | **Access** | `frontend/access.md` |
| Frontend performance | **Prism** | `frontend/prism.md` |

The five frontend rows were added 2026-08-09. They were missing while `apps/web/`
and `apps/mobile/` existed and were owned in `CODEOWNERS` by **Halo and Optic —
two audit-layer agents and no author** (J28-M5). This file is the authority for
the roster, so a persona `CODEOWNERS` assigns must appear here; the omission made
the front end look reviewed when it was unwritten. **Halo audits accessibility;
Access builds it.** Collapsing the two is how "accessibility is the product"
turns into the auditor writing the code and nobody reviewing it.

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
   column exists, by join through `documents` otherwise. **The exemption is a
   class, not a name (H26-C3):** a table is exempt when it carries no user data
   at all, which today is **two** tables — `voices` and `voice_langs` (spec
   §7.1a) — not whichever one is called `voices`. URL fetching is
   egress-controlled. *(This named `voices` alone while §7's rule had already
   grown to two, and an enumeration goes stale the first time the set grows.
   Scheduled Scribe · 2026-08-15; closed early, 2026-08-10, because the
   reconciliation grep surfaced it while constraint 7 was being edited.)*
6. **Users can delete their data.** Every document and account has a real
   erasure path that cascades to storage. A takedown you cannot honour is a
   legal liability, not a backlog item.
7. **Users are told where their documents go.** A subprocessor list is
   maintained and disclosed. **TTS is TWO vendors, not three: Fish Audio
   `s2-pro` and Lemonfox.** Text additionally reaches an LLM via **OpenRouter**.
   Generated audio reaches our own transcription sidecar; that one is
   first-party and is disclosed as such, not as a subprocessor.

   **CORRECTED 2026-08-09 (J29-C3).** This clause read *"up to three TTS vendors
   — including OpenRouter and Google on the Gemini path… with direct Google as
   the **fallback chain**."* Gemini was only ever the Haitian Creole TTS route;
   `ht` left scope on 2026-08-08 (`docs/architecture/0005`) and the route left
   with it, but this clause did not — **so the file that declares constraint 2,
   "no fallback launch," described a live primary-to-fallback chain four
   constraints below it.** Spec §3.5 was corrected first and this was not, which
   is a document-precedence inversion: this file outranks the spec, so the stale
   text here was authoritative.

   **Open, and it must close before any ingest endpoint ships:** OpenRouter
   dispatches to a model host, and that host is a subprocessor the user is
   entitled to be told about. The Gemini-era answer was "Google". With the TTS
   route gone, **the LLM model has not been chosen and therefore the host cannot
   be named.** Shipping ingest while the list says "an LLM" is this constraint
   breached, not deferred. Owner: **Comply** with **Forge** · **due 2026-08-15**,
   and in no case later than the first ingest endpoint.

   *(J30-m4 — this read "due before Phase 5" and nothing else. A phase gate is
   not comparable with the dates every other open item in these documents
   carries: it cannot fall overdue, it cannot be sorted next to `Forge ·
   2026-08-14`, and the commit gate's `PASS WITH FIXES` row requires "a named
   owner and a date", which a phase is not. The phase condition is kept because
   it is the harder of the two — whichever arrives first binds.)*

---

## Commit conventions

Short conventional-commit subject. No narrated body. No AI co-author trailer.

```
feat(worker): add EPUB spine extractor
fix(align): clamp word boundaries to segment duration
docs(help): add offline download guide
```
