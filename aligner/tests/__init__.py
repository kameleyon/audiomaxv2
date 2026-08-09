"""Tests for the aligner sidecar.

This file is not decoration. `unittest discover` refuses a start directory that
is not importable, so without it the whole suite fails to collect — which is a
green-looking "0 tests ran" in some runners and a hard error in ours. The hard
error is the better failure, and this package marker is what makes the suite run
at all from the repository root:

    python -m unittest discover -s aligner/tests -t aligner
"""
