#!/usr/bin/env python3
"""
Write the META record for one container measurement run.

WHY A SEPARATE FILE FROM THE MEASUREMENT. The measurement is written by
`measure.py` INSIDE the container, at the end of a successful run. A run killed
by its memory limit writes nothing at all — and the most interesting outcome in
the matrix is exactly that one, because it is the answer to "is the recommended
5 GiB limit enough". A collector that enumerated measurements would turn that
answer into an absence, and an absence reads as "we never tried".

So the meta is written TWICE by the workflow: once before the container starts,
with `exit_code` null, and once after it exits, with the real code. The first
write is what makes a dead run visible; the second is what makes it explicable.

WHY NOT INLINE IN THE YAML. Quoting. This runs inside a bash loop that already
carries a docker invocation, and a JSON document assembled by `printf` in that
context is one unescaped quote away from silently emitting invalid JSON — which
`ci_collect.py` would then read as a missing run. Environment variables in,
`json.dump` out, no quoting rules to get wrong.

Usage (all inputs are environment variables, so the caller has no argument
order to get wrong either):

  RUN_ID=en-c2-oneshot-warm LANG_CODE=en CPUS=2 CHUNK=0 MEM_REQ=8192 \
  MEM_EFF=8192 CACHE=warm EXIT_CODE=0 WALL_S=93.2 python3 write_run_meta.py
"""
from __future__ import annotations

import json
import os
import sys

OUT_DIR = os.environ.get("SPIKE_E_CI_DIR", "aligner/spike-e/out/ci")


def number(name, cast, default=None):
    raw = os.environ.get(name, "")
    if raw == "":
        return default
    try:
        return cast(raw)
    except ValueError:
        return default


def main() -> int:
    run_id = os.environ.get("RUN_ID")
    if not run_id:
        print("RUN_ID is required", file=sys.stderr)
        return 2

    meta = {
        "run_id": run_id,
        "_kind": "MEASURED — the configuration this run was launched with",
        "lang": os.environ.get("LANG_CODE"),
        "cpus": number("CPUS", int),
        "align_chunk_s": number("CHUNK", float),
        "memory_limit_requested_mb": number("MEM_REQ", int),
        "memory_limit_effective_mb": number("MEM_EFF", int),
        "memory_limit": f"{number('MEM_EFF', int)}m",
        "memory_limit_clamped": (
            None
            if (number("MEM_REQ", int) is None or number("MEM_EFF", int) is None)
            else number("MEM_REQ", int) != number("MEM_EFF", int)
        ),
        "page_cache": os.environ.get("CACHE"),
        "network": os.environ.get("NETWORK_MODE", "none"),
        "swap": "disabled (--memory-swap == --memory)",
        "exit_code": number("EXIT_CODE", int),
        "wall_seconds": number("WALL_S", float),
        "_network_none_is_a_test": (
            "The `baked` target exists so that no render depends on reaching "
            "download.pytorch.org at render time. Running with the network removed "
            "is what turns that from a claim into a check."
        ),
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{run_id}.meta.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
