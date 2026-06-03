from pathlib import Path

import pytest

from agentmesh.tools import execute_tool


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    (tmp_path / "hello.txt").write_text("hello world")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main(): pass\n")
    return tmp_path


def test_read_file_relative(work_dir: Path) -> None:
    result = execute_tool("read_file", {"path": "hello.txt"}, work_dir)
    assert result == "hello world"


def test_read_file_absolute(work_dir: Path) -> None:
    abs_path = str(work_dir / "hello.txt")
    result = execute_tool("read_file", {"path": abs_path}, work_dir)
    assert result == "hello world"


def test_read_file_not_found(work_dir: Path) -> None:
    result = execute_tool("read_file", {"path": "missing.txt"}, work_dir)
    assert "not found" in result.lower()


def test_read_file_directory(work_dir: Path) -> None:
    result = execute_tool("read_file", {"path": "src"}, work_dir)
    assert "directory" in result.lower()


def test_bash_readonly_grep(work_dir: Path) -> None:
    result = execute_tool("bash_readonly", {"command": "grep -r 'def main' src/"}, work_dir)
    assert "def main" in result


def test_bash_readonly_find(work_dir: Path) -> None:
    result = execute_tool("bash_readonly", {"command": "find . -name '*.txt'"}, work_dir)
    assert "hello.txt" in result


def test_bash_readonly_blocked(work_dir: Path) -> None:
    result = execute_tool("bash_readonly", {"command": "rm -rf ."}, work_dir)
    assert "not allowed" in result.lower()


def test_bash_readonly_blocked_write(work_dir: Path) -> None:
    result = execute_tool("bash_readonly", {"command": "echo foo > bar.txt"}, work_dir)
    assert "not allowed" in result.lower()


def test_unknown_tool(work_dir: Path) -> None:
    result = execute_tool("nonexistent", {}, work_dir)
    assert "unknown" in result.lower()
