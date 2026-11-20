#!/usr/bin/env bash
# The experiment programme. Safe to interrupt and safe to re-run: progress is
# fsync'd per simulation, so re-running the same command resumes.
#
#   bin/run_experiments.sh --dry                  # what it costs
#   bin/run_experiments.sh                        # everything, in order
#   bin/run_experiments.sh --only e1_explorability
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python -m pytest -q >/dev/null   # tests gate every run
exec .venv/bin/python scripts/experiments/run_all.py "$@"
