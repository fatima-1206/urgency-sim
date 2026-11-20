#!/usr/bin/env bash
# Stage-A smoke test: is the field numerically stable and does the plume move?
# Fast (a few seconds). Run this first if you have changed field.py or config.py.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -x .venv/bin/python ]] || { echo "no venv; run bin/setup.sh first" >&2; exit 1; }

mkdir -p figs
.venv/bin/python scripts/smoke_field.py
echo "==> wrote figs/check2_field_sanity.png"
