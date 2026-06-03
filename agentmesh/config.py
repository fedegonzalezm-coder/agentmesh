from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class ExpertConfig(BaseModel):
    description: str
    seed: str | None = None
    tools: list[Literal["read_file", "bash_readonly"]] = Field(
        default_factory=lambda: ["read_file", "bash_readonly"]
    )
    system_prompt: str | None = None


class Config(BaseModel):
    model: str = "claude-sonnet-4-6"
    session_store: str = ".agentmesh/sessions"
    working_dir: str = "."
    session_compression_threshold: int = 60
    experts: dict[str, ExpertConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def experts_not_empty(self) -> "Config":
        if not self.experts:
            raise ValueError("At least one expert must be defined in agentmesh.yml")
        return self

    def expert_domains(self) -> list[str]:
        return list(self.experts.keys())


def load_config(path: str | Path | None = None) -> Config:
    if path is None:
        candidates = [Path("agentmesh.yml"), Path("agentmesh.yaml")]
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break
        else:
            raise FileNotFoundError(
                "agentmesh.yml not found in current directory. Run `agentmesh init` to create one."
            )
    raw = yaml.safe_load(Path(path).read_text())
    return Config.model_validate(raw)


EXAMPLE_CONFIG = """\
model: claude-sonnet-4-6
session_store: .agentmesh/sessions
working_dir: .

experts:
  # Add your domain experts here.
  # Each expert accumulates knowledge across sessions.
  #
  # Example for a codebase with permissions and database domains:
  #
  # permissions:
  #   description: "Expert in ACL, roles, gates, and authorization patterns"
  #   seed: ./docs/permissions.md   # optional context document
  #   tools:
  #     - read_file
  #     - bash_readonly
  #
  # database:
  #   description: "Expert in DB schema, migrations, and query optimization"
  #   tools:
  #     - read_file
  #     - bash_readonly

  general:
    description: "General codebase expert"
    tools:
      - read_file
      - bash_readonly
"""
