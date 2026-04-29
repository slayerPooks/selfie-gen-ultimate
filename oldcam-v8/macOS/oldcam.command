#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
cd "$SCRIPT_DIR" || exit 1

PYTHON_CMD=""
HAD_ERRORS=0

pick_python() {
  local candidate resolved
  local candidates=(
    "${OLDCAM_PYTHON:-}"
    /opt/homebrew/bin/python3
    /opt/homebrew/opt/python@3.14/bin/python3.14
    /opt/homebrew/opt/python@3.13/bin/python3.13
    /opt/homebrew/opt/python@3.12/bin/python3.12
    /opt/homebrew/opt/python@3.11/bin/python3.11
    /usr/local/bin/python3
    /usr/local/bin/python3.11
    python3
    python
  )

  for candidate in "${candidates[@]}"; do
    [ -n "$candidate" ] || continue

    if resolved="$(command -v "$candidate" 2>/dev/null)"; then
      :
    elif [ -x "$candidate" ]; then
      resolved="$candidate"
    else
      continue
    fi

    if "$resolved" -c "import cv2, numpy" >/dev/null 2>&1; then
      printf '%s\n' "$resolved"
      return 0
    fi
  done

  return 1
}

if PYTHON_CMD="$(pick_python)"; then
  :
fi

ensure_deps() {
  local py_cmd="$1"
  if "$py_cmd" -c "import cv2, numpy" >/dev/null 2>&1; then
    return 0
  fi

  if [ "${OLDCAM_SKIP_AUTO_INSTALL:-0}" = "1" ]; then
    return 1
  fi

  if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
    return 1
  fi

  echo "Missing dependencies detected (cv2/numpy). Attempting auto-install..."
  if ! "$py_cmd" -m pip install -r "$SCRIPT_DIR/requirements.txt"; then
    echo "Automatic dependency install failed."
    return 1
  fi

  "$py_cmd" -c "import cv2, numpy" >/dev/null 2>&1
}

pause_if_needed() {
  if [ -z "${OLDCAM_NO_PAUSE:-}" ]; then
    printf "\nPress Enter to exit..."
    read -r _
  fi
}

if [ -z "$PYTHON_CMD" ]; then
  echo "Could not find a Python interpreter with both cv2 and numpy installed."
  echo "Install dependencies with: python3 -m pip install -r requirements.txt"
  pause_if_needed
  exit 1
fi

if ! ensure_deps "$PYTHON_CMD"; then
  echo "Dependencies are still missing for selected Python: $PYTHON_CMD"
  echo "Try manually: \"$PYTHON_CMD\" -m pip install -r \"$SCRIPT_DIR/requirements.txt\""
  pause_if_needed
  exit 1
fi

if [ ! -f "$SCRIPT_DIR/oldcam.py" ]; then
  echo "Could not find oldcam.py next to the launcher."
  pause_if_needed
  exit 1
fi

EXTRA_ARG_ARRAY=()
if [ -n "${OLDCAM_EXTRA_ARGS:-}" ]; then
  read -r -a EXTRA_ARG_ARRAY <<< "${OLDCAM_EXTRA_ARGS}"
fi

process_one() {
  local file_path="$1"
  echo
  echo "==============================================================="
  echo "Processing: ${file_path}"
  "$PYTHON_CMD" "$SCRIPT_DIR/oldcam.py" "$file_path" "${EXTRA_ARG_ARRAY[@]}"
  local status=$?
  if [ $status -ne 0 ]; then
    echo "Failed: ${file_path}"
    HAD_ERRORS=1
  else
    echo "Finished: ${file_path}"
  fi
  return 0
}

pick_files() {
  osascript <<'APPLESCRIPT'
set selectedFiles to choose file with prompt "Select one or more media files for Oldcam V8" with multiple selections allowed
set outputText to ""
repeat with oneFile in selectedFiles
  set outputText to outputText & POSIX path of oneFile & linefeed
end repeat
return outputText
APPLESCRIPT
}

if [ "$#" -eq 0 ]; then
  if ! SELECTED_FILES="$(pick_files)"; then
    echo "No files selected."
    pause_if_needed
    exit 0
  fi

  while IFS= read -r file_path; do
    [ -z "$file_path" ] && continue
    process_one "$file_path"
  done <<< "$SELECTED_FILES"
else
  for file_path in "$@"; do
    process_one "$file_path"
  done
fi

echo
if [ "$HAD_ERRORS" -ne 0 ]; then
  echo "Completed with one or more errors."
else
  echo "All done."
fi
pause_if_needed
exit "$HAD_ERRORS"
