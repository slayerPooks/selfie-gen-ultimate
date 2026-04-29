#!/usr/bin/env bash

# Ensure we are in the directory where the script is located
cd "$(dirname "$0")" || exit 1

# Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in your PATH."
    echo "Please install Python 3 (e.g., via Homebrew: brew install python) and try again."
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if .venv exists
if [ ! -f ".venv/bin/activate" ]; then
    echo "[INFO] Virtual environment not found. Creating one..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        read -p "Press Enter to exit..."
        exit 1
    fi
else
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
