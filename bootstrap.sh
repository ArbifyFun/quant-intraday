#!/usr/bin/env bash
# This lightweight bootstrap script has been superseded by the more feature‑complete
# `scripts/bootstrap.sh` located in the `scripts/` directory.  For convenience,
# this wrapper will delegate to the unified bootstrap script if it exists.  It
# falls back to the original venv installer logic for backward compatibility.

set -euo pipefail

# If scripts/bootstrap.sh exists, delegate to it (auto mode). Pass through any
# arguments to allow specifying `local` or `docker` explicitly.
if [ -f "scripts/bootstrap.sh" ]; then
  echo "[bootstrap] Detected scripts/bootstrap.sh; delegating to unified bootstrap"
  exec "scripts/bootstrap.sh" "$@"
fi

# Legacy bootstrap logic (local venv installation)
PY=${PYTHON:-python3}
VENV=".venv"

if [ ! -d "$VENV" ]; then
  echo "[bootstrap] Creating venv at $VENV"
  $PY -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -V
pip -V

echo "[bootstrap] Upgrading pip/build toolchain"
pip install -U pip wheel build

echo "[bootstrap] Installing package (editable) with web extras"
pip install -e ".[web]"

# Copy sample env if not exists
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "[bootstrap] Wrote .env from example (edit it with your OKX keys)"
fi

echo "[bootstrap] Running sanity checks"
qi check || true
echo "[bootstrap] Preflight"
qi preflight || true

echo ""
echo "✔ Done. Activate venv next time with: source .venv/bin/activate"
echo "Useful commands:"
echo "  qi web --host 0.0.0.0 --port 8080   # Web UI"
echo "  qi run                               # Start live portfolio (needs OKX keys)"
echo "  qi backtest --csv data.csv           # Backtest on CSV"
