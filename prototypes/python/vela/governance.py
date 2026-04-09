from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_config
from .matrix import classify_change_zone
from .models import EventRecord, ValidationFinding
from .paths import APPROVALS_PATH, BACKUP_DIR, EVENT_LOG_PATH, PROPOSALS_DIR, QUEUE_DIR, REPO_ROOT
from .rust_bridge import route_for_target as rust_route_for_target
from .rust_bridge import validate_event_payload
from .rust_bridge import validate_target as rust_validate_target


DIRECTIVES = [
    "SoT supremacy",
    "single-writer discipline",
    "role purity",
    "reflection before mutation",
    "human gate on sovereignty",
    "validate before commit",
    "one home, many pointers",
    "event log everything important",
    "pure core, impure edges",
    "narrative structure required",
    "conservative self-modification",
    "sequential interplay over parallel chaos",
]


def is_sovereign_target(target: str) -> bool:
    return rust_route_for_target("write", target) == "sovereign-change"


def approval_status(approval_id: str | None) -> str | None:
    if not approval_id or not APPROVALS_PATH.exists():
        return None
    approvals = json.loads(APPROVALS_PATH.read_text(encoding="utf-8")).get("approvals", {})
    item = approvals.get(approval_id)
    return item.get("decision") if item else None


def record_approval(approval_id: str, decision: str, actor: str, reason: str, target: str) -> dict[str, Any]:
    data = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    data.setdefault("approvals", {})[approval_id] = {
        "decision": decision,
        "actor": actor,
        "reason": reason,
        "target": target,
    }
    APPROVALS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data["approvals"][approval_id]


def narrative_findings(text: str) -> list[ValidationFinding]:
    payload = rust_validate_target("knowledge/refs/narrative-check.md", text, "approved")
    return [ValidationFinding(item["code"], item["detail"], item["severity"]) for item in payload["findings"]]


def validate_target(target: str, content: str, approval_id: str | None = None) -> list[ValidationFinding]:
    payload = rust_validate_target(target, content, approval_status(approval_id) or "missing")
    return [ValidationFinding(item["code"], item["detail"], item["severity"]) for item in payload["findings"]]


def append_event(record: EventRecord) -> None:
    event_validation = validate_event_payload(record.as_dict())
    if not event_validation["ok"]:
        raise ValueError(f"Invalid event record: {event_validation['findings']}")
    EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.as_dict()) + "\n")


def acquire_write_lock(target: str, actor: str) -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(target.encode("utf-8")).hexdigest()
    lock_path = QUEUE_DIR / f"{digest}.lock"
    if lock_path.exists():
        raise RuntimeError(f"Target is already locked for writing: {target}")
    lock_path.write_text(actor, encoding="utf-8")
    return lock_path


def release_write_lock(lock_path: Path) -> None:
    if lock_path.exists():
        lock_path.unlink()


def backup_protected_file(target: str, content: str) -> str:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = EventRecord(source="vela", endpoint="backup", actor="system", target=target, status="backup", reason="protected-zone backup").timestamp
    stamp = re.sub(r"[^0-9]", "", timestamp)[:12]
    backup_name = f"{stamp}({Path(target).name})Backup.md"
    backup_path = BACKUP_DIR / backup_name
    backup_path.write_text(content, encoding="utf-8")
    return str(backup_path.relative_to(REPO_ROOT))


def write_text(target: str, content: str, actor: str, endpoint: str, reason: str, approval_id: str | None = None) -> dict[str, Any]:
    findings = validate_target(target, content, approval_id=approval_id)
    blocking = [item for item in findings if item.severity == "error"]
    approval_required = any(item.code == "SOVEREIGN_APPROVAL_REQUIRED" for item in findings)
    if blocking:
        append_event(
            EventRecord(
                source="vela",
                endpoint=endpoint,
                actor=actor,
                target=target,
                status="blocked",
                reason=reason,
                approval_required=approval_required,
                validation_summary={"findings": [item.as_dict() for item in findings]},
            )
        )
        return {"ok": False, "findings": [item.as_dict() for item in findings]}
    lock = acquire_write_lock(target, actor)
    artifacts = [target]
    try:
        path = REPO_ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = path.read_text(encoding="utf-8") if path.exists() else ""
        zone = classify_change_zone(previous, content) if previous else "protected"
        if previous and zone == "protected":
            artifacts.append(backup_protected_file(target, previous))
        path.write_text(content, encoding="utf-8")
    finally:
        release_write_lock(lock)
    append_event(
        EventRecord(
            source="vela",
            endpoint=endpoint,
            actor=actor,
            target=target,
            status="committed",
            reason=reason,
            artifacts=artifacts,
            approval_required=approval_required,
            validation_summary={"findings": [item.as_dict() for item in findings], "change_zone": zone},
        )
    )
    return {"ok": True, "findings": [item.as_dict() for item in findings], "change_zone": zone, "artifacts": artifacts}


def archive_dimension_entry(
    target: str,
    dimension_heading: str,
    entry_value: str,
    archived_reason: str,
    actor: str,
    endpoint: str,
    reason: str,
    approval_id: str | None = None,
) -> dict[str, Any]:
    path = REPO_ROOT / target
    content = path.read_text(encoding="utf-8")
    entry_marker = f"- {entry_value}"
    if entry_marker not in content:
        finding = ValidationFinding("ARCHIVE_ENTRY_NOT_FOUND", f"Entry not found for archive: {entry_value}")
        return {"ok": False, "findings": [finding.as_dict()]}

    section_start = content.find(dimension_heading)
    if section_start == -1:
        finding = ValidationFinding("ARCHIVE_DIMENSION_NOT_FOUND", f"Dimension not found: {dimension_heading}")
        return {"ok": False, "findings": [finding.as_dict()]}

    next_section = content.find("\n## ", section_start + 1)
    dimension_section = content[section_start: next_section if next_section != -1 else len(content)]
    active_start = dimension_section.find("### Active")
    inactive_start = dimension_section.find("### Inactive")
    if active_start == -1 or inactive_start == -1:
        finding = ValidationFinding("ARCHIVE_STRUCTURE_INVALID", f"Dimension missing Active/Inactive sections: {dimension_heading}")
        return {"ok": False, "findings": [finding.as_dict()]}

    active_section = dimension_section[active_start:inactive_start]
    entry_block = _extract_entry_block(active_section, entry_value)
    if not entry_block:
        finding = ValidationFinding("ARCHIVE_ACTIVE_ENTRY_NOT_FOUND", f"Active entry not found for archive: {entry_value}")
        return {"ok": False, "findings": [finding.as_dict()]}
    archived_entry = (
        f"{entry_block}\n"
        f"  - Archived: {EventRecord(source='vela', endpoint='archive', actor=actor, target=target, status='archived', reason=reason).timestamp[:10]}\n"
        f"  - Archived Reason: {archived_reason}"
    )
    updated_active = active_section.replace(entry_block, "").rstrip()
    if updated_active.strip() == "### Active":
        updated_active = "### Active\n\n(No active entries.)"
    inactive_section = dimension_section[inactive_start:]
    inactive_section = inactive_section.replace("### Inactive\n\n(No inactive entries.)", f"### Inactive\n\n{archived_entry}")
    if archived_entry not in inactive_section:
        inactive_section = inactive_section.rstrip() + f"\n\n{archived_entry}\n"
    new_dimension_section = updated_active + "\n\n" + inactive_section.lstrip("\n")
    new_content = content[:section_start] + new_dimension_section + content[next_section if next_section != -1 else len(content):]

    archive_heading = "## 700.Archive"
    archive_pos = new_content.find(archive_heading)
    if archive_pos == -1:
        finding = ValidationFinding("ARCHIVE_BLOCK_MISSING", "700.Archive is missing from target SoT")
        return {"ok": False, "findings": [finding.as_dict()]}
    archive_entry = (
        f"[{re.sub(r'[^0-9]', '', EventRecord(source='vela', endpoint='archive', actor=actor, target=target, status='archived', reason=reason).timestamp)[:12]}] "
        f"FROM: {dimension_heading}\n{archived_entry}\n"
    )
    if "(No archived entries.)" in new_content[archive_pos:]:
        new_content = new_content.replace("(No archived entries.)", archive_entry.strip())
    else:
        new_content = new_content.rstrip() + "\n\n" + archive_entry

    result = write_text(target, new_content, actor=actor, endpoint=endpoint, reason=reason, approval_id=approval_id)
    if result["ok"]:
        append_event(
            EventRecord(
                source="vela",
                endpoint=endpoint,
                actor=actor,
                target=target,
                status="archived",
                reason=archived_reason,
                artifacts=result.get("artifacts", [target]),
                approval_required=False,
                validation_summary={"entry_value": entry_value, "dimension_heading": dimension_heading},
            )
        )
    return result


def _extract_entry_block(section: str, entry_value: str) -> str:
    lines = section.splitlines()
    start_index: int | None = None
    block: list[str] = []
    marker = f"- {entry_value}"
    for idx, line in enumerate(lines):
        if line.strip() == marker:
            start_index = idx
            break
    if start_index is None:
        return ""
    for line in lines[start_index:]:
        if line.startswith("- ") and block:
            break
        if line.startswith("### ") and block:
            break
        if line.startswith("## ") and block:
            break
        block.append(line)
    return "\n".join(block).strip()


def governance_snapshot() -> dict[str, Any]:
    cfg = load_config()
    return {
        "directives": DIRECTIVES,
        "single_writer": cfg["governance"]["single_writer"],
        "reflection_before_mutation": cfg["governance"]["reflection_before_mutation"],
        "human_gate_on_sovereignty": cfg["governance"]["human_gate_on_sovereignty"],
    }


def propose_growth(route: str, target: str, body: str, critique: list[str], findings: list[dict[str, Any]]) -> dict[str, Any]:
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    proposal = PROPOSALS_DIR / _proposal_name(route, target)
    proposal_target = str(proposal.relative_to(REPO_ROOT))
    rationale = "growth proposal recorded after governed assessment"
    result = write_text(proposal_target, body, actor="grower", endpoint="growth-proposal", reason=rationale)
    if result["ok"]:
        append_event(
            EventRecord(
                source="vela",
                endpoint="growth-proposal",
                actor="grower",
                target=proposal_target,
                status="proposed",
                reason=rationale,
                artifacts=result.get("artifacts", [proposal_target]),
                approval_required=is_sovereign_target(target),
                validation_summary={
                    "route": route,
                    "proposal_target": proposal_target,
                    "assessed_target": target,
                    "critique": critique,
                    "warden_findings": findings,
                },
            )
        )
    return {
        "ok": result["ok"],
        "target": proposal_target,
        "critique": critique,
        "findings": findings if findings else result.get("findings", []),
        "approval_required": is_sovereign_target(target),
        "artifacts": result.get("artifacts", [proposal_target]),
    }


def _proposal_name(route: str, target: str) -> str:
    created = datetime.now(timezone.utc).date().isoformat()
    stem = re.sub(r"[^A-Za-z0-9.-]+", "-", Path(target).stem).strip("-") or "target"
    return f"Growth-Proposal.{created}.{route}.{stem}.md"
