# Audit Record — Founding Documents, Round 29

- **Date:** 2026-08-09 · **Subject:** 107 staged files — SPIKE A's outstanding items completed, plus repair of every round-28 finding
- **Reviewer:** Jury · **Response:** v29
- **Authorship provenance:** ruling by Jury; **transcribed by the audited party.** States what was true at the ruling. The three Criticals were fixed after it and are certified by no one until re-audit.
- **Index/worktree identity verified by the reviewer:** `git diff --name-only` = 0, so the scan covered exactly the blobs the commit would write.

## Verdict

**`FAIL` — 0 Blocker · 3 Critical · 6 Major · 6 Minor · 1 Polish.** Commit blocked
(`CLAUDE.md:19-23`). Round 28's precedent — *a defect in a control that did not
exist before this commit* — **does not transfer**: two of the three Criticals are
false statements about measured results, and the third is one regex boundary.

> *The work itself is the strongest of the series. `groundtruth.py` is the best
> instrument this project has built — 11 injected mutations, all 11 caught;
> `--verify` re-derives every boundary from bytes; the `_limits` block explicitly
> retracts its own first draft. `spike-a-groundtruth-fa.json` was split from the
> ASR file **specifically** so no document could quote one figure from each.*
>
> ***And then three documents quoted the wrong file anyway.** That is the finding
> of this round: the author built the guardrail, wrote the warning label, and
> drove past both.*

## `J29-C1` — the word-sync figures were attributed to an artifact that says the opposite

`README:407` and `roadmap:178` stated **95.8 / 86.4 / 91.7** and *"`en` clears the
bar"*, citing `out/spike-a-groundtruth.json`. **That file does not contain those
numbers.**

| | `spike-a-groundtruth.json` — ASR only | `spike-a-groundtruth-fa.json` — FA given the TRUE text |
| --- | --- | --- |
| `en` | **8.3** | 95.8 |
| `es` | **4.5** | 86.4 |
| `fr` | **0.0** | 91.7 |
| median | 436.7 / 409.6 / 514.4 ms | 29.4 / 41.1 / 61.7 ms |
| p95 | 587.3 / 645.7 / 1307.1 ms | 79.6 / **298.9** / 233.7 ms |
| pass field | `passes_matched_bar: false` x3 | **the field is ABSENT — it emits no verdict** |

The FA file's own header reads:

> *"FA HERE IS GIVEN THE TRUE TEXT… §6.1 is `ASR -> FA -> match`, where FA
> receives the ASR TRANSCRIPT, and on this same corpus that transcript is 100% /
> 90.9% / 75.0% correct. So these figures answer 'how well can forced alignment
> place words when the words are known', which is the ceiling of the refinement
> stage and NOT an end-to-end result. **Anything quoting them as end-to-end word
> sync is quoting the wrong number, which is the failure this whole spike keeps
> repeating.**"*

`spike-a-groundtruth-fa.json` was cited **nowhere in the repository**; `8.3 / 4.5
/ 0.0` appeared **nowhere in the repository**. Three consequences: *"`en` passes"*
was unsupported — **the end-to-end quantity was never measured and lies somewhere
between floor and ceiling**; `spec:1353` entered a refinement-stage ceiling into a
**series** of end-to-end readings and nominated it for `sync_grade`; and
`README:407`'s *"all three inside the 250 ms bound at p95"* was false — `es` is
**298.9 ms** (`J29-M3`).

**Why Critical.** Blind and low-vision users are a primary population; the 250 ms
bound and the 95% bar are their contract. The repository stated that contract was
met for English and cited, as proof, a file reporting 8.3% and `false`.

*(Corrected 2026-08-09 per J30-M1: this row read "**null** — it declines to claim". The field is absent from `spike-a-groundtruth-fa.json`, not null; `grep -c passes_matched_bar` returns 0. The conclusion stands, the mechanism was invented — and it propagated from this record into three documents before anyone opened the file.)*

**What held it off Blocker:** `voice_langs` ships empty, every row `unmeasured`,
enforced by proof `S9`. **Nothing user-facing asserts sync works.**

## `J29-C2` — the secret scanner failed on this commit; the attestation was false

```
$ node .github/scripts/secret-scan.mjs
  tools/doc-check.mjs:1318  [assigned-secret-anycase]        EXIT=1
```

The line is **added by this commit**, inside the `[TREE-MARKER]` guard that repairs
`J28-M3`: `const token = body.split(/\s+/)[0] || '';`. `token` hits the name
alternation and `body.split(/\s+/` is **exactly 16 characters** — the floor.
**The `J28-M3` fix tripped the `J28-M1` fix, in one commit.** `ci.yml` runs that
command as a required job, so the commit could not go green.

> *A false positive is how scanners get allowlisted, and `ci.yml` says in its own
> words that "a scanner with no mutation test is an attestation, not a control."
> An attestation is what this was.*

The artifact itself was clean — Jury scanned the index and `--all` and found no key
material.

## `J29-C3` — the §3.5 correction was never reconciled

`CLAUDE.md:114-118`: *"the spec wins and the roadmap is defective — because the
roadmap is what gets built, **that defect is Critical, not cosmetic**."*

Five sites still carried the removed Gemini route: `CLAUDE.md:243` (**rank-1
authority, declaring a live "fallback chain" four constraints below the one
forbidding fallbacks**), `README:348`, `spec §11` (which gates all ingest and
therefore contradicted §3.5 **inside one document**), `roadmap:917` (`Adapters: …
Google/Gemini`) and `roadmap:919` (`` `ht` route per Spike B ``).

**The reconciliation pass was not run for this edit** — the revision header's
SPIKE A pass lists eight identifiers and **not one routing identifier**. Fifth
consecutive round. The correct sentence existed in exactly one file
(`CODEOWNERS:37`) and reached none of the five.

**Leg 2f does not cover the class:** it tests only a §3.5 provider head, so
`Fish s2-pro. Falls back to Gemini via OpenRouter` passes clean. **No guard
anywhere tests "a primary path names a fallback"** — constraint 2's actual content.

## Majors

`J29-M1` — `fr` **95.8/4.3** is assembled from two model configurations; `95.8` is
base, `4.3` is `small`, and no run produces the pair. **The causal story is also
refuted:** `participants.` is still in `hallucinated_tokens` in both files, so the
8.7→4.3 delta is `chaîne`, a base-vs-small recognition difference — **the matcher
fix did not do what the roadmap says it did.** *(Owner: Forge · before any
re-quote.)* · `J29-M2` — *"drift does not accumulate"* asserted from a test with no
power: slope 95% CIs reach ±0.65 to ±2.75 ms/s, spanning **tens of seconds** over a
9-hour book against a 250 ms bound; the artifact's own `_stat_note` says *"not the
same as none existing."* **H26-M7 reopened.** *(Forge · 2026-08-16.)* ·
`J29-M3` — `es` p95 298.9 ms exceeds the 250 ms bound the sentence names. *(Scribe ·
with C1.)* · `J29-M4` — the `.gitignore` fix orphaned six `tts-manifest.json` rows;
`[ART-STALE]` passes only because it reads the **disk**, so any clone gets six
MAJORs. *(Forge · 2026-08-12.)* · `J29-M5` — `fixtures.json:19` still asserts the
**withdrawn** voice lock in the present tense, two lines below edits made in this
commit. *(Forge · 2026-08-11.)* · `J29-M6` — 204 MB of `fr-long-*.wav` staged for a
withdrawn claim and a **nonexistent** artifact, in the same commit that excluded
35 MB of bit-for-bit reconstructible audio to save space. *(Forge · before commit.)*

## What Jury verified and accepted

- **The gitignore argument survives.** Jury reconstructed all six corpora from the
  committed `gt/words/` clips and compared PCM SHA-256: **six of six match.**
  Deterministic concatenation is categorically unlike non-deterministic TTS, so
  J23-M5 does not reach it. *"The exclusion stands. No finding on the ruling."*
- **The uniqueness loosening — disputed, author wins.** *"J26-M4's protected
  property requires a row to be language-total; leg 2e makes that impossible by
  construction, so leg 2e **is** strictly stronger… Correct call, correctly
  recorded."*
- **Value collisions — annotation is sufficient. No finding.** *"With grim irony,
  the single best-executed paragraph in a commit whose central defect is quoting
  one metric's number for another."*
- **8 of 8 round-28 findings fixed as specified** — *"the best repair rate in the
  series, and I want it on the record before the rest of this ruling is read."*
  `[WS-OWNED]`, which round 28 required to be green and which **had never been
  built**, exists and caught `eslint.config.mjs` on its first run.

## Minor — 6, and one Polish

**Restored 2026-08-09 (J30-M9).** This record stated the counts *"6 Minor · 1
Polish"* and carried none of them, so 7 of 16 findings existed nowhere in the
repository while `CLAUDE.md` requires a re-audit to resolve **each** prior
finding by ID. Jury raised it against its own record. Rule 5 — *"no silent
passes; the trail matters"* — is about exactly this.

- **`J29-m1`** — `bare-credential-token` holes, reproduced against the shipped
  regexes: a bare **64-char** and a bare **52-char** mixed token both MISSED
  (over the `{28,48}` cap); `ghp_` + 36 and `glpat-` + 20 both MISSED because
  the lookbehind `(?<![A-Za-z0-9_/+-])` excludes `_` and `-`; a **40-char
  lowercase+digits** run MISSED. Control (bare 32-char Lemonfox shape) caught.
  **The last one matters most:** `KEYLIKE` was explicitly widened this round to
  accept lowercase-and-digits *because one of the four real keys has no
  uppercase letter*, while `bare-credential-token` still requires `[A-Z]` — two
  rules for one property, fixed on one side. The 48-char cap is unnecessary: the
  `[a-z]`+`[A-Z]`+`\d` conjunction already excludes lowercase hex digests.
- **`J29-m2`** — `grep -c "Access\|Prism" CODEOWNERS` = **0**. The five personas
  added to `CLAUDE.md` were justified as *"CODEOWNERS referenced agents the
  roster didn't list"* — true for Arch, Vega, Touch; **false for Access and
  Prism**. Worse: `CLAUDE.md` declares *"Halo audits accessibility; Access
  builds it"* while `CODEOWNERS` still assigns `/apps/web/` and `/apps/mobile/`
  WCAG to **Halo**, with Access owning nothing anywhere. The principle is stated
  in the authority and contradicted in the file it was written for.
- **`J29-m3`** — `doc-check.mjs` `pat.slice(1).replace(/[.]/g, '\.')`: in a
  normal JS string `'\.'` **is** `'.'`, so the escape is a no-op and
  `/eslint.config.mjs` compiles with `.` as a wildcard. Separately `AUDIT_LAYER`
  is hardcoded `{Jury, Halo, Proof, Optic}` instead of harvested from
  `CLAUDE.md`'s roster, so a new audit persona silently escapes `[WS-OWNED]`
  leg (b).
- **`J29-m4`** — `[COST]`, `[TREE-MARKER]` and `loadArtifacts()` all read the
  **disk** while the commit writes the **index** — `J28-C1`'s shape surviving
  intact in the second gate. Contained only by `[STAGED]`, which is blind to
  gitignored divergence, **which is exactly how `J29-M4` hid**.
- **`J28-minor-a` (carried, open)** — the RLS class rule's `unclassifiable` leg
  still never tests `relrowsecurity`, so a correctly-protected table keyed on
  `owner_id` blocks every later migration.
- **`J28-minor-b` (carried, open)** — `relkind = 'r'` only; partitioned parents
  (`relkind='p'`) remain invisible to the class rule.

**Polish — `J29-p1`** — `README` marks `resources/` `── present`; it is
gitignored, so the claim is false in every clone. `[TREE-MARKER]` cannot catch
it because `doc-check` exits 2 in exactly the condition that would make it fire.

## Round-28 findings, resolved by ID

`J28-C1` **fixed** — reads `git show :<path>`; the attack no longer reproduces ·
`J28-M1` **fixed** as specified · `J28-M2` **fixed** (leg 2e) · `J28-M2b` (the
Gemini row) **fixed in §3.5, open everywhere else → `J29-C3`** · `J28-M3`
**fixed** · `J28-M4` **fixed**, arithmetic independently verified · `J28-M5`
**fixed** · `J28-M6` **fixed**, executed · `J28-minor-a`, `J28-minor-b`, and
*migrations unvalidated by a real Postgres* — **open**, unchanged.

## The line the author has to keep

> *The problem is no longer that the checks are weak. **It is that the prose is
> written from memory and the artifacts are consulted afterwards.** The grep in
> `CLAUDE.md:127-133` is not a documentation chore; it is the only step in this
> process that puts the artifact in front of the sentence before the sentence is
> written. It has now been skipped in five consecutive rounds, and in this one it
> would have caught two of the three Criticals.*
