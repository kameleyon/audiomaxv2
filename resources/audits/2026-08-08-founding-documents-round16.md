# Audit Record — Founding Documents, Round 16

- **Date:** 2026-08-08 · **Subject:** spec v16, roadmap v16, `README.md`, `CLAUDE.md`, `tools/doc-check.mjs`
- **Reviewer:** Jury — regression sweep, read-only · **Response:** v17
- **Reconciliation:** `node tools/doc-check.mjs` → exit 0 · `--self-test` → 45/45 → **46/46**

## Verdict

**`FAIL` — 0 Blocker · 3 Critical · 9 Major · 4 Minor.** Fourteen of the
seventeen round-15 findings were verified closed. The three that were not shared
one shape.

## The three

| ID | Finding |
| --- | --- |
| **J16-C1** | `word_sync_confidence` was deleted **in one document and still built by another** — removed from the §8.2 payload with a full rationale, still named normatively at `spec:626`, and still bolded, justified, owned and dated in the roadmap's `GET /quote` item. `CLAUDE.md:112-115` decides the severity: the roadmap is what gets built, so the thing that was deleted would have shipped |
| **J16-C2** | §6.3 called `transcription_unreliable` **voice-independent and `(lang, voice)` four lines apart**, then stored it in `segments` — a table with no `voice_id` column. It would have been right for one voice and wrong for every other, and the user would learn which after paying |
| **J16-C3** | `observed_words` existed in **exactly one sentence project-wide**. No build item, no owner, no date, no migration. It would simply not have been built |

## Why the tool did not see J16-C3

The S2R harvest requires a closing backtick — `` `observed_words` `` — but §7.2a
writes columns as `` `observed_words JSONB` ``. The type suffix made the
identifier invisible. **The tool already knew about that notation:** a different
function sixty lines away handles it explicitly, with a comment saying so
(N9-M2). The knowledge existed in one function and not its neighbour — the same
defect as a fix living in one document and not the other, committed in code
rather than in prose.

## Majors

Catalogue recount propagated to the headline and not the derivation (15 + 2 = 17
≠ 19) · the numeric SPIKE A bar asserted *about* the spike and stated nowhere
*in* it · §9's `GET /segments` row naming neither threshold, so the split was
coherent in §6.3 and Phase 6 and absent from the contract · `overall_conf`
scheduled to be served when the spec uses it only as the name of a **failure
mode** · §11 legal still omitting Google after README and `CLAUDE.md` were fixed
· Phase 4.5's header corrected and its conclusion left standing · the `HARVEST`
floor set **at** the measured value rather than below it · **rounds 13–15 had no
stored report**, so the sweep had to reconstruct its subject from a chat message,
which `CLAUDE.md` forbids · `speech_blocker` recorded rather than fixed.

## The guard that had to change direction

`INV-OPAQUE-PERM` — demanded by Jury in round 11 — **fired on a correct edit**.
It asserted a specific sentence was *present*, and the sentence had been
legitimately reworded. That exposed J12-M1, open since round 12:

> **Every real leak in this chain was an ADDED copy at a new site, and a presence
> guard cannot see one.**

Response: two `BANNED` **contradiction guards** — fire if
`transcription_unreliable` is ever classified `permanent`, or `no_transcriber`
ever `retryable`, **anywhere in the document**. Jury attacked both and confirmed
them faithful: *"it adds a wrong classification while leaving the right one
standing, which is the added-copy shape a presence guard structurally cannot
see."* `INV-TRANSCRIBER-PERM` was then added for the presence direction, after
Jury showed that silently **deleting** `no_transcriber` from the `permanent` list
wrote no wrong sentence, fired nothing, and let the derivation fall through to
`retryable` — inviting a paid retry that cannot succeed.

## The measurement, a fourth time

> *`R14-C6` — a one-line assertion propagated to three sites — closed with **zero**
> defects. `R14-C2` — one decision, ~24 sites — asserted at four and left standing
> at eight, and generated most of what follows. **The ratio, not the size.***

## The gate ran green through all of it

`doc-check` exited 0 and self-tested 45/45 with three Criticals open. Jury:
*"Every Critical below sits at a green gate. That is the finding about the gate,
not about the authors."*
