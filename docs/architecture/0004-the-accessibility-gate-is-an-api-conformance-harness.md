# ADR-0004 — The accessibility gate is an API conformance harness

## Status

**Accepted 2026-08-08. Decided by Jo**, the product owner — option **(b)** of
three.

**The obligation it does not discharge is recorded in the decision itself.** Read
[the limitation](#the-limitation-read-this-with-the-decision-not-after-it) before
citing this ADR as accessibility sign-off. It is not one.

Design intent, not gate approval — see [the status note](README.md#what-accepted-means-here-and-what-it-does-not).

## Context

`CLAUDE.md` opens its constraints with *"accessibility is the product, not a
feature"*, and names **blind and low-vision users who depend on reliable TTS** as
a **primary population**. **Halo**, the accessibility auditor, reviews every
phase.

That produced a real deadlock:

- **Halo cannot issue `PASS` before implementation, by its own rules.** A `PASS`
  requires a recorded **NVDA** transcript and a recorded **VoiceOver**
  transcript, taken against a real client.
- **No client exists.** Client applications are explicitly out of scope of this
  spec (§13), and the client spec has not been written.
- **`CLAUDE.md` forbids discharging an accessibility obligation onto a component
  that is out of scope.** If the data is not captured server-side, no client can
  invent it — so "the client team will handle accessibility" is not available as
  an answer.

So the backend could neither prove accessibility nor honestly defer it. The
decision was originally scheduled in Phase 10 and was moved to **Phase 0**,
because a decision about whether an accessibility gate exists must precede the
stages that produce everything it would exercise — Phases 4.5 and 6 — rather than
follow them by five weeks (`R5-M13`).

### The three options

| # | Option | Cost | What it proves |
| --- | --- | --- | --- |
| **(a)** | Build a reference client | Adds a client spec and a whole phase | The most, and the most expensive |
| **(b)** | **API conformance harness** — headless, drives the documented flows | Far cheaper | Whether the backend **forecloses** an accessible client |
| **(c)** | Defer to the client project | Nothing now | Nothing — and the backend then ships **unsigned-off on accessibility**, which requires an explicit, signed, recorded risk acceptance, *not a checkbox* |

Option (b) was **Halo's own proposal** and was not on the earlier menu.

## Decision

**Build a headless API conformance harness as the Phase 0 accessibility gate.**
*(Owner: **Probe** · due **2026-08-25**.)*

It drives the documented §9 API flows and asserts, for **every** disclosure, that
it is:

1. **reachable** by a client,
2. **correctly addressed** — positioned, not merely tallied, and
3. carries a **catalogue string in all three supported languages** (`en`, `es`, `fr`).

**Concretely, it must fail on the three defects round 17 found by hand:**

- a `speech_blocker` that returns `0` for **every** document — a pre-payment
  disclosure with no reachable raiser;
- a `GET /voices?lang=` that returns an **empty list with no reason** — the
  "choose a different voice" remedy pointing at a door that does not exist;
- an `align_reason` with **no string in one of the three supported languages** (H21-C1 — this specimen read *"no string in an unsupported language"*, which every `align_reason` satisfies by design, so a harness built to it could never go green: the gate defining conformance specified its own unconditional failure) — an untranslated enum token is
  not a status message a user can receive (WCAG 4.1.3).

Those three are the acceptance specimens. A harness that passes while any of them
is present has not been built.

## The limitation — read this with the decision, not after it

**The harness does not substitute for NVDA or VoiceOver.**

- **Halo still cannot issue `PASS`.** The harness answers only whether the
  backend *forecloses* an accessible client — which is the only question a
  backend audit can answer at all. It does not answer whether a blind user can
  use the product.
- **A real screen-reader transcript remains required before the product launches
  to blind users as a named primary population.**
- **That obligation moves to the client project. It is *not* discharged here.**

The item is marked done in the roadmap **because** it records the limitation.
Jury accepted the `[x]` on exactly that basis:

> *"That statement is the reason I accept the `[x]`. A decision that closed the
> item by declaring the obligation discharged would have been a Critical."*
> (`-round19.md`)

Halo's own position on option (c) draws the line the same way, and it applies to
(b) as well: if "ship" means merging a backend with no user-facing surface, no
user is excluded and it has no objection; **if it means the *product* launches
with blind users as a named primary population, that is Halo's Rule 6 and it does
not ship.** The documents must say which — and this one says which.

## Consequences

### What still has to happen, with owner and date

**Assistive-technology acceptance** stays in Phase 10 as the artifact Halo needs
to issue a `PASS` *(Owner: **Halo** · due **2026-10-15**)*:

- **NVDA + Firefox** and **VoiceOver + Safari** on the reference client, each
  producing a **recorded transcript** retained in `resources/audits/`;
- the matrix must also include **TalkBack** and **VoiceOver/iOS** — mobile is in
  the topology and offline download is mobile-only — and a **keyboard-only pass**;
- heading navigation (`H` key / rotor) reaches every chapter and section;
- language changes are announced with the correct voice at passage granularity in
  a document mixing `fr` with an unsupported language;
- a degraded segment announces **its reason and its permanence**, in the user's
  locale, from the message catalogue;
- the skip manifest is announced **at position**, not only as an import tally;
- an undescribed figure and an unnarratable equation are both announced;
- **pass criterion: zero WCAG 2.2 AA failures on the primary flow**, and every
  disclosure above is *heard*, not merely present in the API.

### What the harness changes about how the backend is built

Because the gate is an API harness, **every accessibility obligation must be
expressible as an API assertion** — which is the same discipline the spec already
imposes: a disclosure that a client cannot reach, address, or translate does not
exist. Concretely it keeps honest the four pre-payment and mid-session disclosure
channels (`word_sync_available_segments`, `progress_resolution`,
`blocked_language_unsupported`, `spoken_chars` per span), the §9.1 disclosure
spans, and the 20-key / 60-string message catalogue.

### What it does not change

`CLAUDE.md` constraint 1 is unchanged: **WCAG 2.2 AA is a floor.** This ADR
records how a *backend with no user-facing surface* is gated in the interim. It
is not a redefinition of the standard, and it is not permission to launch without
a screen-reader pass.

## References

- Roadmap Phase 0 (the decision, the harness build item, the superseded options),
  Phase 10 (assistive-technology acceptance)
- Spec §13 (clients out of scope)
- `CLAUDE.md` — constraint 1, and the rule against discharging an accessibility
  obligation onto an out-of-scope component
- Audits: `-round19.md` (Jo's decision, Jury's acceptance, the three hand-found
  defects), `-round5.md` (`R5-M13`, moving the decision to Phase 0)
