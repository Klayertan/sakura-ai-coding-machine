# Changelog

## 0.2.0 — 2026-10-03

Review of the 0.1.0 scaffold. The Docker image and the DOK deployment are still unverified on real hardware; see `docs/dok-deployment.md`.

### Security
- **Gateway fails closed.** 0.1.0 disabled authentication entirely when `SAKURA_AI_API_KEY` was unset. The gateway now refuses to start without a real key (unset, placeholder and <16-character keys are rejected); `ALLOW_NO_AUTH=1` is an explicit local-only opt-out.
- API key comparison is constant-time.
- `/health` no longer exposes cost, voucher or model information without authentication; that moved to authenticated `/api/usage`.
- Interactive API docs (`/docs`, `/openapi.json`) are disabled.
- `docker-compose.local.yml` binds to `127.0.0.1` and reads the key from `.env` instead of hard-coding `dev-only-change-me`.

### Added
- **Streaming** for `/api/chat` (NDJSON `delta` / `done` / `error` events) and in the CLI client.
- **`InferenceProvider` abstraction** with `OllamaProvider`. The gateway's response format is now its own, so a vLLM provider needs no client changes.
- **`/api/usage`**: uptime, estimated spend, voucher estimate, idle timer, and GPU name/VRAM/utilisation from `nvidia-smi`.
- **Idle auto-shutdown** (`IDLE_SHUTDOWN_MINUTES`, default 60) so a forgotten task stops billing.
- `temperature` and `max_tokens` on chat requests; token usage and generation time in replies.
- Client: `--usage`, `--models`, `--health`, `--no-stream`, `--thinking`, `--system`, and readable errors.
- `GATEWAY_API_KEY` as an alternative key variable, because DOK reserves the `SAKURA_` prefix.
- Optional `BAKE_MODEL` build argument to ship model weights inside the image.
- Backend test suite (46 tests) and a CI test job on Python 3.9 and 3.12.
- `docs/dok-deployment.md`, `docs/repo-context-design.md`.

### Fixed
- Ollama errors (unknown model, provider down) returned unhandled HTTP 500s; they now map to 404/502 with the provider's message.
- `start.sh` treated any model of the same family as present (`grep` on the name before `:`), so switching `gpt-oss:20b` → `gpt-oss:120b` skipped the pull. It now checks the exact tag.
- `start.sh` continued silently if Ollama never became ready; it now exits with an error.
- Ollama logs went to `/tmp/ollama.log`, invisible in the DOK task log; they now go to stdout.
- The client sent requests to the literal `https://YOUR-DOK-ENDPOINT` when no URL was configured.

### Changed
- `GPU_YEN_PER_HOUR` defaults to `1008` (DOK H100 list price) instead of `0`, which made every estimate ¥0.
- Ollama runs with `OLLAMA_KEEP_ALIVE=-1` (no unload after 5 idle minutes) and `OLLAMA_CONTEXT_LENGTH=32768`.
- Dockerfile is based on the official `ollama/ollama` image rather than `nvidia/cuda` plus `curl | sh`; Python dependencies install into a venv.
- `/api/models` returns a provider-neutral shape (`models[].name` is unchanged).
- Code is compatible with Python 3.9 so tests and the client run on stock macOS Python.

## 0.1.0

Initial scaffold: Ollama + FastAPI gateway, `/health`, `/api/models`, `/api/chat` (non-streaming), CLI client, Docker build workflow.
