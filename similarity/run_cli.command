#!/usr/bin/env bash

# Ensure we are in the directory where the script is located
cd "$(dirname "$0")" || exit 1

pick_supported_python() {
    for candidate in python3.12 python3.11 python3.10 python3; do
        if ! command -v "$candidate" >/dev/null 2>&1; then
            continue
        fi
        if "$candidate" -c 'import sys; raise SystemExit(0 if ((3,9) <= sys.version_info[:2] <= (3,12)) else 1)' >/dev/null 2>&1; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

PYTHON_BIN="$(pick_supported_python)"
if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] No supported Python found (requires 3.9-3.12 for TensorFlow/DeepFace)."
    echo "Install Python 3.12 and retry (macOS: brew install python@3.12)."
    read -p "Press Enter to exit..."
    exit 1
fi

echo "[INFO] Using Python interpreter: $PYTHON_BIN"

# Check if .venv exists
if [ ! -f ".venv/bin/activate" ]; then
    echo "[INFO] Virtual environment not found. Creating one..."
    "$PYTHON_BIN" -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        read -p "Press Enter to exit..."
        exit 1
    fi
else
    if ! .venv/bin/python -c 'import sys; raise SystemExit(0 if ((3,9) <= sys.version_info[:2] <= (3,12)) else 1)' >/dev/null 2>&1; then
        echo "[INFO] Existing virtual environment uses unsupported Python. Recreating..."
        rm -rf .venv
        "$PYTHON_BIN" -m venv .venv
        if [ $? -ne 0 ]; then
            echo "[ERROR] Failed to recreate virtual environment."
            read -p "Press Enter to exit..."
            exit 1
        fi
    fi
    echo "[INFO] Activating existing virtual environment..."
fi

echo "[INFO] Activating virtual environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate virtual environment."
    read -p "Press Enter to exit..."
    exit 1
fi

echo "[INFO] Synchronizing dependencies from requirements.txt..."
python -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to synchronize dependencies from requirements.txt."
    read -p "Press Enter to exit..."
    exit 1
fi

# Run the application
echo "[INFO] Launching Face Similarity CLI..."
python main.py --cli

echo ""
echo "[INFO] Application finished."
read -p "Press Enter to exit..."
