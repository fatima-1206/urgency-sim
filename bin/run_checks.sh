#!/usr/bin/env bash
# Run the feasibility checks. Takes ~3 minutes for all of them.
#
#   bin/run_checks.sh                 # all 9 checks
#   bin/run_checks.sh --only 1,6      # just checks 1 and 6
#   bin/run_checks.sh --seeds 30      # more seeds in check 6
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -x .venv/bin/python ]] || { echo "no venv; run bin/setup.sh first" >&2; exit 1; }

mkdir -p figs results
echo "==> running feasibility checks"
.venv/bin/python scripts/run_checks.py "$@" 2>&1 | tee results/checks_console.log
echo "==> wrote figs/*.png, results/*.csv, results/report.json, results/checks_console.log"
