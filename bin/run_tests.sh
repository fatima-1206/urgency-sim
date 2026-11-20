#!/usr/bin/env bash
# Phase 1 regression suite. Fast (~6 s) and meant to be run before every
# experiment pass -- it is what stops a mechanical change from silently
# invalidating a result table.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] && source .venv/bin/activate
python -m pytest "$@"
