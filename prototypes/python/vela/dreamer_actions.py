from __future__ import annotations

import json
import re
from typing import Any

from .paths import DREAMER_ACTIONS_PATH

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "through",
    "when",
    "then",
    "than",
    "path",
    "change",
    "review",
    "blocked",
    "reason",
}


def load_dreamer_actions() -> dict[str, Any]:
    if not DREAMER_ACTIONS_PATH.exists():
        return {
            "validator_changes": [],
            "workflow_changes": [],
            "refusal_tightenings": [],
        }
    return json.loads(DREAMER_ACTIONS_PATH.read_text(encoding="utf-8"))


def matching_validator_actions(target: str, content: str) -> list[dict[str, Any]]:
    return _matching_actions("validator_changes", target=target, text=content)


def matching_workflow_actions(text: str) -> list[dict[str, Any]]:
    return _matching_actions("workflow_changes", text=text)


def matching_refusal_actions(target: str, endpoint: str, reason: str, content: str) -> list[dict[str, Any]]:
    return _matching_actions("refusal_tightenings", target=target, text=f"{endpoint} {reason} {content}")


def _matching_actions(bucket: str, *, target: str = "", text: str = "") -> list[dict[str, Any]]:
    data = load_dreamer_actions()
    haystack = f"{target} {text}".lower()
    matches: list[dict[str, Any]] = []
    for item in data.get(bucket, []):
        if item.get("status") != "active":
            continue
        tokens = _meaningful_tokens(str(item.get("pattern_reason", "")))
        if tokens and any(token in haystack for token in tokens):
            matches.append(item)
    return matches


def _meaningful_tokens(value: str) -> list[str]:
    tokens = [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 3 and token not in STOPWORDS]
    return list(dict.fromkeys(tokens))
