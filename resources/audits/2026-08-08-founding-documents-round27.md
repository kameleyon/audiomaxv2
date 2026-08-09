# Audit Record — Founding Documents, Round 27

- **Date:** 2026-08-09 · **Subject:** SPIKE A's corrected result, Atlas's `voice_langs` schema, Forge's harness and guard repairs — 28 staged files
- **Reviewer:** Jury, **on synthesis** — Halo's round-26 report present before ruling · **Response:** v27
- **Authorship provenance:** ruling by Jury; **transcribed by the audited party.** States what was true at the ruling; the two Criticals were fixed **after** it and are certified by no one.

## Verdict

**`FAIL` — 0 Blocker · 2 Critical · 9 Major.** Both Criticals in `README.md`; Jury's terms: *"Fix `README.md:354-356` and `README.md:392` and this is `PASS WITH FIXES`. I will clear it on those two lines alone."*

Jury was explicit about what the `FAIL` is not:

> *The engineering in this round is the best in the series. `fa.py` is properly
> fixed. `voice_langs` is the strongest single piece of design work I have
> reviewed here. The harness now moves numbers **against** the project and says
> so. Halo's substance was received and acted on. **The failure is not effort or
> honesty** — it is that the corrected story landed in two **gitignored**
> documents and the **committed** one still carries the old one, with the
> disproof stapled to it.*

## The finding of the round

**The corrected story went where nobody can read it.** `resources/specs/` and
`resources/roadmap/` are gitignored by owner decision. `README.md` is the only
committed public statement of what SPIKE A found — and it was in neither
dispatched agent's file scope. Atlas owned the schema, Forge owned the harness,
and **the document that quotes both was owned by neither.**

> *Non-overlapping dispatch guaranteed the gap.*

The same mechanism produced the second seam: `fixtures.json:19` locks `fr` to
Robert on cross-engine figures, while `spike-a-crossengine.json:54` — added in the
same commit — says *"any figure from that file … is a word-vs-SEGMENT comparison.
Do not cite it as word sync."* Two files in one commit, contradicting each other,
neither agent owning the sentence both depend on.

## The two Criticals

**J26-C1** — `README:354-356` claimed *"most recent verdict … `PASS WITH FIXES`,
round 25, 0 Blocker · 0 Critical"* while **linking to `-round26.md`**, which reads
*"FORECLOSES — 2 Blocker · 3 Critical · 8 Major."* Wrong reviewer, wrong verdict,
wrong counts, **introduced by this commit's own diff** — the link was advanced and
the prose beside it was not. **Sixth recurrence**, with the note documenting the
fifth four lines below it.

**J26-C2** — `README:392` made three claims, each refuted by an artifact staged in
the same commit: the un-producible triple; *"match rate is 100%"* against
`fr` 95.8% / 8.7% hallucination; *"$0.07–$0.15"* against $0.165–$0.224.

## SPIKE A — admissible as an instrument, inadmissible as a headline

Jury's round-22 precedent applied consistently: *a result reported before the
instrument settled is not a result.* The instrument changed again after round 26 —
numeral expansion, display-index pairing, endpoint accounting, model separation —
**and every one of those changes moved the numbers.**

> *Leg (c) — independent re-checkability — is now **substantially met and was not
> before**: audio, fixtures, harness and three separable configurations are all
> committed, and `expect_hard` finally computes. That is enough to falsify the
> headline, which is what leg (c) exists for.*

**What the artifacts establish, and it is stable:** `passes_matched_bar: false`
in **3/3 languages across 3/3 configurations**; best figure anywhere **75.0**
against **95**. The published triple is **not producible by any single run** —
`70.8`/`77.3` are endpoint-credited, `79.2` exists only in the `small`-model file.
Cost $0.165–$0.224, still ~25× under Hypereal. And
`expect_hard_falsifies_match_rate: true` for `en` and `es`: the numerals come back
**as digits** and match verbatim, so **the 100% match rate is measuring the wrong
thing** — by `fixtures.json`'s own rule.

## What Jury verified, and what it broke

Four guards attacked; **two sound, two broken.** `[NO-ROUTE-TOTAL]` and
`[CO-DEFAULT]` genuinely falsified by defeat-by-addition mutations, and Forge's
report that it *reproduced J22-M6 inside its own repair* — a presence-check
CODEOWNERS guard defeated by appending `*  Nobody` — is real and self-honest.

Broken: **`[ART-FIGURE]` is vacuous on hallucination** (`J26-M3`) — `TRACKED`
holds `hallucination_rate_pct`; every artifact uses `hallucination_rate`; the
`if (!vals.size) continue` guard skips it silently for all twelve documents.

> *The metric that feeds the pre-payment disclosure to blind users has a guard
> that checks nothing — the exact failure `[ART-ABSENT]`'s own message names
> thirty lines above it.*

Also: `[ART-FIGURE]` is **membership-only and blind to prose**, so `README:392`
escaped it entirely (`J26-M1/M2`); `[ART-STALE]` compares **mtimes**, which git
discards, so it is unreproducible on any clone (`J26-M5`); `[NO-ROUTE-TOTAL]`
narrowed J22-M6 to a 15-phrase lexical denylist — *"defeatable by addition became
defeatable by addition plus a synonym"* (`J26-M4`).

## Closed

**H26-B2** cleanly — `fa.py` expands numerals and carries the display index, so
three spans of "nineteen eighty four" collapse onto one display token; the same
fix closes `H26-M8`'s uniqueness filter. **H26-C2** — `ASR → FA → match` stated
independently in two files. **H26-M1/M2** — fitted and held-out offsets both
reported, signed-vs-absolute non-comparability named. **H26-C3** — Jury: *"the
strongest work in this round… the fix addresses the **arity**, not the symptom."*

## Phase 0 may begin

`voice_langs` migration and read path — *"the only Phase 0 item whose correctness
depends on no SPIKE A number, and it closes the last foreclosure."* Then
**instrument repair, not more reporting**: one hand-annotated 12-second clip,
~20 minutes, converts 62.5/68.2/75.0 from a floor into a verdict.

**May not begin:** anything treating word sync as established; any pricing or
credit work on the old cost figure; any implementation citing 70.8/77.3/79.2.
