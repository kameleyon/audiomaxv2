# Audit Record — Founding Documents, Round 30

- **Date:** 2026-08-09 · **Subject:** 110 staged files — repair of round 29's three Criticals and six Majors
- **Reviewer:** Jury · **Response:** v30
- **Authorship provenance:** ruling by Jury; **transcribed by the audited party.** States what was true at the ruling. Findings fixed after it are marked *fixed after ruling* and are certified by no one until re-audit.
- **Index/worktree identity verified by the reviewer:** `git diff --name-only` = 0.

## Verdict

**`PASS WITH FIXES` — 0 Blocker · 0 Critical · 10 Major · 5 Minor · 1 Polish.**
**The commit is permitted** (`CLAUDE.md:19-23`): zero Blocker, zero Critical, and
every Major carries a named owner and a date.

> *All three round-29 Criticals are repaired at their core, and I verified each by
> re-running the original command and by opening the artifacts rather than reading
> the claim.*

> *The pattern named in round 29 — "the prose is written from memory and the
> artifacts are consulted afterwards" — has **changed shape, not disappeared**.
> This round the artifacts **were** opened: every figure in the C1 table traces to
> the right file, and I checked all eighteen. What was not opened is the **quoting
> instructions the artifacts carry beside those figures**, and the **line numbers
> the corrections cite**. **The author graduated from misquoting numbers to
> misquoting the rules about the numbers.***

## Verification — all six commands run by the reviewer, all six pass

| command | result |
| --- | --- |
| `node tools/doc-check.mjs` | clean, exit 0 |
| `node tools/doc-check.mjs --self-test` | 82 passed, 0 failed |
| `node .github/scripts/secret-scan.mjs` | clean, **194 files FROM THE INDEX**, exit 0 |
| `node .github/scripts/secret-scan.mjs --self-test` | 21 trials, 21 passed |
| `node supabase/tests/verify_voice_langs.mjs` | all proofs passed; **`S9` green — store ships empty** |
| `cd worker && node --test` | 57 tests, 57 pass |

`secret-scan --all` also clean. **No key material in the index.**

## Round-29 findings, resolved by ID

| ID | Status |
| --- | --- |
| `J29-C1` figures attributed to the wrong artifact | **fixed** — *"the correction did not move the error"*; all 18 figures re-verified against both files |
| `J29-C2` scanner failed on this commit | **fixed** — passes, exit 0 (over-corrected → `J30-M3`) |
| `J29-C3` routing not reconciled | **fixed at the five named sites**; a sixth found → `J30-M5`. Declaring the OpenRouter host open is *"honest, not evasive… the instrument is right"* |
| `J29-M1` mixed-configuration `fr` figures | **fixed** in roadmap + README; open in the spec ledger → `J30-M6` |
| `J29-M2` drift closure without power | **fixed** — CIs published; Jury recomputed all six bounds and all three extrapolations: *"the arithmetic is correct"* |
| `J29-M3` `es` p95 exceeds the bound | **fixed** |
| `J29-M4` orphan manifest rows | **half fixed** — orphan half *"genuinely fixed and independently verified"*; leg (iii) half → `J30-M7` |
| `J29-M5` withdrawn voice lock still asserted | **fixed** |
| `J29-M6` audio backing no measurement | **fixed** — the measurement landed; *"keeping it was the right call"* |
| `J29-m1` | partially fixed; cap + lookbehind gaps **open** |
| `J29-m2` · `J29-m3` · `J29-m4` · `J28-minor-a` · `J28-minor-b` · migrations-unvalidated | **open**, declared honestly, carried forward |

**Prior-round repair rate: 9 of 9 Criticals and Majors addressed — 7 fixed as
specified, 2 partial.**

## Majors — 10

**`J30-M1`** the pass field is described as `null`; `grep -c passes_matched_bar` on
that artifact returns **0** — the field is **absent**. *"The conclusion drawn is
correct… but the mechanism is invented, in the one table whose entire purpose is
that every cell be checkable against the file named beside it."* **Originates in
the round-29 record itself** and propagated into three documents. *(Scribe ·
2026-08-12 — **fixed after ruling**, at all three sites and at the source record.)*

**`J30-M2`** the ASR floor is quoted bare against that artifact's explicit
prohibition. `_limits[6]`: *"**THE INSERTED SILENCE IS LONGER THAN THE BAR.**
315-330 ms separates every pair of words; the drift bound is 250 ms… **the strict
figure must never be quoted without**"* the decomposition — which is committed and
reads `en` 8.3 → 25.0 → **91.7**, `es` 4.5 → 18.2 → **81.8**, `fr` 0.0 → 4.2 →
**54.2** (strict → silence-tolerant → offset-corrected). No document carries it.
*"The published lower edge of the bracket is an artifact of the corpus, and the
file says so twice and forbids the bare quotation once."* Errs conservative, which
is why it is not Critical. *(Scribe · 2026-08-12.)*

**`J30-M3`** the C2 narrowing dropped a class the rule's own alternation
advertises. The value class excludes `! @ # % & :`, and the first 16 characters
must all be in class — so five realistic `password` / `passwd` / `secret` / `auth`
shapes that the old rule caught are now missed. *"A control whose comment asserts
a coverage property it does not have"* is the repo's own definition of an
attestation. *(Forge · 2026-08-11.)*

**`J30-M4`** the heading seven lines above the C1 fix still asserted *"THE SECOND
MEASUREMENT IS THE VERDICT"*. *(Scribe · 2026-08-11 — **fixed after ruling**.)*

**`J30-M5`** a sixth routing site, `roadmap:457`, inside the SPIKE B closure
record: *"Gemini joins the provider set and the subprocessor disclosure."* Unlike
its neighbours it names **our** provider set and cites **our** constraint 7, so it
instructs an addition that would be a false disclosure. **Never enumerated by the
reconciliation grep.** *(Scribe · 2026-08-11 — **fixed after ruling**, struck in
place.)*

**`J30-M6`** the reconciliation ledger records the **retracted** `4.3` claim as
done. *(Scribe · 2026-08-11 — **fixed after ruling**.)*

**`J30-M7`** the `[ART-STALE]` leg (iii) repair is **unreachable**: `scoredRows`
admits a row only on `lang` + `audio_seconds`, and the only rows carrying
`audio_path` use `lang_code` + `clip_seconds`. **Zero of 39 rows can take the new
branch.** No live data defect — Jury parsed all nine WAV headers against the
manifest and they agree to the millisecond — *"only a guard that does not guard."*
Fix by widening `scoredRows`, not by editing leg (iii) again. *(Forge ·
2026-08-13.)*

**`J30-M8`** *"at most 1.9 pp"* is a bound over **two** voices presented as a bound
over three: `feminine` contributes **zero** admissible long clips, and at short
length `locked` vs `feminine` is **4.2 pp** — larger than the stated maximum. The
within-voice floor of 0.1 pp rests on **one** pair. **On the post-hoc exclusion
itself Jury cleared it:** the rule selects on *instrument failure*, not on score,
and `narrateur` desyncing on r1 but not r2 with identical text is direct evidence
that desync is stochastic. *"The exclusion does not invalidate the comparison.
What it invalidates is the coverage of the bound."* *(Forge · 2026-08-16.)*

**`J30-M9`** this series' round-29 record omitted **7 of its 16 findings**.
*(Jury with Scribe · 2026-08-11 — **fixed after ruling**; all seven restored.)*

**`J30-M10`** the reconciliation ledger's line-number citations are unverifiable —
the C1 table inserted seven lines and reflowed everything below, so every sampled
citation points at unrelated text. **The dispositions are substantively right** —
Jury re-checked them independently — but *"no reviewer can follow it, and one
genuine miss hid inside it"* (`J30-M5`). *(Scribe · 2026-08-12.)*

## Minor — 5 · Polish — 1

`J30-m1` the six slope CIs exist in no artifact (correct derivation, unstated —
Jury reproduced them) *(Forge · 2026-08-16)* · `J30-m2` the new
`reconstructible_from` acceptance branch has **no mutation trial** *(Forge ·
2026-08-13)* · `J30-m3` three internal line citations stale after the reflow, one
of them **authored this round and wrong when written** *(Scribe · 2026-08-12)* ·
`J30-m4` constraint 7's open item carries a phase gate where everything else
carries a date *(Comply · 2026-08-11)* · `J30-m5` `spike-a-voices.json`'s
`_art_stale_gap` note must be updated **when** the repair lands, not before
*(Forge · with J30-M7)* · **Polish** `J30-p1` `--all` prints *"FROM THE INDEX"* in
a mode that also reads disk *(Forge · when convenient)*.

## What Jury verified and accepted

- **The three-instrument reconciliation.** `fr` reads 0.0 (ASR, strict), 91.7 (FA
  given the true text) and 71.4 (shipped matcher, neighbour predictor, natural
  prose). *"They are three instruments, not three readings… none of them is
  wrong."* The 0.0 → 91.7 gap on identical audio is the ASR clock:
  `median_signed_delta_ms` is **−514.4 ms**, ≈ the inserted silence. **But no
  document performs the reconciliation** — that is the substance of `J30-M2`, and
  the remedy must state the **reference** beside every figure, not just the metric.
- **Constraint 7's open item is the right instrument.** *"A constraint that names
  an unmet precondition, assigns it an owner, and blocks the dependent phase is
  not a weaker constraint — it is the only honest form available when the fact is
  genuinely unknown."*
- **The load-bearing sentence of the voice result, which must not be diluted:**
  *"the interesting finding here is not which voice wins… at chapter length, on
  the metric that is the accessibility contract, **none of them are close**"* —
  71.4 against 95, no clip passing.
- **Nothing user-facing asserts word sync works.** Re-verified: `voice_langs`
  ships empty, `sync_grade NOT NULL DEFAULT 'unmeasured'`, read path coalesces.

## The line the author has to keep

> *Round 29 said the artifacts were consulted after the sentence. This round they
> were consulted **before** the figures and **not at all** for three other things:
> the quoting instructions printed beside those figures, the field names asserted
> about them, and the line numbers cited to prove the check was run. **The
> reconciliation ledger is the right invention. It fails because it is written in
> a coordinate system — line numbers — that the edit it documents destroys as it
> is written. Cite by quotation, not by line.** A quoted string survives a
> reflow; a line number is only ever true for the version that no longer exists.*
