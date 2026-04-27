#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv-macos/bin/python"

"${ROOT_DIR}/setup_macos.sh"

exec "${PYTHON_BIN}" -u "${ROOT_DIR}/kling_automation_ui.py"
