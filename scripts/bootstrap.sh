#!/usr/bin/env bash
set -euo pipefail
MODE="${1:-auto}"   # auto|local|docker
YES="${YES:-0}"     # non-interactive: YES=1
log(){ printf "\033[1;34m[BOOT]\033[0m %s\n" "$*"; }
ok(){ printf "\033[1;32m[ OK ]\033[0m %s\n" "$*"; }
warn(){ printf "\033[1;33m[WARN]\033[0m %s\n" "$*"; }
err(){ printf "\033[1;31m[ERR]\033[0m %s\n" "$*"; exit 1; }

detect(){ uname -s; }
has(){ command -v "$1" >/dev/null 2>&1; }

# .env ensure
ensure_env(){
  if [ -f ".env" ]; then return; fi
  log "Generating .env"
  TOKEN=$(python - <<'PY' 2>/dev/null || true
import secrets, string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))
PY
)
  cat > .env <<EOF
OKX_API_KEY=
OKX_API_SECRET=
OKX_API_PASSPHRASE=
OKX_ACCOUNT=trade
OKX_SIMULATED=1
QI_WEB_TOKEN=${TOKEN}
QI_LOG_DIR=live_output
TZ=Asia/Tokyo
EOF
  ok "Wrote .env (SIMULATED=1)"
}

bootstrap_local(){
  VENV="${QI_VENV:-.venv}"
  if ! has python3; then err "python3 not found"; fi
  if [ ! -d "$VENV" ]; then python3 -m venv "$VENV"; fi
  # shellcheck disable=SC1090
  source "$VENV/bin/activate"
  python -m pip install -U pip wheel setuptools >/dev/null
  OS=$(detect)
  if [ "$OS" = "Darwin" ] && has brew; then
    brew list --versions ta-lib >/dev/null 2>&1 || (log "brew install ta-lib"; brew install ta-lib || true)
  fi
  set +e
  pip install -e . && pip install -U 'uvicorn[standard]' 'websockets[proxy]' 'python-socks[asyncio]' Jinja2 Jinja2 python-dotenv python-multipart 'websockets[proxy]' 'python-socks[asyncio]'
  rc=$?
  set -e
  if [ $rc -ne 0 ]; then
    warn "install failed, retry with numpy+TA-Lib wheels"
    pip install -U numpy
    pip install TA-Lib || true
    pip install -e . && pip install -U 'uvicorn[standard]' 'websockets[proxy]' 'python-socks[asyncio]' Jinja2 Jinja2 python-dotenv python-multipart 'websockets[proxy]' 'python-socks[asyncio]'
  fi
  ensure_env
  ok "Local venv ready."
  qi version || python -m quant_intraday version
  qi preflight || true
  qi doctor || true
  ok "Local bootstrap done. Use: source $VENV/bin/activate && qi web && qi run"
}

bootstrap_docker(){
  has docker || err "docker not found"
  docker compose version >/dev/null 2>&1 || err "'docker compose' plugin missing"
  ensure_env
  docker compose -f docker-compose.multi.yml up -d --build
  ok "Docker stack up. Web: http://localhost:8080  Metrics: http://localhost:9000/metrics"
}

if [ "$MODE" = "auto" ]; then
  if has docker && docker info >/dev/null 2>&1; then
    bootstrap_docker
  else
    bootstrap_local
  fi
elif [ "$MODE" = "local" ]; then
  bootstrap_local
elif [ "$MODE" = "docker" ]; then
  bootstrap_docker
else
  err "Unknown mode: $MODE (use auto|local|docker)"
fi


# Auto enter venv (interactive shells) unless disabled
if [ "${MODE}" = "local" ] && [ "${QI_AUTO_ENTER:-1}" = "1" ]; then
  if [[ $- == *i* ]]; then
    echo -e "\nEntering virtualenv shell. Type 'exit' to leave."
    exec ${SHELL:-/bin/zsh} -i -c "source \"${VENV}/bin/activate\"; exec ${SHELL:-/bin/zsh} -i"
  else
    echo "Non-interactive shell; to enter venv: source ${VENV}/bin/activate"
  fi
fi
