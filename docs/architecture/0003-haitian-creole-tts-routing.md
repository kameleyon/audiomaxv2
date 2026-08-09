# ADR-0003 — Haitian Creole routes to Gemini TTS, via OpenRouter

> **SUPERSEDED IN PART by [ADR-0005](0005-haitian-creole-is-removed-from-scope.md), 2026-08-08.**
> Haitian Creole is **out of scope** — the owner removed it the same day this ADR proved it worked.
> **The routing finding below still stands and still governs `es` and `fr`:** Gemini TTS is reached via
> **OpenRouter primary** (`google/gemini-3.1-flash-tts-preview`) with **direct Google as fallback**
> (`gemini-2.5-*-preview-tts`), so **both remain named subprocessors**. The `CLAUDE.md` constraint-2
> conflict recorded here — a silent primary-to-fallback chain in a product that forbids fallback
> launches — is **unaffected and still open**. Read this ADR for the method and the routing fact;
> read ADR-0005 for the language scope.


## Status

**Accepted 2026-08-08.** Resolved from production evidence at **zero cost — no
API calls, $0.00.** Finding `R14-C6`; SPIKE B's TTS half is closed.

**Corrected 2026-08-08**, before first publication, after the routing claim was
re-verified against the call sites rather than the comments. The **language
finding is unchanged** — `ht` is served natively by a Gemini model in production
and is not a launch blocker. **The route and the model name in the first draft
were wrong**, and the correction adds a second named subprocessor and an open
conflict with `CLAUDE.md`. See [Consequences](#consequences).

Design intent, not gate approval — see [the status note](README.md#what-accepted-means-here-and-what-it-does-not).

> **Divergence, stated rather than reconciled.** Spec §3.5 and
> `resources/research/2026-08-08-spike-b-ht-production-evidence.md` currently name
> the provider as *"Google Gemini Flash 2.5 TTS"*. That phrasing predates the
> call-site verification below and is being corrected separately by the document
> owner. This ADR states what the code does; where the two disagree today, this
> page is the one with the `file:line`.

## Context

Haitian Creole is one of four product languages (`en`, `es`, `fr`, `ht`) and the
one with the fewest alternatives for its speakers. For **fourteen revisions** the
spec carried `ht` as **"UNRESOLVED — Phase 0 blocker"**, and the roadmap
scheduled **SPIKE B** — a paid TTS call plus an alignment run — to settle it.

The uncertainty came from a straight contradiction inside the reference stack,
`motionmax`, running in production on this same host:

| Site | Claim |
| --- | --- |
| `motionmax/worker/src/services/audioRouter.ts:10-15` | *"The 11 supported languages (en, fr, es, **ht**, de, it, nl, ru, zh, ja, ko) all go through Gemini Flash 2.5 TTS — it speaks every one of them natively."* |
| `motionmax/worker/src/lib/providerRates.ts:71-73` | *"Google Cloud TTS (only used today for Haitian Creole **because Gemini Flash doesn't support that locale**)."* |

Two comments, opposite claims, same repository.

## Decision

**`ht` is synthesized by a Gemini TTS model, which speaks it natively with no
per-language wiring. `ht` is not a launch blocker and is no longer a Phase 0 gate
item.**

The route, as the reference stack actually implements it:

| Order | Path | Model | Evidence |
| --- | --- | --- | --- |
| **Primary** | **OpenRouter**, `POST https://openrouter.ai/api/v1/audio/speech` | **`google/gemini-3.1-flash-tts-preview`** | `audioProviders.ts:194, 236, 245` |
| **Fallback** | **Direct Google**, native key rotation | `gemini-2.5-pro-preview-tts`, then `gemini-2.5-flash-preview-tts` | `audioProviders.ts:94-97, 316` |

`generateGeminiTTS` (`audioProviders.ts:182`) calls the OpenRouter path first
(`:194`); only if that returns no URL does it `console.warn` and fall through to
native key rotation (`:199`), which walks **5 rounds × every configured Google
key × 2 model variants** (`:94-98`).

### Method — decided by what the code calls, not by which comment reads better

```
grep -rn "google_cloud|googleCloudTTS|texttospeech" motionmax/worker/src
→ providerRates.ts:74,183          rate-card key only
→ handleFinalize.ts:257,261,294    cost-attribution switch, marked "legacy-only"
→ (no synthesis call anywhere)
```

**No code path invokes Google Cloud TTS.** Every occurrence is COGS arithmetic
summing a legacy line item. `audioRouter.ts:213-225` routes CASE 4 —
*"everything else"*, which includes `ht` — to `generateGeminiTTS`.

Corroborating: `handleCinematicAudio.ts:205-222` treats Haitian Creole as an
ordinary Gemini path — the only `ht` special case left is a legacy branch for
projects whose stored voice name predates the current voice picker, and the
default speaker for `ht` is a Gemini voice. The reference stack passed through a
phase of treating `ht` specially and left it behind.

### The method point, twice over

The first draft of this ADR resolved the contradiction by trusting
`audioRouter.ts:10-15` over `providerRates.ts:71-73`. **That comment is itself
stale**: it names *"Gemini Flash 2.5 TTS"*, while the function it describes calls
OpenRouter for `gemini-3.1-flash-tts-preview` and only reaches a 2.5 model on
failure. The router's own header (`:8`) says *"ANYTHING ELSE → Google Gemini
Flash TTS"*, which omits OpenRouter entirely.

So the same file family produced **two** stale provider claims, and the correct
answer was in the call site both times.

> **Rule this ADR now carries: a routing fact is established at the call site.**
> A comment — including one this project has already cited as evidence — is a
> lead, not a source. `providerRates.ts` is independently wrong in three places
> (Lemonfox overstated ~32×, Fish ~6.7×, and the locale claim), so every rate and
> remark in that file is treated as unverified.

Evidence file:
`resources/research/2026-08-08-spike-b-ht-production-evidence.md` (Evidence Tier
**A** — shipping code paths on this host, not vendor documentation), plus the
`audioProviders.ts` line references above, verified 2026-08-08.

## Consequences

### Two named subprocessors, not one

`CLAUDE.md` constraint 7 — *"users are told where their documents go"* — requires
a maintained, disclosed subprocessor list, and spec §11 makes it a Phase 0.5 item
that **gates all ingest**.

A request routed through OpenRouter reaches **OpenRouter *and* the model host**.
Both must be named:

| Subprocessor | Why it is on the list |
| --- | --- |
| **OpenRouter** | The primary `ht` synthesis path. Text passes through it |
| **Google** | The model host behind the OpenRouter route, and the direct fallback path |

Disclosing only the model vendor would leave the party that actually receives the
request undisclosed — and the first draft of this ADR made exactly that mistake.
Uploads already reach an LLM and up to three TTS vendors; generated audio
additionally reaches our own transcription sidecar, which is first-party and is
disclosed as such rather than as a subprocessor.

Users uploading medical, legal or unpublished material have no other notice, and
for blind users — who cannot casually inspect where a document went — the
asymmetry is sharper.

### OPEN — the reference implementation's shape violates `CLAUDE.md` constraint 2

**This is unresolved, and it is recorded here rather than discovered in Phase 5.**

> `CLAUDE.md` constraint 2 — **No fallback launch.** *"A primary path must never
> depend on a fallback. Degraded paths are emergency-only and must be **visible,
> reasoned, and announceable** when they engage."*

The reference stack's Gemini path is a **silent primary → fallback chain**:
OpenRouter first, a `console.warn` on failure (`audioProviders.ts:199`), then
direct Google. Nothing reaches the user, nothing reaches the database, and the
two paths use **different models** — `gemini-3.1-flash-tts-preview` versus
`gemini-2.5-*-preview-tts` — so the audio a user receives depends on which path
served it, with no record of which one did.

**audiomax may not copy that shape.** For this product the same chain would mean:

- a **voice and model substitution that is not announced**, in a product whose
  own `voice_substituted` disclosure exists precisely because *"a Haitian Creole
  speaker hears French-accented Creole with no explanation and no way to find
  out"* is unacceptable (spec §7.2b);
- a **cost attribution that is wrong by construction**, since the two paths bill
  differently and nothing records which was used;
- and, if the fallback is what habitually serves `ht`, a **primary path that
  depends on a fallback** — the thing constraint 2 forbids by name.

**The question, unresolved:** does audiomax route `ht` through OpenRouter, direct
Google, or both — and if both, what makes the switch *visible, reasoned and
announceable*: a `provider` value on the rendition, a disclosure span, an
`align_reason`, or a decision that there is no fallback at all and a failure is a
failure?

**It has no owner and no date today.** It lands in **roadmap Phase 5 — TTS
router**, which is reviewed by Halo, Tongue, Scribe and Jury, and it must be
assigned there before that phase is built. This ADR does not resolve it, and a
resolution that quietly adopts the reference stack's chain would be a constraint
violation, not a default.

### The voice catalogue must actually carry the rows

`voices` gains the Gemini rows, **seeded in Phase 1**, with a `provider` value
that distinguishes the routes rather than flattening them to "Google". Without
them an `ht` user calling `GET /voices?lang=ht` reaches an **empty list** — and
every degraded-path remedy this design offers a blind user is *"choose a
different voice"*. A remedy that names a door which does not exist is worse than
no remedy (`N12-C3`). The Phase 0 accessibility harness is required to fail on
exactly that defect (see
[ADR-0004](0004-the-accessibility-gate-is-an-api-conformance-harness.md)).

### `blocked_language_unsupported` loses its example but keeps its class

`ht` was the concrete instance the spec cited for *"a language with no provider
produces no audio at all"*. It is no longer one. The state is **kept**, because
the class is real: §3.5's routing table enumerates eleven languages and ends in
an explicit **no-route row**, and `blocks` carry a detected per-block `lang`, so
a `de`, `ar` or `zh` passage inside an `fr` document is ordinary rather than
hypothetical.

Keeping the routing table **non-total** is load-bearing and is guarded
mechanically (`INV-NO-ROUTE` in `tools/doc-check.mjs`). Through v17 the table
ended `| Everything else | Google / Gemini TTS |` — a row with no language
condition, which made routing total, left `blocked_language_unsupported` with no
reachable raiser, and made the quote's `speech_blocker` report **0 for every
document** while four artifacts promised otherwise (`J17-C1`). It was also an
unevidenced universal capability claim about a provider — the exact class this
project spent five rounds deleting.

### What this does **not** settle

- **`ht` word-sync quality.** The reference stack produces voiceover for video
  and has no word-sync requirement, so it generates **no evidence** about
  alignment. Recognition is materially weaker in Creole than in `en`/`fr`/`es`
  and its failure mode is fluent hallucination. This folds into **SPIKE A**,
  which must return a numeric per-language bar before the quote asserts anything
  about `ht` sync (`R14-C5`). Until then, `ht` word-sync quality is **unknown**
  and the quote must say so rather than guess.
- **Cost at audiobook length.** OpenRouter bills this endpoint **per token**
  ($1/1M in, $20/1M out) and **does not return token counts on it**; the
  reference stack approximates with a per-second rate and says so in a comment at
  `audioProviders.ts:290-296`. audiomax bills users in characters and preflights
  every render with an exact quote, so an unmeasurable provider cost is a real
  problem, not a rounding note. Unquantified.
- **Which model audiomax pins.** `gemini-3.1-flash-tts-preview` is a **preview**
  model reached through a broker. Preview endpoints move.
- **The `ht` go/no-go**, which is a product decision: if `ht` fails the alignment
  check, does it launch degraded — narrated with word sync absent and disclosed —
  or not at all? **Jo decides in Phase 0** (spec §12).

### A method note worth keeping

Twelve audit rounds argued about provider behaviour while the answer sat in
shipping code one directory away, and the probe that settled it cost nothing.

> Jury: *"Twelve rounds of argument were settled by reading
> `audioRouter.ts:214-223`. I record this as the single best piece of work in
> fourteen rounds."* (`-round14.md`)

The correction to this ADR is the other half of that lesson: the reading has to
reach the **call site**. Stopping at the comment is what produced the
contradiction in the first place.

## References

- Spec §3.5 (routing table and the no-route row), §7.2b (voice substitution is
  disclosed), §11 (subprocessor disclosure), §12 (open question 2, closed)
- Roadmap Phase 0 (SPIKE B), Phase 0.5 (subprocessor list), Phase 1 (`voices`
  seeding), Phase 5 (TTS router — where the fallback question must be assigned)
- `CLAUDE.md` constraint 2 (no fallback launch), constraint 7 (subprocessors)
- Research: `resources/research/2026-08-08-spike-b-ht-production-evidence.md`
- Evidence, verified 2026-08-08:
  `motionmax/worker/src/services/audioProviders.ts:94-98, 182, 194, 199, 213,
  236, 245, 290-296, 316`; `audioRouter.ts:8-16, 213-225`;
  `handleCinematicAudio.ts:205-222`; `handleFinalize.ts:257-294`;
  `providerRates.ts:71-74, 183`
- Audits: `-round14.md` (`R14-C6`, `J14-C2`), `-round19.md` (`J17-C1`)
