from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class DomainInfo:
    domain: str
    message_count: int
    last_used: datetime | None
    compressed: bool


class SessionStore:
    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def load(self, domain: str) -> list[dict]:
        path = self._path(domain)
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        return data.get("messages", [])

    def save(self, domain: str, messages: list[dict]) -> None:
        path = self._path(domain)
        existing = {}
        if path.exists():
            existing = json.loads(path.read_text())
        existing["messages"] = messages
        existing["last_used"] = datetime.now(UTC).isoformat()
        existing.setdefault("created_at", existing["last_used"])
        path.write_text(json.dumps(existing, indent=2))

    def seed(self, content: str) -> list[dict]:
        """Return an initial messages list seeded with context content."""
        return [
            {"role": "user", "content": f"Here is background context about your domain:\n\n{content}"},
            {
                "role": "assistant",
                "content": "Understood. I have absorbed this domain context and will use it when answering questions.",
            },
        ]

    def list_domains(self) -> list[DomainInfo]:
        result = []
        for path in sorted(self._base.glob("*.json")):
            domain = path.stem
            data = json.loads(path.read_text())
            messages = data.get("messages", [])
            last_used_raw = data.get("last_used")
            last_used = datetime.fromisoformat(last_used_raw) if last_used_raw else None
            result.append(
                DomainInfo(
                    domain=domain,
                    message_count=len(messages),
                    last_used=last_used,
                    compressed=data.get("compressed", False),
                )
            )
        return result

    def clear(self, domain: str) -> bool:
        path = self._path(domain)
        if path.exists():
            path.unlink()
            return True
        return False

    def _path(self, domain: str) -> Path:
        safe = domain.replace("/", "_").replace("..", "")
        return self._base / f"{safe}.json"
