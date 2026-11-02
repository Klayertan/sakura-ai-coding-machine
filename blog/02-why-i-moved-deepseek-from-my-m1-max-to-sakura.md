# My 64 GB M1 Max Can't Run This Model, So I Moved It to Sakura Cloud

> DRAFT. Do not publish until every [MEASURE] and [CONFIRM] below is filled in.

Running AI models on my MacBook has one obvious symptom: it gets very hot. Mine is an M1 Max with 64 GB of memory, which is about as well equipped as this generation gets, and it still turns into a hand warmer. [MEASURE: peak temperature, power and fan speed during a 15-minute `gpt-oss:20b` run.]

Heat turned out to be the smaller problem. I wanted to run DeepSeek-V4-Flash as a coding agent, and it needs more memory than my Mac has. Even the most heavily compressed 1-bit version needs about 92 GB, and I have 64.

## Why this model

DeepSeek-V4-Flash-0731 is open-weight and MIT licensed, and DeepSeek built it for agent work. That means I can run it myself rather than paying per token. As a Sakura Internet Ambassador I have GPU credit [CONFIRM: voucher wording], so a Sakura H100 was the natural place to try.

## What I built

The Mac stays the interface. OpenCode reads my files and asks before it changes anything, while the model runs on Sakura 高火力 DOK.

```text
OpenCode on the Mac
        |
        v
Authenticated gateway on Sakura DOK
        |
        v
llama-server
        |
        v
NVIDIA H100 + DeepSeek-V4-Flash
```

## It doesn't quite fit on one H100 either

A single H100 has 80 GB of VRAM. The 3-bit version I chose is 104 GB, so part of the model has to run from system RAM.

[MEASURE: layers on GPU, tokens/sec, time to first token.]

## The cloud has its own costs

The Mac has no hourly fee and starts immediately. Sakura costs ¥1,008 per hour, and DOK's storage doesn't persist, so the weights are downloaded on every start. At 250 Mbps that should take about 56 minutes, or about ¥940.

[MEASURE: real download time, load time and cost of the benchmark job.]

## Can it do real work?

[MEASURE: did the agent fix the failing test? What went wrong? How did the tool calls behave?]

## Was it worth moving?

[Write after the first real run. Say when the Mac is still the better choice.]

## Where my code goes

Running the weights myself means my prompts don't go to DeepSeek's API. They do go to Sakura's servers, so this is a different trust decision, not the absence of one.

## Next

Once one agent works reliably, I want to try a small team of agents: a planner, a coder and a reviewer sharing the same model server.
