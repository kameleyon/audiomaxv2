# ADR-0001 — The segment is the universal unit

## Status

**Accepted.** Present in the backend design spec from v1 and unchanged through
v19; it is the one structural decision no audit round has disputed.

Design intent, not gate approval — see [the status note](README.md#what-accepted-means-here-and-what-it-does-not).

## Context

A reference book is roughly **540,000 characters** and **nine hours of audio**.
Six separate problems each need a granularity to operate on, and each one, taken
alone, wants a different answer:

| Problem | What it wants, taken alone |
| --- | --- |
| Alignment accuracy | Short clips — long audio drifts and cannot be timed in parallel |
| Billing precision | Whatever the provider actually bills |
| Lazy generation | Something orderable, so "render ahead of the playhead" is expressible |
| Retry granularity | Something small, so a failure is cheap |
| Offline download | A contiguous range a client can name |
| Playback and resume | Something a position can be anchored to |

Answering each separately produces a system with six units of work and five
conversion functions between them — and every conversion is a place where a
highlight can land on the wrong word.

The spec does not argue against a named rejected alternative here. What it
records is a **convergence argument**: one unit, deliberately sized, resolves all
six (§3).

## Decision

**The segment is the universal unit — of work, billing, caching, retry, playback,
and sync.**

A segment targets **1,000 characters** and never exceeds a hard ceiling of
**2,000**, which is roughly **60 seconds of audio** (§3, §3.4).

Segments are cut on rules, not on a character count alone (§3.4):

- never split mid-sentence;
- never cross a chapter boundary;
- **never cross a language boundary** — a Haitian Creole passage must not be
  spoken by a French voice;
- a speaker change forces a boundary — one voice per segment;
- a heading becomes its own segment, so it has distinct prosody and is a seek
  target.

## Consequences

### What it buys

| Problem | Resolution via segments |
| --- | --- |
| Alignment accuracy | Short clips transcribe and align accurately, and in parallel |
| Billing precision | The segment is the quote line item |
| Lazy generation | Render-ahead is a queue walk over ordinals |
| Retry granularity | A failure costs one segment, not one book |
| Offline download | "Fetch segments N..M" |
| Playback and resume | `listening_progress` anchors to a segment ordinal and offset |

### What it costs

**The billable count is not the segment's own character count.** Segmentation
records `display_char_count` and `display_byte_count`; the **spoken** and
**inserted** counts that providers bill are produced later, at stage 4.5
Normalize, and those are what the preflight quote meters (§3.4, §8.2). `1984` is
four display characters and twenty spoken ones. The 2,000 ceiling is likewise a
*display* ceiling; post-normalization length is checked separately against
provider per-request limits.

**Ordinals are immutable.** Because a segment ordinal is an address that offline
copies, `listening_progress` rows and rendered audio all reference, changing how
a document is segmented cannot mutate it. It creates a **new `segment_set_id`**,
with `superseded_by` linking the old set forward, and superseded audio is
retained for 30 days with its expiry disclosed (§7.2b). Re-segmentation is
triggered by a skip-policy change, and also by the over-length remedy: when
normalization pushes a segment past a provider ceiling it is split at a group
boundary, expressed as a new set, and **not billed** — it is our constraint, not
a user action (§8.2).

**The block range must tile the document.** A segment's
`[start_block_ord, end_block_ord]` range, together with `skipped_block_ords[]`,
must be gapless and contiguous from block 0 to the last block, so that nothing
the pipeline drops can fall between two segments and vanish from the skip
manifest (§3.4). `block_start_offsets[]` gives the character offset inside
`segments.text` where each constituent block begins, completing the address
chain `block → segment → character-in-segment → word → character-in-word`. Its
arity is stated as a length invariant over
`range ∪ skipped_block_ords ∪ excluded_block_ords`.

**A document with no segments still needs a manifest.** An all-image PDF, or one
where everything was skipped, produces no segment to carry the disclosure, so
`documents.skip_manifest` is authoritative when `segments` is empty (§3.4). A
blind user must never receive a document that yields nothing and no explanation.

**The segment is also where the schema splits.** Content and provenance live on
`segments`; everything that varies per voice — audio path, duration, word
timings, alignment state — lives on `segment_renditions`, one row per
`(segment, voice)` (§7.2, §7.2a). Word timings are computed against a specific
rendition's audio, so keeping them on the segment would let a re-render in voice
B destroy the sync data for voice A's audio, which the user paid for.

### Still open

Segment sizing is an **input to SPIKE A**, not a settled number: the spike
measures word-timestamp accuracy per language and "feeds back into segment
sizing, which the spec calls the central design decision" (roadmap, Phase 0,
SPIKE A · Owner Forge · due 2026-08-14). If short-clip accuracy behaves
differently than assumed, the 1,000-character target moves.

**Two measurements now push on it from opposite directions, and neither has been
resolved into a number.**

**1. Memory says a 60-second segment is expensive to align in one pass**
(SPIKE E). Peak RSS for a single 73–77 s segment is **2,849–4,549 MiB**, and it
is dominated by **forced alignment, not ASR** — ASR plateaus flat at ~493 MiB —
because self-attention is **quadratic in frames**. Chunking the alignment pass
to 15 s bounds memory by the chunk: peak falls to **1,937 MiB**, the
alignment-attributable term falls **3.8×**, and the recommended container drops
from **5 GiB to 2.5 GiB** — twice the memory bill and half the workers per node.

**The cost of chunking is a seam every chunk, and whether the match step
tolerates a seam is a word-sync question, which is why it is routed here rather
than to the queue.** It is genuinely open. ADR-0006's matcher re-synchronises
forward with a 3-token trigger and a 3-token anchor, which is *exactly* the
machinery a chunk seam would need — but re-sync was measured on continuous audio
recovering from ASR error, **not on an imposed boundary every 15 s**, and a
matcher that recovers within a few tokens still loses those tokens at every
seam. **~1,000 characters of audio would cross roughly four seams.**
*(Owner: Forge · due 2026-08-18; roadmap Phase 7 carries the item.)*

**2. Accuracy is currently bound by recognition, not by clip length**
(ADR-0006). The 95 bar is **ASR-bound** — 93 of 125 unplaced tokens on the best
long clip are words the ASR never wrote — so shortening segments to help
alignment would not move the bar today. **That is a reason not to resize yet,
not evidence that size is irrelevant**: the drift-accumulation question the size
target was meant to bound (`H26-M7`) is still open, and its intervals have not
been re-scored under the new matcher.

**So the 1,000-character target is unchanged, and is now unchanged for a stated
reason rather than by default.**

## References

- Spec §3 (pipeline and the resolution table), §3.4 (segment rules,
  addressability, tiling, zero-segment documents), §7.2 / §7.2a (the schema
  split), §7.2b (versioning), §8.2 (quote, over-length remedy)
- Roadmap Phase 0 (SPIKE A), Phase 4 (segmenter), Phase 1 (columns)
- Findings: `N-1` addressability, `N-2` coverage, `NEW-M4`/`R4-M5` arity,
  `NEW-M5a` chapter-boundary collision, `NEW-M5b` zero-segment documents,
  `N3-R3` the rendition split
