#!/usr/bin/env bash
set -euo pipefail
if [ ! -f .env ]; then cp .env.example .env; fi
pip install -e .
qi preflight || true
qi run --cfg qi.yaml
