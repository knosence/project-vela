from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config import load_config
from .models import EventRecord, ValidationFinding
from .paths import APPROVALS_PATH, EVENT_LOG_PATH, PROPOSALS_DIR, QUEUE_DIR, REPO_ROOT


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
    return (
        target.startswith("knowledge/cornerstone/")
        or target == "knowledge/dimensions/200.WHAT.Repo-Watchlist-SoT.md"
        or "Identity-SoT" in target
        or target.endswith("System-Governance-SoT.md")
    )


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
    findings: list[ValidationFinding] = []
    headings = [line for line in text.splitlines() if line.startswith("#")]
    if not headings:
        findings.append(ValidationFinding("NARRATIVE_HEADING_REQUIRED", "Document must contain narrative headings"))
        return findings
    for heading in headings:
        if len(heading.lstrip("#").strip().split()) < 3:
            findings.append(ValidationFinding("NARRATIVE_HEADING_WEAK", f"Heading is too short: {heading}", "warning"))
    return findings


def validate_target(target: str, content: str, approval_id: str | None = None) -> list[ValidationFinding]:
    findings = narrative_findings(content)
    if is_sovereign_target(target) and approval_status(approval_id) != "approved":
        findings.append(
            ValidationFinding(
                "SOVEREIGN_APPROVAL_REQUIRED",
                "Cornerstone or identity change attempted without human approval",
            )
        )
    return findings


def append_event(record: EventRecord) -> None:
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
    try:
        path = REPO_ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
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
            artifacts=[target],
            approval_required=approval_required,
            validation_summary={"findings": [item.as_dict() for item in findings]},
        )
    )
    return {"ok": True, "findings": [item.as_dict() for item in findings]}


def governance_snapshot() -> dict[str, Any]:
    cfg = load_config()
    return {
        "directives": DIRECTIVES,
        "single_writer": cfg["governance"]["single_writer"],
        "reflection_before_mutation": cfg["governance"]["reflection_before_mutation"],
        "human_gate_on_sovereignty": cfg["governance"]["human_gate_on_sovereignty"],
    }


def propose_growth(title: str, body: str) -> Path:
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    proposal = PROPOSALS_DIR / f"{title}.md"
    proposal.write_text(body, encoding="utf-8")
    return proposal

