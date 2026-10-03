# Sakura AI Coding Machine 🌸⚡

Use a Sakura Cloud GPU as your personal AI inference server, with Ollama serving an open-weight model and a small authenticated API that your Mac can call.

**Goal:** use Sakura GPU credits for inference instead of consuming Anthropic/OpenAI hosted-model tokens.

## Architecture

```text
MacBook / client (client/sakura_chat.py)
        |
        | HTTPS (TLS terminated by Sakura)
        v
Sakura 高火力 DOK external endpoint
        |
        | HTTP inside Sakura
        v
FastAPI gateway :8080      auth, streaming, usage, idle shutdown
        |
        v
InferenceProvider          OllamaProvider today, VLLMProvider later
        |
        v
Ollama 127.0.0.1:11434     loopback only, never exposed
        |
        v
NVIDIA H100 80 GB + open-weight model
```

No OpenAI or Anthropic API is required for inference. `gpt-oss` is an open-weight model; running it yourself does not consume ChatGPT/Codex API quota.

## API

All `/api/*` endpoints require `Authorization: Bearer $SAKURA_AI_API_KEY`.

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /health` | no | Liveness: `{ok, provider_ok, model_ready}`. No cost or model details. |
| `GET /api/models` | yes | Models available on the provider, plus the default. |
| `GET /api/usage` | yes | Task uptime, estimated spend, voucher estimate, idle timer, GPU memory/utilisation. |
| `POST /api/chat` | yes | Chat. `{"messages": [...], "model"?, "stream"?, "temperature"?, "max_tokens"?}` |

With `"stream": true` the reply is newline-delimited JSON (`application/x-ndjson`):

```json
{"type": "delta", "content": "Hel"}
{"type": "delta", "thinking": "..."}
{"type": "done", "model": "gpt-oss:20b", "usage": {"prompt_tokens": 11, "completion_tokens": 4, "completion_ms": 2000}}
{"type": "error", "detail": "..."}
```

Failures before the first token (unknown model, provider down) are returned as normal HTTP errors (404/502); `error` events only occur mid-stream. Without `stream`, the reply is one JSON object with `message.content` and `usage`.

This format is the gateway's own, not Ollama's, so the client does not change when the provider does.

## Why start with `gpt-oss:20b`?

It is about 14 GB in Ollama, so it can be baked into the image (DOK's image limit is 30 GB) or pulled quickly at startup. After the pipeline works, try `gpt-oss:120b` on the 80 GB H100; it is about 65 GB, which is too large to bake, so it is pulled at task start (see [docs/dok-deployment.md](docs/dok-deployment.md)).

## Quick start on Sakura DOK

Full details, DOK limits and troubleshooting: [docs/dok-deployment.md](docs/dok-deployment.md).

1. Create a Sakura Container Registry repository.
2. Build for **linux/amd64** (required on Apple Silicon) and push:

   ```bash
   docker build --platform linux/amd64 --build-arg BAKE_MODEL=gpt-oss:20b -t YOUR-REGISTRY.sakuracr.jp/sakura-ai:latest .
   ```

   ```bash
   docker push YOUR-REGISTRY.sakuracr.jp/sakura-ai:latest
   ```

   Omit `BAKE_MODEL` for a small image that pulls the model at startup instead.
3. Generate an API key and keep it somewhere safe:

   ```bash
   openssl rand -hex 32
   ```

4. Create a 高火力 DOK task on the `h100-80gb` plan with:
   - environment variables from `.env.example` (`SAKURA_AI_API_KEY` is required; the container exits immediately without it);
   - **HTTP port `8080`**;
   - **a maximum execution time you are comfortable paying for** (the default is 20 days).
5. Copy the task's HTTPS URL. Until the container is listening, DOK returns 503.
6. On your Mac:

   ```bash
   python3 -m venv .venv && source .venv/bin/activate && pip install -r client/requirements.txt
   ```

   ```bash
   export SAKURA_AI_URL='https://YOUR-DOK-ENDPOINT' SAKURA_AI_API_KEY='your-secret'
   ```

   ```bash
   python client/sakura_chat.py explain this C++ segmentation fault
   ```

   Also: `--health`, `--models`, `--usage`, `--no-stream`, `--thinking`, `--system`, `--model`.

## Cost control

DOK bills per second while the container runs: the H100 plan is ¥0.28/s = ¥1,008/h (tax included, checked 2026-10), so the ¥100,000 voucher is roughly **99 GPU-hours**.

- **Idle shutdown.** The gateway exits after `IDLE_SHUTDOWN_MINUTES` (default 60) without an authenticated request, which ends the task and stops billing. Set `0` to disable.
- **Max execution time.** Set it on the DOK task as a hard backstop.
- **`/api/usage`** estimates spend as uptime × `GPU_YEN_PER_HOUR` for the *current task only*. It is not Sakura billing data and does not know about earlier tasks.

## Security

- Only the gateway on port `8080` is exposed. Ollama binds to loopback inside the container.
- The gateway **refuses to start** without a real `SAKURA_AI_API_KEY` (unset, placeholder and short keys are rejected). `ALLOW_NO_AUTH=1` exists for local development only.
- `/health` is the only unauthenticated endpoint; interactive API docs are disabled.
- Secrets come from environment variables; `.env` is git-ignored.
- Not yet implemented: rate limiting, per-client keys.

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements-dev.txt
```

```bash
python -m pytest backend/tests -q
```

Tests use a fake provider and need neither Ollama nor a GPU. The code runs on Python 3.9+ (stock macOS) and CI tests 3.9 and 3.12.

To add a backend such as vLLM, subclass `InferenceProvider` in `backend/providers/` (three methods: `chat_stream`, `list_models`, `health`) and register it in `build_provider`; select it with `INFERENCE_PROVIDER`.

## Roadmap

- [x] Ollama on Sakura H100
- [x] Authenticated FastAPI gateway
- [x] Usage endpoint with voucher/cost estimate and GPU stats
- [x] Mac CLI client
- [x] Streaming responses
- [x] Provider abstraction (Ollama first)
- [x] Backend tests + CI
- [x] Idle auto-shutdown
- [ ] Validate end to end on a real DOK H100 task (M0)
- [ ] Repository context subsystem ([design](docs/repo-context-design.md))
- [ ] Patch workflow with diff approval
- [ ] Safe terminal tool execution and test/fix loop
- [ ] Desktop UI
- [ ] Local usage history across tasks; actual Sakura billing ingestion
- [ ] Object Storage model cache for models over 30 GB
- [ ] vLLM provider
- [ ] OpenCode/Aider adapter

## More

- [CHANGELOG.md](CHANGELOG.md)
- [docs/dok-deployment.md](docs/dok-deployment.md)
- [docs/repo-context-design.md](docs/repo-context-design.md)
- Blog: [`blog/01-building-a-personal-ai-coding-machine-on-sakura-h100.md`](blog/01-building-a-personal-ai-coding-machine-on-sakura-h100.md)
