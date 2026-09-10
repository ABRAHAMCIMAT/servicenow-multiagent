#!/usr/bin/env bash
# Run with a real LLM (Jan local server or OpenAI) and live ServiceNow
set -e
cd "$(dirname "$0")/.."
export LLM_PROVIDER="${LLM_PROVIDER:-jan}"   # jan | openai | mock
export LLM_BASE_URL="${LLM_BASE_URL:-http://localhost:1337/v1}"
export LLM_MODEL="${LLM_MODEL:-gpt-oss:latest}"
export PORT="${PORT:-8000}"
# ServiceNow (opcional — si se omite, corre en demo)
# export SNOW_INSTANCE="tuinstancia"
# export SNOW_USER="admin"
# export SNOW_PASSWORD="..."
# Notificaciones (opcional)
# export NOTIFY_CHANNEL="slack"
# export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."
echo "🚀 ServiceNow Multi-Agent System (live)"
echo "   LLM: $LLM_PROVIDER ($LLM_MODEL) @ $LLM_BASE_URL"
echo "   ServiceNow: ${SNOW_INSTANCE:-DEMO}"
echo ""
python3 -m backend.server
