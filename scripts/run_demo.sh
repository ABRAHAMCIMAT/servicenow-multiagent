#!/usr/bin/env bash
# Run the full multi-agent system in demo mode (no credentials needed)
set -e
cd "$(dirname "$0")/.."
export LLM_PROVIDER="${LLM_PROVIDER:-mock}"
export PORT="${PORT:-8000}"
echo "🚀 ServiceNow Multi-Agent System (demo mode)"
echo "   LLM: $LLM_PROVIDER | Puerto: $PORT"
echo "   API:      http://localhost:$PORT/api"
echo "   Frontend: abre frontend/index.html en tu navegador"
echo ""
python3 -m backend.server
