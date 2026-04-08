from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass
class ValidationFinding:
    code: str
    detail: str
    severity: str = "error"

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail, "severity": self.severity}


@dataclass
class EventRecord:
    source: str
    endpoint: str
    actor: str
    target: str
    status: str
    reason: str
    artifacts: list[str] = field(default_factory=list)
    approval_required: bool = False
    validation_summary: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: new_id("evt"))
    timestamp: str = field(default_factory=utc_now)

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "endpoint": self.endpoint,
            "actor": self.actor,
            "target": self.target,
            "status": self.status,
            "reason": self.reason,
            "artifacts": self.artifacts,
            "approval_required": self.approval_required,
            "validation_summary": self.validation_summary,
        }

