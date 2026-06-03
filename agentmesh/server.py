from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import Config, load_config
from .expert import ask_expert
from .session import SessionStore


class ExpertRunner:
    """Runs expert queries with per-domain locking and async-safe execution.

    Different domains run concurrently. Same-domain queries are serialized
    to prevent session write races.
    """

    def __init__(self, config: Config, store: SessionStore, working_dir: Path) -> None:
        self._config = config
        self._store = store
        self._working_dir = working_dir
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def run(self, domain: str, question: str) -> str:
        async with self._locks[domain]:
            return await asyncio.to_thread(
                ask_expert,
                domain=domain,
                question=question,
                expert_config=self._config.experts[domain],
                store=self._store,
                working_dir=self._working_dir,
                model=self._config.model,
            )


def create_server(config: Config, working_dir: Path) -> Server:
    app = Server("agentmesh")
    store = SessionStore(working_dir / config.session_store)
    runner = ExpertRunner(config, store, working_dir)

    def _query_expert_description() -> str:
        domains = config.expert_domains()
        domain_list = ", ".join(f'"{d}"' for d in domains)
        descriptions = "\n".join(
            f"- {d}: {cfg.description}" for d, cfg in config.experts.items()
        )
        return (
            "Ask a domain expert agent a specific question. "
            "The expert has persistent knowledge about their domain and will investigate "
            "using tools (read files, run grep/find) if needed. "
            "The main agent (you) only receives the final answer — never the expert's investigation steps. "
            f"Available domains: {domain_list}\n\n"
            f"Domain descriptions:\n{descriptions}"
        )

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="query_expert",
                description=_query_expert_description(),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": f"The expert domain to query. One of: {', '.join(config.expert_domains())}",
                            "enum": config.expert_domains(),
                        },
                        "question": {
                            "type": "string",
                            "description": "Specific, concrete question for the expert. Be precise.",
                        },
                    },
                    "required": ["domain", "question"],
                },
            ),
            Tool(
                name="list_experts",
                description="List all registered expert domains with their descriptions.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="session_info",
                description="Show stats for a specific expert session (message count, last used).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string", "description": "Domain name to inspect"}
                    },
                    "required": ["domain"],
                },
            ),
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "query_expert":
            domain = arguments["domain"]
            question = arguments["question"]
            if domain not in config.experts:
                known = ", ".join(config.expert_domains())
                return [TextContent(type="text", text=f"Unknown domain: {domain!r}. Known: {known}")]
            answer = await runner.run(domain, question)
            return [TextContent(type="text", text=answer)]

        if name == "list_experts":
            lines = [f"**{d}**: {cfg.description}" for d, cfg in config.experts.items()]
            return [TextContent(type="text", text="\n".join(lines))]

        if name == "session_info":
            domain = arguments["domain"]
            domains = store.list_domains()
            info = next((d for d in domains if d.domain == domain), None)
            if info is None:
                return [TextContent(type="text", text=f"No session found for domain: {domain!r}")]
            last = info.last_used.isoformat() if info.last_used else "never"
            compressed = " (compressed)" if info.compressed else ""
            return [
                TextContent(
                    type="text",
                    text=f"Domain: {domain}\nMessages: {info.message_count}{compressed}\nLast used: {last}",
                )
            ]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return app


async def run_server(config_path: str | Path | None = None) -> None:
    working_dir = Path(config_path).parent if config_path else Path.cwd()
    config = load_config(config_path)
    app = create_server(config, working_dir)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
