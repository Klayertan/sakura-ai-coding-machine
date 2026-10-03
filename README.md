# Sakura AI Coding Machine 🌸⚡

Use a Sakura Cloud GPU as your personal AI inference server, with Ollama serving an open-weight model and a small authenticated API that your Mac can call.

**Goal:** use Sakura GPU credits for inference instead of consuming Anthropic/OpenAI hosted-model tokens.

## Architecture

```text
MacBook / custom client
        |
        | HTTPS
        v
Sakura 高火力 DOK external endpoint
        |
        | HTTP inside Sakura
        v
FastAPI gateway :8080
        |
        v
Ollama :11434
        |
        v
NVIDIA H100 + open-weight model
```

No OpenAI or Anthropic API is required for inference. `gpt-oss` is an open-weight model; running it yourself does not consume ChatGPT/Codex API quota.

## Why start with `gpt-oss:20b`?

It is only about 14 GB in Ollama, so startup/pull time is much friendlier for an ephemeral DOK task. After the pipeline works, try `gpt-oss:120b` on the 80 GB H100. The 120B Ollama package is about 65 GB and is designed to fit a single 80 GB GPU.

## Quick start on Sakura DOK

1. Create a Sakura Container Registry repository.
2. Build this image on your Mac or GitHub Actions.
3. Push the image to your Sakura registry.
4. Create a 高火力 DOK task using the H100 plan.
5. Set environment variables from `.env.example`.
6. Configure the task's listening port to `8080` using DOK external connection.
7. Copy the generated public HTTPS endpoint.
8. On your Mac:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r client/requirements.txt
export SAKURA_AI_URL='https://YOUR-DOK-ENDPOINT'
export SAKURA_AI_API_KEY='your-secret'
python client/sakura_chat.py explain this C++ segmentation fault
```

## Security

Never expose raw Ollama (`11434`) to the Internet. Expose only the authenticated gateway on port `8080`. Use a long random API key. This MVP uses bearer-token authentication; v0.2 should add rate limiting and stronger identity controls.

## DOK persistence warning

High-firepower DOK task-local files disappear when the task ends except designated artifacts. Therefore a model pulled by Ollama may need to be downloaded again on a new task. For production, use Sakura Object Storage/model caching or switch to a serving path that mounts/downloads model weights efficiently at startup.

## Roadmap

- [x] Ollama on Sakura H100
- [x] Authenticated FastAPI gateway
- [x] `/health` with rough voucher/cost estimator
- [x] Mac CLI client
- [ ] Streaming responses
- [ ] Native macOS GUI
- [ ] Repository-aware coding agent loop
- [ ] Read/write files + Git diff approval
- [ ] Safe terminal tool execution
- [ ] Sakura task start/stop control
- [ ] Live GPU utilization and actual Sakura billing ingestion
- [ ] Object Storage model cache
- [ ] vLLM backend
- [ ] OpenCode/Aider adapter

## Blog

See [`blog/01-building-a-personal-ai-coding-machine-on-sakura-h100.md`](blog/01-building-a-personal-ai-coding-machine-on-sakura-h100.md).
