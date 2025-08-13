#!/usr/bin/env bash
set -euo pipefail

# Bootstrap script: create venv, install deps (incl. web extras), prepare env, run checks.
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
