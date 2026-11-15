# Planning a Team of DeepSeek Coding Agents on Sakura Cloud

> DRAFT. Fill in every [CONFIRM] before publishing. This post is the plan; results come in later posts.

I want a small team of AI coding agents: one plans, one writes code, one reviews and tests. I want them running on an open-weight DeepSeek model that I host myself, not on someone else's API. This post is the plan, written down before I spend money on GPUs, so you can follow along and so I can check later how wrong I was.

I'm a Sakura Internet Ambassador and I'm using Sakura Cloud GPU credit for this. [CONFIRM: voucher wording and whether to state the amount.]

## Why not just run it on my Mac?

My MacBook is an M1 Max with 64 GB of memory. It runs small models, and gets very hot doing it.

But the model I want, DeepSeek-V4-Flash, doesn't fit. Even the most compressed 1-bit version needs about 92 GB, and I have 64. So the question isn't "Mac or cloud?" any more. The Mac can't do this job at all.

## The model: DeepSeek-V4-Flash

- **Open weights, MIT licence**, so I can run it wherever I like.
- **Built for agent work.** It handles tool calls, which is how an agent reads files and runs commands.
- **Not the biggest DeepSeek.** V4-Pro is about 865 GB, more than even eight H100s hold. Flash is the realistic choice.

For the first test I use a 3-bit version from Unsloth, about 104 GB.

## The hardware: Sakura 高火力 DOK

DOK runs a container on an NVIDIA H100 and bills by the second.

| Plan | GPUs | GPU memory | Price |
|---|---|---|---|
| `h100-80gb` | 1 × H100 | 80 GB | ¥1,008 / hour |
| `h100-8gpu-80gb` | 8 × H100 | 640 GB | ¥2,988 / hour (beta) |

A 104 GB model doesn't fit in one H100's 80 GB either, so part of it will run from system memory. That's slower. How much slower is the first thing I'll measure.

## How the pieces connect

```text
My Mac
  VS Code + Cline (the agent's window)
  - reads my project files
  - asks before every edit or command
        |
        |  HTTPS + API key
        v
Sakura DOK (H100)
  Gateway (checks the key, stops the task when idle)
        |
        v
  llama-server + DeepSeek-V4-Flash
```

Two decisions here:

1. **The agent runs on my Mac; only the model runs in the cloud.** My code stays on my machine and only what the agent needs gets sent.
2. **I'm not building my own GUI.** I wanted something like Codex, a chat window that edits code. Cline, a VS Code extension, already does that and can talk to any OpenAI-compatible server. My gateway speaks that format, so pointing Cline at Sakura is just a URL and a key.

## The catch: you pay while it's on, not while you ask

I hoped to pay only when I send a question. DOK bills for the whole time the task is running, including startup. In this setup each task downloads the 104 GB model again. My first download took 7 minutes and 37 seconds. The server then hit a shared-library error, so I still have to measure how long loading the model takes.

So I use it in **planned sessions**:

| Time | What happens |
|---|---|
| At startup | Model downloads and loads |
| Once the model is ready | I work with the agent |
| Idle or 3:00 | Task stops itself and billing stops |

Two safety nets: a maximum execution time on the task, and an idle timer in my gateway that ends the task when I stop sending requests. Forgetting a running GPU is the most expensive mistake here.

If you really want pay-per-question, use a hosted API instead. Sakura's AI Engine bills per token, but it doesn't offer DeepSeek. [CONFIRM: current AI Engine model list.] Self-hosting means accepting session-style billing.

## The plan, in phases

**Phase 1: one agent on one H100.** About ¥3,000–4,000 per session. Give the agent a small project with one failing test and see whether it can fix it end to end. Measure speed, time to first answer, startup time and cost.

**Phase 2: eight H100s.** Once the first test works, I'll repeat the same job using the same model and llama.cpp settings. The eight-GPU plan costs ¥8,964 for three hours at the listed rate. I'll record how many GPUs the server uses, how much faster the job finishes, and what the job costs.

**Phase 3: the team.** Three roles share one model server:

```text
Planner  ->  Coder  ->  Reviewer / Tester
                ^              |
                +--- fixes ----+
```

- Each coder works in its own git worktree, so agents don't overwrite each other.
- Nothing is merged until tests pass and I approve it.
- Every run has a yen budget cap.
- I'll test 2 agents, then 3, and watch whether speed holds up.

## What could go wrong

- **Too slow on one H100.** Running from system memory might make the agent painful to use.
- **Tool calls might break.** DeepSeek V4 support in llama.cpp is new, and an agent is useless if its tool calls fail.
- **3-bit might be too dumb.** Compression costs quality, and published benchmarks use full weights.
- **Download time can vary,** changing the cost of each session.

## Where my code goes

Self-hosting means my prompts don't go to DeepSeek's API. They do go to Sakura's servers in Japan. That's a different trust decision, not no trust decision.

## Next

The next post is the first real run: does DeepSeek on one H100 actually fix a bug, and what did it cost?
