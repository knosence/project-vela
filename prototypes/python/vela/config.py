from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import APPROVALS_PATH, CONFIG_PATH, PROFILE_DIR, STARTER_PATH, VERIFICATION_STATUS_PATH
from .rust_bridge import validate_config_payload
from .simple_yaml import dumps, loads


REQUIRED_FIELDS = [
    ("project", "name"),
    ("owner", "name"),
    ("assistant", "active_profile"),
    ("onboarding", "assistant_choice"),
    ("runtime", "primary_model"),
    ("providers", "primary"),
    ("deployment", "target"),
]


DEFAULT_CONFIG: dict[str, Any] = {
    "project": {"name": "Project Vela", "setup_complete": False},
    "owner": {"name": "<required>"},
    "assistant": {
        "default_profile": "vela",
        "active_profile": "vela",
        "allow_replacement": True,
        "allow_multiple_profiles": True,
    },
    "onboarding": {
        "assistant_choice": "keep-vela",
        "relationship_stance": "<required>",
        "persona_traits": "clear, rigorous, pragmatic",
        "support_critique_balance": "<required>",
        "subjectivity_boundaries": "<required>",
    },
    "runtime": {
        "primary_model": "<required>",
        "fallback_model": "gpt-5.4-mini",
        "fast_model": "gpt-5.4-mini",
        "local_model": "none",
        "machine_secret": "vela-dev-secret",
    },
    "providers": {"primary": "<required>", "fallback": "openai", "local": "none"},
    "integrations": {"github": True, "git": True, "webhook": True, "discord": False, "localfs": True},
    "governance": {
        "human_gate_on_sovereignty": True,
        "single_writer": True,
        "reflection_before_mutation": True,
    },
    "repo_watch": {
        "watchlist_path": "knowledge/200.WHAT.Repo-Watchlist-SoT.md",
        "bootstrap": "manual-seed",
    },
    "deployment": {"target": "<required>"},
    "preferences": {"response_style": "boring clarity over fancy magic"},
    "open_questions": {"items": "none"},
}


def _field_value(data: dict[str, Any], path: tuple[str, str]) -> Any:
    node: Any = data
    for part in path:
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def missing_required_fields(data: dict[str, Any]) -> list[str]:
    return list(validate_config_payload(data)["missing_fields"])


def ensure_bootstrap_files() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(dumps(DEFAULT_CONFIG), encoding="utf-8")
    if not VERIFICATION_STATUS_PATH.exists():
        VERIFICATION_STATUS_PATH.write_text(json.dumps({"last_passed": False, "report_path": ""}, indent=2), encoding="utf-8")
    if not APPROVALS_PATH.exists():
        APPROVALS_PATH.write_text(json.dumps({"approvals": {}}, indent=2), encoding="utf-8")
    STARTER_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    ensure_bootstrap_files()
    return loads(path.read_text(encoding="utf-8"))


def save_config(data: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.write_text(dumps(data), encoding="utf-8")


def setup_complete(data: dict[str, Any] | None = None) -> bool:
    cfg = data or load_config()
    payload = validate_config_payload(cfg)
    return not payload["setup_required"] and bool(cfg.get("project", {}).get("setup_complete"))


def set_active_profile(name: str) -> dict[str, Any]:
    cfg = load_config()
    cfg["assistant"]["active_profile"] = name
    save_config(cfg)
    return cfg
