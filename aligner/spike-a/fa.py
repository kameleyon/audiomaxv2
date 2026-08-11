#!/usr/bin/env python3
"""
SPIKE A, step 5 — FORCED ALIGNMENT via torchaudio MMS_FA.

Every earlier run used faster-whisper, whose word timings come from attention
weights -- an inference about where a word probably is. Forced alignment is a
different thing: given the transcript, a wav2vec2 phoneme model is aligned to
the audio frame by frame, so a word's boundaries are located rather than
guessed.

WHAT §6.1 ACTUALLY SAYS (H26-C2). It REPUDIATES "forced alignment, not ASR" and
specifies synthesize -> transcribe -> match. Forced alignment cannot be first,
because the only transcript available before ASR is the display text, which is
§6.2's failure verbatim. This file measures FA as a REFINEMENT candidate against
an independent reference; it does not claim the spec asks for it.

WHAT ROUND 26 FOUND IN THIS FILE, and what changed.

  H26-B2, part one (fixed earlier): `romanize()` stripped digits, so `1984`,
  `3`, `47`, `52` and `1,250` were DELETED before alignment. 24 display words
  became 19, and MMS_FA was handed a transcript missing "nineteen eighty-four"
  against audio containing it, with no skip token -- so the unmatched audio was
  absorbed into neighbouring spans. That is a mechanical explanation for a
  median IoU of 57.5%, and it means the instrument was wrong for the fifth time.
  Numerals are now EXPANDED by spell(), not dropped.

  H26-B2, part two (fixed here): expanding them was not enough. The aligner
  emits `nineteen eighty four`; the Lemonfox reference emits `1984`; the
  comparison kept only tokens occurring exactly once in BOTH streams, so every
  expanded numeral was dropped at the last step anyway. The hard tokens the
  fixtures exist to test STILL never reached the score.

  H26-M8 (fixed here): that same uniqueness filter deleted every short frequent
  function word -- the hardest to place, and the ones a reader's eye is on most
  often -- while keeping long content words whose larger spans inflate overlap.
  n = 14-21 on a 24-word clip.

THE FIX FOR BOTH IS ONE FIX. Stop pairing the two streams against each other by
surface form. Map both onto the DISPLAY TEXT and pair by display index:

  * the FA side knows its display index BY CONSTRUCTION -- `tokens_for` records
    which display token each alignable token came from, so the three spans of
    "nineteen eighty four" collapse into the one span of `1984`;
  * the reference side goes through `measure.match`, the shipped monotonic
    matcher, which already bridges `1984` <-> nineteen eighty-four.

Pairing is then POSITIONAL. `the`, `de`, `a`, `les` are scored like every other
word, and a display token and its spoken expansion are one unit.
"""
import json, pathlib, re, sys, unicodedata
import torch, torchaudio
from torchaudio.pipelines import MMS_FA as B
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import reference as R
import harness as H

ROOT = pathlib.Path(__file__).parent; OUT = ROOT / "out"
FX = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))

# ── NOTHING AT IMPORT TIME SPENDS MONEY OR LOADS A MODEL ─────────────────────
# This file used to call `R.env()` and build the MMS_FA model at module scope and
# then run the whole comparison at module scope as well, so `import fa` — which
# is the only way to reach `spell()` and `romanize()` from another spike script —
# made SIX paid Lemonfox ASR calls and rewrote a committed artifact. That is not
# a style point: the owner's standing rule is one call, verified on the
# dashboard, then ask. A module that spends on import cannot obey it, and the
# author of the importing script cannot see that it will.
_MODEL = {}


def _mms():
    """MMS_FA model/tokenizer/aligner, built once, on first use."""
    if not _MODEL:
        _MODEL["model"] = B.get_model()
        _MODEL["tokenizer"] = B.get_tokenizer()
        _MODEL["aligner"] = B.get_aligner()
    return _MODEL["model"], _MODEL["tokenizer"], _MODEL["aligner"]

NUM = {"en": ["zero","one","two","three","four","five","six","seven","eight","nine",
               "ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen",
               "seventeen","eighteen","nineteen"],
       "es": ["cero","uno","dos","tres","cuatro","cinco","seis","siete","ocho","nueve",
              "diez","once","doce","trece","catorce","quince","dieciseis","diecisiete",
              "dieciocho","diecinueve"],
       "fr": ["zero","un","deux","trois","quatre","cinq","six","sept","huit","neuf",
              "dix","onze","douze","treize","quatorze","quinze","seize","dixsept",
              "dixhuit","dixneuf"]}
TENS = {"en": {2:"twenty",3:"thirty",4:"forty",5:"fifty",6:"sixty",7:"seventy",8:"eighty",9:"ninety"},
        "es": {2:"veinte",3:"treinta",4:"cuarenta",5:"cincuenta",6:"sesenta",7:"setenta",8:"ochenta",9:"noventa"},
        "fr": {2:"vingt",3:"trente",4:"quarante",5:"cinquante",6:"soixante",7:"soixantedix",8:"quatrevingt",9:"quatrevingtdix"}}


def spell(n, lang):
    """Digits -> the words a speaker says."""
    w, t = NUM[lang], TENS[lang]
    if n < 20: return [w[n]]
    if n < 100:
        return [t[n // 10]] + ([w[n % 10]] if n % 10 else [])
    if 1100 <= n <= 1999:                       # year form: nineteen eighty-four
        return spell(n // 100, lang) + (spell(n % 100, lang) if n % 100 else [])
    if n < 1000:
        return spell(n // 100, lang) + ["hundred" if lang == "en" else "cien" if lang == "es" else "cent"] \
               + (spell(n % 100, lang) if n % 100 else [])
    return spell(n // 1000, lang) + ["thousand" if lang == "en" else "mil" if lang == "es" else "mille"] \
           + (spell(n % 1000, lang) if n % 1000 else [])


def romanize(w):
    w = unicodedata.normalize("NFKD", w.lower())
    w = "".join(c for c in w if not unicodedata.combining(c))
    return re.sub(r"[^a-z']", "", w)


def tokens_for(display, lang):
    """
    Display tokens -> (alignable tokens, display index per token).

    The second return value is what makes H26-B2 fixable: it is the only record
    of which display token an expanded numeral came from, and without it the
    three spans of "nineteen eighty four" can never be collapsed back onto the
    one display token `1984` that a highlight has to cover.
    """
    toks, owner = [], []
    for i, (tok, _cs, _ce) in enumerate(display):
        digits = re.sub(r"[^0-9]", "", tok)
        if digits and not romanize(tok):
            try:
                for part in spell(int(digits), lang):
                    toks.append(part); owner.append(i)
                continue
            except Exception:
                pass
        r = romanize(tok)
        if r:
            toks.append(r); owner.append(i)
    return toks, owner


def fa_words(wav, display, lang):
    model, tokenizer, aligner = _mms()
    wf, sr = torchaudio.load(str(wav))
    if wf.shape[0] > 1: wf = wf.mean(0, keepdim=True)
    if sr != B.sample_rate:
        wf = torchaudio.functional.resample(wf, sr, B.sample_rate)
    words, owner = tokens_for(display, lang)
    with torch.inference_mode():
        emission, _ = model(wf)
        spans = aligner(emission[0], tokenizer(words))
    ratio = wf.shape[1] / emission.shape[1] / B.sample_rate
    out = [{"w": w, "s": sp[0].start * ratio, "e": sp[-1].end * ratio}
           for w, sp in zip(words, spans)]
    return out, owner


def main() -> int:
    E = R.env()
    print(f"{'grp':<10}{'lang':<5}{'n':>4}{'cov':>6}{'median IoU':>12}{'>=50%':>8}{'abs':>8}{'signed':>9}")
    res = []
    for group, suf in (("languages", ""), ("holdout", "-holdout")):
        for lang, spec in FX[group].items():
            wav = OUT / f"{lang}{suf}.wav"
            if not wav.exists(): continue
            display = H.display_units(spec["text"])
            try:
                W, owner = fa_words(wav, display, lang)
            except Exception as e:
                print(f"{group:<10}{lang:<5}  {type(e).__name__}: {str(e)[:70]}"); continue
            fa_units = H.units_from_expansion(W, owner)
            ref = R.lemonfox_words(wav, E["LEMONFOX_API_KEY"], lang)
            ref_units = H.units_from_asr(
                [{"w": x["word"], "s": float(x["start"]), "e": float(x["end"])} for x in ref],
                display, lang)
            pairs = H.pair_by_display(fa_units, ref_units)
            if not pairs:
                print(f"{group:<10}{lang:<5}   no comparable tokens"); continue
            sc = H.score_pairs(pairs, display)
            # COVERAGE is now a reported number, not a silent filter. The old
            # uniqueness rule dropped 8-10 of 24 words and said nothing; anything
            # this comparison still cannot pair is named below.
            cov = 100.0 * len(pairs) / len(display)
            unpaired = [display[i][0] for i in range(len(display))
                        if i not in fa_units or i not in ref_units]
            hard = H.hard_token_report(spec, display,
                                       {i: {"via_normalizer": ref_units[i]["via_normalizer"],
                                            "obs": ref_units[i]["obs"]} for i, _, _ in pairs}, lang)
            print(f"{group:<10}{lang:<5}{sc['words']:>4}{cov:>5.0f}%{sc['median_overlap_pct']:>11.0f}%"
                  f"{sc['pct_overlap_50']:>7.0f}%{sc['median_abs_error_ms']:>7.0f}ms"
                  f"{sc['median_signed_start_delta_ms']:>+8.0f}ms")
            res.append({"group": group, "lang": lang, **sc,
                        "display_words": len(display),
                        "display_coverage_pct": round(cov, 1),
                        "unpaired_display": unpaired,
                        "expect_hard": hard,
                        "engine": "torchaudio MMS_FA forced alignment",
                        "reference": "lemonfox-asr",
                        "calibration": "none",
                        "_pairing": ("positional on DISPLAY TOKEN INDEX. FA tokens are grouped back "
                                     "onto the display token that produced them (so `1984` and "
                                     "`nineteen eighty four` are ONE unit); the reference stream is "
                                     "mapped onto display tokens by measure.match. No surface-form "
                                     "uniqueness filter, so function words are retained (H26-B2, H26-M8)."),
                        "_error_basis": ("median_abs_error_ms / p95_abs_error_ms are ENGINE DISAGREEMENT "
                                         "against Lemonfox ASR word timestamps, NOT error against human "
                                         "ground truth. Two mechanisms with uncorrelated error models "
                                         "agreeing bounds the common error; it does not measure it.")})
    H.write_json(OUT / "spike-a-forced-alignment.json", res)
    print("\nwrote out/spike-a-forced-alignment.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
