# Audit Record — Founding Documents, Round 20

- **Date:** 2026-08-08 · **Subject:** the Haitian Creole scope removal — spec, roadmap, `README.md`, `CLAUDE.md`, `docs/architecture/` (5 ADRs), `docs/glossary.md`, `CONTRIBUTING.md`, `CODEOWNERS`, `tools/doc-check.mjs`
- **Reviewer:** Halo · **Response:** v20
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 54/54

> **Written late (J22-C2).** This record and `-round21.md` did not exist while
> five artifacts cited their findings. `SD-UNWRITTEN` — the guard built in v20 to
> catch precisely that — matched `J` and `N` prefixes and **not `H`**, so it sat
> green over two missing Halo records. Jury: *"A guard that knows one alphabet
> checks one reviewer."* Fixed in v22; the guard fired on four documents the
> moment it learned the prefix.

## Verdict

**FORECLOSES — 0 Blocker · 4 Critical · 15 Major · 5 Minor.** Halo cannot issue
`PASS` pre-implementation and states so once.

## The finding of the round

**The removal was a 166-site find-and-replace, and it broke 26 sites.** Halo's
own summary:

> *ADR-0005 is the most honest document in this repository about **why** a thing
> was done, and its own directory contradicts it on **what** was done. The
> decision needed no defence and got a good one. **The implementation got a
> find-and-replace.***

## The Critical that matters, and why it was created by the removal

**H20-C1 — the refusal has no catalogue string.** `blocked_language_unsupported`
is a `segment_renditions.status`; the catalogue is keyed on `align_status` ×
reason set; **none of the 20 keys is a status.** So §8.2 hands a client the
integer `3` and no key resolves it into a sentence.

> *While `ht` was in scope the population that hits this path was **empty by
> construction** — the routing table was total (`J17-C1`) — so the missing string
> cost nothing. **ADR-0005 made the path reachable and did not budget its
> words.** That is the defect you told me to assume existed, and it is at the
> exact seam you predicted.*

The refusal was computed correctly, guarded correctly, delivered before payment —
and could not be rendered into a sentence in any supported language. **A refusal
that is not announced is worse than a refusal.** WCAG 4.1.3.

## The other three

| ID | Finding |
| --- | --- |
| **H20-C2** | The Phase 0 accessibility gate was **specified to fail unconditionally**: its pass criterion required a string *"in all three languages"* and, two sentences later, that it fail on *"an `align_reason` with no string in `ht`"* — for a language whose strings had just been deleted |
| **H20-C3** | The 80→60 catalogue reduction was claimed and not propagated; two committed ADRs still budgeted 80, and the superseded 15-reason-set arithmetic still stood in present tense beside the current number |
| **H20-C4** | SPIKE A's scope paragraph **claimed eleven languages, listed three, denied the three were the three**, and argued from *"a `de` passage in an `fr` document now gets audio"* — which `INV-NO-ROUTE` makes false |

## Substitution damage — a sample

`README:391` *"an unsupported language is served natively"* — **self-refuting**;
if it is served it is not unsupported. Three sites told users *"Word sync isn't
available in an unsupported language **yet**"* — where *"yet"* contradicts
`CLAUDE.md`'s *"not deferred; it is out"*, and the user gets no audio at all.
`CODEOWNERS` still provisioned `/i18n/ht/` with owners for strings that had been
deleted. `ADR-0002` **falsified a quotation inside quotation marks** — in the one
ADR round 19 certified for quotation discipline.

## The structural finding

> *`DOCS` was extended 7 → 13 and **the checks were not.** Thirteen files read,
> two checked. Every Critical I found sits in an artifact `DOCS` now reads and no
> check inspects. **The gate exits 0 on a file set containing four Criticals.
> That is the honest measure of what 54/54 currently means.***

## What Halo credited

The refusal **machinery** — raiser, column, pre-payment computation, no-`402`
route, and `INV-NO-ROUTE` guarding the one line it hangs on: *"the best work in
this file set."* `J17-C1` closed by mechanism, not assertion. And ADR-0005 itself
on the decision: it states the removal needs no technical justification and then
declines to supply one, leads with *"Read this before assuming Creole was dropped
because it did not work. It worked,"* and names the loss under its own heading.
*"A record written against its author's interest, and it is the standard the
other documents failed to meet."*
