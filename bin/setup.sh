#!/usr/bin/env bash
# Create the virtual environment and install dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."

VENV=".venv"

if [[ ! -d "$VENV" ]]; then
  echo "==> creating venv at $VENV (reusing system numpy/scipy/matplotlib)"
  python3 -m venv --system-site-packages "$VENV"
else
  echo "==> venv already exists at $VENV"
fi

echo "==> installing requirements"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r requirements.txt

echo "==> verifying"
"$VENV/bin/python" - <<'PY'
import sys
print("  python", sys.version.split()[0])
for m in ("numpy", "scipy", "sklearn", "matplotlib"):
    mod = __import__(m)
    print(f"  {m:12s} {mod.__version__}")
PY

if command -v ffmpeg >/dev/null 2>&1; then
  echo "  ffmpeg       found (animations will be .mp4)"
else
  echo "  ffmpeg       MISSING (animations will fall back to .gif)"
  echo "               install with: sudo apt install ffmpeg"
fi

echo "==> done. Next: bin/run_all.sh"
