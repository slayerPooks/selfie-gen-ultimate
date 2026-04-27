#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
cd "${ROOT_DIR}"

set +e
"${ROOT_DIR}/run_cli.sh"
status=$?
set -e

if [[ ${status} -ne 0 ]]; then
  printf '\nCLI launcher failed with exit code %d.\n' "${status}" >&2
  read -r -p "Press Enter to close..."
fi

exit "${status}"
