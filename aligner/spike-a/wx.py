#!/usr/bin/env python3
"""
SPIKE A, step 5b — WhisperX, the deliverable the roadmap names.

WhisperX runs a wav2vec2 phoneme model over the audio and force-aligns the
Whisper transcript to it, rather than reading word times off attention weights.
`fa.py` measures the same mechanism through torchaudio's MMS_FA; this file
measures the named tool, so the roadmap item can be answered rather than
substituted.

H26-m2 — WHY THIS FILE IS DIFFERENT NOW. `out/spike-a-whisperx.json` was `[]`.
The script caught every exception, printed it to a terminal nobody kept, and
wrote an empty array — so the artifact for the named deliverable recorded
neither a result nor a failure, and no document said WhisperX had not run. An
empty array is indistinguishable from "measured nothing to report".

The artifact is now a RECORD OF THE RUN: it always states whether the engine
executed, and when it did not, why, with the exception text. A tool that cannot
run must say so in the file a reader will open, not in a console.

Pairing is display-anchored (harness.py), the same as fa.py and reference.py --
H26-M8: the surface-form uniqueness filter these three files each implemented
separately deleted the function words and every numeral.
"""
import json, pathlib, sys, traceback, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import reference as R
import harness as H

ROOT = pathlib.Path(__file__).parent; OUT = ROOT / "out"
FX = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))
E = R.env()


def wx_words(wav, lang):
    import whisperx
    m = whisperx.load_model("base", "cpu", compute_type="int8", language=lang)
    audio = whisperx.load_audio(str(wav))
    tr = m.transcribe(audio, batch_size=4, language=lang)
    am, meta = whisperx.load_align_model(language_code=lang, device="cpu")
    al = whisperx.align(tr["segments"], am, meta, audio, "cpu", return_char_alignments=False)
    out = []
    for seg in al["segments"]:
        for w in seg.get("words", []):
            if "start" in w and "end" in w:
                out.append({"w": w["word"], "s": float(w["start"]), "e": float(w["end"])})
    if not out:
        raise RuntimeError("whisperx returned no word timestamps")
    return out


def versions():
    v = {}
    for mod in ("whisperx", "transformers", "torch", "torchaudio", "numpy", "faster_whisper"):
        try:
            v[mod] = __import__(mod).__version__
        except Exception as e:
            v[mod] = f"unavailable: {type(e).__name__}"
    return v


record = {"engine": "whisperx-wav2vec2", "ran": False, "reference": "lemonfox-asr",
          "calibration": "none", "results": [], "failures": [], "versions": versions(),
          "_note": ("H26-m2. This file records whether the named deliverable EXECUTED. "
                    "An empty results list with ran=false and a populated failures list "
                    "is a report of non-execution, not a report of nothing. The previous "
                    "artifact was `[]`, which is indistinguishable from 'measured nothing "
                    "worth reporting', and no document said WhisperX had not run.")}

# Probe the dependency BEFORE the fixture loop, so a single environment fault is
# recorded once as an environment fault rather than six times as six alignment
# failures. Six identical rows is how a dependency problem gets read as a
# measurement problem.
try:
    from whisperx.alignment import load_align_model  # noqa: F401
    record["import_ok"] = True
except Exception as e:
    record["import_ok"] = False
    record["failures"].append({
        "stage": "import", "error": f"{type(e).__name__}: {e}",
        "diagnosis": ("transformers 5.x no longer exports Wav2Vec2ForCTC / Wav2Vec2Processor / "
                      "Pipeline at the top level, and whisperx imports all three at module "
                      "scope. WhisperX cannot execute on this interpreter."),
        "remedy": ("pin transformers<5 in a dedicated venv for the aligner sidecar. NOT done "
                   "here: this Python install is shared with other projects on the host, and "
                   "downgrading it globally to make one spike run is a change with a blast "
                   "radius nobody asked for."),
        "standing_in_for": ("aligner/spike-a/fa.py -- torchaudio MMS_FA. Same mechanism "
                            "(wav2vec2 CTC forced alignment over the audio), bundled with "
                            "torchaudio, no transformers dependency. Its results are in "
                            "out/spike-a-forced-alignment.json. WhisperX is the NAMED tool "
                            "and it did not run; the MECHANISM the roadmap wanted measured "
                            "was measured."),
    })
    print("  whisperx: NOT RUNNABLE on this interpreter -- recorded in the artifact")

if record["import_ok"]:
    for group, suffix in (("languages", ""), ("holdout", "-holdout")):
        for lang, spec in FX[group].items():
            wav = OUT / f"{lang}{suffix}.wav"
            if not wav.exists():
                record["failures"].append({"group": group, "lang": lang, "stage": "audio",
                                           "error": f"{wav.name} absent"})
                continue
            try:
                W = wx_words(wav, lang)
            except Exception as e:
                record["failures"].append({"group": group, "lang": lang, "stage": "align",
                                           "error": f"{type(e).__name__}: {str(e)[:300]}",
                                           "traceback_tail": traceback.format_exc()[-400:]})
                print(f"  {group}/{lang}: {type(e).__name__}: {str(e)[:120]}")
                continue
            display = H.display_units(spec["text"])
            wx_units = H.units_from_asr(W, display, lang)
            ref = R.lemonfox_words(wav, E["LEMONFOX_API_KEY"], lang)
            ref_units = H.units_from_asr(
                [{"w": x["word"], "s": float(x["start"]), "e": float(x["end"])} for x in ref],
                display, lang)
            pairs = H.pair_by_display(wx_units, ref_units)
            if not pairs:
                record["failures"].append({"group": group, "lang": lang, "stage": "pair",
                                           "error": "no display token carried both streams"})
                continue
            sc = H.score_pairs(pairs, display)
            record["ran"] = True
            record["results"].append({
                "group": group, "lang": lang, **sc,
                "display_words": len(display),
                "display_coverage_pct": round(100.0 * len(pairs) / len(display), 1),
                "unpaired_display": [display[i][0] for i in range(len(display))
                                     if i not in wx_units or i not in ref_units],
                "audio_seconds": round(H.wav_seconds(wav), 2),
            })
            print(f"  {group}/{lang}: {sc['words']}w overlap median {sc['median_overlap_pct']}% "
                  f"abs {sc['median_abs_error_ms']}ms signed {sc['median_signed_start_delta_ms']:+.0f}ms")

H.write_json(OUT / "spike-a-whisperx.json", record)
print(f"\nwrote out/spike-a-whisperx.json  ran={record['ran']} "
      f"results={len(record['results'])} failures={len(record['failures'])}")
