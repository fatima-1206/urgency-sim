#!/usr/bin/env bash
# Remove generated output. Does NOT touch the venv or any source.
set -euo pipefail
cd "$(dirname "$0")/.."

read -r -p "Delete figs/ and results/ contents? [y/N] " ans
[[ "${ans:-}" == "y" || "${ans:-}" == "Y" ]] || { echo "aborted"; exit 0; }

rm -f figs/*.png figs/*.mp4 figs/*.gif
rm -f results/*.csv results/*.json results/*.log
find . -name __pycache__ -type d -prune -exec rm -rf {} +
echo "==> cleaned (venv and source left alone)"
