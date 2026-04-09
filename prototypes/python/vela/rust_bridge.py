from __future__ import annotations

import json
import subprocess
from typing import Any

from .paths import REPO_ROOT


def _run(args: list[str], stdin: str | None = None) -> dict[str, Any]:
    command = ["cargo", "run", "--quiet", "--bin", "vela-core-cli", "--", *args]
    result = subprocess.run(
        command,
        input=stdin,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        check=True,
    )
    return json.loads(result.stdout)


def validate_target(target: str, content: str, approval_status: str) -> dict[str, Any]:
    return _run(["validate-target", target, approval_status], stdin=content)


def route_for_target(task_type: str, target: str) -> str:
    payload = _run(["route", task_type, target])
    return str(payload["route"])


def validate_config_payload(config: dict[str, Any]) -> dict[str, Any]:
    return _run(
        [
            "validate-config",
            str(config.get("owner", {}).get("name", "")),
            str(config.get("providers", {}).get("primary", "")),
            str(config.get("runtime", {}).get("primary_model", "")),
            str(config.get("deployment", {}).get("target", "")),
            str(config.get("onboarding", {}).get("assistant_choice", "")),
            str(config.get("onboarding", {}).get("relationship_stance", "")),
            str(config.get("onboarding", {}).get("support_critique_balance", "")),
            str(config.get("onboarding", {}).get("subjectivity_boundaries", "")),
            str(config.get("project", {}).get("name", "")),
            str(config.get("assistant", {}).get("default_profile", "")),
            str(config.get("assistant", {}).get("active_profile", "")),
            "true" if bool(config.get("assistant", {}).get("allow_replacement")) else "false",
            "true" if bool(config.get("assistant", {}).get("allow_multiple_profiles")) else "false",
            "true" if bool(config.get("project", {}).get("setup_complete")) else "false",
        ]
    )


def validate_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    return _run(
        [
            "validate-event",
            str(event.get("event_id", "")),
            str(event.get("timestamp", "")),
            str(event.get("source", "")),
            str(event.get("endpoint", "")),
            str(event.get("actor", "")),
            str(event.get("target", "")),
            str(event.get("status", "")),
            str(event.get("reason", "")),
        ]
    )


def analyze_release_payload(repo: str, version: str, notes: str, watchlist_text: str, context_markers: list[str]) -> dict[str, Any]:
    return _run(["analyze-release", repo, version, notes, ",".join(context_markers)], stdin=watchlist_text)


def inspect_reference_payload(path: str, content: str) -> dict[str, Any]:
    return _run(["inspect-reference", path], stdin=content)
