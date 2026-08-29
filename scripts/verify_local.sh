#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-${ROOT}/.venv}"

cd "$ROOT"
"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r requirements.txt
"$VENV_DIR/bin/python" -m compileall -q .
"$VENV_DIR/bin/python" -m pip check
"$VENV_DIR/bin/python" -m pip install --upgrade pip-audit
"$VENV_DIR/bin/pip-audit" -r requirements.txt

git diff --check
"$VENV_DIR/bin/python" run_all_tests.py

if git status --short --untracked-files=all | grep -E '(ward_hub\.db|audit_events\.jsonl|edge_telemetry_state\.json|forensic_anchors\.jsonl|reliability_validation_result\.json|pilot_simulation_result\.json|serial_bench_evidence\.json)'; then
  echo 'Runtime artifacts must not be tracked or added by verification.' >&2
  exit 1
fi

echo 'LOCAL_VERIFICATION_PASSED'
