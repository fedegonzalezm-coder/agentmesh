from __future__ import annotations

import subprocess
from pathlib import Path

from .config import ExpertConfig
from .session import SessionStore

_ALLOWED_TOOLS = " ".join([
    "Read",
    "Bash(grep *)", "Bash(find *)", "Bash(cat *)", "Bash(ls *)",
    "Bash(git log *)", "Bash(git show *)", "Bash(git diff *)",
    "Bash(git blame *)", "Bash(wc *)", "Bash(head *)", "Bash(tail *)",
])

_DEFAULT_SYSTEM = """\
You are a domain expert agent. Answer specific questions about the codebase by \
investigating with your tools when needed.

Rules:
- Use tools to look for evidence before answering.
- Only use READ-ONLY commands. Do not write, delete, or modify anything.
- Return only the conclusion — not your investigation steps.
- If you cannot determine the answer, say so and explain what you tried.
"""

# How many prior Q&A pairs to include in context (each pair = 2 messages)
_MAX_HISTORY_PAIRS = 10


def ask_expert(
    domain: str,
    question: str,
    expert_config: ExpertConfig,
    store: SessionStore,
    working_dir: str | Path,
    model: str = "claude-sonnet-4-6",
    api_key: str | None = None,  # kept for interface compatibility, unused in CLI mode
) -> str:
    working_dir = Path(working_dir)
    messages = store.load(domain)

    if not messages and expert_config.seed:
        seed_path = working_dir / expert_config.seed
        if seed_path.exists():
            messages = store.seed(seed_path.read_text(encoding="utf-8", errors="replace"))

    messages.append({"role": "user", "content": question})

    system = _build_system(expert_config, messages[:-1])
    answer = _run_claude_cli(question, system, working_dir, model)

    messages.append({"role": "assistant", "content": answer})
    store.save(domain, messages)
    return answer


def _build_system(expert_config: ExpertConfig, prior_messages: list[dict]) -> str:
    base = expert_config.system_prompt or (
        f"You are an expert on: {expert_config.description}\n\n{_DEFAULT_SYSTEM}"
    )
    history = _format_history(prior_messages[-(_MAX_HISTORY_PAIRS * 2):])
    if history:
        base += f"\n\nPrior investigation context for this domain:\n---\n{history}\n---"
    return base


def _format_history(messages: list[dict]) -> str:
    """Extract Q&A text pairs from stored messages, skipping tool use blocks."""
    lines = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, str):
            if role == "user":
                lines.append(f"Q: {content}")
            elif role == "assistant":
                lines.append(f"A: {content}")
        elif isinstance(content, list) and role == "assistant":
            texts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
            if texts:
                lines.append(f"A: {' '.join(texts)}")
    return "\n\n".join(lines)


def _run_claude_cli(
    question: str,
    system: str,
    working_dir: Path,
    model: str,
) -> str:
    cmd = [
        "claude", "--print", question,
        "--system-prompt", system,
        "--allowedTools", _ALLOWED_TOOLS,
        "--output-format", "text",
        "--model", model,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(working_dir),
            timeout=180,
        )
        if result.returncode != 0:
            error = (result.stderr or result.stdout).strip()
            return f"Expert error (exit {result.returncode}): {error}"
        return result.stdout.strip()
    except FileNotFoundError:
        return (
            "Error: 'claude' CLI not found. "
            "Install with: npm install -g @anthropic-ai/claude-code"
        )
    except subprocess.TimeoutExpired:
        return "Error: expert query timed out after 180 seconds."
