# Audit Record — Founding Documents, Round 7

- **Date:** 2026-08-08 · **Subject:** spec v6, roadmap v6, `README.md`, `CLAUDE.md`, `tools/doc-check.mjs`
- **Reviewers:** Jury, Halo — read-only · **Response:** spec/roadmap **v7**, doc-check **rebuilt**
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 27/27

## Verdicts

| Reviewer | R4 | R5 | R6 | R7 |
| --- | --- | --- | --- | --- |
| **Jury** | 0B/2C | 0B/4C | 0B/5C | **0B/3C/6M** |
| **Halo** | 0B/6C | 0B/8C | 0B/9C | **0B/11C/12M** |

Jury composite **3.8 → 3.5 — second consecutive decline**, concentrated in
*buildability* (3.8 → 3.4) and *cross-artifact consistency* (3.7 → 3.4).

## The finding: I shipped a test for the tool and oversold that

Round 6: *"you shipped a tool and oversold it."* Round 7: the same sentence
about the test.

**Halo's demonstration, which is unanswerable.** The self-test exercised
**copies** of the guards against **frozen string literals**:

- Production flattener at line 292; self-test flattener at line 419 — two
  independent literals. The round-6 underscore bug could be reintroduced in
  production tomorrow and `--self-test` would still report 22/22.
- Guard `R5-M2` is `/Revision:\s*v[0-5]\b/` with the specimen pinned at `v5`.
  Passes forever. **Both live headers said `v6` in a v7 response** — the guard
  sat over a live instance of its own defect and reported green, because guard,
  specimen and document had drifted together.
- The six structural specimens were tautologies: `assert(regex fails after I
  delete the regex's needle)`.
- Five whole checks — both directions of field coverage, migration coverage,
  the entire control chain, the duplicate-header guard — had **no specimen at
  all**, and a dead guard was hiding among them.

**Jury's demonstration.** It planted a spurious column in §7.2 and moved a field
to the wrong table. Neither was detected. My enum harvester keyed on `·`, which
is the **column** separator in §7.2 and §7.2a — so 42 real columns, including
every one the round-6 fixes added, were exempted before the check ran. "A field
on the wrong table" — the first property `CLAUDE.md` names as required — was
structurally undetectable, and the item was ticked `[x]` done.

**And the inconsistency the tool missed:** `disclosure_fingerprint`,
`lexicon_fingerprint` and `normalizer_version` — the three inputs `text_hash` is
computed from, and the entire remedy for round 6's flagship Critical — appear
**nowhere in the roadmap**. It schedules `text_hash` twice and none of its
inputs. Built as written, the billing defect returns and a blind user pays
$1.35–$32 to turn off announcements they were already charged for.

## Response: the checker rebuilt

Every check is now a function of a document set, so `--self-test` **mutates the
real documents and runs the shipped checks**. Nothing is verified by a copy.

| Change | Closes |
| --- | --- |
| `runChecks(src)` as one function; harness calls it | Halo's *"a test that constructs its own input can only ever tell you about the input"* |
| Enum harvest restricted to parenthesised `｜` lists | N7-C1/N7-C8 — 42 columns were being exempted by the `·` catch-all |
| **`MIG-H`**: every `text_hash` input must appear in the roadmap | N7-C3 — the finding no check could see |
| **`SD-*`**: guard counts, revision headers, audit rosters and enum-count claims are checked against reality | Jury: *"it doesn't yet check what the documents say about it"* |
| Structural mutation reduces to below a threshold, not total deletion | H6-M19 — total deletion is the one mutation a presence-predicate survives |
| Exit 2 only when the missing set ⊆ `resources/` | N7-M5 — a deleted `CLAUDE.md` wore "not applicable" |
| Baseline-clean assertion before self-test | red/green is meaningless from a dirty baseline |

**It immediately found 16 findings**, including all three Criticals both
reviewers named. And the self-test failed once on first run — my `FWD` specimen
renamed a table row, which exercises migration coverage, not field coverage. A
mutation that does not reproduce the defect proves nothing, and the harness said
so. That is the harness working.

## Product Criticals closed

| ID | Finding | v7 |
| --- | --- | --- |
| **N7-C3 / N7-C1** | The three `text_hash` inputs in no migration | Scheduled, Phase 1, Atlas, dated |
| **N7-C2** | The NFC/grapheme floor existed only in the spec; the roadmap test that ships was the code-point form, under which `pè` → `pe` still passes | Both moved into Phase 1 and the Phase 4.5 test |
| **N7-C4 / N7-M6** | `suppressed_narration` typed as an `InsertedReason` — so `content_narration: off` **synthesized and billed** content the user chose not to hear. And `spans[].reason` had no declared type at all | `SpanReason` union declared; `suppressed_narration` moved out of `InsertedReason` |
| **N7-C5** | The catalogue key omitted `align_status`, but `low_confidence` reaches both `degraded` and `unavailable` — behaviourally different states Phase 10's own pass criterion requires a user to distinguish | Keyed on `align_status` × reason set |
| **N7-C6** | `disclosure_fingerprint`'s domain was undefined; read as emitted *strings* it re-bills every sentinel-bearing segment on one `ht` translation fix | Hashes reason identities and emission decisions; catalogue revisions non-retroactive |
| **N7-C11** | NFC applied to document text and **not** to `user_lexicon.surface_form` — and iOS/macOS emit NFD, so a VoiceOver user typing `Bélizaire` stores a key that can never match, the fingerprint computes empty, and the system reports the correction applied while the audio is unchanged | NFC on write. NFC on one side of a join is worse than on neither |
| **N7-C3 (Halo)** | `\p{No}` blanket-droppable — `"add ½ cup"` → `"add cup"`, and footnote markers deleted silently when the marker is the only channel telling a listener a footnote exists | Glyph drops **with** a `dropped_marker` disclosure span; fractions and enclosed numerals not droppable |

Majors closed: `N7-M1` headers said v6 · `N7-M2` guard count 10 vs 15 vs 13 ·
`N7-M3` roster stopped at round 4 · `N7-M4` "all five `InsertedReason`" over
seven · `N7-M5` exit-2 mislabelling · `N7-M1 (Halo)` `excessive_drop` classed
`render_specific` when dropped spans are voice-independent · `N7-M2 (Halo)`
emoji contradiction · `N7-M3 (Halo)` disclosure spans had no time address, so
"less chatter" required a **billable re-render**.

## Both reviewers, third consecutive round

**Run Phase 0's spikes.** Jury: *"You are re-reading the same paragraph to
settle questions that a real API call would settle for good."* Halo: the NFD
hazard, the `ht` substitution key and whether an `ht` rule set is buildable are
all answerable by one `curl` and one `pdfjs` run. **Not blocked** by any
finding. Four weeks past their own due date.

## Open, carried

Both reviewers note the audit trail cannot support strict by-ID resolution for
Minor findings — round records summarise them rather than enumerating each ID.
`CLAUDE.md`'s "resolve each finding by ID, never silence" is unenforceable
against a summary record. Rule 8: routed to Jo, not self-actioned.
