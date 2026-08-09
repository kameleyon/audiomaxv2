# Audit Record — Founding Documents, Round 28

- **Date:** 2026-08-09 · **Subject:** the first commit containing **runnable code** — Atlas's `supabase/` migrations, Forge's guard repairs and Phase 0 scaffold, and the seam reconciliation
- **Reviewer:** Jury · **Response:** v28
- **Authorship provenance:** ruling by Jury; **transcribed by the audited party.** States what was true at the ruling; the two README lines were amended after it.

## Verdict

**`PASS WITH FIXES` — 0 Blocker · 1 Critical · 6 Major · 4 Minor. The commit proceeds**, after two one-line README amendments (`:185`, `:233`).

**Why a Critical did not block.** Jury's reasoning, recorded because it is a precedent:

> *The Critical is a defect in a control that **did not exist before this commit** — `HEAD` contains no secret scanner at all. Refusing the commit leaves the repository with strictly **less** protection than accepting it. And I verified the commit's own bytes are clean: because `git diff --name-only` is 0, the scan covered exactly the staged blobs. **This commit carries no key. The control is weaker than advertised; the artifact is safe.***

## The Critical — the secret scanner was defeated twice

**J28-C1.** The scanner enumerates paths with `git ls-files` (**the index**) and reads them with `readFileSync` (**the disk**). `git commit` writes the index.

```
index has key: 1 | worktree has key: 0
secret-scan: clean — 0 findings          exit 0
```

On this machine `doc-check`'s `[STAGED]` guard catches the divergence. **On any clone without `resources/` — every contributor who is not the owner — `doc-check` exits 2 and runs no checks at all**, including `[STAGED]`, and CI treats 2 as a pass. Jury reproduced that state: a live key in a staged blob passes both gates and ships.

> *This is round 22's Critical and round 27's Critical — **read from staged blobs** — reproduced inside the one file whose stated subject is four live API keys.*

**J28-M1.** Two of the four real keys have **no vendor rule**; their only coverage is `assigned-secret`, which requires an **uppercase variable name**. Synthetic keys of identical shape, staged in an `Authorization: Bearer` header and a lowercase `api_key =` — this project's own Python idiom — passed both gates clean. The `.env.example` backstop collapses onto the same assumption: it requires an uppercase letter in the *value*, and one of the four keys does not have one.

## Four of five round-27 Majors closed, three by re-breaking them

`J26-M3` — Jury reintroduced the original defect verbatim and got `[ART-VACUOUS]` **CRITICAL, exit 1**, where the old code returned 0 silently. `J26-M5` — proven under `touch -t` setting every file to an identical timestamp, the fresh-clone condition the old check could never fire in. `J26-M1/M2` — absent figures caught in prose *and* numeric form; counted abstention verified at 9.

> *Four of five closed, three by mutation against the original defect. **That is the strongest guard-repair round in the series.***

## `J26-M4` reopened — the denylist became an allowlist

**J28-M2.** One row above the refusal:

```
| Any other voice | Lemonfox |
| **Any other language** | **NO ROUTE...
```

→ `doc-check: clean`, exit 0. Every rendition has a voice, so the row is total and `NO ROUTE` is unreachable. Leg 2 tests whether a row **mentions** a dimension stem, and `voice` is unconditionally a stem — so the guard cannot distinguish *"Cloned voice, any language"* (a genuine restriction) from *"Any other voice"* (a catch-all), **because it never asks whether the dimension narrows anything.**

Fourth recurrence: `J17-C1` → `J22-M6` → `J26-M4` → `J28-M2`.

## The seam moved to the boundary of each fix — three times

- `roadmap:162` corrected; **`roadmap:159`, three lines above, still carried `~$0.07-$0.15`** — the exact figure `J26-C2` named.
- `README:229-232` marked `present`; **`README:233` left `planned`, four lines below — in the commit that creates `supabase/`.**
- `CODEOWNERS:79` path corrected, **owner set not**: restoring Halo's WCAG ownership also handed **8 runtime TypeScript files to two audit-layer agents and no creator**, and **9 files fall only to `*  Jury`** — including `.github/scripts/secret-scan.mjs` and `.env.example`, the two files that *constitute* the key-material control, while `.gitignore` is Vault's. **Vault owns the ignore rule and not the scanner.**

> *Nobody is being careless. The fixes are correct. **It's that a fix draws a line, and the line is where the next problem lives.** The answer isn't to try harder — it's to run the check one more time on the three lines either side of it.*

## Also open

`J28-M3` present/planned markers have **no guard** — flipping `worker/` to `planned` leaves the gate clean · `J28-M4` **cost is tracked by no guard**: replacing `$0.165–$0.224` with `$0.01–$0.02` passes clean · `J28-M6` `verify_voice_langs.mjs` is invoked by **no CI job and no script** — 16 proofs with zero automated invocation · Minors: the RLS rule's `unclassifiable` leg never tests `relrowsecurity`, so a correctly-protected table keyed on `owner_id` blocks every later migration; the rule scans `relkind='r'` only, so partitioned parents are invisible.

**Migrations remain unvalidated** — Jury attempted it; `initdb` succeeded but no Postgres could start in the sandbox and Docker was not running. Contained: no CI job and no script applies them.

## What did not break

> *Atlas's class rule is the best structural idea in this repository, and its two self-reported guard failures were real and correctly reported. Its refusal to add a CHECK enforcing a third of the bar while reading as the whole was the correct call. Forge's `PORT` refusal is right and tested. **Both agents reported findings against their own work, and Atlas found a design gap in something I had praised. That is the behaviour this process exists to produce.***

## The next gate must require, by execution

`secret-scan` reading `git show :path`, plus a rule keyed on value **shape** not variable name, with Lemonfox- and Hypereal-shaped synthetics proven caught in a `Bearer` header and a lowercase `api_key =` · a `[NO-ROUTE-TOTAL]` leg testing **restriction**, with `| Any other voice | Lemonfox |` proven to fire · `/apps/` given a creator co-owner, `.env.example` and `.github/scripts/` given Vault, then Forge's `[WS-OWNED]` guard green · `verify_voice_langs` in CI · guards on present/planned and on cost figures · migrations parsed by a real Postgres before any `db push`.
