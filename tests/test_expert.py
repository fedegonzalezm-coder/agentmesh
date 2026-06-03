from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentmesh.config import ExpertConfig
from agentmesh.expert import _format_history, ask_expert
from agentmesh.session import SessionStore


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "sessions")


@pytest.fixture
def expert_config() -> ExpertConfig:
    return ExpertConfig(description="Test expert on permissions")


def _mock_run(stdout: str = "The answer is X.", returncode: int = 0):
    mock = MagicMock()
    mock.returncode = returncode
    mock.stdout = stdout
    mock.stderr = ""
    return mock


def test_ask_expert_returns_cli_output(store: SessionStore, expert_config: ExpertConfig, tmp_path: Path):
    with patch("agentmesh.expert.subprocess.run", return_value=_mock_run("Policy X applies.")) as mock_sub:
        answer = ask_expert("permissions", "What policy applies?", expert_config, store, tmp_path)

    assert answer == "Policy X applies."
    mock_sub.assert_called_once()
    cmd = mock_sub.call_args[0][0]
    assert cmd[0] == "claude"
    assert "--print" in cmd
    assert "What policy applies?" in cmd


def test_ask_expert_saves_session(store: SessionStore, expert_config: ExpertConfig, tmp_path: Path):
    with patch("agentmesh.expert.subprocess.run", return_value=_mock_run("Answer A.")):
        ask_expert("permissions", "Q1", expert_config, store, tmp_path)

    messages = store.load("permissions")
    assert len(messages) == 2
    assert messages[0]["content"] == "Q1"
    assert messages[1]["content"] == "Answer A."


def test_ask_expert_includes_history_in_system(store: SessionStore, expert_config: ExpertConfig, tmp_path: Path):
    with patch("agentmesh.expert.subprocess.run", return_value=_mock_run("Answer 1.")):
        ask_expert("permissions", "First question", expert_config, store, tmp_path)

    captured_system = None

    def capture(cmd, **kwargs):
        idx = cmd.index("--system-prompt") + 1
        nonlocal captured_system
        captured_system = cmd[idx]
        return _mock_run("Answer 2.")

    with patch("agentmesh.expert.subprocess.run", side_effect=capture):
        ask_expert("permissions", "Second question", expert_config, store, tmp_path)

    assert captured_system is not None
    assert "First question" in captured_system
    assert "Answer 1." in captured_system


def test_ask_expert_cli_not_found(store: SessionStore, expert_config: ExpertConfig, tmp_path: Path):
    with patch("agentmesh.expert.subprocess.run", side_effect=FileNotFoundError):
        answer = ask_expert("permissions", "Q?", expert_config, store, tmp_path)

    assert "claude" in answer.lower()
    assert "not found" in answer.lower()


def test_ask_expert_cli_error(store: SessionStore, expert_config: ExpertConfig, tmp_path: Path):
    with patch("agentmesh.expert.subprocess.run", return_value=_mock_run("auth failed", returncode=1)):
        answer = ask_expert("permissions", "Q?", expert_config, store, tmp_path)

    assert "error" in answer.lower()


def test_ask_expert_seeds_on_first_call(store: SessionStore, tmp_path: Path):
    seed_file = tmp_path / "seed.md"
    seed_file.write_text("ACL is managed via Bouncer.")
    config = ExpertConfig(description="Permissions expert", seed="seed.md")

    captured_system = None

    def capture(cmd, **kwargs):
        idx = cmd.index("--system-prompt") + 1
        nonlocal captured_system
        captured_system = cmd[idx]
        return _mock_run("Answer.")

    with patch("agentmesh.expert.subprocess.run", side_effect=capture):
        ask_expert("permissions", "How does ACL work?", config, store, tmp_path)

    assert captured_system is not None
    assert "ACL is managed via Bouncer." in captured_system


# --- _format_history tests ---

def test_format_history_simple():
    messages = [
        {"role": "user", "content": "What is X?"},
        {"role": "assistant", "content": "X is Y."},
    ]
    result = _format_history(messages)
    assert "Q: What is X?" in result
    assert "A: X is Y." in result


def test_format_history_skips_tool_blocks():
    messages = [
        {"role": "user", "content": "Question?"},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "1", "name": "bash_readonly", "input": {}},
                {"type": "text", "text": "The answer is Z."},
            ],
        },
    ]
    result = _format_history(messages)
    assert "A: The answer is Z." in result
    assert "tool_use" not in result


def test_format_history_empty():
    assert _format_history([]) == ""
