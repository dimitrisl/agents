#!/usr/bin/env bash
# ==============================================================================
# 🩸 Phyrexian Forge - Start Script (Linux & macOS)
# Runs both FastAPI backend (port 8000) and Angular client (port 4200).
# ==============================================================================

set -e

# Ensure all child background jobs are killed on Ctrl+C or script exit
trap 'kill $(jobs -p) 2>/dev/null' EXIT INT TERM

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

# Quick check for setup completion
if [ ! -d "client/node_modules" ] || [ ! -f ".env" ]; then
    echo "⚠️ It looks like the project hasn't been set up yet."
    echo "Running ./setup.sh first..."
    ./setup.sh
fi

echo "====================================================="
echo "🚀 Starting FastAPI Backend (http://localhost:8000)..."
echo "====================================================="

if command -v poetry &> /dev/null; then
    poetry run uvicorn server.main:app --reload --port 8000 &
elif command -v uvicorn &> /dev/null; then
    uvicorn server.main:app --reload --port 8000 &
else
    echo "❌ Error: Neither poetry nor uvicorn was found in PATH."
    echo "Please run ./setup.sh to configure the environment."
    exit 1
fi

BACKEND_PID=$!
sleep 2

echo "====================================================="
echo "💻 Starting Angular Client (http://localhost:4200)..."
echo "====================================================="

cd "$PROJECT_DIR/client"
npm start
