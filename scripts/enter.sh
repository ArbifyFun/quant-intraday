#!/usr/bin/env bash
VENV="${QI_VENV:-.venv}"
if [ ! -f "$VENV/bin/activate" ]; then
  echo "Venv not found. Run ./scripts/bootstrap.sh local"
  exit 1
fi
exec ${SHELL:-/bin/zsh} -i -c "source \"$VENV/bin/activate\"; exec ${SHELL:-/bin/zsh} -i"
