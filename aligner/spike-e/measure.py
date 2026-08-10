#!/usr/bin/env python3
"""
SPIKE E, the measurement harness — aligner container sizing.

Runs IDENTICALLY on the Windows workstation and inside the Linux container, so
the two rows in the artifact are the same instrument on different hardware. That
is the whole point: SPIKE A's cost figure was taken on a developer's box and the
roadmap quotes it as a container cost, and nobody has ever put the two side by
side.

WHAT THIS MEASURES, STAGE BY STAGE. The pipeline §6.1 ships is
`ASR -> forced alignment -> match`. SPIKE A's `compute_cost_per_audio_hour_usd`
times the FIRST STAGE ONLY (`measure.py:192-198` wraps `model.transcribe` and
nothing else). This harness times all three separately so the omission is
visible as a number rather than argued about:

  1. `import`        — interpreter + wheel import cost, paid once per process
  2. `asr_load`      — faster-whisper model load, paid once per process
  3. `align_load`    — the wav2vec2 alignment bundle, paid once PER LANGUAGE
  4. `transcribe`    — per unit of work
  5. `align`         — per unit of work; SPIKE A never timed this
  6. `match`         — deliberately NOT timed here; it is pure Python string work
                       in `worker/src/normalize/` and is not this container's
                       cost driver. Saying so is not the same as measuring it.

PEAK RSS is read from the OS, not sampled from Python. On Linux that is
`VmHWM` in `/proc/self/status` — a kernel high-water mark that cannot miss a
spike between samples. On Windows it is `PeakWorkingSetSize` from
`GetProcessMemoryInfo`. Both are true peaks over the process lifetime, which is
the number that sizes a container memory limit; a sampled maximum is not, and
would understate a short allocation burst.

Usage:
  python measure.py --audio <wav> --lang en [--model base] [--threads 4]
                    [--out results.json] [--label host-windows]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import wave

# ── Peak RSS, from the OS high-water mark ────────────────────────────────────


def peak_rss_bytes() -> int | None:
    """True peak resident set over the process lifetime, or None if unavailable.

    Returns None rather than 0 or an estimate. A memory figure that silently
    degrades to a guess is exactly the failure this project keeps finding.
    """
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/self/status", "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("VmHWM:"):
                        # VmHWM is reported in kB.
                        return int(line.split()[1]) * 1024
        except OSError:
            return None
        return None
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            # argtypes/restype are NOT optional here. GetCurrentProcess returns
            # the pseudo-handle (HANDLE)-1; with ctypes' default int restype that
            # value is truncated to 32 bits and the call fails, which is how this
            # function silently returned None on its first outing.
            kernel32 = ctypes.WinDLL("kernel32.dll")
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi = ctypes.WinDLL("psapi.dll")
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            ok = psapi.GetProcessMemoryInfo(
                kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
            )
            return int(counters.PeakWorkingSetSize) if ok else None
        except Exception:
            return None
    return None


def wav_seconds(path: str) -> float:
    with wave.open(path, "rb") as fh:
        return fh.getnframes() / float(fh.getframerate())


# ── Hardware block, so a number is never separated from the box it came from ──


def cpu_model() -> str:
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or "unknown"


def cgroup_memory_limit_bytes() -> int | None:
    """The container's memory ceiling, if one is imposed. None outside cgroups.

    Recorded because a peak RSS is only interesting against the limit it ran
    under: the same 1.4 GB peak is comfortable at a 2 GB limit and an OOM kill
    at 1 GB.
    """
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read().strip()
            if raw in ("max", ""):
                return None
            value = int(raw)
            # cgroup v1 reports an absurd sentinel when unlimited.
            return None if value > (1 << 62) else value
        except (OSError, ValueError):
            continue
    return None


def hardware_block(threads: int) -> dict:
    return {
        "platform": sys.platform,
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "cpu_model": cpu_model(),
        "logical_cpus_visible": os.cpu_count(),
        "cpu_threads_configured": threads,
        "python": sys.version.split()[0],
        "cgroup_memory_limit_bytes": cgroup_memory_limit_bytes(),
        "_note": (
            "logical_cpus_visible is what the PROCESS sees. Under Docker without "
            "--cpuset-cpus this is the host count even when --cpus caps the quota, "
            "so it is not a statement about how much CPU the container may use."
        ),
    }


# ── The run ──────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--model", default="base")
    ap.add_argument("--compute-type", default="int8")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--out", default="-")
    ap.add_argument("--label", default="unlabelled")
    ap.add_argument("--skip-align", action="store_true")
    ap.add_argument(
        "--align-chunk-s",
        type=float,
        default=0.0,
        help="seconds per alignment forward pass; 0 = one shot over the segment",
    )
    ap.add_argument(
        "--align-backend",
        choices=("torchaudio", "whisperx"),
        default="torchaudio",
        help=(
            "torchaudio drives the wav2vec2 bundle directly — the LEAN stack in "
            "aligner/requirements.txt, and the same mechanism whisperx uses for "
            "en/es/fr. whisperx measures the named tool, which needs "
            "transformers<5 and therefore does not import on the workstation."
        ),
    )
    args = ap.parse_args()

    rec: dict = {
        "label": args.label,
        "measurement": "SPIKE E aligner container sizing",
        "audio": os.path.basename(args.audio),
        "lang": args.lang,
        "asr_model": args.model,
        "compute_type": args.compute_type,
        "stages": {},
        "peak_rss_after_stage_bytes": {},
        "failures": [],
        "_kind": "MEASURED unless a field says otherwise",
    }

    audio_s = wav_seconds(args.audio)
    rec["audio_seconds"] = round(audio_s, 2)

    rec["peak_rss_after_stage_bytes"]["baseline_interpreter"] = peak_rss_bytes()

    # 1. import
    t0 = time.time()
    import faster_whisper  # noqa: F401

    rec["stages"]["import_faster_whisper_s"] = round(time.time() - t0, 3)
    rec["peak_rss_after_stage_bytes"]["import_faster_whisper"] = peak_rss_bytes()

    t0 = time.time()
    try:
        import torch  # noqa: F401

        rec["stages"]["import_torch_s"] = round(time.time() - t0, 3)
        rec["torch_version"] = torch.__version__
    except Exception as exc:
        rec["failures"].append({"stage": "import_torch", "error": f"{type(exc).__name__}: {exc}"})
    rec["peak_rss_after_stage_bytes"]["import_torch"] = peak_rss_bytes()

    # 2. ASR model load — the cold-start term, paid once per container
    from faster_whisper import WhisperModel

    t0 = time.time()
    model = WhisperModel(
        args.model, device="cpu", compute_type=args.compute_type, cpu_threads=args.threads
    )
    rec["stages"]["asr_model_load_s"] = round(time.time() - t0, 3)
    rec["peak_rss_after_stage_bytes"]["asr_model_load"] = peak_rss_bytes()

    # 3. transcribe — the per-unit-of-work term
    t0, c0 = time.time(), time.process_time()
    segments, _info = model.transcribe(
        args.audio, language=args.lang, word_timestamps=True, vad_filter=False
    )
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"w": w.word.strip(), "s": w.start, "e": w.end})
    transcribe_wall = time.time() - t0
    transcribe_cpu = time.process_time() - c0
    rec["stages"]["transcribe_wall_s"] = round(transcribe_wall, 3)
    rec["stages"]["transcribe_cpu_s"] = round(transcribe_cpu, 3)
    rec["asr_word_count"] = len(words)
    rec["peak_rss_after_stage_bytes"]["transcribe"] = peak_rss_bytes()

    # 4. forced alignment — the stage SPIKE A's cost figure does not contain
    align_wall = align_cpu = align_load = None
    rec["align_backend"] = args.align_backend
    if not args.skip_align:
        try:
            if args.align_backend == "whisperx":
                t0 = time.time()
                import whisperx
                from whisperx.alignment import load_align_model, align as wx_align

                rec["stages"]["import_whisperx_s"] = round(time.time() - t0, 3)
                rec["peak_rss_after_stage_bytes"]["import_whisperx"] = peak_rss_bytes()

                t0 = time.time()
                align_model, meta = load_align_model(language_code=args.lang, device="cpu")
                align_load = time.time() - t0
                rec["stages"]["align_model_load_s"] = round(align_load, 3)
                rec["peak_rss_after_stage_bytes"]["align_model_load"] = peak_rss_bytes()

                audio = whisperx.load_audio(args.audio)
                segs_in = [
                    {
                        "start": words[0]["s"],
                        "end": words[-1]["e"],
                        "text": " ".join(w["w"] for w in words),
                    }
                ]
                t0, c0 = time.time(), time.process_time()
                wx_align(segs_in, align_model, meta, audio, "cpu", return_char_alignments=False)
                align_wall = time.time() - t0
                align_cpu = time.process_time() - c0
            else:
                # torchaudio bundle — the lean stack. Emissions are the CTC log
                # probabilities a forced aligner consumes; this measures the
                # model's forward pass over the segment, which is the term that
                # scales with audio length and is the one SPIKE A never timed.
                import torch
                import torchaudio
                import torchaudio.pipelines as pipelines

                bundles = {
                    "en": "WAV2VEC2_ASR_BASE_960H",
                    "es": "VOXPOPULI_ASR_BASE_10K_ES",
                    "fr": "VOXPOPULI_ASR_BASE_10K_FR",
                }
                name = bundles.get(args.lang)
                if name is None:
                    raise RuntimeError(
                        f"no torchaudio alignment bundle mapped for {args.lang!r}; "
                        f"supported: {sorted(bundles)}"
                    )
                rec["align_bundle"] = name

                torch.set_num_threads(args.threads)
                t0 = time.time()
                bundle = getattr(pipelines, name)
                align_model = bundle.get_model()
                align_load = time.time() - t0
                rec["stages"]["align_model_load_s"] = round(align_load, 3)
                rec["peak_rss_after_stage_bytes"]["align_model_load"] = peak_rss_bytes()

                waveform, sample_rate = torchaudio.load(args.audio)
                if sample_rate != bundle.sample_rate:
                    waveform = torchaudio.functional.resample(
                        waveform, sample_rate, bundle.sample_rate
                    )
                # CHUNKING. A single forward pass over a whole segment
                # materialises self-attention activations for the entire
                # waveform at once, and wav2vec2 attention is quadratic in
                # frames. At --align-chunk-s 0 (one shot) a 73 s segment peaks
                # near 3 GiB; chunking bounds that by the chunk, at the cost of
                # a seam every chunk. The seam is why this is a MEASUREMENT
                # option and not silently the default: bounding memory by
                # cutting the audio is only free if the match step tolerates the
                # boundary, which is Forge's call, not this spike's.
                chunk_s = args.align_chunk_s
                rec["align_chunk_seconds"] = chunk_s
                t0, c0 = time.time(), time.process_time()
                frames = 0
                with torch.inference_mode():
                    if chunk_s and chunk_s > 0:
                        step = int(chunk_s * bundle.sample_rate)
                        for start in range(0, waveform.shape[1], step):
                            piece = waveform[:, start : start + step]
                            if piece.shape[1] < bundle.sample_rate // 10:
                                continue  # sub-100 ms tail carries no words
                            emissions, _ = align_model(piece)
                            torch.log_softmax(emissions, dim=-1)
                            frames += int(emissions.shape[1])
                            del emissions
                    else:
                        emissions, _ = align_model(waveform)
                        torch.log_softmax(emissions, dim=-1)
                        frames = int(emissions.shape[1])
                align_wall = time.time() - t0
                align_cpu = time.process_time() - c0
                rec["align_emission_frames"] = frames

            rec["stages"]["align_wall_s"] = round(align_wall, 3)
            rec["stages"]["align_cpu_s"] = round(align_cpu, 3)
            rec["peak_rss_after_stage_bytes"]["align"] = peak_rss_bytes()
        except Exception as exc:
            import traceback

            align_wall = align_cpu = None
            rec["failures"].append(
                {
                    "stage": "align",
                    "backend": args.align_backend,
                    "error": f"{type(exc).__name__}: {str(exc)[:400]}",
                    "traceback_tail": traceback.format_exc()[-600:],
                }
            )

    # ── Derived. Every derived field names its inputs. ───────────────────────
    total_wall = transcribe_wall + (align_wall or 0.0)
    total_cpu = transcribe_cpu + (align_cpu or 0.0)
    cold = rec["stages"].get("asr_model_load_s", 0.0) + (align_load or 0.0)

    rec["derived"] = {
        "realtime_factor_transcribe_only": round(transcribe_wall / audio_s, 4),
        "realtime_factor_pipeline_amortised": round(total_wall / audio_s, 4),
        "realtime_factor_pipeline_including_model_load": round(
            (total_wall + cold) / audio_s, 4
        ),
        "cpu_seconds_per_audio_second_transcribe_only": round(transcribe_cpu / audio_s, 4),
        "cpu_seconds_per_audio_second_pipeline": round(total_cpu / audio_s, 4),
        "cold_start_seconds_asr_plus_align": round(cold, 3),
        # CONTENTION, measured rather than assumed. cpu_seconds / wall_seconds is
        # the number of cores this process actually received; divided by the
        # threads it asked for, it is the share of the requested parallelism it
        # got. A realtime factor taken at low efficiency is a measurement of the
        # BOX'S LOAD, not of the workload, and must not be quoted as the latter.
        "cores_actually_received": round(total_cpu / total_wall, 3) if total_wall else None,
        "thread_efficiency": round(total_cpu / (total_wall * args.threads), 3)
        if total_wall and args.threads
        else None,
        "peak_rss_max_bytes": max(
            (v for v in rec["peak_rss_after_stage_bytes"].values() if v), default=None
        ),
        "_align_included": align_wall is not None,
        "_note": (
            "realtime_factor_*_pipeline collapses to the transcribe-only figure "
            "when _align_included is false. A pipeline factor that silently omits "
            "a stage is the SPIKE A defect, so the flag is emitted beside it."
        ),
    }
    peak = rec["derived"]["peak_rss_max_bytes"]
    rec["derived"]["peak_rss_max_mib"] = round(peak / (1024 * 1024), 1) if peak else None
    rec["hardware"] = hardware_block(args.threads)

    blob = json.dumps(rec, indent=2, ensure_ascii=False)
    if args.out == "-":
        print(blob)
    else:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(blob + "\n")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
