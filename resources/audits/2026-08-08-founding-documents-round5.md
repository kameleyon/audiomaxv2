# Audit Record — Founding Documents, Round 5

- **Date:** 2026-08-08 · **Subject:** spec v5, roadmap v5, `README.md`, `CLAUDE.md`, `.gitignore`, `research/`
- **Reviewers:** Jury, Halo — read-only tools · **Response:** spec/roadmap **v6**
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0

## Verdicts

| Reviewer | R1 | R2 | R3 | R4 | R5 |
| --- | --- | --- | --- | --- | --- |
| **Jury** | `FAIL` 3B/12C | `FAIL` 0B/3C | `FAIL` 0B/1C | `FAIL` 0B/2C | **`FAIL` 0B/4C/7M** |
| **Halo** | `FAIL` 4B/6C | `FAIL` 1B/4C | `FAIL` 0B/3C | `FAIL` 0B/6C | **`FAIL` 0B/8C/13M** |

Jury composite **3.9 → 3.9 — the first round with no net improvement.**
Internal consistency **2/5 for a fifth round.**

## The finding both reviewers converged on

> **Jury:** *"The composite rising while the verdict stays `FAIL` is the
> finding."* Round 5: the composite stopped rising.
>
> **Halo:** *"The author is fixing findings faster than the fixes are being
> integrated. That is a throughput problem, not a comprehension problem, and it
> will not be solved by understanding the findings better."*

Rounds 2–5 each fixed N findings and created ≈N/2 new ones at the seams between
them. Five of Halo's eight Criticals were at seams created by round-4 fixes, and
four **reproduced a defect pattern the same revision names and closes
elsewhere** — inert control with no write route, stale audio judged current,
remedy paywalled, wrong-language speech.

## The response: a program, not a sixth promise

Jury's prescription was literal — *"the difference between this project's
documents and good documents has been exactly the set of things a fifty-line
script would have caught."* Halo's "one thing" was *"trace every user-facing
control end to end: column → write route → producer input → hash → test →
catalogue"*, which is a graph traversal, not a thing to remember.

**`tools/doc-check.mjs`** implements both. Five checks:

| Check | Catches |
| --- | --- |
| Field coverage, **bidirectional** | a field on the wrong table; a spurious column |
| Migration coverage | a table invented in the spec that no phase builds |
| Prose regressions (15 guards) | the class identifier-greps miss — *"character count is what the provider bills"* contains no identifier |
| **Control chain** | Halo's one thing, mechanized |
| Producer signature | a phase header restating a superseded contract |

**It reproduced both auditors' findings independently** — both missing rollup
tables, the sentinel-locale contradiction, the RLS claim in three artifacts, and
`disclosure_verbosity` broken at four of six chain links.

**Then it found what memory did not.** After fixing *"character count is what
the provider bills"* in the README constraints table, the checker reported it
still failing: a **second occurrence 180 lines away**. That is the whole audit
in miniature — the site remembered gets fixed, the site not remembered ships.
It also caught a `documents` row that listed `align_degraded_ratio` *and* said
it had no such column, because the edit appended instead of replacing.

## Disposition — Critical

| ID | Finding | v6 |
| --- | --- | --- |
| **N5-C1 / R4-C5** | Sentinel language fixed in §6.2, untouched in §9.1 — the section a client builds from. 414 lines apart. | **Fixed** + prose guard |
| **N5-C2 / R4-C6** | The reconciliation gate's own fix reached `CLAUDE.md` and not the roadmap, which kept all three properties identified as the hole. | **Fixed** — the gate is now `doc-check.mjs`, run in the revision loop |
| **N5-C3 / R5-C5** | `disclosure_verbosity` not in `text_hash` and not in `utter()` — the control was inert, and it defeated the R4-M7 fix. A user turning disclosures on got an identical hash and no disclosures. | **Fixed** — both are hash inputs and producer arguments; `skip_policy`/`voice_id` deliberately excluded with the reason stated |
| **N5-C4** | `align_degraded_ratio` had three incompatible definitions in one file; the two rollup tables appeared once each and in no migration. | **Fixed** + guard |
| **R5-C1** | `disclosure_verbosity: off` **silently deleted every table in the book** — table linearization is emitted as `inserted` tokens, so a switch advertised as "less chatter" removed content, aimed at readers who cannot see the table. | **Fixed** — `content_narration` split off as its own axis; no level of either may remove the §9.1 positional record |
| **R5-C2** | `disclosure_verbosity` had **one occurrence in four documents**: no column, no route, no migration, no producer input. NEW-M9 reproduced on the new flagship fix. | **Fixed** + control-chain check |
| **R5-C3** | Group monotonicity was vacuous — nothing said what the order was monotonic *in*, so `group_id` assigned in emission order satisfies it by construction. Also unbounded in extent and non-contiguous. | **Fixed** — ordering stated over `cs`/`ce`, contiguity required, `mean_tokens_per_group` monitored. **Recorded: the check is vacuous on `ht`**, which must inform Spike B rather than be found after it |
| **R5-C4** | `origin: 'dropped'` was an unbounded escape hatch — a whole passage could be dropped and every invariant still hold, with `align_status: ok`. | **Fixed** — no `\p{L}`/`\p{N}` in a dropped span; ratio threshold raises `excessive_drop` |
| **R5-C6** | `lexicon_version` undefined; as written one correction re-bills the entire library — the paywall R4-M13 existed to remove, restored by its own remedy. | **Fixed** — per-segment `lexicon_fingerprint`; `normalizer_version` non-retroactive |
| **R5-C7** | The `ht → fr → en` catalogue fallback reintroduced R4-C5 in synthesized speech. | **Fixed** — no cross-language fallback for speech; emit a span instead |
| **R5-C8** | Large tables were unreachable in **both** channels: not narrated inline, and the client forbidden from linearizing. | **Fixed** — `GET /documents/:id/blocks/:ord/narration` |

## Disposition — Major

All closed: `N5-M1` §7.1 missing fields · `N5-M2`/`R5-M5` `display_char_count`
at one site of five · `N5-M3` absolute RLS claim in three artifacts ·
`N5-M4` sentinel strings authored five phases after they are spoken ·
`N5-M5`/`R5-M2` roadmap labelled v4 · `N5-M6` catalogue key an unbounded power
set → **14 keys × 3 permanence = 42 strings per language**, with permanence
**derived** by a stated rule · `N5-M7`/`R5-m2` `dropped` had no `ord` ·
`R5-M1` no route served the rollup · `R5-M3` header counts unverifiable →
replaced by a command · `R5-M4` five stale ratio sites · `R5-M6` Phase 4.5
header restated the repudiated signature → now checked ·
`R5-M7` split remedy broke four invariants → expressed as a new
`segment_set_id`, non-billable · `R5-M8` inserted address unvalidated → test (e)
· `R5-M9` `summary` had no reason code → `disclosure_summary` ·
`R5-M10` Halo roster wrong in five audits → roadmap is now sole authority ·
`R5-M11` voice change left no resolvable anchor → resolution rule +
`progress_resolution` · `R5-M12` recorded · `R5-M13` → **option (b) added** (API
conformance harness) and **the decision moved to Phase 0**, due 2026-08-20,
before the stages it would exercise.

Minor: `R5-m1` duplicate Audits bullet · `R5-m3` superseded-audio retention
(30 days, disclosed) · `R5-m4` `POST /progress` body shape · `R5-m5` threshold
served · `R5-m6` `blocked_quota` prose · `R5-p1` out-of-scope drift — all closed.
`R5-m7` (ID case collision) and `R5-m8` (redundant `lang`) accepted as-is.

## Both reviewers' process recommendation

**Run Phase 0's spikes.** Halo attached three conditions, all now met: the
reconciliation test exists as code; R5-C1 and R5-C8 are fixed; and its Phase 0
review is a written deliverable with a stated question set — per-language word
error and coverage matrix (Spike A), whether `ht` produces intelligible speech
and whether an `fr` acoustic model gives usable alignment on Creole (Spike B),
reading-order accuracy on a two-column academic page (Spike D).

Halo, on why an accessibility auditor with eight open Criticals says this:
*"the next three of them will be discovered by a `curl` against Fish Audio, not
by a sixth reading of §6.2."*

## Preserve

`research/`'s self-demotion of its own Tier A evidence · §7.3's honest statement
of the re-segmentation bill · *"v2 diagnosed the disease and added a
thermometer"* · the behavioural `degraded`/`unavailable` split · 99.5% ·
§3.2's willingness to say a skipped run lives outside its own segment's range ·
§6.2's account of how a check gets weakened until it catches nothing — which has
now correctly diagnosed three findings and fallen to two of them.
