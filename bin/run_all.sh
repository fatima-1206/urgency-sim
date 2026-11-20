#!/usr/bin/env bash
# Everything, from a clean checkout: setup, smoke test, checks, animations.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "############ 1/4  setup"        ; bin/setup.sh
echo "############ 2/4  smoke test"   ; bin/run_smoke.sh
echo "############ 3/4  checks"       ; bin/run_checks.sh
echo "############ 4/4  animations"   ; bin/run_animations.sh

echo
echo "############ done"
echo "Read FINDINGS.md for the short version, FEASIBILITY_REPORT.md for the full one."
