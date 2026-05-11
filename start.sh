#!/usr/bin/env bash
# start.sh — Start MediScribe Rural
# Usage: ./start.sh [port]
set -e

PORT=${1:-8000}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================"
echo "  MediScribe Rural — Gemma 4 Clinical Assistant"
echo "================================================"

# Activate conda env
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate mediascribe

cd "$SCRIPT_DIR"

# Ingest guidelines if KB is empty
echo "[1/3] Checking knowledge base..."
python scripts/ingest_guidelines.py

# Check Ollama
echo "[2/3] Checking Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo "  ⚠  Ollama not running. Start it with: ollama serve"
  exit 1
fi

# Start server
echo "[3/3] Starting server on http://localhost:${PORT}"
echo ""
echo "  Open your browser → http://localhost:${PORT}"
echo "  Press Ctrl+C to stop"
echo ""
uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" --reload
