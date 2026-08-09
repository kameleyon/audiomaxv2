# Audit Record — Founding Documents, Round 22

- **Date:** 2026-08-08 · **Subject:** the staged commit set (24 paths) — the `ht` scope removal, the round-20/21 repairs, and **SPIKE A's first run**
- **Reviewer:** Jury, **on synthesis** — Halo's round-21 report present before ruling · **Response:** v22
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 54/54 · `.env` **not staged**, `.gitignore:22`, staged-blob secret scan **clean**

## Verdict

**`FAIL` — 0 Blocker · 2 Critical · 9 Major · 3 Minor.**

Jury was explicit about what this `FAIL` is not:

> *Halo's three Criticals are **genuinely, correctly fixed** — I verified each by
> reading the mechanism, not the claim. SPIKE A is real measurement and I am
> admitting it. Neither Critical below is a design defect. Both are about the
> same thing: **the artifact under review is not the artifact that would be
> committed**, and the trail that justifies the commit does not contain the
> audits that produced it.*

## The two Criticals

**J22-C1 — the repair set was unstaged.** Every round-20/21 fix — all three of
Halo's Criticals, the catalogue derivation, the counts, the guard anchoring —
existed only in the working tree. `git show :README.md` and
`git show :docs/architecture/0004-…md` returned the **broken text verbatim**.

The mechanism, which is the durable lesson:

> **The gate reads the working tree. The commit writes the index. Nothing
> reconciles them.** `doc-check.mjs` is `readFileSync` on a path — it has never
> inspected a staged blob. `CONTRIBUTING.md` documents Gate 1 as two commands and
> Gate 2 as a Jury review of *"the file set under review"*. **Neither gate
> contains a `git add`.** A green gate and a Jury pass can both be earned on
> files the commit will not carry.

This is the direct descendant of round 18's ruling that the gate governs *the
file set under review* — that resolved spec-vs-commit-set and left
**worktree-vs-index** untouched.

**J22-C2 — Halo's rounds 20 and 21 had no audit record, and `SD-UNWRITTEN` was
blind to Halo's prefix.** Five artifacts cited `H20-*`/`H21-*` findings; the
guard built in v20 for exactly this class matched `J\d\d-` and `N\d\d-` and not
`H\d\d-`.

> *Round 19's record boasts that `SD-UNWRITTEN` caught `J16-M8` "for the first
> time by the gate rather than by a human." **It caught it in one alphabet.**
> A guard that knows one alphabet checks one reviewer.*

Aggravating: `resources/audits/` is committed **as the trail**, and `README.md`
points a reader at it — so it would have shipped missing its two most recent
audits, and Jury had just ruled on three Criticals from a chat message, which
`CLAUDE.md:66-71` forbids.

## Ruling on SPIKE A — admissible in one direction

**Admissible.** Jury's reasoning on the mid-run matcher amendment:

> *The amendment **did not move the verdict**. Before: 91.7/90.9/91.7, FAIL.
> After: 100% match rate, and the bar quantity 70.8/77.3/79.2 — **still FAIL on
> both bars.** An instrument change that cannot manufacture a pass is debugging,
> not p-hacking.*

On the three drift methods:

> *Method 1 gave 100%. Method 2 gave 37.5%. Method 3 gave 70.8%. **The method
> finally used is neither the most permissive nor the one reached for first — it
> is the one §6.1 named in advance.** Convergence on a pre-specified method, away
> from a more flattering number, is what measurement looks like.*

**The precedent, stated as three testable legs.** A spike is admissible when
(a) the decision boundary — bars, scope, language set — is fixed and dated
*before* the run; (b) any mid-run instrument change is recorded with
before-and-after numbers and does not move the verdict; (c) the change is
**independently falsifiable**. SPIKE A satisfies (a) and (b) and **fails (c)**:
`fixtures.json` declared the falsification condition — *"if a run reports 100%
matched and these were not resolved by the normalizer path, the harness is
measuring the wrong thing"* — and `expect_hard` appears in **no code**. The
tripwire was specified and never wired up.

> **A spike whose instrument was amended mid-run may be cited in the direction
> the amendment worked *against*, and not in the direction it worked *toward*.**

- **Admissible, no re-run:** all three languages **fail both bars** at
  70.8/77.3/79.2 within 250 ms, median ~100 ms, p95 393–540 ms. A loosened
  matcher cannot manufacture a failure.
- **Not admissible without a re-run against a frozen matcher:** the 100% match
  rate, the claim that normalisation works, the per-language accuracy matrix.
- **Cost is supported, not settled** (J22-M9): 36–77× cheaper is a 17,000×
  extrapolation from ~1.9 s per language, on unrecorded hardware, with the clock
  started after model load.

## Majors of record

`J22-M1` audio provenance covers 1 of 3 languages · `J22-M2` `expect_hard`
unevaluated · `J22-M3` the emitted drift provenance string describes the
**rejected** global method while the code computes local interpolation ·
`J22-M4` endpoints credited in-bound by fiat, inflating by 8.3 points on `en` ·
`J22-M5` **35 of 38 checks target two files** · `J22-M6` `INV-NO-ROUTE` cannot
detect totality restored *by addition* — the identical weakness `H20-M6` proved
on `INV-RM-HALLUCINATION`, fixed there and not here · `J22-M7`/`J22-M8` counts
and mis-citations · `J22-M9` the cost extrapolation.

## The six-round pattern, named

> *The seam is always at **the boundary of the last fix**. Round 19 extended
> `DOCS` 4→7 and the Criticals moved to the unread files; round 20 extended 7→13
> and they moved to the read-but-unchecked files; round 21 anchored
> `INV-RM-HALLUCINATION` and the identical weakness survives in `INV-NO-ROUTE`.
> **Each fix is correct and each is scoped to its own instance rather than its
> class.**

## Verified clean

`.env` not staged; `git check-ignore` → `.gitignore:22`; a regex scan of every
staged blob for `sk-*`, `AIza*`, `sk_live_*` and JWT shapes returned nothing.
**H21-M1 genuinely closed** — the catalogue derivation is arithmetically sound
and shows its work (~50 keys / ~150 strings, correctly noting
`SpanReason ⊇ SkipReason` so skip reasons are not double-counted).
