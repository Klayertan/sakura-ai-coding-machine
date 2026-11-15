# Running a DeepSeek coding agent on 高火力 DOK

A single agent: OpenCode on the Mac, DeepSeek-V4-Flash-0731 on a single H100. The Nov 13, 2026 DOK task detected the GPU and downloaded all four shards. `llama-server` then failed to load `libllama-server-impl.so`. Model loading and OpenCode are still unverified on DOK.

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
| Weight download | 7 min 37 sec in the Nov 13 run | About ¥128 for the transfer at the listed rate |
| Model load | Unknown | The server exited before loading began |
| Speed | Unknown | The model doesn't fit in 80 GB, so some layers run on 10 vCPUs |
| Tool calling | llama.cpp v0.5.0 has a DeepSeek V4 tool format | Read in its source; test it |

DOK deletes the working copy in `/opt/models` when the task ends. Every new task downloads and loads the model again with this setup. Requests to the same running task reuse the loaded model, and DOK bills the time the task spends idle. [Sakura's object storage tutorial](https://manual.sakura.ad.jp/cloud/koukaryoku-container/tutorial/with-storage-and-registry.html) shows how to keep a separate copy between tasks. A new task still needs to fetch and load that copy.

## Deploy on one H100 first

1. Run **Publish image to Sakura Container Registry** from the Actions tab with `Dockerfile.llamacpp` and image `sakura-ai-deepseek`. The build checks `llama-server --version` before publishing.
2. Create a DOK task on `h100-80gb`:
   - image: `YOUR-REGISTRY.sakuracr.jp/sakura-ai-deepseek:<commit-sha>` using the tag from the publish run
   - HTTP port `8080`
   - variables `GATEWAY_API_KEY`, from `openssl rand -hex 32`, and `EXPECTED_GPU_COUNT=1`
   - **max execution time: 3 hours for the first run**
3. The task checks `llama-server --version` before downloading weights. The log shows timestamps around the download and load. Check `/health` for `model_ready: true` before connecting OpenCode.
4. If the task stops with a disk space error, set `MODEL_DIR` to a path on the 500 GB working storage. The right path hasn't been confirmed on DOK.

## Repeat on eight H100s

After the one-H100 task serves requests and completes the benchmark, stop it and
start a task on `h100-8gpu-80gb` with the **same image tag**. Set
`EXPECTED_GPU_COUNT=8` and `GPU_YEN_PER_HOUR=2988`. Sakura lists this plan at
¥2,988/h in beta. [Sakura DOK plans](https://ai.sakura.ad.jp/gpu/koukaryoku-dok/)

Both runs use the same pinned `UD-IQ3_XXS` weights, context size (65,536),
one server slot and llama.cpp layer splitting. GPU layer placement is automatic.
Record which devices llama.cpp actually used and how many layers it offloaded.
Switching to another serving engine or testing concurrent agents would be a separate experiment.

## Reuse the model files on a GPU VM

On Sakura 高火力 VRT, mount a folder on an attached persistent SSD at `/opt/models` in the container. A dedicated 250 GB disk leaves space for the 104 GB model and the startup script's default free-space check. The first start fills the folder. Later starts reuse unchanged weights when the folder still contains the `.cache/huggingface/` metadata. The model still needs to load into RAM and VRAM each time the server starts. VRT's included temporary NVMe is erased when the VM stops. [Sakura VRT](https://cloud.sakura.ad.jp/products/server/gpu/) · [Hugging Face local downloads](https://huggingface.co/docs/huggingface_hub/main/en/guides/cli#download-to-a-local-folder)

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

Use one small repository with a failing test. Reset it to the same commit for
each run and give OpenCode the same prompt. After the gateway is healthy, run
the job with the same client settings and record the results below. Measure time
to first token from request send to first streamed content, and record generation
tokens per second from llama.cpp's timing log.

| Measure | 1 × H100 | 8 × H100 |
|---|---|---|
| Download time | | |
| Model load time | | |
| GPUs used and layers offloaded | | |
| Time to first token | | |
| Generation tokens/sec | | |
| Agent finished the job? | | |
| Tool calls worked? | | |
| Total task cost | | |

Also confirm that a wrong key returns 401 and that the task ends after the idle
period. Put the measured results in the [DeepSeek blog draft](../blog/02-why-i-moved-deepseek-from-my-m1-max-to-sakura.md).
