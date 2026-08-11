#!/usr/bin/env python3
"""
SPIKE E, the CONTAINER half — assemble one artifact from a CI run, and refuse to
emit a green result that measured nothing.

WHY THIS EXISTS. `spike-e-results.json` answered image size, memory and cold
start from the Windows workstation and left the roadmap's actual question —
realtime factor on container-grade CPU — as `container_value: null`, `kind:
"NOT MEASURED"`. That refusal stands. The only way to discharge it is a Linux
container, and the only Linux Docker daemon this project can reach is a GitHub
Actions runner. `.github/workflows/spike-e-container.yml` runs the four commands
the artifact named; this script turns their output into the artifact and then
checks it.

WHAT IT WILL NOT DO. It does not compute a figure the runs did not produce. If
the required runs are missing, `--verify` exits non-zero and the job goes red —
because the failure this whole spike exists to avoid is a number that looks
measured and is not (`J29-M1`, `J30-m1`, `J32-M1`, `J32-M2`, `J32-M4`, all one
defect). Three guards enforce that mechanically:

  1. every required run is present and terminated successfully;
  2. every load-bearing key is non-null;
  3. EVERY dict holding a number carries a `kind` label, in itself or in an
     ancestor. An unlabelled number cannot reach the artifact.

Guard 3 is the one that generalises: the others check the keys we thought of
today, and it checks the keys somebody adds next.

  python ci_collect.py --self-test                 # prove the guards bite
  python ci_collect.py --runs-dir out/ci ... --out out/spike-e-container.json
  python ci_collect.py --verify out/spike-e-container.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

# ── Constants that are somebody else's measurement, quoted with their source ──
# Railway's PUBLISHED rates. `spike-e-results.json` records that the CPU rate
# matches SPIKE A's previously-unverified ASSUMPTION, which upgraded it to
# vendor-confirmed, and that this does NOT discharge the instruction to
# re-derive against a real invoice.
RAILWAY_USD_PER_VCPU_MINUTE = 0.000463
RAILWAY_USD_PER_GB_MINUTE = 0.000231
RAILWAY_RATES_SOURCE = "https://docs.railway.com/reference/pricing, fetched 2026-08-10"

# The reference book. 9 hours of audio, the unit every per-book figure in this
# project is denominated in.
BOOK_AUDIO_HOURS = 9.0

# A per-job container is refused when startup costs at least this share of the
# work it then performs. The THRESHOLD IS A CHOICE, not a measurement, and is
# labelled ASSUMPTION wherever it appears.
PER_JOB_REFUSAL_THRESHOLD = 0.25

# The runs the job must produce for the artifact to mean anything. Anything else
# is a scaling curve or a second language and may legitimately be absent — a
# 2-vCPU runner cannot honour `--cpus 4`, and skipping it is correct where
# reporting it as a 4-vCPU figure would be a lie about the population.
REQUIRED_RUNS = ("en-c2-oneshot-warm", "en-c2-chunk15-warm", "en-c2-coldstart")


def mib(n):
    return None if n is None else round(n / (1024 * 1024), 1)


def gib(n):
    return None if n is None else round(n / (1024 * 1024 * 1024), 3)


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


# ── Guard 3: no unlabelled numbers ───────────────────────────────────────────


def unlabelled_number_paths(node, path="", labelled=False):
    """Every dict that holds a number without a `kind` label above it.

    A `kind` on an ancestor covers its descendants — that is how
    `spike-e-results.json` already labels, and re-stating it on every leaf would
    make the artifact unreadable. What is forbidden is a number with NO label
    anywhere on its path to the root.
    """
    bad = []
    if isinstance(node, dict):
        here = labelled or ("kind" in node) or ("_kind" in node)
        holds_number = any(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in node.values()
        ) or any(
            isinstance(v, list)
            and any(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)
            for v in node.values()
        )
        if holds_number and not here:
            bad.append(path or "<root>")
        for key, value in node.items():
            bad.extend(unlabelled_number_paths(value, f"{path}.{key}", here))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            bad.extend(unlabelled_number_paths(value, f"{path}[{i}]", labelled))
    return bad


# ── Loading the runs ─────────────────────────────────────────────────────────


def load_runs(runs_dir):
    """Join every attempted run's META with its MEASUREMENT, if one exists.

    The meta file is written BEFORE the container starts and always exists. That
    is the point: a run killed by the memory limit writes no measurement, and a
    collector that enumerated measurements would silently forget the run ever
    happened — turning the most interesting outcome in the matrix (the
    recommended limit was too small) into an absence.
    """
    runs = []
    if not os.path.isdir(runs_dir):
        return runs
    for name in sorted(os.listdir(runs_dir)):
        if not name.endswith(".meta.json"):
            continue
        run_id = name[: -len(".meta.json")]
        meta = read_json(os.path.join(runs_dir, name), {}) or {}
        measurement = read_json(os.path.join(runs_dir, run_id + ".json"))
        ok = bool(measurement) and meta.get("exit_code") == 0
        runs.append(
            {
                "run_id": run_id,
                "_kind": "MEASURED",
                "status": "ok" if ok else "FAILED",
                "meta": meta,
                "measurement": measurement,
                "_failure_reading": None
                if ok
                else (
                    "exit 137 is the kernel OOM killer: the container asked for more "
                    "memory than its limit allowed. That is a RESULT about the limit, "
                    "not a broken job."
                    if meta.get("exit_code") == 137
                    else f"container exited {meta.get('exit_code')} and wrote no measurement"
                ),
            }
        )
    return runs


def ok_runs(runs):
    return [r for r in runs if r["status"] == "ok"]


def find_run(runs, run_id):
    for r in runs:
        if r["run_id"] == run_id:
            return r
    return None


def derived(run, key, default=None):
    if not run or not run.get("measurement"):
        return default
    return run["measurement"].get("derived", {}).get(key, default)


def stage(run, key, default=None):
    if not run or not run.get("measurement"):
        return default
    return run["measurement"].get("stages", {}).get(key, default)


# ── The artifact ─────────────────────────────────────────────────────────────


def build(args):
    runs = load_runs(args.runs_dir)
    host_facts = read_json(args.host_facts, {}) or {}
    build_facts = read_json(args.build_facts, {}) or {}
    prior = read_json(args.spike_e_results, {}) or {}
    spike_a = read_json(args.spike_a_results, []) or []

    prior_estimate = prior.get("answer_1_image_size", {}).get("estimated_image_size_mib", {})
    prior_memory = prior.get("answer_2_memory", {}).get("headline", {})
    prior_cold = prior.get("answer_3_cold_start", {}).get("cleanest_observation", {})
    prior_multiplier = (
        prior.get("answer_5_cost_figure", {})
        .get("defect_1_missing_stages", {})
        .get("pipeline_multiplier")
    )

    # The published ASR-ONLY per-audio-hour costs, read from SPIKE A rather than
    # copied here. A constant duplicated across two files is a constant that
    # goes stale in one of them.
    asr_only_hourly = sorted(
        r["compute_cost_per_audio_hour_usd"]
        for r in spike_a
        if isinstance(r, dict) and r.get("compute_cost_per_audio_hour_usd") is not None
    )
    asr_only_book = (
        [round(asr_only_hourly[0] * BOOK_AUDIO_HOURS, 4), round(asr_only_hourly[-1] * BOOK_AUDIO_HOURS, 4)]
        if asr_only_hourly
        else None
    )

    # ── The chosen run. One run, named, and every headline figure comes from it.
    # SPIKE A published a realtime factor from one run beside a cost from
    # another (`J29-M1`, four occurrences). The defence is to pick ONE run for
    # the pair and say which.
    warm_en_oneshot = [
        r
        for r in ok_runs(runs)
        if r["meta"].get("lang") == "en"
        and float(r["meta"].get("align_chunk_s", 0) or 0) == 0.0
        and r["meta"].get("page_cache") == "warm"
    ]
    chosen = max(
        warm_en_oneshot,
        key=lambda r: derived(r, "thread_efficiency") or 0.0,
        default=None,
    )

    rtf_pipeline = derived(chosen, "realtime_factor_pipeline_amortised")
    cpu_s_per_audio_s = derived(chosen, "cpu_seconds_per_audio_second_pipeline")
    transcribe_cpu = stage(chosen, "transcribe_cpu_s")
    align_cpu = stage(chosen, "align_cpu_s")
    ratio = (
        round(align_cpu / transcribe_cpu, 4)
        if (transcribe_cpu and align_cpu is not None)
        else None
    )
    multiplier = None if ratio is None else round(1.0 + ratio, 4)

    # ── Cost, three terms, each labelled and each naming its inputs ──────────
    corrected_range = (
        [round(asr_only_book[0] * multiplier, 4), round(asr_only_book[1] * multiplier, 4)]
        if (asr_only_book and multiplier)
        else None
    )
    direct_compute_usd = (
        round(
            cpu_s_per_audio_s
            * BOOK_AUDIO_HOURS
            * 3600.0
            * (RAILWAY_USD_PER_VCPU_MINUTE / 60.0),
            4,
        )
        if cpu_s_per_audio_s
        else None
    )

    mean_block = (chosen or {}).get("measurement", {}).get("rss_mean", {}) if chosen else {}
    mean_steady = (mean_block or {}).get("after_models_loaded", {}) or {}
    mean_bytes = mean_steady.get("mean_bytes")
    busy_minutes = (
        BOOK_AUDIO_HOURS * 60.0 * rtf_pipeline if rtf_pipeline else None
    )
    memory_usd = (
        round((mean_bytes / 1e9) * busy_minutes * RAILWAY_USD_PER_GB_MINUTE, 4)
        if (mean_bytes and busy_minutes)
        else None
    )

    # ── Cold start, and whether the Phase 7 architecture survives it ─────────
    cold = find_run(runs, "en-c2-coldstart")
    cold_import = stage(cold, "import_faster_whisper_s")
    cold_total = derived(cold, "cold_start_seconds_asr_plus_align")
    cold_startup_total = (
        round((cold_import or 0.0) + (cold_total or 0.0), 3)
        if (cold_import is not None or cold_total is not None)
        else None
    )
    cold_work_wall = (
        round((stage(cold, "transcribe_wall_s") or 0.0) + (stage(cold, "align_wall_s") or 0.0), 3)
        if cold and cold.get("measurement")
        else None
    )
    startup_share = (
        round(cold_startup_total / cold_work_wall, 4)
        if (cold_startup_total and cold_work_wall)
        else None
    )

    art = {
        "spike": "E",
        "subject": "aligner container sizing — THE CONTAINER HALF",
        "owner": "Queue",
        "produced_by": ".github/workflows/spike-e-container.yml",
        "companion_artifact": "aligner/spike-e/out/spike-e-results.json",
        "_label_key": {
            "MEASURED": "observed by a command this CI run executed",
            "ESTIMATED": "arithmetic over MEASURED inputs, or a cited third-party figure; `derivation` names the inputs",
            "ASSUMPTION": "an input nobody here verified",
        },
        "_what_this_closes": (
            "`spike-e-results.json` left `answer_4_realtime_factor.container_value` "
            "null with kind NOT MEASURED, because no Linux container can run on the "
            "Windows host. This file is the run that answers it. The host artifact is "
            "NOT superseded: its dependency-closure and model-size measurements are "
            "still the source for those, and its host-side figures remain the "
            "contended-workstation column."
        ),
        "provenance": {
            "kind": "MEASURED",
            "git_commit": build_facts.get("git_commit"),
            "workflow_run_url": build_facts.get("workflow_run_url"),
            "date_utc": build_facts.get("date_utc"),
            "runner": host_facts,
            "_the_runner_is_not_the_deploy_target": (
                "A GitHub Actions runner is container-grade CPU on somebody else's "
                "cloud; Railway is container-grade CPU on Railway's. The CPU model is "
                "recorded above so the figure travels with the box it came from, and "
                "no figure here may be quoted as a Railway measurement."
            ),
        },
        "answer_0_self_sufficiency": build_facts.get(
            "self_sufficiency",
            {
                "kind": "NOT MEASURED",
                "_reason": "the offline probe did not run, so nothing here says whether the baked image can render without reaching a CDN",
            },
        ),
        "answer_1_image_size": {
            "kind": "MEASURED",
            "question": "how large is the container once WhisperX, torch and the models are in it?",
            "repro": "docker image inspect --format '{{.Size}}'",
            "runtime_bytes": build_facts.get("runtime_image_bytes"),
            "runtime_mib": mib(build_facts.get("runtime_image_bytes")),
            "baked_bytes": build_facts.get("baked_image_bytes"),
            "baked_mib": mib(build_facts.get("baked_image_bytes")),
            "runtime_build_seconds": build_facts.get("runtime_build_seconds"),
            "baked_build_seconds": build_facts.get("baked_build_seconds"),
            "prior_estimate_mib": {
                "kind": "ESTIMATED — quoted from spike-e-results.json, not recomputed here",
                "lean_runtime_no_models": prior_estimate.get("lean_runtime_no_models"),
                "lean_baked_en_es_fr": prior_estimate.get("lean_baked_en_es_fr"),
            },
            "estimate_error_pct": {
                "kind": "ESTIMATED",
                "derivation": "(measured - estimated) / estimated x 100, per target",
                "runtime": _pct_error(
                    mib(build_facts.get("runtime_image_bytes")),
                    prior_estimate.get("lean_runtime_no_models"),
                ),
                "baked": _pct_error(
                    mib(build_facts.get("baked_image_bytes")),
                    prior_estimate.get("lean_baked_en_es_fr"),
                ),
            },
        },
        "answer_2_memory": {
            "kind": "MEASURED",
            "question": "peak RSS under a container memory limit, and the MEAN the platform bills",
            "_peak_versus_mean": (
                "Two different numbers with two different jobs. The PEAK sizes the "
                "memory limit — exceed it and the kernel kills the container. The MEAN "
                "is what Railway charges for at $0.000231/GB-minute. The host artifact "
                "could only report the peak and said so; this run reports both."
            ),
            "by_run": [
                {
                    "run_id": r["run_id"],
                    "kind": "MEASURED",
                    "status": r["status"],
                    "lang": r["meta"].get("lang"),
                    "cpus": r["meta"].get("cpus"),
                    "align_chunk_s": r["meta"].get("align_chunk_s"),
                    "memory_limit_requested": r["meta"].get("memory_limit"),
                    "cgroup_memory_limit_bytes": (r.get("measurement") or {})
                    .get("hardware", {})
                    .get("cgroup_memory_limit_bytes"),
                    "peak_rss_mib": derived(r, "peak_rss_max_mib"),
                    "mean_rss_steady_state_mib": (
                        ((r.get("measurement") or {}).get("rss_mean", {}) or {})
                        .get("after_models_loaded", {})
                        or {}
                    ).get("mean_mib"),
                    "mean_rss_whole_run_mib": (
                        ((r.get("measurement") or {}).get("rss_mean", {}) or {}).get(
                            "whole_run", {}
                        )
                        or {}
                    ).get("mean_mib"),
                    "_failure_reading": r["_failure_reading"],
                }
                for r in runs
            ],
            "host_comparison": {
                "kind": "MEASURED — quoted from spike-e-results.json",
                "host_one_shot_peak_mib": prior_memory.get("one_shot_60s_segment_peak_mib"),
                "host_chunked_15s_peak_mib": prior_memory.get("chunked_15s_peak_mib"),
                "_read_this_as": (
                    "The host peaks were CONTENTION-INDEPENDENT across two runs 0.3% "
                    "apart, so a container figure that differs materially is a "
                    "property of the container, not of load."
                ),
            },
            "recommended_limit_under_test": {
                "kind": "MEASURED",
                "_what_was_tested": (
                    "spike-e-results.json recommends 5 GiB unchunked and 2.5 GiB "
                    "chunked. The matrix runs at exactly those limits so the "
                    "recommendation is tested rather than restated; an OOM kill at "
                    "either is a result, and the matrix carries a higher-limit run so "
                    "a realtime factor still exists if one dies."
                ),
                "_the_required_runs_do_not_test_a_tight_limit": (
                    "The three runs `--verify` requires all run at a generous limit, so "
                    "a correct answer of 'the recommendation is too small' cannot take "
                    "the whole artifact down with it. These two rows are the "
                    "recommendation test and they are allowed to fail."
                ),
                "unchunked_5120m_survived": _survived(find_run(runs, "en-c2-oneshot-5g")),
                "chunked_2560m_survived": _survived(find_run(runs, "en-c2-chunk15-2560m")),
            },
        },
        "answer_3_cold_start": {
            "kind": "MEASURED",
            "question": "cold start from a COLD page cache — does the long-lived-worker verdict survive?",
            "_what_cold_means_here": (
                "The page cache is dropped (`vm.drop_caches=3`) immediately before "
                "this run, so the container reads its layers and its model weights "
                "from disk. It does NOT include a registry pull: the image is already "
                "in the local store because this job built it. A first start on a "
                "fresh node also pays the pull, so this remains a FLOOR."
            ),
            "page_cache_actually_achieved": (cold or {}).get("meta", {}).get("page_cache"),
            "_read_the_line_above": (
                "`cold` means the page cache was dropped and the drop was checked. "
                "`cold-DROP-FAILED` means it was not, and every figure in this block is "
                "then a WARM measurement and must not be quoted as a cold start."
            ),
            "cold_import_faster_whisper_s": cold_import,
            "cold_model_load_s": cold_total,
            "cold_startup_total_s": cold_startup_total,
            "work_wall_s_same_run": cold_work_wall,
            "startup_share_of_work": startup_share,
            "host_comparison": {
                "kind": "MEASURED — quoted from spike-e-results.json (warm cache, quiet box)",
                "asr_model_load_s": prior_cold.get("asr_model_load_s"),
                "align_model_load_s": prior_cold.get("align_model_load_s"),
                "cold_start_total_s": prior_cold.get("cold_start_total_s"),
                "import_faster_whisper_s": prior_cold.get("import_faster_whisper_s"),
            },
            "per_job_container_refused": {
                "kind": "ESTIMATED",
                "derivation": (
                    "startup_share_of_work >= threshold, where startup is "
                    "import + model load on a cold page cache and work is the "
                    "transcribe + align wall time of the SAME run"
                ),
                "threshold": PER_JOB_REFUSAL_THRESHOLD,
                "_threshold_is_a_choice": "ASSUMPTION. The threshold is a judgement, not a measurement; the ratio beside it is measured.",
                "verdict": None
                if startup_share is None
                else bool(startup_share >= PER_JOB_REFUSAL_THRESHOLD),
                "_consequence_if_false": (
                    "roadmap Phase 7's first item — 'The aligner is a LONG-LIVED, "
                    "MODEL-RESIDENT worker' — rests on this. If a container start is "
                    "cheap here, that item is re-opened rather than quietly kept."
                ),
            },
        },
        "answer_4_realtime_factor": {
            "kind": "MEASURED" if rtf_pipeline is not None else "NOT MEASURED",
            "question": "realtime factor on container-grade CPU",
            "container_value": rtf_pipeline,
            "_this_is_the_key_that_was_null": (
                "spike-e-results.json:answer_4_realtime_factor.container_value was "
                "null with kind NOT MEASURED and `_no_substitute_offered`. This is the "
                "same quantity, measured."
            ),
            "from_run": (chosen or {}).get("run_id"),
            "realtime_factor_transcribe_only": derived(chosen, "realtime_factor_transcribe_only"),
            "realtime_factor_pipeline_amortised": rtf_pipeline,
            "realtime_factor_including_model_load": derived(
                chosen, "realtime_factor_pipeline_including_model_load"
            ),
            "cpu_seconds_per_audio_second_pipeline": cpu_s_per_audio_s,
            "cpu_seconds_per_audio_second_transcribe_only": derived(
                chosen, "cpu_seconds_per_audio_second_transcribe_only"
            ),
            "thread_efficiency": derived(chosen, "thread_efficiency"),
            "cores_actually_received": derived(chosen, "cores_actually_received"),
            "_population": {
                "kind": "MEASURED",
                "lang": (chosen or {}).get("meta", {}).get("lang"),
                "cpus": (chosen or {}).get("meta", {}).get("cpus"),
                "align_chunk_s": (chosen or {}).get("meta", {}).get("align_chunk_s"),
                "audio_seconds": ((chosen or {}).get("measurement") or {}).get("audio_seconds"),
                "asr_model": ((chosen or {}).get("measurement") or {}).get("asr_model"),
                "_why_this_block_exists": (
                    "A figure travels with the population it was measured on — the "
                    "language, the model, the clip length, the CPU quota. A dimension "
                    "this run did not vary is a dimension the sentence quoting it may "
                    "not generalise over."
                ),
            },
            "scaling_curve": {
                "kind": "MEASURED",
                "_note": "one row per CPU quota that the runner could honour; a quota above the runner's core count is SKIPPED, never reported",
                "rows": [
                    {
                        "run_id": r["run_id"],
                        "cpus": r["meta"].get("cpus"),
                        "lang": r["meta"].get("lang"),
                        "align_chunk_s": r["meta"].get("align_chunk_s"),
                        "realtime_factor_pipeline_amortised": derived(
                            r, "realtime_factor_pipeline_amortised"
                        ),
                        "cpu_seconds_per_audio_second_pipeline": derived(
                            r, "cpu_seconds_per_audio_second_pipeline"
                        ),
                        "thread_efficiency": derived(r, "thread_efficiency"),
                    }
                    for r in ok_runs(runs)
                ],
            },
            "skipped": build_facts.get("skipped_runs", []),
        },
        "answer_5_cost_figure": {
            "kind": "ESTIMATED",
            "question": "does the corrected $0.316-$0.429 floor survive a container?",
            "_two_independent_derivations": (
                "The first rescales SPIKE A's published ASR-only cost by the pipeline "
                "multiplier, which is how the $0.316-$0.429 figure was produced and is "
                "therefore the comparable one. The second bills the container's OWN "
                "measured CPU-seconds at the vendor rate and owes SPIKE A nothing. "
                "They should agree within the difference between the two boxes; if "
                "they do not, that gap is the finding."
            ),
            "pipeline_multiplier": {
                "kind": "MEASURED",
                "value": multiplier,
                "align_cpu_over_asr_cpu": ratio,
                "from_run": (chosen or {}).get("run_id"),
                "thread_efficiency_of_that_run": derived(chosen, "thread_efficiency"),
                "host_value_it_replaces": prior_multiplier,
                "_why_it_may_move": (
                    "The host measured 1.916 at thread efficiency 0.662 and recorded "
                    "that the ratio tracks efficiency almost monotonically across six "
                    "observations — so the host figure was published as a FLOOR. A "
                    "runner is a dedicated VM; if its efficiency is higher, the "
                    "multiplier is expected to RISE."
                ),
            },
            "derivation_1_rescaled_spike_a": {
                "kind": "ESTIMATED",
                "derivation": "9 x compute_cost_per_audio_hour_usd from spike-a-results.json, x the container pipeline multiplier above",
                "asr_only_usd_per_9h_book": asr_only_book,
                "corrected_usd_per_9h_book": corrected_range,
                "_inherits": "SPIKE A's rate basis and its ASR measurement, including their limits",
            },
            "derivation_2_container_cpu_seconds": {
                "kind": "ESTIMATED",
                "derivation": (
                    "cpu_seconds_per_audio_second_pipeline (MEASURED, this container) "
                    "x 9 h x 3600 s/h x ($0.000463 per vCPU-minute / 60)"
                ),
                "cpu_seconds_per_audio_second_pipeline": cpu_s_per_audio_s,
                "usd_per_9h_book": direct_compute_usd,
                "rate_source": RAILWAY_RATES_SOURCE,
                "_owes_spike_a_nothing": "this term is computed from this run's own CPU-seconds",
            },
            "memory_term": {
                "kind": "ESTIMATED",
                "_this_was_previously_unquantified": (
                    "spike-e-results.json:defect_2_memory_is_not_billed_at_all declined "
                    "to put a number on memory because billing needs a MEAN and the "
                    "harness measured a PEAK. measure.py now samples the mean, so the "
                    "term exists — but a bill also needs a DUTY CYCLE, and that is "
                    "still unmeasured."
                ),
                "mean_rss_steady_state_bytes": mean_bytes,
                "mean_rss_steady_state_gib": gib(mean_bytes),
                "busy_minutes_per_9h_book": None if busy_minutes is None else round(busy_minutes, 2),
                "usd_per_9h_book_at_full_duty": memory_usd,
                "derivation": (
                    "mean steady-state RSS in GB x (9 h x 60 min x realtime factor) x "
                    "$0.000231 per GB-minute"
                ),
                "duty_cycle_assumed": "ASSUMPTION — the container is billed only while computing. A long-lived worker holding models resident between jobs is billed for that time too, so this term is a FLOOR.",
                "rate_source": RAILWAY_RATES_SOURCE,
            },
            "bottom_line": {
                "kind": "ESTIMATED, and still a FLOOR",
                "compute_plus_memory_usd_per_9h_book": None
                if (direct_compute_usd is None or memory_usd is None)
                else round(direct_compute_usd + memory_usd, 4),
                "still_missing": [
                    "the match step and the normalizer, timed by neither spike",
                    "the duty cycle of a long-lived worker between jobs",
                    "a real Railway invoice — the rates here are the vendor's published ones",
                    "any language but the one the chosen run used",
                ],
            },
        },
        "runs": runs,
        "_limits": [
            "The runner is a GitHub Actions VM, not Railway. It is container-grade CPU, which is what the roadmap asked for, and it is not the deploy target's CPU.",
            "Cold start excludes the registry pull, because the image was built on the same machine that ran it. A first start on a fresh node pays more.",
            "The memory bill needs a duty cycle nobody has measured. The figure here assumes the container exists only while it computes, which is a floor.",
            "One ASR model size (`base`) and one fixture per language, 73-77 s. Alignment memory is quadratic in segment length, so a different segmentation moves the memory answer.",
            "whisperx is still not measured here: the `whisperx` build target is not part of this job, so `requirements-whisperx.txt`'s transformers pin remains UNVERIFIED.",
        ],
        "_what_moves_in_the_documents": [],
    }

    art["_what_moves_in_the_documents"] = _document_deltas(art, prior)
    return art


def _pct_error(measured, estimated):
    if measured is None or not estimated:
        return None
    return round((measured - estimated) / estimated * 100.0, 1)


def _survived(run):
    if run is None:
        return None
    return run["status"] == "ok"


def _document_deltas(art, prior):
    """The strings that go stale the moment this artifact is committed.

    Mechanical, not remembered. `CLAUDE.md`'s reconciliation pass says the hit
    list is produced BEFORE the edit and pasted into the revision header; this
    is the machine half of that for the figures this run moves.
    """
    out = []
    rtf = art["answer_4_realtime_factor"]["container_value"]
    if rtf is not None:
        out.append(
            {
                "find": "no container-grade realtime factor exists and none may be quoted",
                "where": "resources/roadmap — Phase 0 'Finish SPIKE E on a Linux container'",
                "why": f"one now exists: {rtf} (pipeline, amortised), and the Phase 0 item can close",
            }
        )
    est = art["answer_1_image_size"]["prior_estimate_mib"].get("lean_baked_en_es_fr")
    got = art["answer_1_image_size"]["baked_mib"]
    if est and got:
        out.append(
            {
                "find": "estimated_image_size_mib",
                "where": "aligner/spike-e/out/spike-e-results.json — answer_1_image_size",
                "why": f"the baked image is now MEASURED at {got} MiB against an ESTIMATED {est} MiB",
            }
        )
    mult = art["answer_5_cost_figure"]["pipeline_multiplier"]
    if mult.get("value") and mult.get("host_value_it_replaces"):
        if abs(mult["value"] - mult["host_value_it_replaces"]) > 0.05:
            out.append(
                {
                    "find": "1.916",
                    "where": "resources/roadmap, README.md, docs/architecture — the pipeline multiplier and the $0.32-$0.43 range derived from it",
                    "why": f"the container measures {mult['value']}; every site quoting 1.916 or the range it produced moves together",
                }
            )
    chunk_peaks = [
        row["peak_rss_mib"]
        for row in art["answer_2_memory"]["by_run"]
        if row.get("align_chunk_s") and row.get("peak_rss_mib")
    ]
    if chunk_peaks:
        out.append(
            {
                "find": "1,937 MiB",
                "where": "resources/roadmap (two sites), docs/architecture/0001",
                "why": f"the chunked peak in a container is {min(chunk_peaks)}-{max(chunk_peaks)} MiB",
            }
        )
    return out


# ── Verification ─────────────────────────────────────────────────────────────


def verify(path):
    art = read_json(path)
    problems = []
    if not isinstance(art, dict):
        print(f"VERIFY FAILED: {path} is not a JSON object", file=sys.stderr)
        return 1

    runs = art.get("runs", [])
    present = {r.get("run_id"): r for r in runs if isinstance(r, dict)}
    for run_id in REQUIRED_RUNS:
        run = present.get(run_id)
        if run is None:
            problems.append(
                f"required run `{run_id}` is absent. The matrix did not attempt it, or "
                f"its meta file was never written — either way nothing was measured."
            )
        elif run.get("status") != "ok":
            problems.append(
                f"required run `{run_id}` did not complete: {run.get('_failure_reading')}"
            )

    rtf = art.get("answer_4_realtime_factor", {}).get("container_value")
    if rtf is None:
        problems.append(
            "answer_4_realtime_factor.container_value is null. That is the ONE question "
            "this job exists to answer; a green run that leaves it null is the defect, "
            "not a partial success."
        )
    if art.get("answer_4_realtime_factor", {}).get("kind") == "MEASURED" and rtf is None:
        problems.append("answer_4_realtime_factor claims kind MEASURED with a null value")

    for key in ("runtime_bytes", "baked_bytes"):
        value = art.get("answer_1_image_size", {}).get(key)
        if not value:
            problems.append(f"answer_1_image_size.{key} is null or zero — no image was inspected")

    if art.get("answer_3_cold_start", {}).get("cold_startup_total_s") is None:
        problems.append("answer_3_cold_start.cold_startup_total_s is null — the cold-cache run produced nothing")

    # NOT a failure — a FINDING, and it must be impossible to miss. An image that
    # cannot load its own models offline has a CDN in its primary path, which is
    # `CLAUDE.md` constraint 2. Failing the job here would be wrong: the
    # measurement is still valid, and the finding is what needs reading.
    selfsuf = art.get("answer_0_self_sufficiency", {})
    if selfsuf.get("loads_all_models_offline") is False:
        print(
            "FINDING: the baked image could NOT load its models with the network removed. "
            "The `baked` target exists precisely so a render does not depend on reaching "
            "download.pytorch.org, so this is constraint 2 unmet — see "
            "answer_0_self_sufficiency.output_tail.",
            file=sys.stderr,
        )
    elif selfsuf.get("loads_all_models_offline") is None:
        print(
            "NOTE: the offline self-sufficiency probe did not run; nothing here shows the "
            "baked image is CDN-independent.",
            file=sys.stderr,
        )

    unlabelled = unlabelled_number_paths(art)
    for p in unlabelled:
        problems.append(
            f"unlabelled number at `{p}` — every block holding a figure needs MEASURED / "
            f"ESTIMATED / ASSUMPTION on it or on an ancestor"
        )

    if problems:
        print(f"VERIFY FAILED ({len(problems)} problem(s)) — {path}", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"VERIFY OK — {path}")
    print(f"  container realtime factor (pipeline, amortised): {rtf}")
    print(f"  baked image: {art['answer_1_image_size']['baked_mib']} MiB")
    print(f"  cold startup: {art['answer_3_cold_start']['cold_startup_total_s']} s")
    return 0


# ── Self-test: prove the guards bite, on synthetic input ─────────────────────


def _synthetic_run(run_id, lang, cpus, chunk, page_cache, transcribe_cpu, align_cpu, exit_code=0):
    """A measure.py-shaped record with ROUND numbers, so the arithmetic is checkable by hand."""
    meta = {
        "run_id": run_id,
        "lang": lang,
        "cpus": cpus,
        "align_chunk_s": chunk,
        "memory_limit": "5g",
        "page_cache": page_cache,
        "network": "none",
        "exit_code": exit_code,
    }
    if exit_code != 0:
        return meta, None
    measurement = {
        "_kind": "SYNTHETIC — self-test only, never a result",
        "audio_seconds": 100.0,
        "asr_model": "base",
        "stages": {
            "import_faster_whisper_s": 10.0,
            "asr_model_load_s": 2.0,
            "transcribe_wall_s": 50.0,
            "transcribe_cpu_s": transcribe_cpu,
            "align_model_load_s": 3.0,
            "align_wall_s": 20.0,
            "align_cpu_s": align_cpu,
        },
        "rss_mean": {
            "_kind": "SYNTHETIC",
            "whole_run": {"mean_mib": 800.0, "mean_bytes": 838860800, "n": 100},
            "after_models_loaded": {"mean_mib": 1000.0, "mean_bytes": 1000000000, "n": 50},
        },
        "derived": {
            "realtime_factor_transcribe_only": 0.5,
            "realtime_factor_pipeline_amortised": 0.7,
            "realtime_factor_pipeline_including_model_load": 0.75,
            "cpu_seconds_per_audio_second_pipeline": 1.0,
            "cpu_seconds_per_audio_second_transcribe_only": 0.6,
            "cold_start_seconds_asr_plus_align": 5.0,
            "thread_efficiency": 0.9,
            "cores_actually_received": 1.8,
            "peak_rss_max_mib": 2000.0,
        },
        "hardware": {"cgroup_memory_limit_bytes": 5368709120},
    }
    return meta, measurement


def self_test():
    failures = []

    def check(label, condition, detail=""):
        if condition:
            print(f"  ok   {label}")
        else:
            print(f"  FAIL {label} {detail}")
            failures.append(label)

    with tempfile.TemporaryDirectory() as tmp:
        runs_dir = os.path.join(tmp, "ci")
        os.makedirs(runs_dir)

        # transcribe 100 cpu-s, align 50 cpu-s -> ratio 0.5, multiplier 1.5 exactly.
        specs = [
            ("en-c2-oneshot-warm", "en", 2, 0.0, "warm", 100.0, 50.0, 0),
            ("en-c2-chunk15-warm", "en", 2, 15.0, "warm", 100.0, 30.0, 0),
            ("en-c2-coldstart", "en", 2, 0.0, "cold", 120.0, 60.0, 0),
            ("en-c2-oneshot-5g", "en", 2, 0.0, "warm", 0.0, 0.0, 137),
        ]
        for spec in specs:
            meta, measurement = _synthetic_run(*spec)
            with open(os.path.join(runs_dir, spec[0] + ".meta.json"), "w", encoding="utf-8") as fh:
                json.dump(meta, fh)
            if measurement is not None:
                with open(os.path.join(runs_dir, spec[0] + ".json"), "w", encoding="utf-8") as fh:
                    json.dump(measurement, fh)

        host_facts = {"kind": "MEASURED", "vcpus": 4, "mem_total_bytes": 16000000000}
        build_facts = {
            "git_commit": "0" * 40,
            "date_utc": "2026-01-01T00:00:00Z",
            "runtime_image_bytes": 1_200_000_000,
            "baked_image_bytes": 2_500_000_000,
            "runtime_build_seconds": 300.0,
            "baked_build_seconds": 200.0,
            "skipped_runs": [],
        }
        spike_e = {
            "answer_1_image_size": {
                "estimated_image_size_mib": {"lean_runtime_no_models": 1194, "lean_baked_en_es_fr": 2416}
            },
            "answer_2_memory": {
                "headline": {
                    "one_shot_60s_segment_peak_mib": [2848.6, 4549.4],
                    "chunked_15s_peak_mib": [1936.5, 1942.9],
                }
            },
            "answer_3_cold_start": {"cleanest_observation": {"cold_start_total_s": 3.698}},
            "answer_5_cost_figure": {"defect_1_missing_stages": {"pipeline_multiplier": 1.916}},
        }
        spike_a = [
            {"compute_cost_per_audio_hour_usd": 0.02},
            {"compute_cost_per_audio_hour_usd": 0.03},
        ]

        paths = {}
        for name, blob in (
            ("host.json", host_facts),
            ("build.json", build_facts),
            ("spike-e.json", spike_e),
            ("spike-a.json", spike_a),
        ):
            p = os.path.join(tmp, name)
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(blob, fh)
            paths[name] = p

        args = argparse.Namespace(
            runs_dir=runs_dir,
            host_facts=paths["host.json"],
            build_facts=paths["build.json"],
            spike_e_results=paths["spike-e.json"],
            spike_a_results=paths["spike-a.json"],
        )
        art = build(args)

        out = os.path.join(tmp, "artifact.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(art, fh, indent=2)

        print("SELF-TEST — the arithmetic")
        mult = art["answer_5_cost_figure"]["pipeline_multiplier"]
        check("multiplier is 1 + align_cpu/asr_cpu = 1.5", mult["value"] == 1.5, f"got {mult['value']}")
        check(
            "the multiplier comes from the WARM one-shot run, not the cold one",
            mult["from_run"] == "en-c2-oneshot-warm",
            f"got {mult['from_run']}",
        )
        check(
            "container_value is the chosen run's amortised pipeline factor",
            art["answer_4_realtime_factor"]["container_value"] == 0.7,
        )
        # 9 x 0.02 = 0.18 and 9 x 0.03 = 0.27, x 1.5 -> 0.27 / 0.405
        d1 = art["answer_5_cost_figure"]["derivation_1_rescaled_spike_a"]
        check(
            "rescaled range = 9 x SPIKE A hourly x multiplier",
            d1["corrected_usd_per_9h_book"] == [0.27, 0.405],
            f"got {d1['corrected_usd_per_9h_book']}",
        )
        # 1.0 cpu-s per audio-s x 32400 audio-s x (0.000463/60) = 0.25002 -> 0.25
        d2 = art["answer_5_cost_figure"]["derivation_2_container_cpu_seconds"]
        check(
            "direct compute cost bills the container's own CPU-seconds",
            abs(d2["usd_per_9h_book"] - 0.25) < 0.001,
            f"got {d2['usd_per_9h_book']}",
        )
        # 1 GB mean x (9 x 60 x 0.7 = 378 min) x 0.000231 = 0.0873
        mem = art["answer_5_cost_figure"]["memory_term"]
        check(
            "memory term uses the STEADY-STATE mean, not the peak and not the whole-run mean",
            abs(mem["usd_per_9h_book_at_full_duty"] - 0.0873) < 0.0005,
            f"got {mem['usd_per_9h_book_at_full_duty']}",
        )
        check(
            "an OOM-killed run survives as a FAILED row rather than vanishing",
            any(r["run_id"] == "en-c2-oneshot-5g" and r["status"] == "FAILED" for r in art["runs"]),
        )
        check(
            "the OOM run is read as a result about the limit",
            "OOM" in (find_run(art["runs"], "en-c2-oneshot-5g") or {}).get("_failure_reading", ""),
        )
        check(
            "recommended_limit_under_test records that 5 GiB did NOT survive",
            art["answer_2_memory"]["recommended_limit_under_test"]["unchunked_5120m_survived"]
            is False,
        )
        check(
            "a recommendation test that never ran reads as None, not as False",
            art["answer_2_memory"]["recommended_limit_under_test"]["chunked_2560m_survived"]
            is None,
        )
        check(
            "an absent offline probe reads as NOT MEASURED, never as a pass",
            art["answer_0_self_sufficiency"]["kind"] == "NOT MEASURED",
        )

        print("SELF-TEST — verify accepts a complete artifact")
        check("verify passes", verify(out) == 0)

        print("SELF-TEST — verify REJECTS each way of measuring nothing")

        def mutated(fn, label):
            blob = json.loads(json.dumps(art))
            fn(blob)
            p = os.path.join(tmp, f"mutant-{label}.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(blob, fh)
            return verify(p)

        def drop_required(b):
            b["runs"] = [r for r in b["runs"] if r["run_id"] != "en-c2-chunk15-warm"]

        def null_rtf(b):
            b["answer_4_realtime_factor"]["container_value"] = None

        def zero_image(b):
            b["answer_1_image_size"]["baked_bytes"] = 0

        def unlabelled(b):
            b["a_block_somebody_added_later"] = {"a_number": 42.0}

        def null_cold(b):
            b["answer_3_cold_start"]["cold_startup_total_s"] = None

        for fn, label in (
            (drop_required, "missing-required-run"),
            (null_rtf, "null-realtime-factor"),
            (zero_image, "no-image-size"),
            (unlabelled, "unlabelled-number"),
            (null_cold, "null-cold-start"),
        ):
            check(f"rejected: {label}", mutated(fn, label) == 1)

    if failures:
        print(f"\nSELF-TEST FAILED — {len(failures)} check(s): {', '.join(failures)}", file=sys.stderr)
        return 1
    print("\nSELF-TEST OK — the collector's arithmetic holds and every guard bites.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--verify", metavar="ARTIFACT")
    ap.add_argument("--runs-dir")
    ap.add_argument("--host-facts")
    ap.add_argument("--build-facts")
    ap.add_argument("--spike-e-results", default="aligner/spike-e/out/spike-e-results.json")
    ap.add_argument("--spike-a-results", default="aligner/spike-a/out/spike-a-results.json")
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.verify:
        return verify(args.verify)
    if not (args.runs_dir and args.host_facts and args.build_facts and args.out):
        ap.error("--runs-dir, --host-facts, --build-facts and --out are all required")

    art = build(args)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(art, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
