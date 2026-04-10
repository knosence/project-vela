from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dreamer_actions import matching_workflow_actions
from .governance import append_event, build_pointer_entry, route_inbox_entry, write_text
from .models import EventRecord
from .paths import INBOX_DIR, PATCH_LOG_PATH, REPO_ROOT


def triage_inbox(file_name: str | None = None, actor: str = "vela") -> dict[str, Any]:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    candidates = [INBOX_DIR / file_name] if file_name else sorted(path for path in INBOX_DIR.iterdir() if path.is_file() and path.name != "000.Project-Vela-Starter.md")
    results: list[dict[str, Any]] = []
    for path in candidates:
        if not path.exists():
            results.append({"ok": False, "file": str(path.relative_to(REPO_ROOT)), "status": "missing"})
            continue
        if path.suffix.lower() == ".md":
            results.append(_triage_markdown_file(path, actor=actor))
        elif path.suffix.lower() == ".txt":
            results.append(_triage_text_companion_file(path, actor=actor))
        elif path.suffix.lower() == ".csv":
            results.append(_triage_csv_companion_file(path, actor=actor))
        else:
            results.append(_flag_unsupported_inbox_file(path, actor=actor))
    return {
        "ok": all(item.get("ok", False) for item in results) if results else True,
        "processed": len(results),
        "results": results,
    }


def _triage_markdown_file(path: Path, actor: str) -> dict[str, Any]:
    relative_path = str(path.relative_to(REPO_ROOT))
    text = path.read_text(encoding="utf-8")
    target = _extract_target(text)
    dimension = route_inbox_entry(text)
    workflow_actions = matching_workflow_actions(text)

    if not dimension:
        _append_patch_log("flagged", relative_path, "Unsorted — needs review.", actor)
        append_event(
            EventRecord(
                source="vela",
                endpoint="inbox-triage",
                actor=actor,
                target=relative_path,
                status="flagged",
                reason="dimension router could not classify inbox item",
                artifacts=[relative_path],
                validation_summary={"reason": "unsorted-needs-review"},
            )
        )
        return {
            "ok": False,
            "file": relative_path,
            "status": "flagged",
            "reason": "unsorted-needs-review",
            "workflow_actions": [item["pattern_reason"] for item in workflow_actions],
        }

    if not target:
        _append_patch_log("flagged", relative_path, f"Missing target SoT for dimension {dimension}.", actor)
        append_event(
            EventRecord(
                source="vela",
                endpoint="inbox-triage",
                actor=actor,
                target=relative_path,
                status="flagged",
                reason="target SoT not declared for inbox item",
                artifacts=[relative_path],
                validation_summary={"dimension": dimension, "reason": "missing-target"},
            )
        )
        return {"ok": False, "file": relative_path, "status": "flagged", "reason": "missing-target", "dimension": dimension}

    target_path = REPO_ROOT / target
    if not target_path.exists():
        _append_patch_log("blocked", relative_path, f"Declared target does not exist: {target}.", actor)
        append_event(
            EventRecord(
                source="vela",
                endpoint="inbox-triage",
                actor=actor,
                target=relative_path,
                status="blocked",
                reason="declared target SoT does not exist",
                artifacts=[relative_path],
                validation_summary={"dimension": dimension, "target": target},
            )
        )
        return {"ok": False, "file": relative_path, "status": "blocked", "reason": "target-missing", "dimension": dimension, "target": target}

    entry = _extract_entry(text, path)
    updated = _append_entry_to_dimension(target_path.read_text(encoding="utf-8"), dimension, entry)
    write_result = write_text(target, updated, actor=actor, endpoint="inbox-triage", reason=f"triage inbox item {relative_path}")
    if not write_result["ok"]:
        _append_patch_log("blocked", relative_path, f"Target write blocked for {target}.", actor)
        return {
            "ok": False,
            "file": relative_path,
            "status": "blocked",
            "dimension": dimension,
            "target": target,
            "findings": write_result["findings"],
        }

    pointer = build_pointer_entry(entry["value"], Path(target).stem, _dimension_anchor(updated, dimension), _today())
    if path.exists():
        path.unlink()
    _append_patch_log("applied", relative_path, f"Extracted into {target} {pointer}", actor)
    append_event(
        EventRecord(
            source="vela",
            endpoint="inbox-triage",
            actor=actor,
            target=target,
            status="committed",
            reason=f"inbox item {relative_path} extracted into {target}",
            artifacts=[target],
            validation_summary={"dimension": dimension, "source_file": relative_path, "pointer": pointer},
        )
    )
    return {
        "ok": True,
        "file": relative_path,
        "status": "applied",
        "dimension": dimension,
        "target": target,
        "pointer": pointer,
        "workflow_actions": [item["pattern_reason"] for item in workflow_actions],
    }


def _triage_text_companion_file(path: Path, actor: str) -> dict[str, Any]:
    relative_path = str(path.relative_to(REPO_ROOT))
    text = path.read_text(encoding="utf-8")
    target = _extract_target(text)
    dimension = route_inbox_entry(text)
    workflow_actions = matching_workflow_actions(text)

    if not dimension:
        return _flag_for_review(path, actor, "unsorted-needs-review", "dimension router could not classify inbox item")
    if not target:
        return _flag_for_review(path, actor, "missing-target", f"Missing target SoT for dimension {dimension}.", dimension=dimension)

    target_path = REPO_ROOT / target
    if not target_path.exists():
        return _block_missing_target(path, actor, target, dimension)

    companion_path = _move_to_companion_path(path, target_path)
    entry = _extract_entry(text, path)
    entry["context"] = f"{entry['context']} See: [[{companion_path.name}]]".strip()
    updated = _append_entry_to_dimension(target_path.read_text(encoding="utf-8"), dimension, entry)
    write_result = write_text(target, updated, actor=actor, endpoint="inbox-triage", reason=f"triage inbox item {relative_path}")
    if not write_result["ok"]:
        _append_patch_log("blocked", relative_path, f"Target write blocked for {target}.", actor)
        return {
            "ok": False,
            "file": relative_path,
            "status": "blocked",
            "dimension": dimension,
            "target": target,
            "findings": write_result["findings"],
        }

    pointer = build_pointer_entry(entry["value"], Path(target).stem, _dimension_anchor(updated, dimension), _today())
    _append_patch_log("applied", relative_path, f"Extracted into {target} with companion {companion_path.relative_to(REPO_ROOT)} {pointer}", actor)
    append_event(
        EventRecord(
            source="vela",
            endpoint="inbox-triage",
            actor=actor,
            target=target,
            status="committed",
            reason=f"inbox text item {relative_path} extracted into {target}",
            artifacts=[target, str(companion_path.relative_to(REPO_ROOT))],
            validation_summary={"dimension": dimension, "source_file": relative_path, "pointer": pointer},
        )
    )
    return {
        "ok": True,
        "file": relative_path,
        "status": "applied",
        "dimension": dimension,
        "target": target,
        "companion": str(companion_path.relative_to(REPO_ROOT)),
        "pointer": pointer,
        "workflow_actions": [item["pattern_reason"] for item in workflow_actions],
    }


def _triage_csv_companion_file(path: Path, actor: str) -> dict[str, Any]:
    relative_path = str(path.relative_to(REPO_ROOT))
    text = path.read_text(encoding="utf-8")
    target = _extract_target(text)
    if not target:
        return _flag_for_review(path, actor, "missing-target", "Missing target SoT for csv inbox item.")

    target_path = REPO_ROOT / target
    if not target_path.exists():
        return _block_missing_target(path, actor, target, "")

    rows = _parse_csv_rows(text)
    workflow_actions = matching_workflow_actions(text)
    if not rows:
        return _flag_for_review(path, actor, "empty-csv", "CSV inbox item had no extractable rows.")

    extracted_entries: list[dict[str, str]] = []
    for row in rows:
        entry = _entry_from_csv_row(row)
        route_text = " ".join(part for part in [entry["value"], entry["context"]] if part).strip()
        dimension = (row.get("dimension") or "").strip() or route_inbox_entry(route_text)
        if not dimension:
            return _flag_for_review(path, actor, "unsorted-needs-review", "CSV inbox row could not be classified.")
        extracted_entries.append({"dimension": dimension, "value": entry["value"], "context": entry["context"]})

    companion_path = _move_to_companion_path(path, target_path)
    updated = target_path.read_text(encoding="utf-8")
    for extracted in extracted_entries:
        entry_payload = {
            "value": extracted["value"],
            "context": f"{extracted['context']} See: [[{companion_path.name}]]".strip(),
        }
        updated = _append_entry_to_dimension(updated, extracted["dimension"], entry_payload)

    write_result = write_text(target, updated, actor=actor, endpoint="inbox-triage", reason=f"triage inbox item {relative_path}")
    if not write_result["ok"]:
        _append_patch_log("blocked", relative_path, f"Target write blocked for {target}.", actor)
        return {
            "ok": False,
            "file": relative_path,
            "status": "blocked",
            "target": target,
            "findings": write_result["findings"],
        }

    pointers = [
        build_pointer_entry(extracted["value"], Path(target).stem, _dimension_anchor(updated, extracted["dimension"]), _today())
        for extracted in extracted_entries
    ]
    _append_patch_log(
        "applied",
        relative_path,
        f"Extracted {len(extracted_entries)} csv rows into {target} with companion {companion_path.relative_to(REPO_ROOT)}.",
        actor,
    )
    append_event(
        EventRecord(
            source="vela",
            endpoint="inbox-triage",
            actor=actor,
            target=target,
            status="committed",
            reason=f"inbox csv item {relative_path} extracted into {target}",
            artifacts=[target, str(companion_path.relative_to(REPO_ROOT))],
            validation_summary={"rows": len(extracted_entries), "source_file": relative_path, "pointers": pointers},
        )
    )
    return {
        "ok": True,
        "file": relative_path,
        "status": "applied",
        "target": target,
        "companion": str(companion_path.relative_to(REPO_ROOT)),
        "rows": len(extracted_entries),
        "pointers": pointers,
        "workflow_actions": [item["pattern_reason"] for item in workflow_actions],
    }


def _flag_unsupported_inbox_file(path: Path, actor: str) -> dict[str, Any]:
    return _flag_for_review(path, actor, "unsupported-non-markdown", f"Unsupported inbox file type `{path.suffix}` requires richer extraction.")


def _flag_for_review(path: Path, actor: str, reason: str, detail: str, dimension: str | None = None) -> dict[str, Any]:
    relative_path = str(path.relative_to(REPO_ROOT))
    _append_patch_log("flagged", relative_path, detail, actor)
    append_event(
        EventRecord(
            source="vela",
            endpoint="inbox-triage",
            actor=actor,
            target=relative_path,
            status="flagged",
            reason=detail,
            artifacts=[relative_path],
            validation_summary={"reason": reason, "dimension": dimension or ""},
        )
    )
    payload = {"ok": False, "file": relative_path, "status": "flagged", "reason": reason}
    if dimension:
        payload["dimension"] = dimension
    return payload


def _block_missing_target(path: Path, actor: str, target: str, dimension: str) -> dict[str, Any]:
    relative_path = str(path.relative_to(REPO_ROOT))
    _append_patch_log("blocked", relative_path, f"Declared target does not exist: {target}.", actor)
    append_event(
        EventRecord(
            source="vela",
            endpoint="inbox-triage",
            actor=actor,
            target=relative_path,
            status="blocked",
            reason="declared target SoT does not exist",
            artifacts=[relative_path],
            validation_summary={"dimension": dimension, "target": target},
        )
    )
    return {"ok": False, "file": relative_path, "status": "blocked", "reason": "target-missing", "dimension": dimension, "target": target}


def _extract_target(text: str) -> str | None:
    frontmatter_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if frontmatter_match:
        target_match = re.search(r'^target:\s*"?(.+?)"?$', frontmatter_match.group(1), re.MULTILINE)
        if target_match:
            return _normalize_target(target_match.group(1))
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        if stripped.lower().startswith("target:"):
            return _normalize_target(stripped.split(":", 1)[1].strip())
    return None


def _parse_csv_rows(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    data_lines = [line for line in lines if not line.lstrip().startswith("#")]
    if not data_lines:
        return []
    reader = csv.DictReader(data_lines)
    rows: list[dict[str, str]] = []
    for row in reader:
        normalized = {
            (key or "").strip().lower(): (value or "").strip()
            for key, value in row.items()
        }
        if any(value for value in normalized.values()):
            rows.append(normalized)
    return rows


def _normalize_target(value: str) -> str | None:
    value = value.strip().strip("`").strip('"').strip("'")
    match = re.match(r"\[\[(.+?)\]\]", value)
    if match:
        value = match.group(1)
    value = value.split("#", 1)[0].strip()
    if not value:
        return None
    existing_match = _resolve_existing_target(value)
    if existing_match:
        return existing_match
    if value.endswith(".md"):
        return f"knowledge/{value}" if not value.startswith("knowledge/") else value
    return f"knowledge/{value}.md"


def _resolve_existing_target(value: str) -> str | None:
    normalized = value if value.endswith(".md") else f"{value}.md"
    direct = REPO_ROOT / normalized
    if direct.exists():
        return str(direct.relative_to(REPO_ROOT))
    matches = sorted(
        path for path in REPO_ROOT.rglob(normalized)
        if path.is_file() and ".git/" not in str(path)
    )
    if len(matches) == 1:
        return str(matches[0].relative_to(REPO_ROOT))
    return None


def _extract_entry(text: str, path: Path) -> dict[str, str]:
    body = _strip_frontmatter(text)
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    lines = [line for line in lines if not line.lower().startswith("target:")]
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    value = lines[0].lstrip("- ").strip() if lines else path.stem.replace("-", " ")
    context_lines = [line for line in lines[1:] if not line.startswith("#")]
    context = " ".join(context_lines).strip() if context_lines else "Extracted from Inbox during governed triage."
    return {"value": f"{value}. ({_today()})" if not re.search(r"\(\d{4}-\d{2}-\d{2}\)$", value) else value, "context": context}


def _entry_from_csv_row(row: dict[str, str]) -> dict[str, str]:
    value = row.get("value") or row.get("title") or row.get("subject") or ""
    context = row.get("context") or row.get("detail") or row.get("notes") or ""
    if not value:
        value = "Inbox CSV entry"
    if not re.search(r"\(\d{4}-\d{2}-\d{2}\)$", value):
        value = f"{value}. ({_today()})"
    if not context:
        context = "Extracted from Inbox CSV during governed triage."
    return {"value": value, "context": context}


def _move_to_companion_path(source: Path, target_path: Path) -> Path:
    companion_name = f"{target_path.stem}{source.suffix}"
    destination = target_path.with_name(companion_name)
    if destination.exists():
        destination = target_path.with_name(f"{target_path.stem}-{_today().replace('-', '')}{source.suffix}")
    source.rename(destination)
    return destination


def _append_entry_to_dimension(content: str, dimension: str, entry: dict[str, str]) -> str:
    heading = _dimension_heading(content, dimension)
    if not heading:
        raise ValueError(f"Dimension heading not found for {dimension}")
    section_start = content.find(heading)
    next_section = content.find("\n## ", section_start + 1)
    section = content[section_start: next_section if next_section != -1 else len(content)]
    active_marker = "### Active"
    inactive_marker = "### Inactive"
    active_start = section.find(active_marker)
    inactive_start = section.find(inactive_marker)
    if active_start == -1 or inactive_start == -1:
        raise ValueError(f"Dimension structure invalid for {heading}")
    active_section = section[active_start:inactive_start]
    new_entry = f"- {entry['value']}\n  - {entry['context']}"
    if "(No active entries.)" in active_section:
        active_section = active_section.replace("(No active entries.)", new_entry)
    else:
        active_section = active_section.rstrip() + f"\n\n{new_entry}\n"
    new_section = heading + "\n\n" + active_section.lstrip("\n") + "\n\n" + section[inactive_start:].lstrip("\n")
    return content[:section_start] + new_section + content[next_section if next_section != -1 else len(content):]


def _dimension_heading(content: str, dimension: str) -> str:
    match = re.search(rf"^##\s{dimension}\.[^\n]+$", content, re.MULTILINE)
    return match.group(0) if match else ""


def _dimension_anchor(content: str, dimension: str) -> str:
    return _dimension_heading(content, dimension).replace("## ", "", 1)


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) == 3:
            return parts[2]
    return text


def _append_patch_log(status: str, target: str, detail: str, actor: str) -> None:
    PATCH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d@%H%M")
    with PATCH_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(
            f"[{stamp}] ACTION: inbox triage\n"
            f"  TARGET: {target}\n"
            f"  DETAIL: {detail}\n"
            f"  STATUS: {status}\n"
            f"  ACTOR: {actor}\n"
        )


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()
