# Building My Own AI Coding Machine on Sakura Cloud H100 — Without Burning Claude or Codex Tokens

I use AI coding tools a lot, but there is one obvious constraint: the more agentic work I do, the more hosted-model quota or API tokens I consume. At the same time, as a Sakura Internet Ambassador I have access to Sakura Cloud GPU credits. That made me ask a simple question:

> Instead of paying an AI provider for every inference request, can I use Sakura's H100 GPU as the "brain" and build my own coding interface around it?

The answer is yes — as long as I am willing to run an open-weight model instead of Claude or OpenAI's hosted GPT models.

## The idea

Claude Code and Codex feel like single products, but conceptually there are two pieces:

1. the **agent/interface**, which reads files, executes tools and manages a coding workflow; and
2. the **language model**, which performs inference.

If the language model is hosted by Anthropic or OpenAI, requests consume that provider's quota. But if I run an open-weight model myself, inference happens on my own GPU instead.

My first architecture is therefore deliberately simple:

```text
MacBook
  |
  | HTTPS
  v
Sakura Cloud 高火力 DOK
  |
  v
FastAPI gateway
  |
  v
Ollama
  |
  v
NVIDIA H100
  |
  v
gpt-oss / another open-weight coding model
```

The Mac is only the interface. The expensive matrix multiplication happens on Sakura's GPU.

## Why Ollama first?

I considered starting directly with vLLM. vLLM is attractive for high-throughput serving, but Ollama gives me a much faster prototype loop: one runtime, a simple HTTP API, easy model management, and existing model packages.

For the first boot I use `gpt-oss:20b`. It is small enough to make iteration convenient. Once the networking, authentication and client are proven, the H100 80 GB gives me enough VRAM to experiment with `gpt-oss:120b` as well.

The important detail is that **gpt-oss is not ChatGPT running in Sakura Cloud**. It is an open-weight model that I execute myself. No request has to go to OpenAI's hosted inference API.

## Why Sakura 高火力 DOK?

DOK is a container-based GPU service. That fits this project well because I can package the gateway and Ollama environment into a reproducible image rather than manually maintaining a long-lived GPU server.

Sakura also provides an external connection feature. From the Internet I connect over HTTPS; Sakura maps that connection to the HTTP port exposed by my container. That means the first version does not need its own TLS reverse proxy inside the container.

The trade-off is persistence. DOK task-local storage is ephemeral, so model-download strategy matters. DOK does not bill for pulling the container image, and it allows images up to 30 GB, so the ~14 GB `gpt-oss:20b` weights can simply be baked into the image. The ~65 GB `gpt-oss:120b` does not fit; for that model the options are pulling at startup or caching the weights in Sakura Object Storage.

## The gateway

I do not expose Ollama's port directly. Instead, a tiny FastAPI service sits in front of it. The gateway provides:

- bearer-token authentication, and it refuses to start at all without a real key;
- a `/health` endpoint;
- model discovery;
- a `/api/chat` endpoint with streaming;
- an approximate GPU-cost/voucher meter with live GPU memory and utilisation;
- an idle timer that shuts the container down so a forgotten task stops billing.

The gateway talks to the model through a small provider interface rather than calling Ollama directly, so vLLM can be added later without touching the client.

The current cost meter is intentionally approximate. It uses task uptime multiplied by a configurable yen-per-hour value, which defaults to the H100 plan's ¥1,008 per hour. At that rate a ¥100,000 voucher is about 99 GPU-hours. Later I want to replace this with actual Sakura billing/task data.

## From chatbot to coding agent

A chat box alone is not a replacement for Claude Code or Codex. The interesting part comes next: the local client needs an agent loop.

A coding request such as "fix the failing tests" should eventually become:

```text
inspect repository
    ↓
select relevant files
    ↓
ask model for a plan/change
    ↓
apply patch
    ↓
run tests
    ↓
feed result back to model
    ↓
repeat until resolved
    ↓
show Git diff for approval
```

That agent can live on my Mac, meaning my source tree does not have to be stored permanently on the GPU machine. I can send only the context needed for each inference request.

## What this does — and does not — save

When I use this Sakura route:

- OpenAI hosted-model inference: **not used**
- Anthropic hosted-model inference: **not used**
- Sakura GPU compute: **used**
- ordinary Internet traffic: **used**

If I deliberately switch back to Claude or a hosted GPT model, that request will again use the corresponding provider's quota. I want both modes available so I can choose the right model for each job.

## Next steps

My roadmap is:

1. prove Ollama inference on one Sakura H100;
2. ~~add streaming responses~~ (done);
3. build a native/simple Mac GUI;
4. add repository indexing and safe file editing;
5. add a permissioned terminal/tool loop;
6. show Git diffs before destructive edits;
7. integrate Sakura task start/stop controls;
8. replace estimated cost with real usage data;
9. cache model weights efficiently;
10. benchmark Ollama against vLLM and several coding models.

The fun part of this project is that the interface, agent, model and infrastructure are all swappable. Sakura provides the GPU; the rest becomes my own engineering playground.

The source code and deployment files for this experiment live in the accompanying GitHub repository.
