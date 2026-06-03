from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import click

from .config import EXAMPLE_CONFIG, load_config
from .expert import ask_expert
from .session import SessionStore


@click.group()
def main() -> None:
    """agentmesh — Multi-agent framework with persistent expert sessions.

    Runs as an MCP server for Claude Code. Each expert agent maintains its own
    persistent session and is queried in isolation, keeping the main agent's
    context clean.
    """


@main.command()
@click.option("--config", "-c", default=None, help="Path to agentmesh.yml")
def serve(config: str | None) -> None:
    """Start the MCP server (stdio transport). Add this to Claude Code's MCP config."""
    from .server import run_server

    try:
        asyncio.run(run_server(config))
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        pass


@main.command()
@click.argument("domain")
@click.argument("question")
@click.option("--config", "-c", default=None, help="Path to agentmesh.yml")
def ask(domain: str, question: str, config: str | None) -> None:
    """Ask a domain expert directly. Useful for testing expert sessions.

    \b
    Examples:
      agentmesh ask permissions "What policy covers research subjects update?"
      agentmesh ask database "Which tables track pipeline stage ordering?"
    """
    try:
        cfg = load_config(config)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if domain not in cfg.experts:
        known = ", ".join(cfg.expert_domains())
        click.echo(f"Error: unknown domain {domain!r}. Available: {known}", err=True)
        sys.exit(1)

    working_dir = Path(config).parent if config else Path.cwd()
    store = SessionStore(working_dir / cfg.session_store)

    click.echo(f"Querying expert: {domain}", err=True)
    answer = ask_expert(
        domain=domain,
        question=question,
        expert_config=cfg.experts[domain],
        store=store,
        working_dir=working_dir,
        model=cfg.model,
    )
    click.echo(answer)


@main.group()
def sessions() -> None:
    """Manage expert sessions."""


@sessions.command("list")
@click.option("--config", "-c", default=None, help="Path to agentmesh.yml")
def sessions_list(config: str | None) -> None:
    """List all expert sessions with their stats."""
    try:
        cfg = load_config(config)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    working_dir = Path(config).parent if config else Path.cwd()
    store = SessionStore(working_dir / cfg.session_store)
    domains = store.list_domains()

    if not domains:
        click.echo("No sessions found.")
        return

    click.echo(f"{'Domain':<20} {'Messages':>8}  {'Compressed':>10}  Last used")
    click.echo("-" * 65)
    for info in domains:
        last = info.last_used.strftime("%Y-%m-%d %H:%M") if info.last_used else "never"
        compressed = "yes" if info.compressed else "no"
        click.echo(f"{info.domain:<20} {info.message_count:>8}  {compressed:>10}  {last}")


@sessions.command("clear")
@click.argument("domain")
@click.option("--config", "-c", default=None, help="Path to agentmesh.yml")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def sessions_clear(domain: str, config: str | None, yes: bool) -> None:
    """Clear a specific expert session, resetting its accumulated knowledge."""
    try:
        cfg = load_config(config)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    working_dir = Path(config).parent if config else Path.cwd()
    store = SessionStore(working_dir / cfg.session_store)

    if not yes:
        click.confirm(f"Clear session for domain {domain!r}? This cannot be undone.", abort=True)

    if store.clear(domain):
        click.echo(f"Session cleared: {domain}")
    else:
        click.echo(f"No session found for domain: {domain}")


@main.command()
@click.option("--force", "-f", is_flag=True, help="Overwrite existing agentmesh.yml")
def init(force: bool) -> None:
    """Initialize agentmesh in the current directory. Creates agentmesh.yml."""
    target = Path("agentmesh.yml")
    if target.exists() and not force:
        click.echo("agentmesh.yml already exists. Use --force to overwrite.")
        sys.exit(1)

    target.write_text(EXAMPLE_CONFIG)
    click.echo("Created agentmesh.yml")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Edit agentmesh.yml to define your expert domains")
    click.echo("  2. Add agentmesh to Claude Code's MCP config:")
    click.echo("")
    click.echo('     # In .claude/settings.json:')
    click.echo('     {')
    click.echo('       "mcpServers": {')
    click.echo('         "agentmesh": {')
    click.echo('           "command": "agentmesh",')
    click.echo('           "args": ["serve"]')
    click.echo('         }')
    click.echo('       }')
    click.echo('     }')
    click.echo("")
    click.echo("  3. Open Claude Code — query_expert will be available automatically")
    click.echo("")
    click.echo("  Test an expert directly:")
    click.echo('    agentmesh ask general "What is the main entry point of this project?"')
