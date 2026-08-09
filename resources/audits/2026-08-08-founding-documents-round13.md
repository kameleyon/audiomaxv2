# Audit Record — Founding Documents, Round 13

- **Date:** 2026-08-08 · **Subject:** spec v12, roadmap v12, `README.md`, `CLAUDE.md`, `tools/doc-check.mjs`
- **Reviewers:** Jury, Halo — read-only · **Response:** spec/roadmap **v13**, then **v14**
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 43/43

> **Written late (J16-M8).** This record, and rounds 14 and 15, were reconstructed
> and committed during round 16, after Jury found `resources/audits/` stopped at
> round 12 and reported: *"I could not load the prior report — I reconstructed the
> seventeen findings from your message, which is exactly what the rule forbids."*
> `CLAUDE.md` makes artifact continuity the substitute for reviewer continuity;
> three rounds of missing artifacts broke it. Recorded as a defect, not a
> formality.

## Verdicts

| Reviewer | R11 | R12 | R13 |
| --- | --- | --- | --- |
| **Jury** | 0B/2C/7M | 0B/4C/11M (vacated `PASS WITH FIXES`) | **0B/2C/3M — `FAIL`** |
| **Halo** | 0B/6C/11M | 0B/7C/14M | **0B/3C — FORECLOSES** |

## The finding of the round, and it is arithmetic

Jury directed round 13 as *"four fixes and nothing else"* (Ruling 3). Four
authorised fixes were made and two unrequested additions were made alongside
them. The result:

> **Four authorised fixes produced zero defects. Two unauthorised additions
> produced two Criticals. Nothing that was in scope broke. Everything that broke
> was out of scope.**

That measurement governs every round after this one.

## Criticals closed (the four Jury sustained on synthesis in round 12)

| ID | Finding | v13 |
| --- | --- | --- |
| **N12-C1** | `GET /quote` inherited `// 402 if insufficient` from the §8.2 payload it returns — the non-committing disclosure route refusing exactly the zero-balance users it exists for | Scoped the `402` to `POST /render`; `GET /quote` returns **200 at any balance**, `balance_after` may be negative |
| **N12-C2** | The quote disclosed sync loss and **not speech loss** — a mixed `fr`/`ht` document could contain segments producing no audio at all, discovered after payment as audio stopping | `speech_blocker` + `speech_available_segments` added to the payload and scheduled |
| **N12-C3** | **No route returned the `voices` catalogue** while four routes required a `voice_id`. Every degraded-path remedy in the design is *"choose a different voice"*, and no client could present the choice. Jury: *"the most serious finding in twelve rounds"*, and the only one not self-inflicted | `GET /voices?lang=` added to §9 and Phase 9 |
| **N12-C5** | `disclosure_summary` is chapter-scoped audio hashed by a segment-scoped fingerprint — a stale summary announced as current | `CHAPTER_DIGEST` as a fifth tuple element on chapter-first segments |

## The two additions, and what they cost

Both were made "while in the file" and both were Critical:

- **N13-C1** — `align_permanence` added to the quote. It showed `render_specific`
  over a reason set of `{no_normalizer}`, which §6.3 derives as `permanent` — and
  annotated itself *"DERIVED per §6.3"*. It told a blind user to pay $1.35–$32
  again for a different voice, when a missing normalizer is a function of
  language and text and never of voice. **Closed in v14 by deletion.**
- **N13-C2** — `supports_normalization_control=` added as a `GET /voices` filter,
  alongside three returned fields (`normalization_opaque`, `lang[]`, sample URLs)
  that the `voices` table has no columns for. The route queried what the database
  does not store, and the roadmap built a different route than the spec described.
  **Closed in v14 by deletion.**

## Halo, round 13

3 Criticals, verdict FORECLOSES. Its resolution of the four: `N12-C1` and
`N12-C5` **fixed**; `N12-C2` and `N12-C3` **open** — the fields existed in the
payload and the route existed in §9, but neither had a column or a producer.

> **Both open Criticals are the same mistake: the disclosure was written into the
> payload and not into the thing that produces it.** `speech_blocker` is a field
> with no column and no producer. `GET /voices` is a route returning four fields
> the table cannot supply, filtered on a column that does not exist. Each reads
> as complete, ships green, and answers a blind user with a confident zero or an
> empty array.

Its prescription became a standing test applied in every later round: **for every
new field, name the column it is stored in, name the pipeline stage that writes
it, and name what a client receives when the answer is "none."**

## Jury's Ruling 4

> *No further document revision after `N13-C1` and `N13-C2` close, until Spikes
> A / B / B2 / C / D / E return. That closing revision fixes two Criticals and
> adds nothing.*

v14 complied exactly: both closed by deletion, nothing added.
