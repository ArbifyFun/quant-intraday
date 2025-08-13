#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e . && pip install -U 'uvicorn[standard]' 'websockets[proxy]' 'python-socks[asyncio]' Jinja2 python-dotenv python-multipart
echo "env activated. Run: source scripts/activate.sh"
