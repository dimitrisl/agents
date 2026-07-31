#!/bin/bash

# Ensure script stops background job on exit/Ctrl+C
trap 'kill $(jobs -p) 2>/dev/null' EXIT INT TERM

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

PYTHON_UVICORN="/home/dimitrisl/.cache/pypoetry/virtualenvs/agents-RZSmSi36-py3.13/bin/uvicorn"

echo "========================================="
echo "🚀 Starting FastAPI Backend (Port 8000)..."
echo "========================================="

if command -v poetry &> /dev/null; then
    poetry run uvicorn server.main:app --reload --port 8000 &
elif [ -f "$PYTHON_UVICORN" ]; then
    "$PYTHON_UVICORN" server.main:app --reload --port 8000 &
else
    echo "❌ Error: Could not find uvicorn or poetry virtual environment."
    exit 1
fi

BACKEND_PID=$!
sleep 2

echo "========================================="
echo "💻 Starting Angular Client (Port 4200)..."
echo "========================================="

cd "$PROJECT_DIR/client"
npm start
