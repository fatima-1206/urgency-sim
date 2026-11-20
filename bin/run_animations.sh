#!/usr/bin/env bash
# Render the side-by-side animations and the timeline plots.
# One animation per scenario per method, same seed so they are comparable.
#
#   bin/run_animations.sh                       # seed 3, proposed + threshold
#   bin/run_animations.sh --seed 7 --fps 24
#   bin/run_animations.sh --methods proposed
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -x .venv/bin/python ]] || { echo "no venv; run bin/setup.sh first" >&2; exit 1; }

mkdir -p figs
echo "==> rendering animations (about a minute each)"
.venv/bin/python scripts/animate.py "$@"
echo "==> wrote:"
ls -1sh figs/anim_*.mp4 figs/anim_*.gif figs/timeline_*.png 2>/dev/null || true
