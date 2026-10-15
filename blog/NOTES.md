# Blog notes

Running notes to keep the article series consistent with the repository. Not for publication as-is.

## 2026-10-03 — v0.2.0 review

Material for article 2 (*Deploying Ollama on Sakura 高火力 DOK*):

- DOK numbers worth quoting: 30 GB image limit, `linux/amd64`, H100 at ¥0.28/s (¥1,008/h, tax included), image pull unbilled, 20-day default max execution time, 20 GB / 72 h artifacts, 500 GB working storage.
- ¥100,000 voucher ≈ 99 H100-hours. Good framing for the series.
- The baked-model trick: because image pulls are not billed and the limit is 30 GB, `gpt-oss:20b` can live in the image. `gpt-oss:120b` cannot.
- Idle auto-shutdown as the answer to "what if I forget to stop the task".
- The 0.1.0 gateway ran with authentication off when the key was unset. Worth telling as a lesson: fail closed.
- Still to capture on the first real run: boot time, pull time, tokens/sec for 20b and 120b, whether the DOK proxy streams or buffers, screenshot of `--usage`.

Material for article 3 (*Connecting a Mac Coding Client to a Remote H100*):

- NDJSON streaming protocol and why the gateway has its own format instead of passing Ollama's through (provider swap).
- Errors before the first token are HTTP errors; errors mid-stream are events.

Material for article 6 (*Ollama vs vLLM*):

- `InferenceProvider` has three methods; a vLLM provider maps `chat_stream` onto `/v1/chat/completions` SSE.

## 2026-10-15 — AI Engine comparison article

`sakura-ai-engine-vs-h100-on-dok.md` (unnumbered; slot it into the series when publishing):

- AI Engine prices are launch figures (gpt-oss-120b ¥0.15 in / ¥0.75 out per 10K tokens). Prices could not be re-read from the official page here (fetch blocked); check before publishing.
- Model list churns: Kimi-K2.5 preview added 2026-03, the Anthropic-compatible endpoint now lists only `preview/Kimi-K2.6`. Recheck.
- Open question that changes the conclusion: can Ambassador voucher credit pay for AI Engine pay-as-you-go?
- All H100 vs AI Engine break-even numbers are arithmetic, not measurements. Replace with measured time to first token, tokens/sec and cost per task once the AI Engine provider exists.

Not yet verified on real hardware, so do not state as fact in an article: the Docker image build, GPU detection in the `ollama/ollama` base image on DOK, streaming behaviour through the DOK endpoint, and whether DOK accepts a user variable named `SAKURA_AI_API_KEY`.
