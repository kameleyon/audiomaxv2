#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPIKE C — does Fish Audio bill UTF-8 BYTES or CHARACTERS?

WHY THIS IS NOT ACADEMIC
------------------------
`CLAUDE.md` constraint 4: credits are denominated in CHARACTERS, every render is
preflighted with an EXACT quote. If Fish bills UTF-8 bytes, then every accented
Spanish and French character costs 2 bytes, and every `es`/`fr` quote computed
from a character count is UNDERSTATED — silently, and only for the two
non-English languages in scope. A quote that is wrong only for the languages the
reader cannot check is not a rounding error; it makes the pre-payment number a
false statement.

Spec §5 already prices Fish at "$0.015 / 1k (bytes)" and marks it **Tier C**; §5
also says `display_byte_count` / `spoken_bytes` "are not cemented until Fish
byte-billing is confirmed by a real billed call". This is that call. (Cited by
quotation, not by line number, per `CLAUDE.md`: a peer reflows the file you are
citing while you cite it.)

HOW THE ANSWER IS READ — BALANCE DELTA, NOT A GUESS
---------------------------------------------------
`POST /v1/tts` returns audio. It does NOT return a usage object, and no billing
header is documented — every response header is captured verbatim under
`response.headers` in artifact.json, so the claim "it reports nothing" is
checkable rather than asserted. So usage is read from the account instead:

    GET /wallet/self/api-credit   ->  {"credit": "<decimal string>", ...}

`credit` is a DECIMAL STRING, not a float, so the balance is exact. Reading it
before and after one TTS call gives the billed amount to full precision. That is
an observation of the vendor's own ledger, which is the strongest evidence
available without a dashboard screenshot — and it is reproducible, which a
screenshot is not.

Three hypotheses are scored, not two, because "neither" is a real outcome:

    H_chars   cost == len(text)                 * $15 / 1_000_000
    H_bytes   cost == len(text.encode("utf-8")) * $15 / 1_000_000
    H_seconds cost == audio_seconds             * (some per-second rate)

H_seconds is included because a delta matching NEITHER count would otherwise be
reported as "inconclusive" when it is actually a third billing model. The probe
text is built so all three predictions are far apart.

COST DISCIPLINE (owner's standing rule)
---------------------------------------
`--plan` and `--balance` make NO billed call. `--run` makes EXACTLY ONE and
stops. `--run` refuses to send text whose worst-case cost exceeds --budget
(default $0.05). Read the dashboard before anything is scaled.

KEY ROTATION
------------
The four provider keys were rotated on 2026-08-10. `--balance` is a free GET and
is the auth check: if it 401s, the key on disk is stale, and the correct action
is to STOP and report — not to retry and not to hunt for a key elsewhere.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal

ROOT = pathlib.Path(__file__).parent
REPO = ROOT.parent.parent

API = "https://api.fish.audio"
MODEL = "s2-pro"                                    # spec §3.5 / §5 — the es+fr voice
FR_REFERENCE_ID = "a5d7dcbb81b4472ea0e240af3edaae7d"  # "Robert", fr; proven in SPIKE A

# docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits, read
# 2026-08-10: "TTS pricing is based on the size of input text, measured in
# millions of UTF-8 bytes." s2-pro: "$15.00 / M UTF-8 bytes". The published
# figure is what the probe TESTS, not what it assumes — a rate card in the
# sibling project carried `fish_audio_tts: per_1k_chars: 0.10` and a helper
# literally named `ttsCharsCostUsd`, i.e. the same vendor documented twice with
# two different billing UNITS and a 6.7x rate error. Documentation is a
# hypothesis until the ledger agrees with it.
USD_PER_UNIT = Decimal("15") / Decimal("1000000")

# ── the probe text ────────────────────────────────────────────────────────────
# Accent-dense French. Every word carries at least one 2-byte character, so
# bytes/chars = 1.3409 at the 600-byte default, against 1.028 measured on ordinary
# French prose (`probe.py impact`) — a divergence ~12x larger than production text
# would give, which is the whole point: at the natural ratio a 2.8% gap sits
# inside the noise of any rounding the vendor might do, and would not identify
# the unit even if the ledger were read perfectly.
#
# Letters and separators only. No digits, no abbreviations, no symbols, so the
# provider's own text normalization (`normalize: true`, the production request
# shape) is a NO-OP on it. That removes the confound of "billed on the raw text
# or on the normalized text?" without having to change the request shape away
# from what production will send.
DENSE_FR_WORDS = [
    "Été", "âgé", "ôté", "créée", "âgée",
    "aînée", "réélue", "élevée", "hébétée",
    "étêtée", "écrémée", "ôtée",
    "préférée", "dégénérée", "éphémère",
    "désespérée", "élève", "élégante", "œuvre",
    "répétée", "célébrée", "éprouvée",
    "assiégée", "déléguée",
]


def probe_text(target_bytes: int) -> str:
    """
    Deterministic: cycle the word pool until the UTF-8 size reaches the target,
    then close with a period. No RNG, so the SHA-256 in the artifact identifies
    exactly one string and a re-run reproduces it byte for byte.
    """
    out: list[str] = []
    size = 0
    i = 0
    while size < target_bytes - 1:
        w = DENSE_FR_WORDS[i % len(DENSE_FR_WORDS)]
        i += 1
        add = len(w.encode("utf-8")) + (1 if out else 0)
        if size + add > target_bytes - 1:
            break
        out.append(w)
        size += add
    return " ".join(out) + "."


def counts(text: str) -> dict:
    b = text.encode("utf-8")
    return {
        "chars_sent": len(text),
        "utf8_bytes_sent": len(b),
        "non_ascii_chars": sum(1 for c in text if ord(c) > 127),
        "bytes_per_char": float(round(Decimal(len(b)) / Decimal(len(text)), 4)),
        "sha256_text_utf8": hashlib.sha256(b).hexdigest(),
    }


def predictions(text: str) -> dict:
    c = counts(text)
    return {
        "usd_if_billed_per_char": str((Decimal(c["chars_sent"]) * USD_PER_UNIT).quantize(Decimal("0.000001"))),
        "usd_if_billed_per_utf8_byte": str((Decimal(c["utf8_bytes_sent"]) * USD_PER_UNIT).quantize(Decimal("0.000001"))),
    }


# ── env ───────────────────────────────────────────────────────────────────────
def fish_key() -> str:
    """Repo-root .env. The value is never printed and never enters the artifact."""
    p = REPO / ".env"
    if not p.exists():
        sys.exit("no .env at repo root -- SPIKE C needs FISH_AUDIO_API_KEY")
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("FISH_AUDIO_API_KEY=") :
            v = line.split("=", 1)[1].strip()
            if v:
                return v
    sys.exit("FISH_AUDIO_API_KEY missing or empty in .env")


# ── HTTP ──────────────────────────────────────────────────────────────────────
def _wallet(key: str, leaf: str) -> dict:
    """FREE. No billed units."""
    req = urllib.request.Request(
        f"{API}/wallet/self/{leaf}",
        headers={"Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def get_credit(key: str) -> dict:
    """
    FREE. Doubles as the post-rotation auth check.

    `credit` arrives as a STRING and is kept as a string / Decimal all the way
    through. Parsing money as a float is how a 6-decimal delta becomes 0.0.
    """
    return _wallet(key, "api-credit")


def get_package(key: str) -> dict:
    """
    FREE. The OTHER wallet ledger — the monthly subscription quota.

    Read because "the balance did not move" has two explanations and only one of
    them is a billing model: the call may have drawn on package quota instead of
    API credit. Snapshotting both settles which ledger the API debits, and its
    `updated_at` dates the movement independently of our own polling.
    """
    return _wallet(key, "package")


# The package payload carries the owner's Stripe subscription and price IDs and
# the Fish user/team IDs. NONE of that is evidence for a billing-unit question,
# and this artifact is committed and CI-secret-scanned. Only the four fields that
# carry the argument survive: the quota did not move, and its `updated_at` is
# three weeks stale, so the TTS call was NOT debited against the subscription.
PACKAGE_KEEP = ("type", "total", "balance", "extra_balance", "updated_at", "billing_period")


def redact_package(pkg: dict) -> dict:
    out = {k: pkg.get(k) for k in PACKAGE_KEEP}
    out["_redacted"] = "stripe_subscription_id, stripe_price_id, user_id, team_id, _id"
    return out


def tts(text: str, key: str) -> tuple[bytes, dict, int]:
    """
    ONE billed call, in the production request shape (spike-a `tts.synth_fish`).
    Returns (audio, response headers verbatim, status).
    """
    req = urllib.request.Request(
        f"{API}/v1/tts",
        data=json.dumps({
            "text": text, "reference_id": FR_REFERENCE_ID, "format": "wav",
            "sample_rate": 44100, "normalize": True,
            "prosody": {"speed": 1, "normalize_loudness": True},
            "temperature": 0.8, "top_p": 0.8, "latency": "normal",
        }).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "model": MODEL},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read(), dict(r.headers.items()), r.status


def wav_seconds(raw: bytes) -> float:
    """
    Duration from the ACTUAL data size, never from the declared chunk size.

    SPIKE A finding H26-m1: Fish `s2-pro` streams, so the data-chunk length it
    emits is the sentinel 0xFFFFFFFC -- 48,695 seconds for a ten-second clip.
    Trusting the header here would make the per-second hypothesis unfalsifiable.
    """
    import struct
    if raw[:4] != b"RIFF":
        return 0.0
    pos, rate, ba, data = 12, 0, 0, 0
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        (sz,) = struct.unpack("<I", raw[pos + 4:pos + 8])
        if cid == b"fmt ":
            _, ch, rate, _, ba, _ = struct.unpack("<HHIIHH", raw[pos + 8:pos + 24])
        elif cid == b"data":
            data = len(raw) - (pos + 8)          # measured, not declared
            break
        if sz in (0xFFFFFFFF, 0xFFFFFFFC) or sz == 0:
            break
        pos += 8 + sz + (sz & 1)
    return data / (rate * ba) if rate and ba else 0.0


# ── commands ──────────────────────────────────────────────────────────────────
def cmd_plan(args) -> None:
    """No network. What would be sent, and what each hypothesis predicts."""
    t = probe_text(args.bytes)
    c, p = counts(t), predictions(t)
    print(f"  text        : {c['chars_sent']} chars / {c['utf8_bytes_sent']} UTF-8 bytes "
          f"(ratio {c['bytes_per_char']}, {c['non_ascii_chars']} non-ASCII)")
    print(f"  sha256      : {c['sha256_text_utf8']}")
    print(f"  if per-char : ${p['usd_if_billed_per_char']}")
    print(f"  if per-byte : ${p['usd_if_billed_per_utf8_byte']}")
    print(f"  worst case  : ${p['usd_if_billed_per_utf8_byte']}  (budget ${args.budget})")
    print(f"\n{t[:160]}...")


def cmd_balance(args) -> None:
    """FREE. Auth check + the precision of the ledger we are about to read."""
    try:
        j = get_credit(fish_key())
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "replace")
        print(f"  HTTP {e.code} from GET /wallet/self/api-credit -- {body}")
        print("\n  STOP. The key on disk is stale or revoked (rotated 2026-08-10).")
        print("  Do not retry and do not look for a key elsewhere. Report this.")
        sys.exit(2)
    cred = j.get("credit")
    dp = len(str(cred).split(".")[1]) if "." in str(cred) else 0
    print(f"  auth OK. credit = {cred!r} ({type(cred).__name__}, {dp} decimal places)")
    print(f"  smallest resolvable delta: {Decimal(1).scaleb(-dp) if dp else Decimal(1)}")
    print(f"  free_credit={j.get('has_free_credit')}  cumulative_top_up={j.get('cumulative_top_up')}")


def cmd_run(args) -> None:
    """EXACTLY ONE billed call, bracketed by two free balance reads."""
    text = probe_text(args.bytes)
    pred = predictions(text)
    worst = Decimal(pred["usd_if_billed_per_utf8_byte"])
    if worst > Decimal(str(args.budget)):
        sys.exit(f"REFUSED: worst-case ${worst} exceeds --budget ${args.budget}. "
                 f"Lower --bytes or raise the budget deliberately.")

    art = ROOT / "artifact.json"
    if art.exists() and not args.again:
        sys.exit(f"{art.name} already exists -- this spike is ONE call. "
                 f"--again only after the dashboard has been read.")

    key = fish_key()
    print("  reading balance (free)...")
    before = get_credit(key)
    print(f"    credit before: {before['credit']}")

    print(f"  ONE billed TTS call: {counts(text)['utf8_bytes_sent']} bytes / "
          f"{counts(text)['chars_sent']} chars, model {MODEL}...")
    t0 = time.time()
    audio, headers, status = tts(text, key)
    elapsed = round(time.time() - t0, 1)
    secs = wav_seconds(audio)
    # The audio is NOT the evidence here -- the ledger delta is -- and it is 2.1 MB
    # of accent-drill word salad. It is hashed so the call's output is anchored and
    # `--keep-audio` reproduces it, but it is not committed by default. SPIKE A
    # commits its wavs because there the audio IS the measurement; here it is a
    # by-product.
    audio_sha = hashlib.sha256(audio).hexdigest()
    if args.keep_audio:
        (ROOT / "probe.wav").write_bytes(audio)
    print(f"    {len(audio)} bytes of audio / {secs:.2f}s in {elapsed}s (HTTP {status})")

    # MEASURED, not assumed: the ledger is eventually consistent and settles
    # roughly a MINUTE after the call, not immediately. The first run of this
    # probe polled for 10 seconds, saw no movement, and reported
    # INCONCLUSIVE_NO_LEDGER_MOVEMENT for a call that was in fact billed 62
    # seconds later. A short poll does not read "free"; it reads "not yet".
    after, settled_after = before, None
    deadline = time.time() + args.settle
    while time.time() < deadline:
        time.sleep(10)
        after = get_credit(key)
        if Decimal(after["credit"]) != Decimal(before["credit"]):
            settled_after = round(time.time() - t0, 1)
            break
    delta = Decimal(before["credit"]) - Decimal(after["credit"])
    print(f"    credit after : {after['credit']}   delta = {delta}"
          f"{f'  (settled ~{settled_after}s after the call)' if settled_after else ''}")

    pkg_after = redact_package(get_package(key))
    verdict = judge(text, delta, secs)
    rec = {
        "spike": "C", "question": "Does Fish Audio bill UTF-8 bytes or characters?",
        "date": time.strftime("%Y-%m-%d"), "model": MODEL,
        "reference_id": FR_REFERENCE_ID, "lang": "fr",
        "published_rate": "$15.00 / M UTF-8 bytes (docs.fish.audio, read 2026-08-10)",
        "text_sent": text,
        **counts(text),
        **pred,
        "request": {"endpoint": f"{API}/v1/tts", "method": "POST", "model_header": MODEL,
                    "normalize": True, "format": "wav", "sample_rate": 44100},
        "response": {"http_status": status, "audio_bytes": len(audio),
                     "audio_sha256": audio_sha, "audio_kept_on_disk": bool(args.keep_audio),
                     "audio_seconds": round(secs, 3), "elapsed_seconds": elapsed,
                     "headers": headers,
                     "reports_usage": any(k.lower().replace("-", "_") in
                                          ("x_usage", "x_billed_bytes", "x_credits_used", "usage")
                                          for k in headers)},
        "ledger": {"endpoint": f"{API}/wallet/self/api-credit",
                   "credit_before": before["credit"], "credit_after": after["credit"],
                   "credit_decimal_places": len(str(before["credit"]).split(".")[1])
                                            if "." in str(before["credit"]) else 0,
                   "ledger_updated_at": after.get("updated_at"),
                   "settled_seconds_after_call": settled_after,
                   "usd_charged": str(delta)},
        "package_ledger_after": pkg_after,
        **verdict,
    }
    art.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  VERDICT: {verdict['verdict']}")
    print(f"  {verdict['reasoning']}")
    print(f"\n  wrote {art}")
    print("  ONE call made. Read the Fish dashboard before any second call.")


# Spec §5's reference book, so the impact figure is comparable with the cost
# table it corrects rather than being a new unit nobody else uses.
REFERENCE_BOOK_CHARS = 540000


def cmd_impact(args) -> None:
    """
    NO NETWORK, NO COST. Turns the verdict into the number the quote contract
    actually needs: how far a CHARACTER-denominated quote falls short of the
    BYTE-denominated invoice, per language, on real prose.

    The corpus is SPIKE A's committed fixtures rather than a second copy of the
    same sentences living here. Duplicated prose is duplicated fact, and the
    documents in this repo have been burned four times by a fact updated in one
    of its homes; the fixture SHA-256 is recorded so the reading is pinned even
    though the file is read live.

    Why this matters more than the ratio of the probe text: the probe was
    ENGINEERED for divergence (ratio 1.34). Production text is not. Quoting the
    engineered ratio as the business impact would overstate it by ~10x, which is
    the same mistake, in the same direction, as the one this command corrects.
    """
    fx = ROOT.parent / "spike-a" / "fixtures.json"
    if not fx.exists():
        sys.exit(f"no corpus at {fx} -- cannot measure production accent load")
    raw = fx.read_bytes()
    data = json.loads(raw.decode("utf-8"))

    per: dict[str, list[int]] = {}
    for group in ("languages", "holdout", "paragraph"):
        for lang, v in (data.get(group) or {}).items():
            t = v.get("text", "")
            per.setdefault(lang, [0, 0])
            per[lang][0] += len(t)
            per[lang][1] += len(t.encode("utf-8"))

    rate_per_byte = Decimal("0.015") / 1000
    rows = {}
    print(f"  corpus: {fx.name} sha256 {hashlib.sha256(raw).hexdigest()[:16]}…\n")
    print(f"  {'lang':<6}{'chars':>8}{'bytes':>8}{'ratio':>9}{'understated':>13}"
          f"{'quoted':>10}{'invoiced':>10}{'shortfall':>11}")
    for lang, (c, b) in sorted(per.items()):
        ratio = Decimal(b) / Decimal(c)
        quoted = (Decimal(REFERENCE_BOOK_CHARS) * rate_per_byte).quantize(Decimal("0.01"))
        billed = (Decimal(REFERENCE_BOOK_CHARS) * ratio * rate_per_byte).quantize(Decimal("0.01"))
        rows[lang] = {
            "corpus_chars": c, "corpus_utf8_bytes": b,
            "bytes_per_char": float(round(ratio, 4)),
            "quote_understated_pct": float(round((ratio - 1) * 100, 2)),
            "reference_book_quoted_usd_if_chars": str(quoted),
            "reference_book_invoiced_usd_bytes": str(billed),
            "shortfall_usd": str(billed - quoted),
        }
        print(f"  {lang:<6}{c:>8}{b:>8}{float(ratio):>9.4f}"
              f"{float((ratio - 1) * 100):>12.2f}%{'$' + str(quoted):>10}"
              f"{'$' + str(billed):>10}{'$' + str(billed - quoted):>11}")

    # UPPER BOUND for a real book, not for engineered text. The fixture prose uses
    # ASCII punctuation; a French EPUB does not. Curly apostrophes (U+2019) are 3
    # bytes and French elides constantly (l', d', qu', s'), guillemets are 2, and
    # the narrow no-break space French typography REQUIRES before ; : ! ? is 3.
    # None of those are accents, so an accent-only estimate misses them entirely.
    fr_src = ((data.get("paragraph") or {}).get("fr") or {}).get("text", "")
    typo = (fr_src.replace("'", "’").replace("...", "…")
            .replace(" ;", " ;").replace(" :", " :")
            .replace(" !", " !").replace(" ?", " ?").replace(" - ", " — "))
    upper = None
    if fr_src:
        r_plain = Decimal(len(fr_src.encode("utf-8"))) / Decimal(len(fr_src))
        r_typo = Decimal(len(typo.encode("utf-8"))) / Decimal(len(typo))
        upper = {
            "fr_plain_ascii_punctuation_ratio": float(round(r_plain, 4)),
            "fr_epub_typography_ratio": float(round(r_typo, 4)),
            "fr_epub_understated_pct": float(round((r_typo - 1) * 100, 2)),
            "transform": "U+2019 apostrophe, U+2026 ellipsis, U+202F before ; : ! ?, U+2014 dash",
        }
        print(f"\n  fr upper bound with real EPUB typography: ratio {float(r_typo):.4f} "
              f"(+{float((r_typo - 1) * 100):.2f}%) vs plain {float(r_plain):.4f}")

    art = ROOT / "artifact.json"
    if art.exists():
        rec = json.loads(art.read_text(encoding="utf-8"))
        rec["production_impact"] = {
            "fr_typography_upper_bound": upper,
            "corpus": f"aligner/spike-a/{fx.name}",
            "corpus_sha256": hashlib.sha256(raw).hexdigest(),
            "reference_book_chars": REFERENCE_BOOK_CHARS,
            "fish_usd_per_1k_utf8_bytes": "0.015",
            "note": ("Accent load on REAL prose. The probe text was engineered to a ratio "
                     "of 1.34 to make the billing unit unmistakable; production es/fr text "
                     "sits near 1.03. Both numbers are true and they answer different "
                     "questions -- the first identifies the unit, the second sizes the money."),
            "by_language": rows,
        }
        rec["finding"] = FINDING
        art.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  merged into {art.name}")


FINDING = (
    "VERDICT: Fish Audio bills UTF-8 BYTES, not characters. Confirmed by one billed "
    "call on 590 UTF-8 bytes / 440 characters of accented French: the account ledger "
    "(GET /wallet/self/api-credit) moved 16.521720 -> 16.512870, a charge of $0.008850. "
    "590 bytes x $15/1M = $0.008850 exactly, residual $0.000000. The character model "
    "predicts $0.006600 and is wrong by 34%. The published rate "
    "($15.00 / M UTF-8 bytes, docs.fish.audio) is therefore confirmed in BOTH the unit "
    "and the magnitude, and spec 5's '$0.015 / 1k (bytes)' is correct as written. "
    "Tier C can be retired for this row.\n\n"
    "MECHANISM NOTES. POST /v1/tts reports no usage: not in the body (it returns raw "
    "audio) and not in any response header (all 16 captured verbatim in this artifact; "
    "there is no x-usage, no credit header, nothing). Usage is observable ONLY as a "
    "balance delta on the wallet endpoint, and that delta posts roughly ONE MINUTE "
    "after the call -- the first read of this probe polled for 10 seconds, saw no "
    "movement, and would have reported the call as free. Any future cost telemetry "
    "must poll the wallet ledger asynchronously; it cannot read cost off the TTS "
    "response, and it must not treat an unsettled ledger as a zero charge. The debit "
    "landed on api-credit, not on the subscription package (package updated_at was "
    "unchanged at 2026-07-20), so API usage is pay-as-you-go and independent of the "
    "monthly plan quota.\n\n"
    "CONSEQUENCE FOR THE QUOTE CONTRACT (CLAUDE.md constraint 4). Credits are "
    "denominated in characters and every render is preflighted with an EXACT quote. "
    "A character-denominated quote for a Fish render is understated for es and fr and "
    "exact for en -- the error appears only in the two non-English languages, which is "
    "the population least able to notice it. On real prose the understatement is +2.4% "
    "(es) and +2.8% (fr), rising to +4.3% for French with genuine EPUB typography "
    "(curly apostrophes, guillemets, em dashes and narrow no-break spaces are 2-3 bytes "
    "each). The fix is not to redenominate credits: keep characters as the user-facing "
    "unit, and compute the COST side of the quote from spoken_bytes. spoken_bytes "
    "already appears in the GET /quote payload alongside \"display_characters\", "
    "\"spoken_characters\" and \"inserted_characters\" -- this spike cements it as "
    "REQUIRED for any Fish-routed segment, not optional.\n\n"
    "SECOND FINDING, opposite direction, and it is a Major. Spec 5's cost table "
    "reads \"$8.10 floor; $16-32 for accented fr\", and audit finding J-m3 says "
    "\"accented Latin is 2-4x under byte billing\". That is wrong by an order of "
    "magnitude. 2-4x requires text that is 100-300% non-ASCII; French and Spanish "
    "prose measure 1.028 and 1.024 bytes per character, and even French with full "
    "EPUB typography reaches only 1.043. The reference book costs $8.33 in French, "
    "not $16-32. The byte penalty is real, it is small, and the cost model "
    "currently overstates the worst case by ~4x while the quote understates the "
    "actual charge by ~3% -- two errors in opposite directions, which is why "
    "neither cancelled out or got noticed."
)


def cmd_reconcile(args) -> None:
    """
    ZERO BILLED CALLS. Re-reads the two wallet ledgers and re-judges the call
    already recorded in artifact.json against its own `credit_before`.

    This exists because the billed call is not repeatable at will — it costs
    money and the owner's rule is one call, then verify. When the first read
    lands before the vendor's ledger settles, the fix is to re-read the ledger,
    NOT to re-run the call. The text, the counts, and `credit_before` are all
    already pinned in the artifact, so the delta this recomputes is the delta of
    the original call.
    """
    art = ROOT / "artifact.json"
    if not art.exists():
        sys.exit("no artifact.json -- run `probe.py run` first.")
    rec = json.loads(art.read_text(encoding="utf-8"))
    key = fish_key()
    now, pkg = get_credit(key), get_package(key)

    before = Decimal(rec["ledger"]["credit_before"])
    delta = before - Decimal(now["credit"])
    print(f"  credit before (recorded): {before}")
    print(f"  credit now    (re-read) : {now['credit']}   delta = {delta}")
    print(f"  ledger updated_at       : {now.get('updated_at')}")
    print(f"  package balance         : {pkg.get('balance')}/{pkg.get('total')} "
          f"(updated_at {pkg.get('updated_at')})")

    rec["ledger"]["credit_after"] = now["credit"]
    rec["ledger"]["ledger_updated_at"] = now.get("updated_at")
    rec["ledger"]["usd_charged"] = str(delta)
    rec["ledger"]["read_method"] = (
        "re-read after settlement; the debit posts ~1 min after the call, so the "
        "in-run 10 s poll saw an unsettled ledger")
    rec["package_ledger_after"] = redact_package(pkg)
    rec["reconciled_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec["billed_calls_total"] = 1
    rec.update(judge(rec["text_sent"], delta, rec["response"]["audio_seconds"]))
    art.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n  VERDICT: {rec['verdict']}")
    print(f"  {rec['reasoning']}")
    print(f"\n  updated {art}  (no billed call was made)")


def judge(text: str, delta: Decimal, secs: float) -> dict:
    """
    Score the three hypotheses against the observed delta. Named explicitly so
    the verdict is arithmetic, not an impression.
    """
    c = counts(text)
    pc = Decimal(c["chars_sent"]) * USD_PER_UNIT
    pb = Decimal(c["utf8_bytes_sent"]) * USD_PER_UNIT
    if delta == 0:
        return {"verdict": "INCONCLUSIVE_NO_LEDGER_MOVEMENT",
                "reasoning": "The balance did not move. Either the account draws on a "
                             "subscription package rather than API credit, or the ledger "
                             "settles later than this probe waits. Re-read the dashboard "
                             "before drawing any conclusion; do NOT conclude the call was free.",
                "residual_vs_char_model": str(pc), "residual_vs_byte_model": str(pb)}
    rc, rb = abs(delta - pc), abs(delta - pb)
    tol = pb * Decimal("0.02")
    if rb <= tol and rb < rc:
        v, why = "UTF8_BYTES", (
            f"Charged ${delta}. The UTF-8-byte model predicts ${pb.quantize(Decimal('0.000001'))} "
            f"(residual ${rb}); the character model predicts ${pc.quantize(Decimal('0.000001'))} "
            f"(residual ${rc}). Billing is per UTF-8 byte. Every quote for es/fr computed "
            f"from a character count is UNDERSTATED by the accent load of the text.")
    elif rc <= tol and rc < rb:
        v, why = "CHARACTERS", (
            f"Charged ${delta}, matching the character model ${pc.quantize(Decimal('0.000001'))} "
            f"(residual ${rc}) and not the byte model ${pb.quantize(Decimal('0.000001'))} "
            f"(residual ${rb}). Character-denominated credits quote es/fr correctly.")
    else:
        v, why = "NEITHER", (
            f"Charged ${delta}. Neither model fits: chars predict "
            f"${pc.quantize(Decimal('0.000001'))} (residual ${rc}), bytes predict "
            f"${pb.quantize(Decimal('0.000001'))} (residual ${rb}). "
            f"Implied per-second rate over {secs:.2f}s of audio: "
            f"${(delta / Decimal(str(secs))).quantize(Decimal('0.000001')) if secs else 'n/a'}/s. "
            f"A third billing model is in play and the schema must not be cemented on either count.")
    return {"verdict": v, "reasoning": why,
            "residual_vs_char_model": str(rc), "residual_vs_byte_model": str(rb),
            "implied_usd_per_audio_second": str((delta / Decimal(str(secs))).quantize(Decimal("0.000001")))
                                            if secs else None}


def main() -> None:
    ap = argparse.ArgumentParser(description="SPIKE C -- Fish Audio billing unit")
    ap.add_argument("--bytes", type=int, default=2000, help="target UTF-8 size of the probe text")
    ap.add_argument("--budget", type=float, default=0.05, help="hard worst-case USD ceiling")
    ap.add_argument("--settle", type=int, default=240,
                    help="SECONDS to wait for the ledger to settle (it posts ~1 min late)")
    ap.add_argument("--again", action="store_true", help="overwrite artifact.json (second call -- ASK FIRST)")
    sub = ap.add_subparsers(dest="cmd")
    for name, fn in (("plan", cmd_plan), ("balance", cmd_balance),
                     ("run", cmd_run), ("reconcile", cmd_reconcile), ("impact", cmd_impact)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        p.add_argument("--bytes", type=int, default=600)
        p.add_argument("--budget", type=float, default=0.05)
        p.add_argument("--settle", type=int, default=240)
        p.add_argument("--again", action="store_true")
        p.add_argument("--keep-audio", action="store_true",
                       help="write probe.wav (2 MB, not evidence -- hashed either way)")
    a = ap.parse_args()
    if not getattr(a, "fn", None):
        ap.print_help()
        sys.exit(1)
    a.fn(a)


if __name__ == "__main__":
    main()
