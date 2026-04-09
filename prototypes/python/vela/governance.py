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
from .simple_yaml import loads


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


def apply_growth_proposal(proposal_target: str, actor: str, approval_id: str | None = None) -> dict[str, Any]:
    proposal_path = REPO_ROOT / proposal_target
    if not proposal_path.exists():
        finding = ValidationFinding("GROWTH_PROPOSAL_NOT_FOUND", f"Growth proposal not found: {proposal_target}")
        return {"ok": False, "findings": [finding.as_dict()]}

    proposal_text = proposal_path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(proposal_text)
    assessed_target = str(frontmatter.get("target", "")).strip().strip('"')
    stage = str(frontmatter.get("recommended-stage", "")).strip().strip('"')
    route = str(frontmatter.get("route", "")).strip().strip('"')

    if not assessed_target or not stage:
        finding = ValidationFinding(
            "GROWTH_PROPOSAL_METADATA_INVALID",
            f"{proposal_target} is missing required growth metadata",
        )
        return {"ok": False, "findings": [finding.as_dict()]}

    if is_sovereign_target(assessed_target) and approval_status(approval_id) != "approved":
        finding = ValidationFinding(
            "SOVEREIGN_APPROVAL_REQUIRED",
            "Growth execution targets a sovereign artifact and requires approval",
        )
        append_event(
            EventRecord(
                source="vela",
                endpoint="growth-apply",
                actor=actor,
                target=proposal_target,
                status="blocked",
                reason="growth execution requires sovereign approval",
                artifacts=[proposal_target],
                approval_required=True,
                validation_summary={"assessed_target": assessed_target, "stage": stage, "route": route},
            )
        )
        return {"ok": False, "findings": [finding.as_dict()], "approval_required": True}

    execution = _build_growth_execution(stage=stage, assessed_target=assessed_target, proposal_target=proposal_target)
    result = write_text(
        execution["target"],
        execution["content"],
        actor=actor,
        endpoint="growth-apply",
        reason=f"apply growth proposal {proposal_target}",
        approval_id=approval_id,
    )
    if not result["ok"]:
        return {"ok": False, "findings": result["findings"], "execution_target": execution["target"]}

    proposal_update = _mark_proposal_applied(proposal_text, execution["target"], stage)
    proposal_result = write_text(
        proposal_target,
        proposal_update,
        actor=actor,
        endpoint="growth-apply",
        reason=f"mark growth proposal applied {proposal_target}",
    )

    append_event(
        EventRecord(
            source="vela",
            endpoint="growth-apply",
            actor=actor,
            target=proposal_target,
            status="applied" if proposal_result["ok"] else "partially-applied",
            reason=f"applied growth proposal stage {stage}",
            artifacts=[proposal_target, execution["target"], *result.get("artifacts", [])],
            approval_required=is_sovereign_target(assessed_target),
            validation_summary={
                "assessed_target": assessed_target,
                "execution_target": execution["target"],
                "stage": stage,
                "route": route,
                "execution_kind": execution["kind"],
            },
        )
    )
    return {
        "ok": result["ok"] and proposal_result["ok"],
        "proposal_target": proposal_target,
        "execution_target": execution["target"],
        "execution_kind": execution["kind"],
        "stage": stage,
        "findings": result["findings"] + proposal_result.get("findings", []),
    }


def _build_growth_execution(stage: str, assessed_target: str, proposal_target: str) -> dict[str, str]:
    target_path = Path(assessed_target)
    created = datetime.now(timezone.utc).date().isoformat()
    stem = re.sub(r"[^A-Za-z0-9.-]+", "-", target_path.stem).strip("-") or "target"
    proposal_name = Path(proposal_target).stem

    if stage == "reference-note":
        ref_stem = stem[:-4] if stem.endswith("-SoT") else stem
        execution_target = f"knowledge/refs/Ref.{ref_stem}.md"
        content = (
            f"# Reference Note for {target_path.name}\n\n"
            "## This Reference Note Exists Because the Parent Artifact Has Exceeded a Flat Shape\n"
            f"The governed growth proposal `{proposal_target}` recommended extraction into a reference note.\n\n"
            "## This Reference Note Points Back to the Assessed Parent Artifact\n"
            f"- parent artifact: `{assessed_target}`\n"
            f"- proposal: `{proposal_target}`\n"
            f"- created: `{created}`\n"
        )
        return {"target": execution_target, "content": content, "kind": "reference-note"}

    if stage == "spawn" and assessed_target.endswith("-SoT.md"):
        execution_target = str(target_path.with_name(f"{stem}.Spawned-Child-SoT.md"))
        content = _render_spawned_sot(execution_target, assessed_target, proposal_target, created)
        return {"target": execution_target, "content": content, "kind": "spawned-sot"}

    execution_target = f"knowledge/proposals/Applied.{proposal_name}.md"
    content = (
        "# Applied Growth Action\n\n"
        "## This Artifact Records the Governed Structural Action Chosen from the Growth Proposal\n"
        f"Proposal `{proposal_target}` was applied against `{assessed_target}`.\n\n"
        f"Recommended stage: `{stage}`.\n\n"
        "## This Artifact Records the Immediate Controlled Outcome\n"
        f"- action kind: `{stage if stage else 'unknown'}`\n"
        f"- assessed target: `{assessed_target}`\n"
        "- direct canonical mutation was deferred in favor of a governed structural action artifact\n"
    )
    return {"target": execution_target, "content": content, "kind": "applied-action"}


def _render_spawned_sot(execution_target: str, assessed_target: str, proposal_target: str, created: str) -> str:
    parent_name = Path(assessed_target).stem
    child_name = Path(execution_target).name
    return (
        "---\n"
        "sot-type: system\n"
        f"created: {created}\n"
        f"last-rewritten: {created}\n"
        f'parent: "[[{parent_name}]]"\n'
        "domain: growth\n"
        "status: active\n"
        'tags: ["growth","spawned","sot"]\n'
        "---\n\n"
        f"# {child_name} Source of Truth\n\n"
        "## 000.Index\n\n"
        "### Subject Declaration\n\n"
        f"**Subject:** {child_name} was spawned from a governed growth proposal.\n"
        "**Type:** system\n"
        f"**Created:** {created}\n"
        f"**Parent:** [[{parent_name}]]\n\n"
        "### Links\n\n"
        f"- Parent: [[{parent_name}]]\n"
        "- Cornerstone: [[Cornerstone.Project-Vela-SoT]]\n"
        f"- Proposal: `{proposal_target}`\n\n"
        "### Inbox\n\n"
        "No pending items.\n\n"
        "### Status\n\n"
        "Newly spawned from a governed growth proposal.\n\n"
        "### Open Questions\n\n"
        "- What content should migrate here from the parent SoT? "
        f"({created})\n"
        "  - The spawn establishes the branch before extraction work begins. [AGENT:gpt-5]\n\n"
        "### Next Actions\n\n"
        f"- Extract the branch-specific material from `{assessed_target}`. ({created})\n"
        "  - The new child should earn its content through governed extraction, not duplication. [AGENT:gpt-5]\n\n"
        "### Decisions\n\n"
        f"- [{created}] Spawned child SoT created from `{proposal_target}`.\n\n"
        "### Block Map — Single Source\n\n"
        "| ID | Question | Dimension | This SoT's Name |\n"
        "|----|----------|-----------|-----------------|\n"
        "| 000 | — | Index | Index |\n"
        "| 100 | Who | Circle | Identity |\n"
        "| 200 | What | Domain | Scope |\n"
        "| 300 | Where | Terrain | Placement |\n"
        "| 400 | When | Chronicle | Timeline |\n"
        "| 500 | How | Method | Operation |\n"
        "| 600 | Why/Not | Compass | Rationale |\n"
        "| 700 | — | Archive | Archive |\n\n"
        "---\n\n"
        "## 100.WHO.Identity\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n"
        "## 200.WHAT.Scope\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n"
        "## 300.WHERE.Placement\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n"
        "## 400.WHEN.Timeline\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n"
        "## 500.HOW.Method\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n"
        "## 600.WHY.Compass\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n(No inactive entries.)\n\n---\n\n"
        "## 700.Archive\n\n(No archived entries.)\n"
    )


def _mark_proposal_applied(proposal_text: str, execution_target: str, stage: str) -> str:
    updated = proposal_text.replace("status: proposed", "status: applied", 1)
    if "## This Proposal Records the Applied Outcome" in updated:
        return updated
    if not updated.endswith("\n"):
        updated += "\n"
    updated += (
        "\n## This Proposal Records the Applied Outcome\n"
        f"- stage applied: `{stage}`\n"
        f"- execution target: `{execution_target}`\n"
        "- proposal status changed from `proposed` to `applied`\n"
    )
    return updated


def _parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        return {}
    try:
        _, frontmatter, _ = text.split("---\n", 2)
    except ValueError:
        return {}
    return loads(frontmatter)
