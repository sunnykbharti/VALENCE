#!/usr/bin/env bash
# VALENCE Application Launcher (Milestone 4B)
# Runs strictly offline without downloading packages or model weights.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"
export PYTHONPATH="."

echo "=========================================================="
echo "      VALENCE: Offline Industrial Knowledge Assistant     "
echo "=========================================================="

# Check if virtualenv is activated or available
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Using active virtual environment: $VIRTUAL_ENV"
elif [ -d ".venv" ]; then
    echo "Activating local virtual environment (.venv)..."
    source .venv/bin/activate
elif [ -d "env" ]; then
    echo "Activating local virtual environment (env)..."
    source env/bin/activate
else
    echo "Warning: No virtual environment active. Using system Python ($(which python3))."
fi

# Run diagnostics in brief mode
echo ""
echo "Running pre-flight environment doctor..."
python3 scripts/doctor.py || true

echo ""
echo "Starting Streamlit web application on http://localhost:8501 ..."
echo "(Press Ctrl+C to terminate)"
echo "=========================================================="

exec streamlit run src/ui/app.py

