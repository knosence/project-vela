from __future__ import annotations

import json
from typing import Any


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        return json.loads(value.replace("'", '"'))
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def loads(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if line.startswith("- "):
            raise ValueError("Top-level lists are not supported by this lightweight parser")
        key, _, raw_value = line.partition(":")
        if not _:
            continue
        while stack and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1]
        if raw_value.strip() == "":
            next_container: dict[str, Any] = {}
            container[key] = next_container
            stack.append((indent, next_container))
        else:
            container[key] = _parse_scalar(raw_value.strip())
    return root


def dumps(data: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    pad = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.extend(dumps(value, indent + 2).splitlines())
        elif isinstance(value, list):
            rendered = json.dumps(value)
            lines.append(f"{pad}{key}: {rendered}")
        elif isinstance(value, bool):
            lines.append(f"{pad}{key}: {'true' if value else 'false'}")
        elif value is None:
            lines.append(f"{pad}{key}: null")
        else:
            lines.append(f"{pad}{key}: {value}")
    return "\n".join(lines) + "\n"
