from __future__ import annotations

import json
from typing import Any

from .paths import DREAMER_ACTIONS_PATH
from .rust_bridge import match_dreamer_actions_payload, parse_dreamer_actions_payload


def load_dreamer_actions() -> dict[str, Any]:
    if not DREAMER_ACTIONS_PATH.exists():
        return {
            "validator_changes": [],
            "workflow_changes": [],
            "refusal_tightenings": [],
        }
    payload = parse_dreamer_actions_payload(DREAMER_ACTIONS_PATH.read_text(encoding="utf-8"))
    return dict(payload.get("registry", {}))


def matching_validator_actions(target: str, endpoint: str, reason: str, content: str) -> list[dict[str, Any]]:
    return _matching_actions("validator", target=target, endpoint=endpoint, reason=reason, text=content)


def matching_workflow_actions(text: str) -> list[dict[str, Any]]:
    return _matching_actions("workflow", target="", endpoint="", reason="", text=text)


def matching_refusal_actions(target: str, endpoint: str, reason: str, content: str) -> list[dict[str, Any]]:
    return _matching_actions("refusal", target=target, endpoint=endpoint, reason=reason, text=content)


def _matching_actions(mode: str, *, target: str = "", endpoint: str = "", reason: str = "", text: str = "") -> list[dict[str, Any]]:
    data = load_dreamer_actions()
    payload = match_dreamer_actions_payload(
        json.dumps(data, indent=2),
        mode,
        target,
        endpoint,
        reason,
        text,
    )
    return list(payload.get("matches", []))
