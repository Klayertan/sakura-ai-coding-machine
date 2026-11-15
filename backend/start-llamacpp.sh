#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

export INFERENCE_PROVIDER=openai
export INFERENCE_MODEL="${INFERENCE_MODEL:-deepseek-v4-flash}"
export INFERENCE_URL="${INFERENCE_URL:-http://127.0.0.1:8081}"

# Check configuration and the server binary before downloading the weights.
python3 config.py
if ! llama-server --version; then
  echo "ERROR: llama-server startup check failed. Skipping the model download." >&2
  exit 1
fi

MODEL_REPO="${MODEL_REPO:-unsloth/DeepSeek-V4-Flash-0731-GGUF}"
revision_args=()
if [ "$MODEL_REPO" = "unsloth/DeepSeek-V4-Flash-0731-GGUF" ]; then
  MODEL_REVISION="${MODEL_REVISION:-fbbb5b93fb787c21338159b0af3318bb3f4d9768}"
fi
if [ -n "${MODEL_REVISION:-}" ]; then
  revision_args=(--revision "$MODEL_REVISION")
fi
MODEL_QUANT="${MODEL_QUANT:-UD-IQ3_XXS}"
MODEL_DIR="${MODEL_DIR:-/opt/models}"
MIN_FREE_GB="${MIN_FREE_GB:-120}"
MODEL_LOAD_TIMEOUT="${MODEL_LOAD_TIMEOUT:-1800}"

gpu_count=0
if gpu_info=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader) && [ -n "$gpu_info" ]; then
  printf '%s\n' "$gpu_info"
  gpu_count=$(printf '%s\n' "$gpu_info" | wc -l | tr -d ' ')
fi
if [ -n "${EXPECTED_GPU_COUNT:-}" ] && [ "$gpu_count" != "$EXPECTED_GPU_COUNT" ]; then
  echo "ERROR: expected $EXPECTED_GPU_COUNT visible GPUs, found $gpu_count." >&2
  exit 1
fi

mkdir -p "$MODEL_DIR"
free_gb=$(df -BG --output=avail "$MODEL_DIR" | tail -n 1 | tr -dc '0-9')
if [ "$free_gb" -lt "$MIN_FREE_GB" ]; then
  echo "ERROR: $MODEL_DIR has ${free_gb} GB free, need ${MIN_FREE_GB} GB. Set MODEL_DIR or MIN_FREE_GB." >&2
  exit 1
fi

# DOK bills this transfer as container runtime. Its duration varies by task.
echo "Downloading $MODEL_REPO@${MODEL_REVISION:-main} ($MODEL_QUANT) to $MODEL_DIR ..."
date
hf download "$MODEL_REPO" "${revision_args[@]}" --include "$MODEL_QUANT/*" --local-dir "$MODEL_DIR"
date

first=$(ls "$MODEL_DIR/$MODEL_QUANT"/*-00001-of-*.gguf 2>/dev/null | head -n 1 || true)
if [ -z "$first" ]; then
  echo "ERROR: no first GGUF shard in $MODEL_DIR/$MODEL_QUANT." >&2
  exit 1
fi
expected=$(basename "$first" | sed -E 's/.*-of-0*([0-9]+)\.gguf$/\1/')
found=$(ls "$MODEL_DIR/$MODEL_QUANT"/*.gguf | wc -l | tr -d ' ')
if [ "$found" != "$expected" ]; then
  echo "ERROR: expected $expected GGUF shards, found $found." >&2
  exit 1
fi

# llama-server stays on loopback; only the authenticated gateway is exposed.
# Sampling follows the model card's recommendation for agent work.
# Unset GPU layers default to auto, which offloads as much as fits in VRAM.
llama-server \
  --model "$first" \
  --alias "$INFERENCE_MODEL" \
  --host 127.0.0.1 \
  --port "${INFERENCE_URL##*:}" \
  --ctx-size "${LLAMA_CTX_SIZE:-65536}" \
  --parallel "${LLAMA_PARALLEL:-1}" \
  --gpu-layers "${LLAMA_GPU_LAYERS:-auto}" \
  --split-mode layer \
  --temp 1.0 \
  --top-p 0.95 &
server=$!

ready=0
for _ in $(seq 1 "$MODEL_LOAD_TIMEOUT"); do
  if curl -fsS "$INFERENCE_URL/health" >/dev/null 2>&1; then ready=1; break; fi
  if ! kill -0 "$server" 2>/dev/null; then
    echo "ERROR: llama-server exited while loading the model." >&2
    exit 1
  fi
  sleep 1
done
if [ "$ready" != 1 ]; then
  echo "ERROR: llama-server did not load within ${MODEL_LOAD_TIMEOUT}s." >&2
  exit 1
fi
date

exec uvicorn app:create_app --factory --host 0.0.0.0 --port "${PORT:-8080}"
