# My Own H100 or Sakura's AI Engine? Pricing Out Two Ways to Run gpt-oss on Sakura

In the [first article](01-building-a-personal-ai-coding-machine-on-sakura-h100.md) I described my plan: rent a Sakura Cloud H100 on 高火力 DOK, run an open-weight model like `gpt-oss` on it, and put a small gateway in front so my Mac can use it as a coding assistant without spending Claude or OpenAI tokens.

While I was building it, I noticed that Sakura sells a second way to reach the same model. **さくらのAI Engine** is a hosted inference API: no GPU to rent, no container to build, just an API key and an OpenAI-compatible endpoint. One of its models is `gpt-oss-120b`, the very model I was planning to load onto my H100.

So the obvious question is: why rent the GPU at all?

This article puts the two options side by side, works through the numbers, and explains where I ended up.

> **Prices and terms change.** Figures below come from Sakura's announcements and documentation as published, and were checked again on 2026-10-15. The AI Engine model list in particular has changed several times since launch. Check the official pricing page before relying on any number here.

## The two options

```text
Option A: my own H100                     Option B: AI Engine

Mac client                                Mac client
  |                                         |
  | HTTPS                                   | HTTPS
  v                                         v
DOK task (billed per second)              api.ai.sakura.ad.jp/v1
  |                                         (billed per token,
FastAPI gateway                              3,000 free requests/month)
  |                                         |
Ollama                                      v
  |                                       Sakura's shared GPUs
H100 80 GB, only mine
```

**Option A, H100 on DOK.** I rent a whole H100 by the second, run my own container, and choose any open-weight model that fits in 80 GB of VRAM. The meter runs from the moment the container starts until it stops, whether or not I send a request.

**Option B, AI Engine.** Sakura runs the GPUs and I send API requests. Billing counts tokens rather than time, and each month's first 3,000 chat requests are free.

## What each costs

### H100 on DOK

| Item | Figure |
|---|---|
| H100 plan | ¥0.28/s = **¥1,008/hour** incl. tax, 60 s minimum |
| Image pull and queue time | Not billed |
| Model pulled at startup (`gpt-oss:20b`) | ~8 minutes, roughly ¥130 per start |
| ¥100,000 voucher | ≈ 99 GPU-hours |

The rate is easy to read. The catch is that you pay for the clock, not for the work done. A task left running while I read a diff, eat lunch, or forget about it costs the same ¥0.28 every second. That's why the gateway has an idle auto-shutdown.

### AI Engine

AI Engine has two plans. Both include the same monthly free allowance:

| Free allowance (per month) | |
|---|---|
| Chat completions | 3,000 requests |
| Embeddings | 10,000 requests |
| Audio transcription | 50 requests |

The difference is what happens after the allowance runs out:

- **基盤モデル無償プラン (free plan):** you are never billed. Once the allowance is used up, requests are rate-limited until it resets at the start of the next month.
- **従量課金プラン (pay-as-you-go):** usage beyond the allowance is billed per token.

Pay-as-you-go prices at launch (incl. tax, per 10,000 tokens):

| Model | Input | Output |
|---|---|---|
| `gpt-oss-120b` | ¥0.15 | ¥0.75 |
| `Qwen3-Coder-480B-A35B-Instruct-FP8` | ¥0.30 | ¥2.50 |

Other things to know:

- The free plan caps the number of sign-ups. Once the cap is reached, Sakura stops accepting new applications.
- Even with allowance left, a busy service can answer **429 Too Many Requests**. Sakura's advice is to wait a few minutes and retry.
- Signing up takes a Sakura member ID, phone verification, and a Sakura Cloud project.

## Working through the numbers

Free requests are not all equal, because each AI Engine request is priced by its tokens. A one-line chat question and an agent step carrying 20,000 tokens of repository context each use up one of the 3,000 free requests. On pay-as-you-go, though, they cost very different amounts.

Here are two typical request shapes, priced at `gpt-oss-120b` rates:

| Request | Input | Output | Pay-as-you-go cost |
|---|---|---|---|
| Quick question | 2,000 tokens | 500 tokens | ¥0.03 + ¥0.04 ≈ **¥0.07** |
| Agent step (files + test output in context) | 20,000 tokens | 1,000 tokens | ¥0.30 + ¥0.08 ≈ **¥0.38** |

**One H100 hour (¥1,008) buys about 2,700 agent steps on AI Engine.**

To break even, my H100 would have to finish an agent step every 1.3 seconds, nonstop, for a whole hour. I haven't benchmarked the H100 yet, so I can't give its real speed. But generating a thousand-token answer for a 20,000-token prompt every 1.3 seconds is far beyond one person's coding session. A realistic session also spends most of its time with the GPU idle while I read, think, and run tests, and DOK bills for all of that.

The free allowance tells the same story from the other side:

- 3,000 free requests × ¥0.38 ≈ **¥1,100**, or about **one H100 hour**.
- If a coding task takes around 20 model calls, 3,000 requests cover about **150 tasks a month**, roughly five per working day.

**For one developer's day-to-day coding, the free plan beats the H100 on price by a wide margin.** On pay-as-you-go, the H100 only pulls ahead with sustained, near-continuous load.

## What the H100 does better

Price isn't the only factor. Running my own GPU still does some things AI Engine can't:

1. **Any model.** On DOK I can run any open-weight model that fits in 80 GB: other coding models, quantisations, my own fine-tunes, or a model released yesterday. AI Engine offers only what Sakura has chosen to host, and that list changes.
2. **No shared queue.** The GPU is mine. There's no rate limit, no 429 when the service is busy, and no monthly cap to plan around. If I want to run an agent overnight against a large repository, nothing stops me.
3. **Data stays in my container.** Prompts go to a GPU I rent, in a container I built, and nobody else's service touches them. AI Engine also runs in Sakura's Japanese data centres, which already satisfies many data-residency requirements. But "nobody else's software sees my code" is a stronger guarantee than "a domestic provider's API sees my code".
4. **It's an engineering playground.** Benchmarking Ollama against vLLM, measuring tokens per second, and testing how model weights load from Object Storage: none of that exists without the GPU. I started this project partly to learn those things.
5. **The voucher.** My Sakura Ambassador credits are meant for Sakura Cloud. I haven't yet confirmed whether they can also pay for AI Engine's pay-as-you-go usage. If they can't, the H100 is effectively free to me until the voucher runs out, which changes the comparison above.

## What AI Engine does better

1. **No startup wait.** The first token comes back in seconds. With DOK, every session waits for a task to start and, with the slim image, roughly eight minutes for the model to download.
2. **No idle cost.** Forgetting to stop something costs nothing. With DOK, the idle timer and maximum execution time stand between me and a large bill.
3. **No infrastructure to maintain.** I don't need a Dockerfile, a registry, a publish workflow, `start.sh` or GPU drivers. That's half of this repository.
4. **Bigger models without the weight problem.** `gpt-oss-120b` (~65 GB) can't be baked into a 30 GB DOK image, so on my H100 it costs ¥600 or more per start just to download. On AI Engine it's simply there, as is `Qwen3-Coder-480B`, which wouldn't fit on one H100 at all.
5. **Standard APIs.** The endpoint is OpenAI-compatible (`/v1/chat/completions`), so existing tools and SDKs work by changing the base URL. Sakura also documents an Anthropic-compatible `/v1/messages` endpoint, though at the time of writing only a preview model was available on it. I haven't tested it yet.

## Side by side

| | H100 on DOK | AI Engine (free plan) | AI Engine (pay-as-you-go) |
|---|---|---|---|
| Billing unit | Seconds of task time | None | Tokens |
| Idle cost | ¥1,008/hour | ¥0 | ¥0 |
| Typical agent step | Depends on how busy the GPU is | 1 of 3,000 monthly requests | ≈ ¥0.38 |
| Startup wait | Task start + model pull | None | None |
| Model choice | Anything that fits in 80 GB | Sakura's list | Sakura's list |
| Largest practical model | ~120B (with a slow pull) | Whatever is hosted | Whatever is hosted (incl. 480B) |
| Rate limits | None | Monthly cap, plus 429s at busy times | 429s at busy times |
| Who sees prompts | Only my container | Sakura's service | Sakura's service |
| Operating effort | High | None | None |
| Surprise-bill risk | Real (forgotten task) | None | Low (pay per use) |

## Where I'm going with it

I'm not choosing one or the other. The gateway was built with an `InferenceProvider` interface so the backend can be swapped without touching the Mac client. That was originally meant for adding vLLM, but an AI Engine backend fits the same slot: it maps the gateway's `chat_stream` onto `/v1/chat/completions` streaming, exactly as a vLLM backend would.

The plan:

- **AI Engine for everyday use.** Quick questions and ordinary agent tasks go to `gpt-oss-120b` on the free plan. That costs nothing and needs no startup.
- **H100 for heavy use and experiments.** Overnight agent runs, models AI Engine doesn't host, sensitive code, and anything I want to benchmark.
- **The same client and the same commands for both,** with one setting to switch between them.

When I first saw AI Engine, the honest reaction was "this makes my H100 pointless". After working through the numbers, I'd put it differently: AI Engine is the cheaper option for everyday coding. The H100 is the one that gives me any model I want, no rate limits, prompts that stay in my own container, and a GPU to experiment on.

## Next

The next step is to add the AI Engine backend to the gateway, send real requests through both backends, and replace the estimates in this article with measurements: time to first token, tokens per second, and what a real coding task actually costs on each.

---

*Sources: Sakura Internet's AI Engine general-availability announcement (2025-09-24), the AI Engine product page and manual, the Kimi-K2.5 preview announcement (2026-03-17), and Sakura's DOK pricing page. Coverage by @IT and INTERNET Watch was used to cross-check launch prices.*
