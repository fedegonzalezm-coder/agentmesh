# agentmesh

Multi-agent framework with persistent expert sessions and context isolation — runs as an **MCP server for Claude Code**.

## The problem

When investigating complex bugs or features that span multiple domains (permissions, database, frontend...), a single Claude Code session accumulates too much context. It gets slow, expensive, and loses focus.

### Why existing approaches don't fully solve it

**Documentation files (SKILL.md, README, notes)** give the agent orientation — but they load into *your* context, not a separate one. Every file you add to help Claude understand a domain is context your session consumes. And they're static: they don't update as Claude investigates.

**Memory files** have the same problem. They're summaries you write manually after the fact. They help with orientation but they don't capture the actual investigation — the grep results, the file reads, the chain of reasoning. Next session you start from the summary, not from where the investigation left off.

**Neither approach isolates context.** When Claude investigates a permissions issue to answer a question about pipelines, all that permissions code ends up in the pipeline session. Context bleeds.

The real problem is: **there's no way to ask "what does the permissions expert know?" without loading all of that knowledge into the current session.**

## How agentmesh solves it

You define **expert agents** — each specialized in one domain. When Claude Code needs to know something outside its current focus, it calls `query_expert`. The expert:

1. Loads its **persistent session** (accumulated knowledge from prior investigations)
2. **Investigates** using tools (read files, grep, find) — in its own isolated context
3. Returns **only the answer** to Claude Code — never the investigation steps

Claude Code's context stays clean. The expert's context grows richer over time.

```
Claude Code (main agent):
  "Why does checkout fail for guest users?"
  → calls query_expert("auth", "can guest users reach the checkout flow?")

agentmesh expert (auth):
  [loads prior session: 6 messages of accumulated knowledge]
  [reads GuestSessionMiddleware.php]
  [greps for guest user checks in checkout]
  → returns: "Guest users are blocked by RequiresAccount middleware mounted on /checkout/*"

Claude Code receives only: "Guest users are blocked by RequiresAccount middleware mounted on /checkout/*"
```

## What makes it different

| Property | SKILL.md / docs | Memory files | AutoGen / CrewAI | agentmesh |
|----------|----------------|--------------|------------------|-----------|
| Doesn't load into your context | no | no | no | **yes** |
| Captures live investigation results | no | manual | no | **yes (automatic)** |
| Persists across sessions | yes (static) | yes (static) | no | **yes (grows with use)** |
| Context isolation between domains | no | no | no | **yes (core design)** |
| Works with Claude Code as-is | yes | yes | no | **yes (MCP)** |

## Installation

```bash
pip install agentmesh
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

## Configuration (agentmesh.yml)

```yaml
model: claude-sonnet-4-6
session_store: .agentmesh/sessions   # where sessions persist (gitignored)
working_dir: .                       # root for file reads and shell commands

experts:
  orders:
    description: "Expert in order lifecycle, cancellations, refunds, and fulfilment logic"
    seed: ./docs/orders.md           # optional: pre-populate with context
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
agentmesh sessions list                # view all sessions with stats
agentmesh sessions clear payments      # reset a domain's accumulated knowledge
```

## How sessions work

Each expert's conversation history is stored in `.agentmesh/sessions/<domain>.json`. Sessions persist across Claude Code invocations — the expert gets smarter over time without repeating investigations.

Add `.agentmesh/` to your `.gitignore` (sessions contain investigation artifacts, not source code).

## Built-in tools for experts

| Tool | What it does | Restrictions |
|------|-------------|--------------|
| `read_file` | Read any file relative to `working_dir` | Read-only |
| `bash_readonly` | Run shell commands | Allowlist: `grep`, `find`, `cat`, `ls`, `git log`, `git show`, `git diff`, `git blame`, `wc`, `head`, `tail` |

## Examples

See [examples/](examples/) for ready-to-use configurations:
- [`basic/`](examples/basic/) — single general-purpose expert
- [`codebase-investigation/`](examples/codebase-investigation/) — permissions, database, frontend, API experts

## License

MIT
