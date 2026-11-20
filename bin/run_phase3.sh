#!/usr/bin/env bash
# Phase 3, the study of record. Safe to interrupt and safe to re-run: progress
# is fsync'd per run, so re-running the same command picks up where it stopped.
#
#   bin/run_phase3.sh --plan            # what is left, and how long
#   bin/run_phase3.sh --speed 0.25      # the first shippable slice
#   bin/run_phase3.sh                   # everything, slice by slice
#   bin/run_phase3.sh --report          # summarise what is already done
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python -m pytest -q >/dev/null   # PROTOCOL section 9: tests gate every pass
exec .venv/bin/python scripts/phase3.py "$@"
