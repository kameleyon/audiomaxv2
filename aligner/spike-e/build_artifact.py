#!/usr/bin/env python3
"""
SPIKE E — assemble `out/spike-e-results.json` from the runs in `out/`.

Every number this file emits carries a `kind`:

  MEASURED    an observation taken by a command recorded in `repro`
  ESTIMATED   arithmetic over MEASURED inputs, or a figure from a cited source;
              `derivation` names every input
  ASSUMPTION  an input nobody here verified

That distinction is not decoration. SPIKE A's cost figure is an ESTIMATED number
whose own artifact labels its rate basis an ASSUMPTION, and it has since been
quoted as though it were MEASURED. The label travels with the number so the next
reader cannot repeat that.

Run:  python aligner/spike-e/build_artifact.py
"""
from __future__ import annotations

import glob
import json
import pathlib

HERE = pathlib.Path(__file__).parent
OUT = HERE / "out"

# ── Constants MEASURED by a command, recorded with that command ──────────────

# `pip download` for linux/amd64 cp312 against the PyTorch CPU index, then the
# uncompressed size summed from each wheel's zip central directory. This is the
# site-packages footprint, not the download.
WHEELS = {
    "lean": {
        "packages": 35,
        "wheel_download_bytes": 320_255_230,
        "installed_bytes": 1_120_763_401,
        "largest_installed_bytes": {
            "torch": 678_030_540,
            "ctranslate2": 139_984_896,
            "av": 105_172_582,
            "numpy": 57_147_392,
            "onnxruntime": 54_316_646,
        },
    },
    "whisperx": {
        "packages": 105,
        "wheel_download_bytes": 452_441_834,
        "installed_bytes": 1_526_094_465,
        "largest_installed_bytes": {
            "torch": 678_030_540,
            "ctranslate2": 139_984_896,
            "scipy": 111_673_344,
            "av": 105_172_582,
            "transformers": 52_428_800,
        },
    },
}

# HTTP HEAD Content-Length against download.pytorch.org for each bundle.
ALIGN_BUNDLES = {
    "en": {"name": "WAV2VEC2_ASR_BASE_960H", "bytes": 377_667_584},
    "es": {"name": "VOXPOPULI_ASR_BASE_10K_ES", "bytes": 377_689_600},
    "fr": {"name": "VOXPOPULI_ASR_BASE_10K_FR", "bytes": 377_711_616},
}

# `du` over the workstation's Hugging Face cache.
ASR_MODELS_BYTES = {"base": 148_897_792, "small": 486_539_264, "medium": 1_610_612_736}

BASE_IMAGE_COMPRESSED_BYTES = 42_991_616  # python:3.12-slim linux/amd64, registry API
BASE_IMAGE_UNCOMPRESSED_EST_MIB = 125

SPIKE_A_COST_PER_AUDIO_HOUR = {"min": 0.0183, "max": 0.0249}
SPIKE_A_ASR_CPU_S_PER_AUDIO_S = {"min": 0.657, "max": 0.895}
BOOK_HOURS = 9


def mib(n):
    return round(n / (1024 * 1024), 1) if n else None


def load_runs():
    runs = []
    for path in sorted(glob.glob(str(OUT / "host-*.json"))):
        with open(path, "r", encoding="utf-8") as fh:
            runs.append(json.load(fh))
    return runs


def main() -> int:
    runs = load_runs()
    oneshot = [r for r in runs if not r.get("align_chunk_seconds")]
    chunked = [r for r in runs if r.get("align_chunk_seconds")]

    def row(r):
        s = r["stages"]
        d = r["derived"]
        return {
            "label": r["label"],
            "lang": r["lang"],
            "audio_seconds": r["audio_seconds"],
            "align_chunk_seconds": r.get("align_chunk_seconds", 0.0),
            "thread_efficiency": d["thread_efficiency"],
            "cores_actually_received": d["cores_actually_received"],
            "asr_cpu_s_per_audio_s": round(s["transcribe_cpu_s"] / r["audio_seconds"], 4),
            "pipeline_cpu_s_per_audio_s": d["cpu_seconds_per_audio_second_pipeline"],
            "align_cpu_over_asr_cpu": round(s["align_cpu_s"] / s["transcribe_cpu_s"], 3),
            "rtf_transcribe_only": d["realtime_factor_transcribe_only"],
            "rtf_pipeline": d["realtime_factor_pipeline_amortised"],
            "peak_rss_mib": d["peak_rss_max_mib"],
            "cold_start_s": d["cold_start_seconds_asr_plus_align"],
        }

    all_rows = sorted((row(r) for r in runs), key=lambda x: -x["thread_efficiency"])
    cleanest = max(oneshot, key=lambda r: r["derived"]["thread_efficiency"])
    c = row(cleanest)

    multiplier = round(1 + c["align_cpu_over_asr_cpu"], 3)
    corrected = {
        "min_usd": round(SPIKE_A_COST_PER_AUDIO_HOUR["min"] * BOOK_HOURS * multiplier, 3),
        "max_usd": round(SPIKE_A_COST_PER_AUDIO_HOUR["max"] * BOOK_HOURS * multiplier, 3),
    }
    asr_reproduced = (
        SPIKE_A_ASR_CPU_S_PER_AUDIO_S["min"]
        <= c["asr_cpu_s_per_audio_s"]
        <= SPIKE_A_ASR_CPU_S_PER_AUDIO_S["max"]
    )

    lean_models_all3 = ASR_MODELS_BYTES["base"] + sum(v["bytes"] for v in ALIGN_BUNDLES.values())

    def img_mib(installed_bytes, models_bytes=0, ffmpeg_mib=0):
        return round(
            BASE_IMAGE_UNCOMPRESSED_EST_MIB
            + installed_bytes / (1024 * 1024)
            + models_bytes / (1024 * 1024)
            + ffmpeg_mib
        )

    artifact = {
        "spike": "E",
        "subject": "aligner container sizing",
        "owner": "Queue",
        "date": "2026-08-10",
        "roadmap_item": "Phase 0 — SPIKE E (Owner: Queue · due 2026-08-14)",
        "verdict": (
            "PARTIAL. Image size, memory and cold start are answered from measurement. "
            "The container-grade realtime factor is NOT answered: no Linux container can "
            "run on this host, and no container number is simulated anywhere in this file."
        ),
        "_label_key": {
            "MEASURED": "observed by the command in `repro`",
            "ESTIMATED": "arithmetic over MEASURED inputs, or a cited third-party figure; `derivation` names the inputs",
            "ASSUMPTION": "an input nobody here verified",
        },
        # ── Scope boundary, because two same-shaped numbers are already loose ─
        "_what_this_spike_costs_and_what_it_does_not": {
            "this_artifact_reports": (
                "SELF-HOSTED ASR + FORCED-ALIGNMENT COMPUTE — the cost of running our own "
                "aligner container. Denominated in vCPU-seconds and GB-minutes of our own "
                "infrastructure."
            ),
            "this_artifact_does_NOT_report": (
                "TTS VENDOR SPEND. Oracle's SPIKE C result — Fish billing UTF-8 bytes, "
                "$8.10-$8.33 per reference book — is a DIFFERENT QUANTITY: money paid to a "
                "third-party synthesis vendor per character of text."
            ),
            "why_this_note_exists": (
                "both are 'dollars per book' and they are ~20x apart, so summing them or "
                "substituting one for the other is an easy and expensive mistake. This "
                "project has already confused two same-shaped numbers more than once "
                "(J29-M1, and the 0.162x pairing found below). They are additive terms in a "
                "unit cost, not alternatives: a book pays Oracle's TTS bill AND this "
                "artifact's compute bill."
            ),
        },
        # ── The blocker, stated rather than worked around ────────────────────
        "container_measurement_blocked": {
            "kind": "MEASURED",
            "blocked": True,
            "what_is_blocked": [
                "image size as built (only the dependency closure and model weights could be measured)",
                "peak RSS under a container memory limit / cgroup",
                "cold start from a cold page cache and cold image layers",
                "realtime factor on container-grade CPU — the roadmap's actual question",
            ],
            "root_cause": (
                "Docker Desktop 4.41.2 is installed and its Windows services run, but the "
                "Linux engine cannot start: it provisions a WSL2 distro, and WSL2 cannot "
                "create a VM on this host."
            ),
            "vendor_error_verbatim": (
                "deploying \"docker-desktop\": importing WSL distro \"WSL2 is not supported "
                "with your current machine configuration. Please enable the \"Virtual Machine "
                "Platform\" optional component and ensure virtualization is enabled in the "
                "BIOS. Error code: Wsl/Service/RegisterDistro/CreateVm/HCS/"
                "HCS_E_HYPERV_NOT_INSTALLED\""
            ),
            "evidence_path": "~/AppData/Local/Docker/log/host/com.docker.backend.exe.log",
            "host_state": {
                "VirtualMachinePlatform": "Enabled",
                "Microsoft-Windows-Subsystem-Linux": "Enabled",
                "Microsoft-Hyper-V": "Enabled",
                "HypervisorPlatform": "Disabled",
                "HypervisorPresent": True,
                "wsl_default_version": 2,
                "wsl_distros": "Ubuntu (VERSION 1). No docker-desktop distro was ever created.",
                "docker_cli": "28.1.1 present; `docker context ls` lists desktop-linux but its named pipe never appears",
                "docker_windows_engine": "responds, but runs WINDOWS containers and cannot run a linux/amd64 image",
            },
            "why_not_fixed_here": (
                "HypervisorPlatform is Disabled and this machine is ALREADY a guest "
                "(HypervisorPresent=true, AMD EPYC). Enabling it requires a reboot, AND the "
                "cloud provider must expose nested virtualisation on this VM — which "
                "HCS_E_HYPERV_NOT_INSTALLED indicates it does not. Four other agents were "
                "mid-task on this host; rebooting to finish a sizing spike is not a trade "
                "this spike gets to make unilaterally."
            ),
            "what_would_be_needed": {
                "simplest": "any linux/amd64 Docker daemon — a GitHub Actions ubuntu-latest job is sufficient and free",
                "commands": [
                    "docker build --target runtime -t audiomax-aligner:runtime aligner/",
                    "docker build --target baked   -t audiomax-aligner:baked   aligner/",
                    "docker image inspect --format '{{.Size}}' audiomax-aligner:runtime audiomax-aligner:baked",
                    "docker run --rm --cpus 2 --memory 5g -v $PWD/aligner/spike-a/out:/audio:ro "
                    "audiomax-aligner:baked python /app/spike-e/measure.py --audio /audio/en-para.wav "
                    "--lang en --threads 2 --label container-2vcpu --out /dev/stdout",
                    "# repeat with --cpus 1 / 4 to get the scaling curve, and with --align-chunk-s 15",
                ],
                "why_a_container_is_required_and_not_optional": (
                    "the three numbers that move the cost model — realtime factor, peak RSS "
                    "under a limit, and cold start from cold layers — are all properties of "
                    "the container, and this host cannot produce any of them."
                ),
            },
        },
        # ── 1. Image size ────────────────────────────────────────────────────
        "answer_1_image_size": {
            "question": "how large is the container once WhisperX, torch and the models are in it?",
            "built_image_size_bytes": None,
            "built_image_size_reason": "BLOCKED — see container_measurement_blocked",
            "dependency_closure": {
                "kind": "MEASURED",
                "repro": (
                    "python -m pip download --only-binary=:all: "
                    "--platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 "
                    "--platform manylinux2014_x86_64 --platform any --python-version 3.12 "
                    "--implementation cp --abi cp312 "
                    "--extra-index-url https://download.pytorch.org/whl/cpu "
                    "-r aligner/requirements.txt -d <dir>  ; then sum each wheel's "
                    "uncompressed zip central directory"
                ),
                "_what_this_is": (
                    "the resolved linux/amd64 wheel set and its unpacked site-packages size — "
                    "the dominant image term, genuinely measured. It is NOT the built image, "
                    "which also carries the base layer and filesystem overhead."
                ),
                "lean_stack": WHEELS["lean"],
                "whisperx_stack": WHEELS["whisperx"],
                "whisperx_delta_installed_bytes": (
                    WHEELS["whisperx"]["installed_bytes"] - WHEELS["lean"]["installed_bytes"]
                ),
                "whisperx_delta_packages": 70,
                "_torch_cpu_index_is_load_bearing": (
                    "torch resolves to torch-2.8.0+cpu at 678 MiB installed. From plain PyPI "
                    "the linux/amd64 build pulls the nvidia-* CUDA runtime wheels instead — "
                    "roughly 2.5 GB of GPU libraries this CPU-only container never loads. The "
                    "--extra-index-url in the Dockerfile is the single largest size decision "
                    "in the image and the build asserts it took."
                ),
            },
            "base_image": {
                "kind": "MEASURED",
                "image": "python:3.12-slim linux/amd64",
                "compressed_bytes": BASE_IMAGE_COMPRESSED_BYTES,
                "repro": "Docker Hub registry v2 manifest, summed layer sizes",
                "uncompressed_bytes": None,
                "uncompressed_estimate_mib": BASE_IMAGE_UNCOMPRESSED_EST_MIB,
                "uncompressed_kind": "ESTIMATED — not measurable without a daemon; ~3x compressed is typical",
            },
            "models": {
                "kind": "MEASURED",
                "asr_faster_whisper_bytes": ASR_MODELS_BYTES,
                "asr_repro": "du over ~/.cache/huggingface/hub/models--Systran--faster-whisper-*",
                "align_bundles": ALIGN_BUNDLES,
                "align_repro": "HTTP HEAD Content-Length against download.pytorch.org/torchaudio/models/<file>",
                "all_three_align_bundles_bytes": sum(v["bytes"] for v in ALIGN_BUNDLES.values()),
                "asr_base_plus_all_three_bytes": lean_models_all3,
                "per_language_residency": (
                    "THE ROADMAP ASKS FOR PER-LANGUAGE MODEL RESIDENCY AND THIS IS THE ANSWER. "
                    "Alignment weights are PER LANGUAGE at ~360 MiB each: a container serving "
                    "one language holds ~360 MiB, one serving all three holds ~1.08 GiB. ASR "
                    "is shared across languages (one multilingual model, 142 MiB at `base`), "
                    "so only the alignment half scales with language count."
                ),
                "_these_are_torchaudio_not_huggingface": (
                    "For all three of en/es/fr, whisperx selects torchaudio bundles, not HF "
                    "checkpoints (whisperx/alignment.py DEFAULT_ALIGN_MODELS_TORCH). They "
                    "download from download.pytorch.org into TORCH_HOME. A bake or cache-warm "
                    "step that primed only HF_HOME would therefore prime NOTHING that matters "
                    "and the first render per language would still fetch 360 MiB. The "
                    "Dockerfile sets TORCH_HOME and HF_HOME under one /models root for exactly "
                    "this reason."
                ),
                "_alternative_single_multilingual_model": {
                    "name": "MMS_FA (torchaudio, multilingual)",
                    "bytes": 1_262_047_414,
                    "repro": "ls ~/.cache/torch/hub/checkpoints/model.pt on this workstation",
                    "trade": (
                        "one 1.20 GiB model covers every language versus 0.35 GiB per language. "
                        "Cheaper only beyond ~3 languages; strictly worse for a worker sharded "
                        "to one language. aligner/spike-a/fa.py drives this one, and it is the "
                        "mechanism SPIKE A actually reports."
                    ),
                },
            },
            "estimated_image_size_mib": {
                "kind": "ESTIMATED",
                "derivation": (
                    "base uncompressed (ESTIMATED 125 MiB) + site-packages (MEASURED) + "
                    "models (MEASURED) [+ ffmpeg apt tree, ESTIMATED 300 MiB, whisperx only]. "
                    "Excludes filesystem and metadata overhead."
                ),
                "lean_runtime_no_models": img_mib(WHEELS["lean"]["installed_bytes"]),
                "lean_baked_en_es_fr": img_mib(WHEELS["lean"]["installed_bytes"], lean_models_all3),
                "lean_baked_one_language": img_mib(
                    WHEELS["lean"]["installed_bytes"],
                    ASR_MODELS_BYTES["base"] + ALIGN_BUNDLES["en"]["bytes"],
                ),
                "whisperx_runtime_no_models": img_mib(
                    WHEELS["whisperx"]["installed_bytes"], 0, 300
                ),
                "whisperx_baked_en_es_fr": img_mib(
                    WHEELS["whisperx"]["installed_bytes"], lean_models_all3, 300
                ),
                "confidence": (
                    "the site-packages and model terms are MEASURED and together are ~90% of "
                    "the total, so this should be good to roughly 10%. It is NOT a substitute "
                    "for `docker image inspect`."
                ),
            },
            "ffmpeg_finding": {
                "kind": "MEASURED",
                "finding": (
                    "The lean image does NOT need the ffmpeg apt package. faster-whisper 1.2.1 "
                    "decodes through PyAV, and the `av` wheel bundles its own ffmpeg shared "
                    "libraries — 25 of them, verified in the installed package. Only whisperx "
                    "needs the binary, because whisperx.load_audio shells out to it."
                ),
                "saving_mib_estimated": 300,
            },
            "baked_vs_fetched": {
                "fetched": "smaller image, but the first request per language fetches ~360 MiB from download.pytorch.org. Sound ONLY with a persistent cache volume, so it is paid once per volume rather than once per container.",
                "baked": "every container starts equal; no render depends on a third-party CDN being reachable. Costs image size and pull time per node.",
                "recommendation": (
                    "BAKE the three shipping languages. CLAUDE.md constraint 2 forbids a "
                    "primary path that depends on a fallback, and a render that must reach "
                    "download.pytorch.org before it can start has one. The Dockerfile's "
                    "`baked` target does this and REFUSES an unmapped language rather than "
                    "silently skipping it."
                ),
            },
        },
        # ── 2. Memory ────────────────────────────────────────────────────────
        "answer_2_memory": {
            "question": "peak RSS transcribing ~1,000 characters ~= 60 s of audio",
            "kind": "MEASURED",
            "caveat": "measured on the WORKSTATION, not under a container memory limit. See _limits.",
            "unit_of_work": "the *-para.wav fixtures, 73-77 s — the closest thing on disk to the 60 s unit",
            "peak_rss_source": (
                "GetProcessMemoryInfo PeakWorkingSetSize (Windows) / VmHWM (Linux) — an OS "
                "high-water mark over the whole process lifetime, not a sampled maximum, so "
                "it cannot miss a short allocation burst."
            ),
            "headline": {
                "one_shot_60s_segment_peak_mib": [2848.6, 4549.4],
                "chunked_15s_peak_mib": [1936.5, 1942.9],
                "asr_only_plateau_mib": 493,
            },
            "finding": (
                "MEMORY IS DOMINATED BY FORCED ALIGNMENT, NOT BY ASR, AND IT IS THE BIGGEST "
                "SURPRISE IN THIS SPIKE. ASR peaks at ~493 MiB and is flat across all runs. A "
                "single-shot wav2vec2 forward pass over a 73-77 s segment then drives the peak "
                "to 2.8-4.5 GiB, because self-attention is quadratic in frames and the whole "
                "segment is one pass. NOTHING IN SPIKE A COULD HAVE SEEN THIS: its clips are "
                "8-12 s, where the quadratic term is ~40x smaller, and it never ran the "
                "alignment stage under measurement at all."
            ),
            "chunking_result": {
                "kind": "MEASURED",
                "finding": (
                    "Chunking the alignment forward pass to 15 s bounds memory by the chunk. "
                    "Peak falls from 4388 MiB to 1937 MiB; the alignment-ATTRIBUTABLE term "
                    "(peak minus the post-model-load baseline) falls from 3316 MiB to 872 MiB, "
                    "a 3.8x reduction."
                ),
                "reproducibility": (
                    "two chunked runs at wildly different host load (thread efficiency 0.171 "
                    "and 0.100) produced 1936.5 and 1942.9 MiB — 0.3% apart. PEAK RSS IS "
                    "CONTENTION-INDEPENDENT, which is why the memory answers here are solid "
                    "while the CPU answers are not."
                ),
                "cost": "a seam every chunk, which the match step must tolerate.",
            },
            "_peak_rss_rises_with_available_parallelism": (
                "The one-shot peak was 2849 MiB at thread efficiency 0.36 and 4388 MiB at 0.66 "
                "on the SAME input. More cores actually running means more concurrent "
                "activation buffers. A production box is LESS contended than this one, so the "
                "higher figure is the more representative one — contention flattered the "
                "memory number, it did not inflate it."
            ),
            "recommended_container_memory": {
                "kind": "ESTIMATED",
                "derivation": "measured peak plus headroom for allocator slack and the request path",
                "unchunked_60s_segment_gib": 5,
                "chunked_15s_segment_gib": 2.5,
                "_note": (
                    "These bracket a real engineering choice rather than describing one. "
                    "Whether the match step tolerates a chunk seam is Forge's call; this spike "
                    "measures both sides of the trade and does not make it. The difference is "
                    "2x on the memory bill and on how many workers fit per node."
                ),
            },
            "_resample_note": (
                "es/fr fixtures are 44.1 kHz and en is 24 kHz; both are resampled to the "
                "bundle's 16 kHz before the forward pass and the resample intermediate sits "
                "inside the peak. Feeding the aligner 16 kHz mono audio removes that term and "
                "is free to arrange upstream."
            ),
        },
        # ── 3. Cold start ────────────────────────────────────────────────────
        "answer_3_cold_start": {
            "question": "model load time — does it make the worker long-lived or per-job?",
            "kind": "MEASURED",
            "caveat": (
                "workstation, WARM page cache and warm model files. A container's first start "
                "reads cold layers, so every figure here is a FLOOR."
            ),
            "cleanest_observation": {
                "label": c["label"],
                "asr_model_load_s": cleanest["stages"]["asr_model_load_s"],
                "align_model_load_s": cleanest["stages"]["align_model_load_s"],
                "cold_start_total_s": c["cold_start_s"],
                "import_faster_whisper_s": cleanest["stages"]["import_faster_whisper_s"],
            },
            "observed_range_across_runs": {
                "asr_model_load_s": [2.0, 32.3],
                "align_model_load_s": [3.3, 8.0],
                "import_faster_whisper_s": [13.5, 65.6],
                "_note": "the wide upper ends are contended observations; the lower ends are the quieter box",
            },
            "verdict": {
                "answer": "LONG-LIVED, MODEL-RESIDENT WORKER. Per-job containers are refused.",
                "reasoning": (
                    "Even on the quiet box and with everything warm, model load is ~3.7 s and "
                    "the import of faster-whisper alone is 13.5 s — roughly 17 s before any "
                    "audio is touched, against a 60 s unit of work whose own processing is "
                    "~25-40 s. A per-job container would pay something close to its own "
                    "runtime again in startup, and pay it PER LANGUAGE, because alignment "
                    "weights load per language. SPIKE A's own artifacts already separate "
                    "realtime_factor_including_model_load from realtime_factor_amortised by "
                    "~1.7x for this reason; amortising to nothing REQUIRES a process that "
                    "outlives the job."
                ),
                "consequences_for_the_queue": [
                    "workers hold models resident and poll for jobs; they are not spawned per job",
                    "per-language residency is a SCHEDULING attribute: a worker holding es weights should preferentially receive es segments, or it pays ~3-8 s to swap plus ~360 MiB of residency",
                    "graceful shutdown must drain in-flight work — SIGTERM cannot be a hard kill when restart costs this much (aligner/service.py already handles SIGTERM)",
                    "the orphaned-job sweeper's claim timeout must exceed cold start PLUS the job, or a cold worker's first job is reaped as orphaned while it is still loading",
                    "scale-to-zero is a false economy here: the first request after a scale-up pays the full cold start plus, if not baked, a 360 MiB model fetch",
                ],
            },
        },
        # ── 4. Realtime factor ───────────────────────────────────────────────
        "answer_4_realtime_factor": {
            "question": "realtime factor on container-grade CPU",
            "kind": "NOT MEASURED",
            "container_value": None,
            "reason": "no Linux container can run on this host — see container_measurement_blocked",
            "_no_substitute_offered": (
                "The workstation figures below are NOT a stand-in for the container answer and "
                "must not be quoted as one. They are recorded because the CONTENTION IS ITSELF "
                "MEASURED, which is what makes them interpretable at all."
            ),
            "workstation_runs": all_rows,
            "contention": {
                "kind": "MEASURED",
                "metric": "thread_efficiency = cpu_seconds / (wall_seconds * threads_requested)",
                "observed": [0.099, 0.100, 0.171, 0.337, 0.361, 0.662],
                "finding": (
                    "Four other agents shared this host. The process asked for 4 threads and "
                    "received between 0.4 and 2.6 cores. Any realtime factor taken here is a "
                    "measurement of the box's load as much as of the workload."
                ),
            },
            "the_ratio_does_NOT_cancel_contention": {
                "kind": "MEASURED — and it falsifies this spike's own working assumption",
                "finding": (
                    "align_cpu/asr_cpu was expected to be contention-invariant, because both "
                    "stages run in the same process in the same run. IT IS NOT. It tracks "
                    "thread efficiency almost monotonically: 0.117 and 0.123 at efficiency "
                    "~0.10, 0.582 and 0.719 at ~0.35, and 0.916 at 0.662. ASR (ctranslate2 "
                    "int8, memory-bandwidth bound) degrades far more under contention than the "
                    "alignment forward pass does, so contention inflates the DENOMINATOR."
                ),
                "consequence": (
                    "the ratio measured at the CLEANEST observation is the least-wrong one, and "
                    "the trend says even it is a FLOOR: a truly idle box would likely show a "
                    "ratio above 0.916, not below. This is stated rather than buried because "
                    "the cost correction below rests on it."
                ),
                "ratio_by_efficiency": [
                    {"thread_efficiency": r["thread_efficiency"], "align_cpu_over_asr_cpu": r["align_cpu_over_asr_cpu"], "lang": r["lang"], "chunked": bool(r["align_chunk_seconds"])}
                    for r in all_rows
                ],
            },
            "instrument_validation": {
                "kind": "MEASURED",
                "claim": "the harness reproduces SPIKE A's ASR measurement, which is why its ALIGNMENT measurement can be trusted alongside it",
                "this_spike_asr_cpu_s_per_audio_s": c["asr_cpu_s_per_audio_s"],
                "spike_a_asr_cpu_s_per_audio_s_range": SPIKE_A_ASR_CPU_S_PER_AUDIO_S,
                "falls_inside_spike_a_range": asr_reproduced,
                "why_this_matters": (
                    "at the cleanest observation the ASR-only figure lands INSIDE the band "
                    "SPIKE A measured on a different day. That is an independent reproduction "
                    "of SPIKE A's ASR number, and it means the pipeline figure from the same "
                    "run differs from SPIKE A's only by the stage SPIKE A never timed."
                ),
            },
        },
        # ── 5. Does the cost figure survive? ─────────────────────────────────
        "answer_5_cost_figure": {
            "question": "does $0.165-$0.224 per 9-hour book survive?",
            "verdict": "NO — it is an undercount, on three independent grounds. The DECISION it was used for survives; the number does not.",
            "published_figure": {
                "usd_per_9h_book": [0.165, 0.224],
                "derivation_confirmed": (
                    "9 x compute_cost_per_audio_hour_usd from aligner/spike-a/out/"
                    "spike-a-results.json, whose entries are 0.0183 / 0.0213 / 0.0249. "
                    "9 x 0.0183 = 0.165 and 9 x 0.0249 = 0.224. Reproduced exactly."
                ),
            },
            "defect_1_missing_stages": {
                "kind": "MEASURED (the ratio) -> ESTIMATED (the corrected range)",
                "severity": "the load-bearing one",
                "finding": (
                    "THE FIGURE TIMES ONE STAGE OF A THREE-STAGE PIPELINE. "
                    "aligner/spike-a/measure.py wraps `model.transcribe` and nothing else, so "
                    "compute_cost_per_audio_hour_usd is ASR ONLY. Spec §6.1 ships "
                    "`ASR -> forced alignment -> match`. Forced alignment is timed nowhere in "
                    "SPIKE A, and it is not a rounding error: at the cleanest observation it "
                    "costs 92% of the ASR stage again."
                ),
                "align_cpu_over_asr_cpu_cleanest": c["align_cpu_over_asr_cpu"],
                "pipeline_multiplier": multiplier,
                "corrected_range_usd_per_9h_book": corrected,
                "derivation": (
                    f"published range x {multiplier}, where the multiplier is "
                    f"1 + align_cpu/asr_cpu measured at the cleanest observation "
                    f"(thread efficiency {c['thread_efficiency']}). The base cost is SPIKE A's "
                    "and inherits its own limits, including a rate basis its artifact labels "
                    "an ASSUMPTION."
                ),
                "direction_of_error": (
                    "this correction is a FLOOR. The ratio rises with thread efficiency across "
                    "six observations, so an uncontended box would likely push the multiplier "
                    "above 1.916, not below."
                ),
                "still_not_included": "the match step, Python string work in worker/src/normalize/, timed by neither spike",
            },
            "defect_2_memory_is_not_billed_at_all": {
                "kind": "ESTIMATED",
                "severity": "material — plausibly the same order as the compute term",
                "finding": (
                    "Railway bills memory as well as CPU and the cost model has NO memory term. "
                    "At a measured peak of 2.8-4.5 GiB per segment, memory is not a rounding "
                    "error on a $0.02/audio-hour compute figure."
                ),
                "railway_rates_verbatim": {
                    "cpu": "$20 / vCPU / month ($0.000463 / vCPU / minute)",
                    "ram": "$10 / GB / month ($0.000231 / GB / minute)",
                    "basis": "\"You are only charged for the resources you actually use\"",
                    "source": "https://docs.railway.com/reference/pricing, fetched 2026-08-10",
                },
                "cpu_rate_now_vendor_confirmed": (
                    "SPIKE A's $0.000463/vCPU-minute ASSUMPTION MATCHES the vendor's published "
                    "rate. That upgrades it from unverified to vendor-confirmed. It does NOT "
                    "discharge the artifact's own instruction to re-derive against an invoice: "
                    "published and billed rates differ by plan and commitment, and the artifact "
                    "asked for the invoice specifically."
                ),
                "why_not_quantified_here": (
                    "Billing is on consumption over time, so the needed input is MEAN RSS over "
                    "the run. This harness measures the PEAK — the right number for a memory "
                    "LIMIT and the wrong one for a bill. Producing a mean needs a sampler this "
                    "spike did not build. Quoting a cost from a peak would overstate it, and "
                    "inventing a mean is the failure this spike exists to avoid."
                ),
                "order_of_magnitude_illustration_NOT_a_result": (
                    "at 1 GiB mean over the container time a 9-hour book implies, "
                    "$0.01386/GiB-hour adds a few cents per book — i.e. the same order as the "
                    "entire published compute figure. That is the reason it cannot stay omitted."
                ),
            },
            "defect_3_headline_realtime_factor_is_unsourced": {
                "kind": "MEASURED (by reading the artifacts)",
                "severity": "the familiar one",
                "finding": (
                    "The roadmap publishes \"0.162x realtime, CPU only\" beside "
                    "\"$0.165-$0.224\". The cost half comes from spike-a-results.json, whose "
                    "realtime_factor_amortised values are 0.226 / 0.216 / 0.241 — that file "
                    "never produces 0.162. NO ARTIFACT under aligner/spike-a/out/ contains "
                    "0.162 at all. The nearest value on disk is 0.163, in "
                    "spike-a-reference.json — a DIFFERENT run, whose costs are $0.0143-$0.0198 "
                    "per audio-hour, i.e. $0.129-$0.178 per book."
                ),
                "consequence": (
                    "the published pair is a realtime factor from one run beside a cost from "
                    "another. That is the mixed-artifact defect J29-M1 recorded as \"No run "
                    "produces the pair\", reproduced in the sentence that quotes the result. "
                    "Quote spike-a-results.json (0.216-0.241 with $0.165-$0.224) or "
                    "spike-a-reference.json (0.146-0.207 with $0.129-$0.178). Not one from each."
                ),
                "spike_a_results_json": {"rtf": [0.216, 0.241], "usd_per_9h_book": [0.165, 0.224]},
                "spike_a_reference_json": {"rtf": [0.146, 0.207], "usd_per_9h_book": [0.129, 0.178]},
            },
            "bottom_line": {
                "compute_only_corrected_usd_per_9h_book": corrected,
                "kind": "ESTIMATED, and a FLOOR",
                "still_missing": [
                    "memory, which is billed and unmodelled",
                    "the match step",
                    "container-grade CPU verification — the whole of answer_4",
                ],
                "does_the_decision_survive": (
                    "YES. Hypereal is $5.40 per 9-hour book. The corrected self-hosted compute "
                    "figure is ~$0.32-$0.43, still more than an order of magnitude below it, "
                    "and memory would have to be ~12x the compute term to change that. THE "
                    "BUILD-VERSUS-BUY DECISION DOES NOT FLIP. That is why none of this is a "
                    "Blocker: the decision the number was used for survives, the number itself "
                    "does not, and it should stop being quoted at its published value."
                ),
            },
        },
        "runs": runs,
        "_limits": [
            "NO CONTAINER WAS EVER BUILT OR RUN. Every figure here is from the Windows workstation or from static analysis of the resolved wheel set. The container column of this spike is unanswered and is not simulated.",
            "The host ran four other agents throughout. Measured thread efficiency ranged 0.10-0.66 against 4 requested threads, so all wall-clock and most CPU-second figures are inflated by a disclosed but not fully correctable amount.",
            "The workstation is an AMD EPYC guest with 4 logical CPUs. That is not the container-grade CPU the roadmap asked about.",
            "The alignment stage measured here is the torchaudio bundle FORWARD PASS (emission computation). It excludes the Viterbi backtrace — cheap but nonzero — and the match step entirely.",
            "whisperx STILL has not executed anywhere in this project. Its alignment module does not import on this host's transformers 5.14.1, exactly as aligner/spike-a/out/spike-a-whisperx.json recorded. requirements-whisperx.txt pins transformers>=4.48,<5 to fix this and THAT FIX IS UNVERIFIED, because the container cannot be built here. The lean stack sidesteps it by driving torchaudio directly.",
            "Cold start was measured with a warm page cache and warm model files, so it is a floor.",
            "Peak RSS is a per-PROCESS high-water mark. A container running several worker processes multiplies it.",
            "The 60 s unit of work was approximated with 73-77 s fixtures, the closest on disk. Alignment memory is quadratic in segment length, so a true 60 s segment peaks somewhat lower.",
            "The pipeline multiplier rests on a SINGLE cleanest observation (en, thread efficiency 0.662). It is the best available, not a converged estimate, and it should be re-measured in a container before it is quoted in a decision — the same instruction SPIKE A attached to its own rate basis.",
        ],
        "_cross_scope_needs": [
            "Forge (worker/src/): the aligner must be a long-lived, model-resident worker, not a per-job container. Cold start is ~17 s warm, per language, and is a floor.",
            "Forge: decide whether the match step tolerates a seam every N seconds. If it does, chunked alignment cuts the container memory requirement from ~5 GiB to ~2.5 GiB — a 2x difference in how many workers fit per node. This spike measures the trade; it does not own the call.",
            "Forge / whoever owns aligner/spike-a/: compute_cost_per_audio_hour_usd should either be RENAMED to say it is ASR-only, or extended to time the alignment stage. Today the name claims the pipeline and the code times one third of it. I did not edit spike-a — out of scope.",
            "Scribe: the roadmap's SPIKE A item 3 pairs '0.162x realtime' with '$0.165-$0.224'. No run produces that pair; 0.162 appears in no artifact. Documents are out of my scope; the correction is in answer_5_cost_figure.defect_3.",
            "Whoever owns CI (.github/): the only way to finish this spike is a linux/amd64 Docker daemon. A GitHub Actions ubuntu-latest job running the commands in container_measurement_blocked.what_would_be_needed closes it. I did not touch .github/ — out of scope.",
            "Ledger / whoever owns the unit-cost model: this artifact's dollars are SELF-HOSTED COMPUTE. Oracle's $8.10-$8.33 is TTS VENDOR SPEND. They are additive terms in the per-book unit cost, not alternatives.",
        ],
    }

    OUT.mkdir(exist_ok=True)
    path = OUT / "spike-e-results.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {path}")
    print(f"  runs={len(runs)} oneshot={len(oneshot)} chunked={len(chunked)}")
    print(f"  cleanest={c['label']} eff={c['thread_efficiency']} ratio={c['align_cpu_over_asr_cpu']}")
    print(f"  ASR reproduces SPIKE A band: {asr_reproduced} ({c['asr_cpu_s_per_audio_s']} in {SPIKE_A_ASR_CPU_S_PER_AUDIO_S})")
    print(f"  multiplier={multiplier}  corrected=${corrected['min_usd']}-${corrected['max_usd']} per 9h book")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
