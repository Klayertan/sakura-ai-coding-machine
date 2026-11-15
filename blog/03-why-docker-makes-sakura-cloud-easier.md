# Why Docker Makes Sakura Cloud Easier to Use

> DRAFT. Fill in every [MEASURE] and [CONFIRM] before publishing.

I don't have an NVIDIA GPU at home. My development machine is an M1 Max, and the place I actually run models is a Sakura 高火力 DOK H100. The thing that connects the two is a Docker image. This post explains why I ended up packaging everything that way, and what Docker gives you when Sakura Cloud is the place your code runs.

I'm a Sakura Internet Ambassador and I use GPU credit from that programme. [CONFIRM: voucher wording.]

## 1. On DOK, the image *is* the deployment

DOK doesn't give you a server to SSH into. You give it a container image, a plan and some environment variables, and it runs the task. So Docker isn't one option among several here; it's the only interface.

That turns out to be a feature. Everything the task needs is written down in the `Dockerfile`:

```dockerfile
FROM ollama/ollama:${OLLAMA_VERSION}
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ...
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
CMD ["./start.sh"]
```

There's no hand-configured machine to forget about, and nothing to rebuild from memory next month.

## 2. You don't have to install CUDA

Setting up GPU drivers and CUDA by hand is the slowest part of most GPU projects. With Docker I start from an image that already has the GPU runtime:

- `ollama/ollama` for the Ollama build
- `ghcr.io/ggml-org/llama.cpp:server-cuda-v0.5.0` for the DeepSeek build

The DOK host provides the driver and the base image provides the libraries. My `Dockerfile` only adds a small Python gateway on top.

## 3. Swapping the engine is swapping the base image

The same gateway code runs in two images. One serves models through Ollama; the other runs `llama-server` for models too large for Ollama packaging. Changing inference engines meant writing a second `Dockerfile` about twenty lines long, not rebuilding a server.

From the client's point of view nothing changes: it talks to the same authenticated gateway on port 8080 either way.

## 4. Pay attention to what's billed

This is where Docker and DOK's pricing fit together well. On the H100 plan:

- Run time is billed per second (¥0.28/s, about ¥1,008/h including tax).
- **Image pulls and queue time are not billed.**
- Images can be up to 30 GB.

So a model inside the image costs nothing to "download", while a model fetched when the container starts is billed by the second. My `Dockerfile` has an optional build argument for exactly this:

```bash
docker build --build-arg BAKE_MODEL=gpt-oss:20b .
```

`gpt-oss:20b` (about 14 GB) fits under the limit. `gpt-oss:120b` (about 65 GB) doesn't, and pulling it at startup takes roughly 35 minutes at DOK's 250 Mbps, or about ¥600.

[MEASURE: real boot time with a baked model vs. a startup pull.]

## 5. Build in CI, push to Sakura's registry

Building a large image on a home connection and then uploading it is slow. Instead, a GitHub Actions workflow builds the image and pushes it straight to Sakura Container Registry:

```yaml
- uses: docker/build-push-action@v6
  with:
    file: ${{ inputs.dockerfile }}
    platforms: linux/amd64
    push: true
    tags: |
      ${{ inputs.registry }}/${{ inputs.image }}:latest
      ${{ inputs.registry }}/${{ inputs.image }}:${{ github.sha }}
```

Two things matter here:

- **`linux/amd64`.** DOK hosts are amd64 and my Mac is ARM. Building in CI avoids cross-compiling on the laptop.
- **Tagging with the commit SHA.** Every DOK task can point at an exact build, and going back to an earlier version means changing one tag.

## 6. The same image runs locally

Anyone with an NVIDIA GPU can run the same container with Docker Compose before spending cloud credit:

```yaml
services:
  sakura-ai:
    build: .
    ports:
      - "127.0.0.1:8080:8080"   # loopback only
    env_file: .env
```

The port is bound to loopback on purpose, so a local test never exposes the gateway to the network.

## 7. Configuration stays outside the image

Secrets go in as environment variables, not into the image. One thing I learned: DOK reserves the `SAKURA_` prefix for its own variables, so the gateway also accepts `GATEWAY_API_KEY`. If the key is missing or too short, the container exits immediately with a clear error rather than running without authentication.

## Things Docker doesn't solve

- **Nothing persists.** When a DOK task ends, everything outside the artifact directory is deleted. Docker doesn't change that, which is why baking the model matters.
- **The 30 GB limit is real.** Large models still need a startup download or an Object Storage cache, which I haven't built yet.
- **Cold starts.** A task takes time to start, and a laptop doesn't. [MEASURE: time from task submit to first token.]

## Summary

On Sakura Cloud, Docker gives you:

1. A deployment described entirely in one file
2. GPU support without installing CUDA yourself
3. Engine swaps by changing the base image
4. Lower bills, by baking models into unbilled image pulls
5. Builds in CI pushed straight to Sakura Container Registry
6. Local testing with the same image
7. Secrets kept out of the image

The code is at [Klayertan/sakura-ai-coding-machine](https://github.com/Klayertan/sakura-ai-coding-machine). [CONFIRM: repo is public.]
