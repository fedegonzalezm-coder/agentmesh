"""
Tests for concurrent query_expert behavior via ExpertRunner:
- Different domains run in parallel (locks don't block each other)
- Same domain queries are serialized (no session write race)
"""
import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from agentmesh.config import Config, ExpertConfig
from agentmesh.server import ExpertRunner
from agentmesh.session import SessionStore


def make_config() -> Config:
    return Config(
        experts={
            "alpha": ExpertConfig(description="Alpha expert"),
            "beta": ExpertConfig(description="Beta expert"),
        }
    )


@pytest.fixture
def runner(tmp_path: Path) -> ExpertRunner:
    cfg = make_config()
    store = SessionStore(tmp_path / "sessions")
    return ExpertRunner(cfg, store, tmp_path)


@pytest.mark.asyncio
async def test_different_domains_run_concurrently(runner: ExpertRunner):
    """Two queries to different domains should complete faster than sequential."""
    delay = 0.15

    def slow_ask_expert(domain, **kwargs):
        time.sleep(delay)
        return f"answer from {domain}"

    with patch("agentmesh.server.ask_expert", side_effect=slow_ask_expert):
        start = time.monotonic()
        results = await asyncio.gather(
            runner.run("alpha", "question"),
            runner.run("beta", "question"),
        )
        elapsed = time.monotonic() - start

    assert results == ["answer from alpha", "answer from beta"]
    # Ran concurrently: total time ≈ one delay, not two
    assert elapsed < delay * 1.8, f"Expected ~{delay:.2f}s (parallel), got {elapsed:.2f}s (sequential)"


@pytest.mark.asyncio
async def test_same_domain_serialized(runner: ExpertRunner):
    """Two queries to the same domain must never execute simultaneously."""
    concurrent_count = 0
    max_concurrent = 0

    def counting_ask_expert(**kwargs):
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        time.sleep(0.05)
        concurrent_count -= 1
        return "answer"

    with patch("agentmesh.server.ask_expert", side_effect=counting_ask_expert):
        await asyncio.gather(
            runner.run("alpha", "q1"),
            runner.run("alpha", "q2"),
        )

    assert max_concurrent == 1, (
        f"Same-domain queries must be serialized, but {max_concurrent} ran concurrently"
    )


@pytest.mark.asyncio
async def test_same_domain_both_complete(runner: ExpertRunner):
    """Both queries to the same domain should complete, just one after the other."""
    results = []

    def recording_ask_expert(domain, question, **kwargs):
        results.append(question)
        return f"answer to {question}"

    with patch("agentmesh.server.ask_expert", side_effect=recording_ask_expert):
        answers = await asyncio.gather(
            runner.run("alpha", "first"),
            runner.run("alpha", "second"),
        )

    assert set(answers) == {"answer to first", "answer to second"}
    assert len(results) == 2
