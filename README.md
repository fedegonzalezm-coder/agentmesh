# agentmesh

[![PyPI version](https://img.shields.io/pypi/v/agentmesh-mcp)](https://pypi.org/project/agentmesh-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/agentmesh-mcp)](https://pypi.org/project/agentmesh-mcp/)
[![CI](https://img.shields.io/github/actions/workflow/status/fedegonzalezm-coder/agentmesh/ci.yml?branch=master)](https://github.com/fedegonzalezm-coder/agentmesh/actions)
[![License](https://img.shields.io/github/license/fedegonzalezm-coder/agentmesh)](https://github.com/fedegonzalezm-coder/agentmesh/blob/master/LICENSE)

Per-domain expert agents you can query without loading their knowledge into your context — runs as an **MCP server for Claude Code**.

## The problem

When investigating bugs or features that span multiple domains (permissions, database, frontend...), a single Claude Code session accumulates context fast. To answer one question about the frontend, it ends up reading permissions code, and that code now lives in your session for the rest of the conversation. Context bleeds and the session gets slower and less focused.

You want to be able to ask *"what does the permissions code say about X?"* and get back **just the answer** — without the investigation that produced it ending up in your window.

## What agentmesh does

You define **expert agents** in YAML — each scoped to one domain. When Claude Code needs something outside its current focus, it calls `query_expert`. The expert:

1. Runs as a **separate `claude --print` process** — its own isolated context
2. **Investigates** using read-only tools (read files, grep, find) to answer the question
3. Returns **only the final answer** to your session — never the investigation steps
4. Saves the **question + answer** to a per-domain log, so future queries to that domain carry the prior Q&A as context

```
Claude Code (main agent):
  "Why does checkout fail for guest users?"
  → calls query_expert("auth", "can guest users reach the checkout flow?")

agentmesh expert (auth):
  [spawned as a separate process, with prior auth Q&A in its system prompt]
  [reads GuestSessionMiddleware.php, greps for guest checks in checkout]
  → returns: "Guest users are blocked by RequiresAccount middleware on /checkout/*"

Claude Code receives only that one sentence. The file reads and greps stay in the
expert's process and never touch your session.
```

## Honest scope — what it is and isn't

**What persists is the Q&A, not the investigation.** agentmesh stores each question and its final answer. It does **not** store the grep output, file contents, or reasoning the expert used to get there. So "the expert remembers" means "the last few Q&A pairs for that domain are prepended to the next query as text" — closer to an auto-updated memory file than a stateful agent that learns.

**Each query is a fresh process.** The expert has no live memory between calls beyond that stored Q&A text. Every `query_expert` call spawns a full `claude --print` invocation, so it costs a real model call and can take time on deep questions.

**Claude Code already covers part of this.** Its built-in Agent/Task tool gives you context isolation *within a session*, and its memory system persists facts *across* sessions. What agentmesh adds on top:

| | Claude Agent tool | Claude memory | agentmesh |
|---|---|---|---|
| Isolates context within a session | yes | n/a | yes |
| Persists across sessions | no | yes (you curate) | yes (auto, per domain) |
| Domains defined in shareable/versioned config | no | no | **yes (YAML in repo)** |
| Explicit, named routing target per domain | no | no | **yes (`query_expert("auth", …)`)** |

If you work in single long sessions, the Agent tool covers most of this. agentmesh earns its place when a **team shares the same domain experts via a versioned YAML file**, or when you repeatedly query the same domains across many separate sessions and want that routing to be explicit and named.

## Installation

```bash
pip install agentmesh-mcp
```

## Quickstart

```bash
# 1. In your project root
cd my-project
agentmesh init
# → creates agentmesh.yml in the current directory

# 2. Edit agentmesh.yml (created in my-project/agentmesh.yml) to define your experts
# 3. Register with Claude Code:
claude mcp add --transport stdio agentmesh -- agentmesh serve --config /path/to/my-project/agentmesh.yml
```

```bash
# 4. Verify Claude Code picked it up
claude mcp list
# → agentmesh   stdio   /path/to/agentmesh serve ...

# 5. Test an expert directly (no Claude Code needed)
agentmesh ask orders "How does the order cancellation flow work?"
```

> **Note:** experts run via the `claude` CLI, so you need [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated. The expert inherits your Claude Code auth — no separate API key required.

## Configuration (agentmesh.yml)

```yaml
model: claude-sonnet-4-6
session_store: .agentmesh/sessions   # where per-domain Q&A logs persist (gitignored)
working_dir: .                       # root for file reads and shell commands

experts:
  orders:
    description: "Expert in order lifecycle, cancellations, refunds, and fulfilment logic"
    seed: ./docs/orders.md           # optional: loaded as initial context on the first call
    tools:
      - read_file
      - bash_readonly               # grep, find, cat, git log, ls

  payments:
    description: "Expert in payment processing, providers, retries, and webhooks"
    tools:
      - read_file
      - bash_readonly

  auth:
    description: "Expert in authentication, sessions, guest users, and access control"
    tools:
      - read_file
      - bash_readonly

  frontend:
    description: "Expert in React components, state management, and UI patterns"
    tools:
      - read_file
```

## CLI reference

```bash
agentmesh init                         # create agentmesh.yml
agentmesh serve                        # start MCP server (used by Claude Code)
agentmesh ask orders "How does order cancellation work?"   # query an expert directly
agentmesh sessions list                # view all domains with stats
agentmesh sessions clear payments      # reset a domain's stored Q&A
```

## How sessions work

Each expert's question/answer history is stored in `.agentmesh/sessions/<domain>.json`. On the next query to that domain, the most recent Q&A pairs (last 10 by default) are prepended to the expert's system prompt as text, so it answers with awareness of what was asked before.

Note this is **stored Q&A, not stored investigation** — if an earlier answer was wrong, that wrong answer carries forward until you run `agentmesh sessions clear <domain>`. Treat sessions as a curated log, not an infallible memory.

Add `.agentmesh/` to your `.gitignore` (sessions contain question/answer artifacts, not source code).

## Built-in tools for experts

Experts run through `claude --print` with a read-only allowlist:

| Tool | What it does |
|------|-------------|
| `Read` | Read any file relative to `working_dir` |
| `Bash` (allowlisted) | `grep`, `find`, `cat`, `ls`, `git log`, `git show`, `git diff`, `git blame`, `wc`, `head`, `tail` |

No write, delete, or network commands are permitted.

## Examples

See [examples/](examples/) for ready-to-use configurations:
- [`basic/`](examples/basic/) — single general-purpose expert
- [`codebase-investigation/`](examples/codebase-investigation/) — orders, payments, auth, frontend experts

## License

MIT
