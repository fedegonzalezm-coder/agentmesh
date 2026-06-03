from pathlib import Path

import pytest
import yaml

from agentmesh.config import Config, ExpertConfig, load_config


def write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "agentmesh.yml"
    path.write_text(yaml.dump(data))
    return path


def test_load_minimal_config(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        {
            "experts": {
                "permissions": {"description": "ACL expert"},
            }
        },
    )
    cfg = load_config(path)
    assert cfg.model == "claude-sonnet-4-6"
    assert "permissions" in cfg.experts
    assert cfg.experts["permissions"].description == "ACL expert"


def test_load_full_config(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        {
            "model": "claude-haiku-4-5-20251001",
            "session_store": ".custom/sessions",
            "session_compression_threshold": 40,
            "experts": {
                "db": {"description": "DB expert", "tools": ["read_file"]},
            },
        },
    )
    cfg = load_config(path)
    assert cfg.model == "claude-haiku-4-5-20251001"
    assert cfg.session_compression_threshold == 40
    assert cfg.experts["db"].tools == ["read_file"]


def test_config_no_experts_raises(tmp_path: Path) -> None:
    path = write_config(tmp_path, {"experts": {}})
    with pytest.raises(Exception, match="expert"):
        load_config(path)


def test_config_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/agentmesh.yml")


def test_expert_default_tools() -> None:
    cfg = ExpertConfig(description="test")
    assert "read_file" in cfg.tools
    assert "bash_readonly" in cfg.tools


def test_config_expert_domains() -> None:
    cfg = Config(
        experts={
            "a": ExpertConfig(description="A"),
            "b": ExpertConfig(description="B"),
        }
    )
    assert cfg.expert_domains() == ["a", "b"]
