#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
CLEAN_ARG=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --clean) CLEAN_ARG="--clean-output" ;;
    --engine=python|--engine=PYTHON|--engine=auto|--engine=AUTO) ;;
    --engine=powershell|--engine=POWERSHELL) echo "[WARN] PowerShell engine mode was removed. Python engine will be used." ;;
  esac
  shift
done

PY_EXE=""
for candidate in "$ROOT/runtime/python" "$(command -v python3 2>/dev/null || true)" "$(command -v python 2>/dev/null || true)"; do
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then
    PY_EXE="$candidate"
    break
  fi
done

[ -n "$PY_EXE" ] || { echo "[ERROR] Python not found"; exit 1; }
echo "[INFO] Requested engine: python"
exec "$PY_EXE" "$SCRIPT_DIR/collect_third_party_licenses.py" --project-root "$ROOT" --output-root "$ROOT" ${CLEAN_ARG:+$CLEAN_ARG}
