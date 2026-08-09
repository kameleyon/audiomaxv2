# ADR-0005 — Haitian Creole is removed from scope

- **Status:** Accepted, 2026-08-08. Supersedes the language-scope half of [ADR-0003](0003-haitian-creole-tts-routing.md); ADR-0003's *routing* finding still stands and still governs `es`/`fr`.
- **Decider:** Jo (owner). This is a product-scope decision, not a technical one.
- **Supported languages after this ADR:** `en`, `es`, `fr`.

> **Read this before assuming Creole was dropped because it did not work.** It
> worked. That is the fact this ADR exists to preserve.

## Context

Haitian Creole was a founding requirement. It shaped the design in ways that
outlast it: per-block language tagging, the never-cross-a-language-boundary
invariant, `voice_substituted`, the message catalogue's per-language key
structure, and the entire pre-payment disclosure chain were all specified with a
low-resource language as the hard case.

For fourteen document revisions `ht` sat marked **"UNRESOLVED — Phase 0
blocker"**. It was then resolved at zero cost from production evidence
(ADR-0003): a sibling product routes `ht` and ten other languages to Gemini,
which speaks it natively, and no code path called the provider the stale comment
named. `ht` was not a launch risk.

**The owner removed it from scope the same day it was proven to work.** That is
allowed, it needs no technical justification, and this ADR does not supply one.

## Decision

`ht` is **out of scope**, not deferred.

It is **not erased from the design.** It falls through §3.5's routing table to
the **no-route row** and is refused with an announced
`blocked_language_unsupported`. That machinery already exists — it was built for
`J17-C1`, when the routing table was total over languages and the pre-payment
speech disclosure could therefore only ever report *"you will hear all of it."*

So a Creole document now produces a **correct, announced refusal at quote time,
before payment**, rather than silence, a wrong-language voice, or a charge for
audio that will not arrive. `ht` becomes the canonical example of the
unsupported-language class rather than its counter-example.

## Consequences

**Simplification.** The message catalogue drops from 20 keys × 4 languages
(80 strings) to 20 × 3 (**60 strings**). SPIKE A's language-coverage matrix
covers the three supported languages instead of the eleven the reference stack
routes — and the scope question that `J18-M4` opened closes with it.

**The hardest test case is gone, and that is a real loss.** `ht` was the
language that exposed defects the others did not:

- `R14-C5` — that transcription-based word sync is materially weaker on
  low-resource languages, and that its failure mode is *fluent* hallucination:
  a token timed to 50 ms and mapped to the wrong word. That risk does not
  disappear; it merely stops having a named victim in the document. `es` and
  `fr` are better-resourced, not perfectly resourced.
- `J17-C1` — that a pre-payment disclosure with no raiser reports `0` forever.
  Found because someone asked what a Creole speaker would be told.
- `J15-C2` — that `no_transcriber` derived as `retryable` invites a paid retry
  that cannot succeed.

**Every one of those defects was general.** Creole was the lens, not the cause.
Removing the lens does not remove the class, and a reviewer should not read the
absence of `ht` from this design as evidence that low-resource-language handling
has been tested.

**Subprocessor disclosure is unchanged in substance.** ADR-0003 established that
Gemini TTS is reached via **OpenRouter primary** with **direct Google as
fallback**. That still holds for `es` and `fr`, so **both parties remain named
subprocessors** under `CLAUDE.md` constraint 7. The `ht` framing goes; the
disclosure obligation does not.

**What this ADR does not claim.** It does not claim `ht` was infeasible, poorly
supported, or expensive. It was none of those. It claims only that the owner
chose three languages instead of four.

## Reversal cost

Low, and deliberately kept low. Re-adding `ht` requires: a routing row in §3.5,
Gemini voice rows in `voices`, 20 catalogue strings, and inclusion in SPIKE A's
matrix. The per-block language tagging, the substitution machinery and the
disclosure chain all remain — they were never `ht`-specific. Nothing in this
removal burns a bridge.
