# Audit Record — Founding Documents, Round 18

- **Date:** 2026-08-08 · **Subject:** spec v18, roadmap v18, `README.md`, `CLAUDE.md`, `.gitignore`, `tools/doc-check.mjs`, `resources/audits/`
- **Reviewer:** Jury — gate ruling on the first commit · **Response:** v19
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 49/49 → **54/54**

> **Written late, and found by Scribe rather than by the gate.** Spec and roadmap
> v19 both claimed to close "Jury's round-18 Majors (`J18-M1`…`J18-M4`)" and
> `doc-check.mjs` carried a guard citing `// J18 §5` — while `resources/audits/`
> held 17 records ending at round 17. **`SD-ROSTER` is structurally blind to
> this:** `ROUNDS_ON_DISK` is counted from the same files the roster describes,
> so a missing record makes the claim self-consistently wrong. The guard can only
> catch over-claiming, never under-writing. This is the third occurrence of
> J16-M8 and the second time a reviewer has had to reconstruct its own subject.

## Verdict

**`PASS WITH FIXES` — 0 Blocker · 0 Critical · 4 Major · 3 Minor.**

**The first round in eighteen with zero open Criticals.** All three round-17
Criticals verified closed by reading — mechanism, column, producer and payload —
not by assertion.

| Set | B / C / M | Gate |
| --- | --- | --- |
| spec + roadmap — **gitignored, not committed** | 0 / 0 / 3 | tracked with owners and dates |
| commit set — `README.md`, `CLAUDE.md`, `.gitignore`, `tools/doc-check.mjs`, `assets/`, `resources/audits/` | 0 / 0 / **1** | one sentence from clean |

Jury verified the commit set by execution rather than accepting the summary —
`git add -A --dry-run`, `git check-ignore -v` on both design paths — and applied
the round-17 gate-scope rule: `CLAUDE.md:43` makes the gate govern **the file set
under review**; the spec is supplied as context. For seventeen rounds those sets
were identical. This was the first round they differed.

**The commit proceeded** once `README:18` was corrected. It said *"this
repository has no commits and no code"* twelve lines above a table describing
what the commits contain — the round-18 pattern arriving inside the commit set.

## The three Criticals closed

| ID | Finding |
| --- | --- |
| **J17-C1** | `speech_blocker` had **no raiser**. §3.5 ended `\| Everything else \| Google / Gemini TTS \|` — a row with no language condition, making routing **total over languages**, so `blocked_language_unsupported` could never fire and the pre-payment speech disclosure reported **0 for every document** while four artifacts promised otherwise. Jury, reversing its own round-16 Major: *"**Adding a column does not fix this.** A column with no reachable write is still a zero."* Closed by making the table non-total — eleven enumerated languages plus an explicit **no-route** row. That also deleted an unevidenced claim that one model speaks every language, the class this project removed five times as `normalization_opaque` |
| **J17-C2** | `segment_renditions.align_blocker` carried two enums and two opposite pre-payment semantics across four sites. **A fifth was found mid-fix.** Closed by splitting on the kind of fact |
| **J17-C3** | The spec asserted the hallucinated-token disclosure settled while the roadmap says the display-address choice is unmade |

## What the fixes broke — the fifth consecutive round

**`J18-M4`, and it is the interesting one:** making the speech table non-total
made SPIKE A's four-language scope **load-bearing for the first time**. §3.5 now
routes eleven languages; the matrix measured four; `no_transcriber` and
`transcription_unreliable` are both lookups into it; **no rule existed for a
miss**. Both readings were wrong — `null` promises a blind user word sync will
work with no evidence, and `no_transcriber` is `permanent`, telling a German
reader *never* when WhisperX handles German well.

**Resolved in v19 before any measurement: the matrix covers all eleven routed
languages.** The four product languages report first and gate the phase; the
other seven are measured in the same run and may not be dropped for time. Same
discipline as the 250 ms drift bound, and for the same reason — *a scope chosen
after the measurement is a scope chosen to make the result look good.*

`J18-M1` a payload comment still declaring `speech_blocker` *"still open… not
solved"* beside its fix · `J18-M2` three catalogue counts in one sentence (80,
76, 60) in the item **Tongue scopes the `ht` catalogue from** · `J18-M3` the
README line, the only finding inside the commit set.

## The guards, and the line that had none

Jury attacked the three roadmap invariants added in v18 and confirmed them real —
*"faithful semantic inversions at unique sites, not re-pointed specimens"* — then
found what they did not cover:

> *Delete `spec:381`, and the routing table is total again,
> `blocked_language_unsupported` loses its raiser, `speech_blocker` returns 0 for
> every document, and `node tools/doc-check.mjs` **exits 0 and reports clean**.
> **The repair for my highest-severity finding of round seventeen is the least
> protected line in the document.**

Five guards added in v19 and verified by execution, including `INV-NO-ROUTE`,
which was proven by re-running Jury's exact attack. The `align_blocker` column —
a Critical in three consecutive rounds — is now guarded at all four sites, and
`hallucination_rate`, which the roadmap itself calls *"the only one of the
metrics that distinguishes `ht` from `en`"*, is guarded for the first time.

## Standing

`SPIKE A` is unblocked and is the only remaining word-sync gate. Its two
free parameters — the drift bound and the language scope — are now **both fixed
before the run**, movable only publicly with the reason recorded. Halo cannot
issue `PASS` pre-implementation and the NVDA/VoiceOver obligation is **not
discharged** by Jo's option (b).
