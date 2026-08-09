# Audit Record — Founding Documents, Round 17

- **Date:** 2026-08-08 · **Subject:** spec v17, roadmap v17, `README.md`, `CLAUDE.md`, `.gitignore`, `tools/doc-check.mjs`, `resources/audits/`
- **Reviewers:** **Halo first, then Jury on synthesis** · **Response:** v18
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 46/46 → **49/49**

**This is the gate ruling on the first commit**, requested by Jo: *"commit and
start with phase 0 — do not commit without a full pass from Jury."*

## Verdicts

| Reviewer | Verdict |
| --- | --- |
| **Halo** | **ENABLES** — 0 Blocker · 5 Critical · 11 Major · 4 Minor. **No foreclosure found, for the first time.** |
| **Jury** | **`FAIL`** on the design — 0 Blocker · 3 Critical · 10 Major · 2 Minor. **Commit permitted** on the file set under review. |

## Halo withdrew its round-14 characterisation

> *`R14-A1` was the right call, and **v17 is the first revision in which a
> competent client team could build a correct reader from these documents.** A
> blind reader is better off under v17 than under v14, and I withdraw my
> round-14 characterisation.*

It also **re-graded its own four-round-standing `table_cell` foreclosure Critical
→ Major** on changed facts — *"I will not hold a Critical for a fourth round on
facts that moved"* — and Jury accepted the downgrade explicitly: *"a reviewer
re-grading its own long-standing finding downward on changed facts is the
behaviour I want, not a lapse."*

## Jury reversed itself on N13-C1, and Halo was right for four rounds

Halo disputed Jury's round-16 **Major** and sustained **Critical**, with an
argument Jury had not seen: `speech_blocker` has **no raiser**, not merely no
column.

- `spec:1418` defines the raiser as *"any language with no provider row in the
  §3.5 routing table."*
- §3.5 ended `| Everything else | Google / Gemini TTS |` — **a row with no
  language condition**, making routing *total over languages*. No `segments.lang`
  could fail it, so the qualifying set was empty by construction.
- So the field reported **0 for every document** while four artifacts promised
  otherwise, and `roadmap` scheduled `blocked_language_unsupported` as *"built
  and reachable"*.

Jury: *"**Adding a column does not fix this.** That is what my Major assumed and
it is false. A column with no reachable write is still a zero."* And on its own
grade: *"I wrote 'a pre-payment field that always returns 0 is worse than absent'
and then graded it Major. **A severity that contradicts its own stated harm is
not a severity, it is a hedge.**"*

It was also an **unevidenced universal capability claim about a provider** — the
exact class this project spent five rounds deleting as `normalization_opaque`,
reintroduced as a table row.

**Closed in v18** by making the routing table non-total: eleven enumerated
languages plus an explicit **no-route** row that raises
`blocked_language_unsupported`.

## The `align_blocker` column, third consecutive round

`J15-C1` (two enums) → `J16-C2` (the fix moved the value) → `J17-C2` (the move
was made by addition without deletion). Jury:

> **At this column, every fix by addition has produced a Critical. The next
> revision must be made by deletion first, edit second.**

v18 found a **fourth** site while fixing it — `roadmap:281` put
`transcription_unreliable` on `segments` as well. Closed by splitting on the kind
of fact: `segments` carries the voice-independent pair, `segment_renditions`
carries the voice-dependent pair, and both reach the quote because
`GET /quote?voice_id=` takes the voice as a parameter.

## Halo's one thing: the bar that set its own pass rate

The match contract named *"a drift bound"* with **no number**, while SPIKE A's
pass bar was *"share of words matched inside the drift bound ≥ 95%."* Circular:
whoever ran the spike would pick the bound after seeing the results and thereby
pick the pass rate, with nobody to defend the choice to.

> *This document set caught that exact pattern once already — it built
> `mean_tokens_per_group` as a monitored metric specifically because "an
> implementer hitting spurious failures merges groups, the cheapest fix." The
> same sentence applies word for word to a drift bound chosen to make `ht` pass.*

**Fixed at 250 ms, stated before the spike runs**, movable only publicly with the
reason recorded — and a **`hallucination_rate`** metric added, because
`p95_abs_error_ms` is a *timing* bound and the documented Creole failure mode is
a **fluent** hallucination: timed perfectly, mapped to the wrong word.

## The gate-scope question, resolved

Jury resolved it explicitly rather than splitting it:

> *`CLAUDE.md:43` — "the **file set under review** — paths, not summaries." The
> spec is supplied as **context**. For seventeen rounds those sets were
> identical. This round is the first time they differ.*

| Set | B/C/M | Gate |
| --- | --- | --- |
| spec + roadmap — **gitignored, not committed** | 0 / 3 / 7 | `FAIL` — blocks the **build**, not the commit |
| `README.md`, `CLAUDE.md`, `.gitignore`, `tools/doc-check.mjs`, `assets/`, `resources/audits/` | 0 / 0 / 3 | `PASS WITH FIXES` — **permitted** |

> *A `FAIL` blocks the artifact that failed. The artifacts that failed are a
> design describing software nobody has written, in files git is configured to
> refuse. Blocking the commit would not correct one line of the failing design —
> it would block only the audit trail that **records** the failure.*
>
> *And the commit publishes its own failing grade. That is the answer to anyone
> who reads this as laundering: **nothing is being hidden by committing — the
> opposite.***

## Jo's accessibility-gate decision

**Option (b), the API conformance harness** — decided 2026-08-08. Recorded with
the explicit statement that it does **not** substitute for NVDA/VoiceOver and
that Halo still cannot issue `PASS`. Jury: *"That statement is the reason I
accept the `[x]`. A decision that closed the item by declaring the obligation
discharged would have been a Critical."*

The harness must fail on three defects this audit found by hand: a
`speech_blocker` returning `0` for every document, a `GET /voices?lang=`
returning an empty list with no reason, and an `align_reason` with no `ht`
string.

## Closed in v18

All three Jury Criticals · Halo's `H17-C2` (the `README` gave `degraded` the
behaviour the spec assigns to `unavailable`, inside the commit set) and `H17-C3`
· the catalogue recount **19/76 → 20/80** for `align_status: pending`, a state
every rendition now passes through under R14-A1 · the `NEW-M7b` gloss, which had
drifted onto `excessive_drop` and would have produced an `ht` string telling a
blind reader something categorically untrue · `normalization_opaque` removed from
the permanence derivation · `observed_words` named in §7.4's deletion cascade ·
`README`'s "Commits on main: Zero" · the dead `word_sync_confidence` allowlist
entry · **N12-C7 / J17-M6, open since round 12: three roadmap invariants added**,
so the artifact an engineer builds from is guarded for the first time.
