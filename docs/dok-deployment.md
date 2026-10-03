# Deploying on Sakura 高火力 DOK

Facts below are from the Sakura manual and pricing page as read on 2026-10-03. Items marked **unverified** have not yet been tested on a real task.

## DOK facts that shape this project

| Fact | Consequence here |
|---|---|
| Host architecture is `linux/amd64` | Build with `--platform linux/amd64` on Apple Silicon. |
| Container image limit: 30 GB | `gpt-oss:20b` (~14 GB) can be baked into the image; `gpt-oss:120b` (~65 GB) cannot. |
| Image pull time and queue time are not billed; container run time is, per second | A baked model costs nothing to "download"; a startup `ollama pull` is billed. |
| H100 plan: ¥0.28/s = ¥1,008/h incl. tax, 60 s minimum | ¥100,000 ≈ 99 GPU-hours. |
| H100 plan: 80 GB VRAM, 10 vCPU, 192 GB RAM, 500 GB working storage, 250 Mbps best-effort network | Plenty of disk for any model; a 65 GB pull takes roughly 35+ minutes (~¥600) at best. |
| Max execution time: default 20 days, minimum 1 hour | **Always set it.** A forgotten task at the default would cost far more than the voucher. |
| Everything outside `SAKURA_ARTIFACT_DIR` is deleted when the task ends; artifacts are capped at 20 GB and kept 72 h | Artifacts are not a model cache. |
| One HTTP port is exposed; Sakura terminates HTTPS and forwards plain HTTP; only HTTP is supported | No TLS proxy in the container. Streaming uses plain chunked HTTP, not WebSockets. |
| The endpoint returns 503 until the container listens on the port | The client reports this as "not ready"; retry. |
| The HTTP feature is intended for temporary services, not permanent daemons | Fits this use: start a task for a coding session, let it shut down when idle. |
| `SAKURA_*` environment variables are reserved; `SAKURA_TASK_ID` is provided | The API key variable is `SAKURA_AI_API_KEY`, which uses the reserved prefix (see below). |

## Open questions to confirm on the first real task (M0)

1. **`SAKURA_AI_API_KEY` uses the reserved `SAKURA_` prefix.** If the DOK console rejects or drops it, the container exits at once with a clear configuration error. The fix would be to rename the variable; this is deliberately not done before it is confirmed to be a problem.
2. **Streaming through the DOK proxy.** If the proxy buffers responses, tokens will arrive in one burst. The gateway already sends `X-Accel-Buffering: no`; the fallback is `--no-stream`.
3. **Proxy idle timeout.** A long non-streaming generation sends no bytes until it finishes. If DOK cuts idle connections, use streaming (the default).
4. **GPU visibility with the `ollama/ollama` base image.** `start.sh` prints `nvidia-smi` output at boot; `/api/usage` shows VRAM in use after the first request.
5. **The Docker image itself.** It has not been built locally (no Docker on the development Mac); CI builds it on every push.

## M0 validation checklist

```bash
python client/sakura_chat.py --health
```

Expect `{"ok": true, "provider_ok": true, "model_ready": true}`.

```bash
python client/sakura_chat.py --models
```

```bash
python client/sakura_chat.py --usage
```

Expect the GPU line to show an H100 with ~80 GB total.

```bash
python client/sakura_chat.py write a haiku about GPUs
```

Tokens should appear incrementally, and the footer shows tokens/sec. Then confirm that a wrong `--key` gives a 401 error, and that the task ends by itself after the idle period.

## Model persistence

| Option | Fits | Status |
|---|---|---|
| **Bake into the image** (`--build-arg BAKE_MODEL=...`) | Models under ~25 GB, e.g. `gpt-oss:20b` | Implemented. Pull is unbilled and needs no extra service. Build on a machine with enough disk; GitHub's hosted runners are too small. |
| **Pull at startup** (`ollama pull`) | Any model | Implemented (default when not baked). Billed while downloading. |
| **Sakura Object Storage cache** | Models over 30 GB, e.g. `gpt-oss:120b` | Not implemented. Sketch: on startup, sync `OLLAMA_MODELS` from a bucket if present, otherwise pull and upload once. Worth doing only if it beats the Ollama registry on speed from inside DOK, so measure both first. |
| DOK artifacts | Nothing | 20 GB cap, 72 h retention, download-only. |

Recommendation: bake `gpt-oss:20b` for everyday use; for `gpt-oss:120b`, accept the startup pull until measurements justify the Object Storage cache.

## Troubleshooting

- **Task exits immediately:** read the task log. `Configuration error: SAKURA_AI_API_KEY ...` means the key is missing, a placeholder, or under 16 characters.
- **503 from the endpoint:** the container is still starting or pulling the model.
- **`model_ready: false`:** `OLLAMA_MODEL` is not present; check the pull in the task log.
- **Task stopped by itself:** idle shutdown. Raise `IDLE_SHUTDOWN_MINUTES` or set it to `0`.
