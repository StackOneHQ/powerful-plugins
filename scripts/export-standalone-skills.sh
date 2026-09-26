#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPOSITORY_ROOT="$(dirname -- "$SCRIPT_DIR")"
PYTHON_BIN="${PYTHON:-python3}"
export PYTHONPATH="$REPOSITORY_ROOT${PYTHONPATH:+:$PYTHONPATH}"
if ! "$PYTHON_BIN" -c 'import yaml' >/dev/null 2>&1; then
  echo "ERROR: PyYAML is required; run: python3 -m pip install -r requirements.txt" >&2
  exit 2
fi
exec "$PYTHON_BIN" -m scripts.export_standalone_skills "$@"
