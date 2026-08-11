# Contributing to audiomax.ai

This describes the repository **as it actually is today**, not as it will be. If
a step here does not match what you find on disk, that mismatch is a Scribe
finding — report it rather than working around it.

---

## 1. Phase 0 scaffolding exists; no product feature does

There is a `package.json`, a pnpm lockfile, three workspaces, two services with
`/health`, and a test suite **`pnpm test` counts for you**. Use **`pnpm test`**,
not `pnpm -r test`: `aligner/` is deliberately not a pnpm workspace, so `-r`
silently drops its tests.

```bash
pnpm test        # worker + apps/web + apps/mobile (node --test) + aligner (unittest)
```

**Nothing ingests a document, synthesizes audio or serves a segment** — every
product path is still design-only.

> **This sentence no longer states a total, and that is the fix.** The count has
> been wrong in **four consecutive rounds**, in a different way each time:
> **30** (stale since the scaffold, guarded by nothing) → **66** (round 31's
> correction, which counted `worker` and `aligner` and forgot the two client
> workspaces existed) → **76** (correct for one day) → **99** (Forge's matcher
> work took `worker` from 57 to 80). `J31-M4` was filed because this number was
> fixed in one of its two homes; the round that fixed it published a *new* wrong
> value into **both**; and the round after that went stale again through nobody's
> error at all — a peer simply wrote tests.
>
> **A number that changes whenever anyone does their job cannot live in prose in
> three files.** No `[SD-*]` guard checks it. So the durable answer is the
> command, not the integer: **`pnpm test` prints the total, and it is never
> stale.** If you need a figure for a document, run it — and expect it to have
> moved.

Use **`pnpm`** (pinned via `packageManager`), not `npm`. Zero runtime
dependencies by design: `node:http`, `node:test` and the Python stdlib. Nothing
emits, so there is no build output to ignore.

What exists is: the working agreement (`CLAUDE.md`), the root `README.md`, this
file, `CODEOWNERS`, `docs/`, the documentation gate (`tools/doc-check.mjs`),
brand assets, and **33 audit records**.

Contributing today means **documents and decisions**: picking up a Phase 0 item,
running a spike and recording its evidence, or correcting a document that has
drifted.

### What to read, in order — about 15 minutes

| # | Read | Minutes | You will know |
| --- | --- | --- | --- |
| 1 | `README.md` | 5 | What the product is, what exists, what the rules are |
| 2 | `CLAUDE.md` | 4 | The working agreement and the commit gate — **authoritative** |
| 3 | `docs/architecture/` | 4 | The **six** decisions that shape everything, and *why* — including the one that was reversed |
| 4 | `docs/glossary.md` | 2 | The vocabulary you cannot infer |

Then, if you have them locally: the spec, the roadmap, and the most recent audit
record.

---

## 2. Three gates, and you must clear all three

### Gate 1 — `doc-check` must be clean

```bash
node tools/doc-check.mjs             # must exit 0
node tools/doc-check.mjs --self-test # must report 94 passed, 0 failed
node .github/scripts/secret-scan.mjs --self-test  # must report 32 passed, 0 failed
node .github/scripts/secret-scan.mjs              # reads STAGED BLOBS, not the disk
node supabase/tests/verify_voice_langs.mjs        # static proofs, read from the migration text
```

Both self-test counts are checked by `[SD-SELFTEST]`, which obtains the
`secret-scan` number by **running** that harness rather than by keeping a second
copy of it. So these two numbers cannot drift from the harnesses: adding a guard
without a specimen, or a specimen without updating this line, turns `doc-check`
red.

The **live** half of the schema proofs needs a real PostgreSQL and runs in CI —
see §"Gate 3" below. It is not part of the local pre-commit loop.

Run **all of them** before every commit. The first checks the documents; the
second mutates the live documents in memory and re-runs the shipped checks,
proving each guard still fires on its own defect. A guard that no longer fires is
a guard that has rotted around a changed document, and it will sit green over the
defect it was written for.

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

### Gate 3 — the migrations must apply to a real PostgreSQL

`node supabase/tests/verify_voice_langs.mjs` with no arguments runs the **static**
proofs: it reads the migration text and checks that each guarantee is *declared*.
That is worth having and it is not the same as knowing the migration *works*.
`assert_rls_class_rule` can be perfectly written and still fail on a server, and
no amount of reading the SQL finds that out.

CI therefore runs a `migrations` job that creates a throwaway cluster, applies
`supabase/migrations/*.sql` in filename order with `ON_ERROR_STOP=1`, and then
runs the harness against it:

```bash
node supabase/tests/verify_voice_langs.mjs --db-url=postgresql://…
```

The live probes execute inside **one transaction that ends in `ROLLBACK`**, so
the job is re-runnable and the cluster is never mutated. The harness **refuses
any non-loopback host** unless `--allow-remote` is passed, and CI does not pass
it — the job cannot reach a real project even if the URL were wrong.

To run it locally you need a PostgreSQL you can throw away. There is no
credential and no network involved:

```bash
initdb -D /tmp/pgdata -U postgres --auth=trust --encoding=UTF8 --locale=C
pg_ctl -D /tmp/pgdata -o "-p 55432 -c listen_addresses=127.0.0.1" -l /tmp/pg.log start
for f in supabase/migrations/*.sql; do psql "postgresql://postgres@127.0.0.1:55432/postgres" -v ON_ERROR_STOP=1 -f "$f"; done
node supabase/tests/verify_voice_langs.mjs --db-url=postgresql://postgres@127.0.0.1:55432/postgres
pg_ctl -D /tmp/pgdata stop -m immediate
```

> **The version we deploy on is not declared anywhere in this repository.**
> Supabase serves PostgreSQL 15 or 17; the local verification above was done on
> 18.1, because that is what one developer's machine had. CI therefore gates
> **both 15 and 17** rather than guessing, which is strictly stronger than
> picking one. When the deploy version is written down, narrow the matrix to it
> in the same change that declares it.

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

### Cite by quotation, never by line number

Step 2's `grep -F` takes a **string**. Write your citations so they are runnable
by the same command: quote the sentence you mean and name the file. A line
number is true only for the version of the file that no longer exists, and in a
round where several people are editing, the file is being reflowed **while you
cite it**. `J30-M10` and `J31-M2` are the same defect a round apart; the ruling
after the second is general — **quotation, in every artifact, including SQL
comments and JSON.**

### When more than one person edits in the same round

The pass above runs **before** you edit, which is the one moment it cannot see a
peer's work: their change does not exist yet when you grep for it. Round 31 put
three agents on disjoint scopes; each was clean inside its own scope and **four
of that round's six new Majors were between them.**

> **Disjoint scopes do not compose. They only fail to overlap.**

So a second sweep runs **after everyone has finished and before the gate**, and
it belongs to whoever is coordinating — no individual author owns a sentence
that spans two scopes:

1. **Union** the identifiers *everyone* touched, not just your own.
2. Grep each across all four precedence documents **plus every author's files**,
   including SQL, JSON and CI YAML. A stale claim in a migration comment is a
   stale claim.
3. Grep for the phrases that describe **someone else's work as pending** —
   `out of scope`, `no CI job`, `still`, `due 20`, `Owner:`, `REPAIR:`,
   `not yet`. These are the sentences that go stale by another person's success,
   and every one of them is checked against what the round actually did.

`CLAUDE.md` is authoritative for this; the section is *"When more than one agent
writes in a round — the second sweep"*.

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
