# Audit Record — Founding Documents, Round 15

- **Date:** 2026-08-08 · **Subject:** spec v16, roadmap v16, `README.md`, `CLAUDE.md`, `tools/doc-check.mjs`
- **Reviewer:** Jury — regression sweep, read-only · **Response:** v17
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 43/43 → **45/45**

> Written late alongside rounds 13 and 14 — see the note in `-round13.md` (J16-M8).

**Requested by Jo** in these words: *"can you ask the jury to make a last swip, to
make sure you are not fucking up things while fixing anything."* The brief named
six areas the author was least confident about, rather than letting the sweep
hunt blind.

## Verdict

**`FAIL` — 0 Blocker · 8 Critical · 9 Major · 4 Minor.** Every finding was a
round-15 artifact: defects introduced by the fixes for round 14.

**All three self-flagged suspicions were confirmed**, plus five the author did not
anticipate.

| ID | Finding |
| --- | --- |
| **J15-C1** | Two live Phase 1 items, five lines apart, same owner, same due date, defining `segments.align_blocker` with **different enums**. The new item was added and the old one not removed — Atlas would build one column from two contradictory specifications |
| **J15-C2** | `no_transcriber` and `wrong_match` appeared in no permanence classification, so the derivation's *"else `retryable`"* caught them. **`no_transcriber` means we have no transcriber for this language — derived `retryable`, a blind Haitian Creole user is told to pay $1.35–$32 again for a retry structurally incapable of succeeding.** J11-C1 inverted, arriving through the fix for J11-C1's successor |
| **J15-C3** | `asr_conf`/`match_conf` had no column, and the word record existed in **three incompatible shapes** across two documents |
| **J15-C4** | `align_conf = min(asr_conf, match_conf)` while the client was instructed to key highlighting on `match_conf` and served only `align_conf_threshold` — comparing one quantity against a bound computed from another. The R14-C3 confusion re-created at the client |
| **J15-C5** | `word_sync_confidence` — an unrequested field. It failed **all three** of Halo's tests: no column, no producing stage, and a value domain of exactly one constant, so a client could not branch on it and there was nothing to translate |
| **J15-C6** | The catalogue budget still read **17 keys / 68 strings**, computed from the retired reason set. Recount: **19 keys / 76 strings.** Tongue's `ht` work was scoped against a number 12% low, and the three new states had **no string in any of four languages** — so the states this architecture exists to introduce could not be announced to any user |
| **J15-C7** | README blocked the entire build on an `ht` question the other two artifacts had closed the same day |
| **J15-C8** | Spec §2 and §3 never learned the architecture changed — a reader opening the spec at page one met an eight-stage pipeline ending in `align`, and did not reach §6.1's contradiction of it until line 551 |

Majors: subprocessor disclosure applied to 1 of 3 sites · no Gemini row in the
§5 cost model · the numeric SPIKE A bar required in three places and stated in
none · a live, owned, dated roadmap item scheduling work against a deleted
dependency · Phase 4.5's header still claiming to own the headline feature · the
`HARVEST` floor set **at** the measured value rather than below it · dead
allowlist entries pre-silencing a guard · `INV-UNRELIABLE-PERM` a re-pointed
specimen · `speech_blocker` prose broken by its own repair.

## The scope measurement, a fourth time

> *`R14-C6` — a one-line assertion propagated to three sites — is closed with
> **zero** defects. `R14-C2` — one decision, ~24 sites — is asserted at four
> sites, left standing at eight, and generated most of what follows. **The ratio,
> not the size.***

And on the one unrequested addition:

> *Your last two rounds found every defect in unrequested additions; this round
> found one unrequested addition and it is a Critical. The pattern held with
> unusual precision.*

Out-of-scope discipline was otherwise good: `R14-M1` (sample URLs) stayed deleted
and open, `R14-M2` (transcription pricing) stayed open with no invented price, no
spike was retired that `R14-A1` did not require, no prose was polished for its
own sake.

## The guard that had to change direction

`INV-OPAQUE-PERM`, demanded by Jury in round 11, fired on a **correct** edit —
it asserted a specific sentence was *present*, and the sentence had been
legitimately reworded. That exposed the real defect, open since round 12 as
J12-M1:

> **Every real leak in this chain was an ADDED copy at a new site, and a presence
> guard cannot see one.** Jury proved it by pasting the wrong claim into four
> files at a green gate.

Response: two `BANNED` **contradiction guards** — `N15-CONTRA-UNRELIABLE` fires
if `transcription_unreliable` is ever classified `permanent` *anywhere*;
`N15-CONTRA-TRANSCRIBER` fires if `no_transcriber` is ever classified
`retryable`/`render_specific` *anywhere*. Round 16 attacked them and confirmed
they hold: *"genuinely faithful — it adds a wrong classification while leaving
the right one standing, which is the added-copy shape a presence guard
structurally cannot see."*

## The gate ran green through all of it

> **Every Critical below sits at a green gate.** *That is the finding about the
> gate, not about the authors.*

`doc-check` exited 0 and self-tested 43/43 while eight Criticals stood. The
authorised tooling change — `[HARVEST]`, failing when a parse returns nothing —
was verified by re-running the round-14 CRLF accident deliberately; it fired with
`parsed 0 declared interface fields`. Previously that corruption produced 33
misleading findings while the forward check passed silently over an empty set.
