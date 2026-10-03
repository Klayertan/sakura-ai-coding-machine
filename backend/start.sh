#!/usr/bin/env bash
set -euo pipefail
export OLLAMA_HOST=127.0.0.1:11434
ollama serve >/tmp/ollama.log 2>&1 &
for i in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null; then break; fi
  sleep 1
done
MODEL="${OLLAMA_MODEL:-gpt-oss:20b}"
if ! ollama list | grep -q "${MODEL%%:*}"; then
  echo "Pulling $MODEL ..."
  ollama pull "$MODEL"
fi
exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8080}"
