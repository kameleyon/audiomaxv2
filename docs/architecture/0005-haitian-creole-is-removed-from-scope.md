# ADR-0005 — Haitian Creole is removed from scope

- **Status:** Accepted, 2026-08-08. Supersedes the language-scope half of [ADR-0003](0003-haitian-creole-tts-routing.md). **ADR-0003's routing finding governs nothing in audiomax** — see the correction below.
- **Decider:** Jo (owner). This is a product-scope decision, not a technical one.
- **Supported languages after this ADR:** `en`, `es`, `fr`.

> **CORRECTED 2026-08-10 (`J29-C3`, found unfixed here).** The Status line above
> read *"ADR-0003's *routing* finding still stands and **still governs
> `es`/`fr`**."* **It does not, and it never did.** Gemini was reached for `ht`
> only; `es` and `fr` are **Fish Audio `s2-pro`** and always were, in the
> reference stack and in spec §3.5.
>
> That exact sentence is the one round 29 ruled *"the single sentence that
> propagated the error into SPIKE A's first `es`/`fr` measurement"* — audio for
> two of three shipping languages generated on a provider this product does not
> use. It was struck from ADR-0003's banner on 2026-08-09 and **left standing
> verbatim in the ADR that supersedes it**, which is the newer document and the
> one a reader reaches last. The round-29 routing reconciliation listed *"the
> bodies of ADR-0003 and ADR-0005"* as **deliberately unchanged**, on the
> ground that each is *"a dated record of what was true or of the reference
> stack's behaviour"*. That disposition is correct for the *Context* section
> below and **wrong for this line and for "Subprocessor disclosure is unchanged
> in substance"**, because those two are not records of anything — they are live
> assertions about audiomax's routing and audiomax's compliance obligations.
> **A hit you dispositioned wrongly is worse than a hit you missed: it is
> recorded as reconciled.**

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

**Simplification.** The **`align_*` half** of the message catalogue drops from
20 keys × 4 languages (80 strings) to 20 × 3 (**60 strings**). *That is the
`align_*` budget only* (`H20-C1`); the catalogue's total is **~54 keys / ~162
strings across three languages** (spec §9, recounted for `H26-C3`), and quoting
the 20/60 pair as the whole catalogue is the defect `H20-C1` was filed for.
SPIKE A's language-coverage matrix
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

**Subprocessor disclosure changes in substance — CORRECTED 2026-08-10.** This
paragraph read: *"ADR-0003 established that Gemini TTS is reached via
**OpenRouter primary** with **direct Google as fallback**. That still holds for
`es` and `fr`, so **both parties remain named subprocessors** under `CLAUDE.md`
constraint 7."* **Every clause of that is now false**, and it was a live
compliance instruction in a committed document.

What is true, per `CLAUDE.md` constraint 7 as corrected on 2026-08-09 (`J29-C3`):

- **TTS is two vendors, not three: Fish Audio `s2-pro` and Lemonfox.** Gemini
  entered the routing table only as the `ht` route and left scope with `ht`.
  **audiomax routes nothing to Gemini or to Google**, so Google is **not** a
  subprocessor of this product and must not be listed as one. Listing a
  processor that never receives the data is not a harmless over-disclosure — it
  is a false statement in the artifact whose entire purpose is to be true.
- **Text still reaches an LLM via OpenRouter**, so OpenRouter remains a named
  subprocessor.
- **The LLM's model host is not yet named**, because the model has not been
  chosen. `CLAUDE.md` records that as open and gating: *"Shipping ingest while
  the list says 'an LLM' is this constraint breached, not deferred."*
  **Owner: Comply with Forge · due 2026-08-15**, and in no case later than the
  first ingest endpoint.
- **Generated audio reaches our own transcription sidecar.** First-party;
  disclosed as such, never as a subprocessor.

The `ht` framing goes and **so does half the disclosure**. What does not go is
the obligation: `CLAUDE.md` constraint 7 is *"users are told where their
documents go"*, and it is breached by an inaccurate list exactly as it is by a
missing one.

**What this ADR does not claim.** It does not claim `ht` was infeasible, poorly
supported, or expensive. It was none of those. It claims only that the owner
chose three languages instead of four.

## Reversal cost

Low, and deliberately kept low. Re-adding `ht` requires: a routing row in §3.5,
voice rows in `voices` **plus their `(voice, language)` rows in `voice_langs`
(§7.1a)** for whichever provider is then chosen, 20 `align_*` catalogue strings,
and inclusion in SPIKE A's matrix. The per-block language tagging, the
substitution machinery and the disclosure chain all remain — they were never
`ht`-specific. Nothing in this removal burns a bridge.

*(This read "Gemini voice rows in `voices`". Two things went stale under it: a
re-introduction would have to **re-choose a provider**, since audiomax has no
Gemini or Google integration to switch back on; and `voices.lang` was scalar and
is **gone** (`H26-C3`) — the `(voice, language)` pairing lives in `voice_langs`,
so a voice row alone reaches no `GET /voices?lang=ht` caller. A reversal-cost
estimate that names the wrong table understates the reversal.)*
