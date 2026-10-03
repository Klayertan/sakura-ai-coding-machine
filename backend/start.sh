#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Fail before anything billable happens if the gateway would refuse to start.
python3 config.py

MODEL="${OLLAMA_MODEL:-gpt-oss:20b}"

# Ollama stays on loopback; only the authenticated gateway is exposed.
export OLLAMA_HOST=127.0.0.1:11434
# Keep the model in VRAM between requests (default unloads after 5 minutes).
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:--1}"
# Ollama's default context is too small for repository context.
export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-32768}"

if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true
else
  echo "WARNING: nvidia-smi not found; Ollama will fall back to CPU." >&2
fi

# Logs go to stdout/stderr so they show up in the DOK task log.
ollama serve &

ready=0
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
if [ "$ready" != 1 ]; then
  echo "ERROR: Ollama did not start within 60s." >&2
  exit 1
fi

# Exact tag check (a baked image or an earlier pull already has it).
if ! ollama show "$MODEL" >/dev/null 2>&1; then
  echo "Pulling $MODEL ..."
  ollama pull "$MODEL"
fi

exec uvicorn app:create_app --factory --host 0.0.0.0 --port "${PORT:-8080}"
