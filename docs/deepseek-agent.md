# Running a DeepSeek coding agent on 高火力 DOK

A single agent: OpenCode on the Mac, DeepSeek-V4-Flash-0731 on a single H100. **Not yet tested on a real task.** Complete the M0 checklist in [dok-deployment.md](dok-deployment.md) first, because a failure here costs far more to find.

```text
OpenCode on the Mac       reads files, runs tools, asks for approval
        |  HTTPS, OpenAI API
        v
Gateway :8080             auth, idle shutdown, cost meter
        |
        v
llama-server :8081        loopback only
        |
        v
H100 80 GB + 192 GB RAM   UD-IQ3_XXS, 104 GB
```

## What to expect

| Item | Value | Status |
|---|---|---|
| Rate | ¥1,008/h | Sakura list price, read 2026-11 |
| Weights | 104.2 GB in 4 files | Hugging Face listing, read 2026-11 |
| Cold start | About 56 min, about ¥940, plus load time | Calculated at 250 Mbps; measure it |
| Speed | Unknown | The model doesn't fit in 80 GB, so some layers run on 10 vCPUs |
| Tool calling | llama.cpp v0.5.0 has a DeepSeek V4 tool format | Read in its source; test it |

The weights are downloaded on every start because task storage doesn't persist. Plan one long session instead of several short ones. If the DOK network is faster than 250 Mbps in practice, these figures improve.

## Deploy

1. Run **Publish image to Sakura Container Registry** from the Actions tab with `Dockerfile.llamacpp` and image `sakura-ai-deepseek`.
2. Create a DOK task on `h100-80gb`:
   - image: `YOUR-REGISTRY.sakuracr.jp/sakura-ai-deepseek:latest`
   - HTTP port `8080`
   - variable `GATEWAY_API_KEY`, from `openssl rand -hex 32`
   - **max execution time: 3 hours for the first run**
3. The endpoint returns 503 until the model has loaded. The task log shows timestamps around the download and load.
4. If the task stops with a disk space error, set `MODEL_DIR` to a path on the 500 GB working storage. The right path hasn't been confirmed on DOK.

## Connect OpenCode

Add this to `opencode.json` in your project, using your own endpoint:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "sakura": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Sakura DeepSeek",
      "options": {
        "baseURL": "https://YOUR-DOK-ENDPOINT/v1",
        "apiKey": "{env:SAKURA_AI_API_KEY}"
      },
      "models": {
        "deepseek-v4-flash": {
          "name": "DeepSeek V4 Flash",
          "limit": { "context": 65536, "output": 8192 }
        }
      }
    }
  },
  "model": "sakura/deepseek-v4-flash"
}
```

## Benchmark and record

Use one fixed job: fix a failing test in a small repository. Then fill in this table for the blog.

| Measure | Result |
|---|---|
| Download time | |
| Model load time | |
| Layers on GPU, from the task log | |
| Time to first token | |
| Tokens/sec | |
| Agent finished the job? | |
| Tool calls worked? | |
| Total task cost | |

Also confirm that a wrong key returns 401 and that the task ends after the idle period.

## Decide what's next

- **Agent finishes and speed is acceptable:** stay on this setup and start on multiple agents.
- **Tool calls fail:** debug this before changing hardware, because more GPUs won't fix it.
- **Works but too slow:** move to vLLM on `h100-8gpu-80gb` at ¥2,988/h. This plan is beta, and the official serving example targets different hardware.
