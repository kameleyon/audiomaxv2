# Contributing to audiomax.ai

This describes the repository **as it actually is today**, not as it will be. If
a step here does not match what you find on disk, that mismatch is a Scribe
finding — report it rather than working around it.

---

## 1. There is no implementation code yet

**Nothing to install. Nothing to build. Nothing to run.** There is no
`package.json`, no lockfile, no service, no test suite. Any instruction anywhere
telling you to `npm install` this project is wrong.

What exists is: the working agreement (`CLAUDE.md`), the root `README.md`, this
file, `CODEOWNERS`, `docs/`, the documentation gate (`tools/doc-check.mjs`),
brand assets, and **27 audit records**.

Contributing today means **documents and decisions**: picking up a Phase 0 item,
running a spike and recording its evidence, or correcting a document that has
drifted.

### What to read, in order — about 15 minutes

| # | Read | Minutes | You will know |
| --- | --- | --- | --- |
| 1 | `README.md` | 5 | What the product is, what exists, what the rules are |
| 2 | `CLAUDE.md` | 4 | The working agreement and the commit gate — **authoritative** |
| 3 | `docs/architecture/` | 4 | The four decisions that shape everything, and *why* |
| 4 | `docs/glossary.md` | 2 | The vocabulary you cannot infer |

Then, if you have them locally: the spec, the roadmap, and the most recent audit
record.

---

## 2. Two gates, and you must clear both

### Gate 1 — `doc-check` must be clean

```bash
node tools/doc-check.mjs             # must exit 0
node tools/doc-check.mjs --self-test # must report 67 passed, 0 failed
```

Run **both** before every commit. The first checks the documents; the second
mutates the live documents in memory and re-runs the shipped checks, proving each
guard still fires on its own defect. A guard that no longer fires is a guard that
has rotted around a changed document, and it will sit green over the defect it
was written for.

`doc-check` verifies bidirectional field coverage (every spec interface field has
a column **and** every column traces to a field), migration coverage, 17
prose-regression guards, load-bearing invariants, span kinds, phase scoping, an
end-to-end control chain, and the claims the documents make about themselves
(revision number, guard count, audit roster).

**If your edit turns the gate red, fix your edit — not the gate.** Weakening a
check to make a document pass is the exact failure mode the tool was rebuilt to
eliminate; its own source carries the history.

> **Honest caveat: `doc-check` exits 2 on a fresh clone.** Two of the four
> documents it checks (`resources/specs/`, `resources/roadmap/`) are
> **gitignored**, so a clean clone does not have them and the tool reports
> `NOT RUN — the private design documents are absent`. **Exit 2 is not a pass.**
> It is an authoring gate, not CI: it only means anything where those documents
> exist. If you are working on the design and see exit 2, your working copy is
> incomplete — get the documents from the owner.

### Gate 2 — the Jury commit gate is mandatory

> **No commit. No push. Not code, not config, not markdown. Nothing.**

Every commit MUST be preceded by a review from **Jury**, the Studio Zero audit
orchestrator. This is not advisory and there is no override. `CLAUDE.md` is the
single source of truth for it; the table below mirrors it, and if they ever
diverge, `CLAUDE.md` wins.

| Jury verdict | Condition | Commit |
| --- | --- | --- |
| `PASS` | Zero open Blocker, Critical, or Major | **Permitted** |
| `PASS WITH FIXES` | Zero open Blocker or Critical. Majors open, each with a named owner and a date | **Permitted** |
| `FAIL` | Any open Blocker or Critical | **Blocked** |

Minor and Polish findings never block a commit. **A `FAIL` is not negotiable** —
rework and re-audit. *"I'll fix it in the next commit"* is rejected by Jury's own
rules.

**How to run it.** Spawn a subagent whose system context is the full contents of
`studio-zero/agents/audit/jury.md`, and hand it four things:

1. the **file set under review** — paths, not summaries;
2. the **audience rubric** — Jury refuses to audit without one: students,
   commuting professionals, **blind and low-vision users who depend on reliable
   TTS as a primary population**, and casual readers, across `en`/`es`/`fr`;
3. the relevant **spec** from `resources/specs/`;
4. the **prior audit report**, if one exists, so findings are resolved by ID.

**Reviewers get read-only tools.** Jury's rule that auditors do not edit code is
enforced by tool scope, not by instructions — never grant a reviewer Write, Edit
or destructive Bash.

**Every report is stored**, including passes, at
`resources/audits/<date>-<subject>.md`. Silent passes are forbidden. A re-audit
opens by loading the prior report and resolving **each finding by ID** —
`fixed` / `open` / `disputed`, never silence — and by re-running the original
verification command rather than accepting a claim that something was fixed.

---

## 3. Where things live, and what git does with them

| Path | Contents | Git | Owner |
| --- | --- | --- | --- |
| `docs/` | Public technical documentation — ADRs, glossary, schema docs, API reference, runbooks | **Committed** | Scribe |
| `docs/help/` | Public user documentation — help centre, onboarding, error copy | **Committed** | Guide |
| `resources/specs/` | Design specs | **Ignored** | — |
| `resources/roadmap/` | Build checklists | **Ignored** | — |
| `resources/research/` | Provider pricing probes, dated evidence | **Ignored** | — |
| `resources/audits/` | Jury verdicts and punch lists | **Committed** | Jury |

`resources/audits/` is committed **on purpose**: the commit gate is enforced by
those reports, and a governance trail that `git clean -xdf` can destroy is not a
trail. `.gitignore` implements this as `/resources/*` followed by
`!/resources/audits/` — it excludes the *contents*, not the directory, because
git will not re-include a file whose parent directory is excluded. **Do not
"simplify" that back to `resources/`**; it silently un-does the exception.

**Document precedence.** When two documents disagree:
`CLAUDE.md` > `resources/specs/` > `resources/roadmap/` > `README.md`, which
**mirrors and never originates**. A contradiction is a **finding**, not a
judgement call — report it; do not pick a side and edit quietly.

---

## 4. Before you edit: the reconciliation pass

This is a `grep`, not a memory exercise, and it runs **before** the edit:

1. List every identifier your edit changes — column, enum, endpoint, invariant.
2. ```bash
   grep -rn -F "<identifier>" CLAUDE.md README.md resources/specs resources/roadmap
   ```
3. Paste the hit list into the revision header and mark each line **reconciled**
   or **deliberately unchanged**. A hit you did not look at is an unreconciled
   hit.
4. Only then edit.

Doing this *after* editing is what failed four times: you patch where you
remember the concept living, and memory misses roughly a third of the sites.

---

## 5. Commits

Short **conventional-commit subject**. No narrated body. No AI co-author
trailer.

```
feat(worker): add EPUB spine extractor
fix(align): clamp word boundaries to segment duration
docs(help): add offline download guide
docs(architecture): record the observed-not-predicted reversal
```

**Branch.** `main`, remote `origin`. The repository root is `audioMax/` itself —
verify before your first commit and stop if it returns anything else:

```bash
git rev-parse --show-toplevel   # must be .../audioMax
```

This check exists because the host's **home directory is itself an initialized
git repository**. A mis-rooted `git init` here would stage `.ssh/` and
`.claude.json` on the first `git add`.

### Line endings — read this before you write a file on Windows

**Preserve LF.** Every tracked document in this repository uses LF. A CRLF
conversion makes every ` ```ts ` fence in the spec invisible to `doc-check`,
which turns whole check families vacuous.

`core.autocrlf` is `true` on this host, so git converts LF → CRLF **on
checkout**. Before writing files with any Windows tool, confirm what you are
about to produce, and confirm afterwards:

```bash
file README.md CONTRIBUTING.md    # must NOT say "with CRLF line terminators"
```

If a document arrives with CRLF, convert it back to LF before running the gate;
a `HARVEST` finding from `doc-check` is the usual first symptom.

---

## 6. Documentation duty

**Documentation is written as features are built, never retrofitted.** A change
in behaviour updates its documentation **in the same change**.

| Owner | Scope |
| --- | --- |
| **Scribe** | READMEs, ADRs (`docs/architecture/`), OpenAPI, runbooks, schema docs, this file, `CODEOWNERS`, the glossary |
| **Guide** | Help centre, microcopy, onboarding, error copy, changelog framing |

Guide reports to Scribe. **Proof** grades user-facing copy independently before
it ships on critical surfaces — onboarding, errors, paid flows, account deletion.

**Scribe Rule 1: outdated docs are worse than no docs.** Missing docs make you
search; wrong docs make you ship bugs.

### Adding an ADR

A decision that changes the architecture, reverses a previous decision, or
commits the product to a vendor gets an ADR in `docs/architecture/`. Read
[`docs/architecture/README.md`](docs/architecture/README.md) first — it fixes the
format, the numbering, the status vocabulary, and the rule that a superseded ADR
is never deleted. Then add your file and a row to the index table.

---

## 7. Constraints that bind every change

A change that violates one of these does not pass the gate. Full text in
`CLAUDE.md`; the short form:

1. **Accessibility is the product**, not a feature. WCAG 2.2 AA is a floor, and
   the backend may not discharge an accessibility obligation onto a client that
   is out of scope.
2. **No fallback launch.** A primary path never depends on a fallback. Degraded
   paths are emergency-only and must be *visible, reasoned and announceable* when
   they engage.
3. **Text before audio.** Extracted text is served the moment parsing finishes.
   Reading never waits on TTS.
4. **Credits are characters**, every render is preflighted with an exact quote,
   and **no path is unmetered**.
5. **Provider keys never leave the worker.** Clients get short-lived signed URLs.
   RLS on every table carrying user data. URL fetching is egress-controlled.
6. **Users can delete their data**, with a real erasure path that cascades to
   storage.
7. **Users are told where their documents go.** The subprocessor list is
   maintained and disclosed.

Two of these have teeth in the test strategy: a **false skip** — dropping real
content from the narration — is a **Blocker**, because it is silent data loss for
a user who cannot see the page. A false keep (reading an extra footnote) is
Minor. The asymmetry is deliberate.

---

## 8. Before proposing any tool or dependency

Consult `studio-zero/CAPABILITIES.md`. It is the source of truth for what this
host can actually run. Do not add a dependency that is not listed there without
escalating.
