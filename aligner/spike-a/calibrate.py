#!/usr/bin/env python3
"""
SPIKE A, step 4 — per-language timestamp calibration, fit and held-out scored.

faster-whisper reports word starts systematically EARLY: the start-delta and
end-delta medians against the Lemonfox reference are identical in every language
(-120/-120 en, -100/-100 es, -80/-80 fr), which is a constant offset, not a
disagreement about which audio a word occupies.

THE DISCIPLINE. The offset is fit on `fixtures.languages` and scored ONLY on
`fixtures.holdout` -- different text, same voices, audio the calibration never
saw. Fitting and scoring on one clip would choose the parameter that makes the
bar pass, which is the thing the pre-fixed drift bound and language scope exist
to prevent. If the discipline does not apply to calibration it is theatre.
"""
import json, pathlib, statistics, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import reference as R, measure as M, harness as H

ROOT = pathlib.Path(__file__).parent; OUT = ROOT / "out"
FX = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))
E = R.env()

def pairs_for(wav, lang, text):
    """
    H26-M8. Both streams are mapped onto the DISPLAY TEXT and paired by display
    index. The previous surface-form uniqueness filter is what a calibration fit
    could least afford: it dropped the short frequent words, so the offset was
    fit on long content words and then applied to every word.
    """
    ref = R.lemonfox_words(wav, E["LEMONFOX_API_KEY"], lang)
    ww, _wall, _tm = M.transcribe(wav, lang, "base", "int8", False)
    display = H.display_units(text)
    w_units = H.units_from_asr(ww, display, lang)
    r_units = H.units_from_asr(
        [{"w": x["word"], "s": float(x["start"]), "e": float(x["end"])} for x in ref],
        display, lang)
    return [(w, r) for _i, w, r in H.pair_by_display(w_units, r_units)]

def score(pairs, shift, scale=1.0):
    ov = []
    for w, r in pairs:
        d = (w["e"] - w["s"]) * scale
        s = w["s"] + shift; e = s + d
        inter = max(0.0, min(e, r["e"]) - max(s, r["s"]))
        union = max(e, r["e"]) - min(s, r["s"])
        ov.append(100.0 * inter / union if union > 0 else 0.0)
    return statistics.median(ov), 100.0 * sum(1 for o in ov if o >= 50) / len(ov)

cal = {}
print("FIT on fixtures.languages")
for lang in FX["languages"]:
    p = pairs_for(OUT / f"{lang}.wav", lang, FX["languages"][lang]["text"])
    # Grid search shift and a duration scale -- whisper words also run ~0.85x short.
    best = max(((sh, sc) + score(p, sh, sc) for sh in [i / 1000 for i in range(0, 261, 10)]
                for sc in [x / 100 for x in range(90, 156, 5)]), key=lambda t: (t[3], t[2]))
    cal[lang] = {"shift_ms": round(best[0] * 1000), "duration_scale": best[1]}
    print(f"  {lang}: shift {best[0]*1000:+.0f}ms  scale {best[1]:.2f}x  -> fit {best[3]:.0f}% (median {best[2]:.0f}%)")

print("\nSCORE on fixtures.holdout -- audio the calibration never saw")
res = []
for lang in FX["holdout"]:
    wav = OUT / f"{lang}-holdout.wav"
    if not wav.exists(): continue
    p = pairs_for(wav, lang, FX["holdout"][lang]["text"])
    m0, k0 = score(p, 0.0, 1.0)
    m1, k1 = score(p, cal[lang]["shift_ms"] / 1000, cal[lang]["duration_scale"])
    flag = "PASS" if k1 >= 95 else "BELOW BAR"
    # H26-M5 -- THE HOLDOUT CONFOUNDS THE VARIABLE IT EXISTS TO CONTROL when the
    # voice differs between fit and score. A holdout is meant to vary the TEXT
    # and hold everything else fixed; if the voice also changes, a drop in the
    # score cannot be attributed to generalisation failure rather than to the
    # voice -- and fixtures.json:19 already records a 12-point swing from voice
    # alone. Recorded per row so the reader is not left to notice it.
    fit_voice = FX["languages"][lang].get("voice")
    holdout_voice = FX["holdout"][lang].get("voice")
    print(f"  {lang} [{flag}] {len(p)}w  uncalibrated {k0:.0f}%  ->  calibrated {k1:.0f}%  (median overlap {m1:.0f}%)"
          + ("" if fit_voice == holdout_voice else f"   CONFOUNDED: fit on {fit_voice}, scored on {holdout_voice}"))
    res.append({"lang": lang, **cal[lang], "holdout_words": len(p),
                "uncalibrated_pct": round(k0, 1), "calibrated_pct": round(k1, 1),
                "median_overlap_pct": round(m1, 1), "passes_95_bar": bool(k1 >= 95),
                "fit_voice": fit_voice, "holdout_voice": holdout_voice,
                "voice_confounded": fit_voice != holdout_voice,
                "_confound_note": ("H26-M5. When fit_voice != holdout_voice the holdout varies TWO "
                                   "things at once, so it cannot separate 'the offset did not "
                                   "generalise to new text' from 'the offset did not generalise to "
                                   "this voice'. Voice is a measured word-sync variable "
                                   "(fixtures.json:19, a 12-point swing). This row is not evidence "
                                   "of generalisation.")})
H.write_json(OUT / "spike-a-calibration.json", {"calibration": cal, "holdout": res})
print("\nwrote out/spike-a-calibration.json")
