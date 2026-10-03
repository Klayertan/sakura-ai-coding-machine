# Repository context subsystem — design (M2)

Status: design only. Nothing here is implemented yet.

## Goal

Given a local repository and a task, send the model the smallest set of text that lets it answer, within a fixed token budget. Never upload the whole repository per turn.

## Where it runs

Entirely on the Mac, in the client. The gateway stays a stateless inference API: source code only travels inside chat messages and is never stored on the GPU machine. This also means the subsystem needs no backend changes.

## Components

```text
client/repo/
├── index.py    RepoIndex: walk the tree, decide what is eligible
├── search.py   text and filename search over eligible files
└── pack.py     ContextPacker: fit selected content into a token budget
```

### RepoIndex

- **File listing.** In a Git repository use `git ls-files --cached --others --exclude-standard`. This gives exact `.gitignore` semantics (nested ignore files, global excludes) with no extra dependency. Outside Git, fall back to a directory walk with a built-in deny list (`.git`, `node_modules`, `.venv`, `dist`, `build`, `__pycache__`).
- **Binary detection.** Read the first 8 KB; a NUL byte or a failed UTF-8 decode means binary. Binary files are listed by name but never read.
- **Size guard.** Files over 256 KB are listed but only readable by explicit line range.
- **Secrets guard.** `.env*`, `*.pem`, `*.key`, `id_rsa*` and similar are never sent, even if tracked. This list is client configuration.
- **Path safety.** Every path is resolved and must stay inside the repository root; symlinks leading outside are skipped.
- **Record per file:** relative path, size, line count, mtime, binary flag. Cached in memory and refreshed by mtime; no on-disk index until profiling shows it is needed.

### Search

- Content search shells out to `git grep -n -I` (fast, ignore-aware, skips binaries), with a pure-Python fallback outside Git.
- Filename search is a substring/glob match over the index.
- Results are capped (for example 50 matches) and returned as `path:line: text`.

No embeddings or vector store in the first version. Grep plus the file tree is what the model-driven tool loop (M4) needs, and it has no infrastructure cost. Revisit only if evaluation shows retrieval is the bottleneck.

### ContextPacker

Builds the context block for a request from, in priority order:

1. files the user named explicitly;
2. files touched by `git status` / `git diff`;
3. search hits for the task;
4. a compact file tree (paths only, depth-limited).

Rules:

- **Budget.** A fraction of the server's context window (`OLLAMA_CONTEXT_LENGTH`, default 32,768 tokens), leaving room for the reply. Token counts are estimated at 1 token per 3 characters, which is deliberately pessimistic and avoids a tokenizer dependency.
- **Truncation.** Whole files while they fit; otherwise the matching line ranges with surrounding lines. Every truncation is marked so the model knows content is missing.
- **Format.** Each file is a fenced block headed by its path and line range, with line numbers, so that later patches (M3) can refer to exact lines.
- **Determinism.** The same inputs produce the same context, which keeps behaviour testable.

## How it feeds the later milestones

In M4 these become the agent's read-only tools: `list_files`, `read_file(path, start, end)`, `search_files(query)`. The packer supplies the initial context; the model then asks for more through tools rather than receiving everything up front.

## Testing

Unit tests against temporary Git repositories: ignore handling, binary and oversized files, the secrets deny list, path traversal attempts, budget enforcement and truncation markers.

## Open questions

- What budget split between context and reply works best for each model? Needs measurement on the H100.
- Is `git grep` retrieval good enough, or do larger repositories need symbol-level indexing (for example tree-sitter)?
- Should the gateway report the model's real context length so the client can size its budget automatically?
