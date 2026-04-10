from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .paths import DREAMER_ACTIONS_PATH
from .rust_bridge import (
    match_dreamer_actions_payload,
    parse_dreamer_actions_payload,
    register_dreamer_action_payload,
    update_dreamer_action_status_payload,
)


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


def register_dreamer_action(
    *,
    kind: str,
    follow_up_target: str,
    execution_target: str,
    pattern_reason: str,
    actor: str,
    execution_reason: str,
    status: str = "active",
) -> dict[str, Any]:
    current = json.dumps(load_dreamer_actions(), indent=2)
    payload = register_dreamer_action_payload(
        current,
        kind,
        follow_up_target,
        execution_target,
        pattern_reason,
        actor,
        execution_reason,
        datetime.now(timezone.utc).isoformat(),
        status,
    )
    registry = payload.get("registry", {})
    DREAMER_ACTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DREAMER_ACTIONS_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return {
        "ok": bool(payload.get("ok", False)),
        "target": str(DREAMER_ACTIONS_PATH),
        "registry": registry,
        "findings": list(payload.get("findings", [])),
    }


def update_dreamer_action_status(*, follow_up_target: str, status: str) -> dict[str, Any]:
    current = json.dumps(load_dreamer_actions(), indent=2)
    payload = update_dreamer_action_status_payload(current, follow_up_target, status)
    registry = payload.get("registry", {})
    DREAMER_ACTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DREAMER_ACTIONS_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return {
        "ok": bool(payload.get("ok", False)),
        "target": str(DREAMER_ACTIONS_PATH),
        "registry": registry,
        "findings": list(payload.get("findings", [])),
    }
