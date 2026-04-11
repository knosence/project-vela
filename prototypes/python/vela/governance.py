from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_config
from .dreamer_actions import matching_refusal_actions, matching_validator_actions
from .matrix import classify_change_zone
from .models import EventRecord, ValidationFinding
from .paths import APPROVALS_PATH, BACKUP_DIR, EVENT_LOG_PATH, PROPOSALS_DIR, QUEUE_DIR, REPO_ROOT
from .rust_bridge import route_for_target as rust_route_for_target
from .rust_bridge import plan_event_append_payload
from .rust_bridge import plan_growth_execution_payload
from .rust_bridge import render_event_payload
from .rust_bridge import route_inbox_payload
from .rust_bridge import validate_archive_postconditions_payload
from .rust_bridge import validate_event_payload
from .rust_bridge import validate_growth_stage_payload
from .rust_bridge import validate_subject_declaration_payload
from .rust_bridge import validate_target as rust_validate_target
from .simple_yaml import loads
from .traceability import annotate_finding, annotate_findings


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

ROLE_RULES: dict[str, set[str]] = {
    "vela": {"inbox-triage", "cross-reference"},
    "warden": {"validate", "write-artifact"},
    "scribe": {"write-text", "archive", "growth-apply", "cross-reference"},
    "grower": {"growth-proposal", "growth-apply", "write-artifact"},
    "reflector": {"reflect", "write-artifact"},
    "repo-watch": {"repo-release", "write-artifact"},
    "n8n": {"inbox-triage", "cross-reference", "growth-apply", "approval-record", "validate", "reflect", "repo-release"},
    "human": {"*"},
    "system": {"*"},
}


def is_sovereign_target(target: str) -> bool:
    return rust_route_for_target("write", target) == "sovereign-change"


def enforce_actor_operation(
    actor: str,
    operation: str,
    *,
    target: str | None = None,
    endpoint: str | None = None,
    stage: str | None = None,
) -> ValidationFinding | None:
    permissions = ROLE_RULES.get(actor, set())
    if "*" in permissions:
        return None
    if operation in permissions:
        if operation == "growth-apply" and stage == "spawn" and actor not in {"scribe", "human", "system", "n8n"}:
            return annotate_finding(
                ValidationFinding(
                    "ROLE_ACTION_NOT_ALLOWED",
                    f"Actor `{actor}` may recommend spawn but may not execute it.",
                )
            )
        return None
    if operation == "write-text" and "write-artifact" in permissions and target and target.startswith("knowledge/ARTIFACTS/"):
        return None
    if actor == "n8n" and endpoint in {"inbox-triage", "cross-reference", "growth-apply", "repo-release"}:
        return None
    if actor == "vela" and endpoint in {"inbox-triage", "cross-reference"}:
        return None
    return annotate_finding(
        ValidationFinding(
            "ROLE_ACTION_NOT_ALLOWED",
            f"Actor `{actor}` is not permitted to perform `{operation}`.",
        )
    )


def approval_status(approval_id: str | None) -> str | None:
    if not approval_id or not APPROVALS_PATH.exists():
        return None
    approvals = json.loads(APPROVALS_PATH.read_text(encoding="utf-8")).get("approvals", {})
    item = approvals.get(approval_id)
    return item.get("decision") if item else None


def record_approval(approval_id: str, decision: str, actor: str, reason: str, target: str) -> dict[str, Any]:
    role_failure = enforce_actor_operation(actor, "approval-record", target=target)
    if role_failure:
        raise PermissionError(role_failure.detail)
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
    payload = rust_validate_target("knowledge/ARTIFACTS/refs/narrative-check.md", text, "approved")
    return annotate_findings(
        [ValidationFinding(item["code"], item["detail"], item["severity"], item.get("rule_refs", [])) for item in payload["findings"]]
    )


def validate_target(
    target: str,
    content: str,
    approval_id: str | None = None,
    *,
    endpoint: str = "",
    reason: str = "",
) -> list[ValidationFinding]:
    if target.endswith(".json"):
        payload = rust_validate_target(
            target,
            "# Structured Artifact\n\n## This Artifact Records Machine Readable Data\nStructured validation is governed while narrative validation is skipped for JSON artifacts.\n",
            approval_status(approval_id) or "missing",
        )
        return annotate_findings(
            [ValidationFinding(item["code"], item["detail"], item["severity"], item.get("rule_refs", [])) for item in payload["findings"]]
        )
    payload = rust_validate_target(target, content, approval_status(approval_id) or "missing")
    findings = annotate_findings(
        [ValidationFinding(item["code"], item["detail"], item["severity"], item.get("rule_refs", [])) for item in payload["findings"]]
    )
    for action in matching_validator_actions(target, endpoint or "validate-target", reason, content):
        findings.append(
            annotate_finding(
                ValidationFinding(
                    "DREAMER_VALIDATOR_CHANGE_ACTIVE",
                    f"Active Dreamer validator action applies: {action['pattern_reason']}",
                    severity="warning",
                )
            )
        )
    return findings


def authorize_dreamer_action_mutation(
    *,
    actor: str,
    target: str,
    endpoint: str,
    reason: str,
    approval_id: str | None,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    role_failure = enforce_actor_operation(actor, "dreamer-action-mutate", target=target, endpoint=endpoint)
    if role_failure:
        findings.append(role_failure)
    if approval_status(approval_id) != "approved":
        findings.append(
            annotate_finding(
                ValidationFinding(
                    "DREAMER_ACTION_APPROVAL_REQUIRED",
                    "Dreamer action registry mutation requires explicit approved authorization.",
                )
            )
        )
    if findings:
        append_event(
            EventRecord(
                source="vela",
                endpoint=endpoint,
                actor=actor,
                target=target,
                status="blocked",
                reason=reason,
                artifacts=[target],
                approval_required=True,
                validation_summary={"findings": [item.as_dict() for item in findings]},
            )
        )
    return findings


def append_event(record: EventRecord) -> None:
    append_plan = plan_event_append_payload(record.as_dict())
    if not append_plan["ok"]:
        raise ValueError(f"Invalid event append plan: {append_plan['findings']}")
    EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(str(append_plan["plan"]["line"]) + "\n")


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
    path = REPO_ROOT / target
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    local_findings: list[ValidationFinding] = []
    role_failure = enforce_actor_operation(actor, "write-text", target=target, endpoint=endpoint)
    if role_failure:
        local_findings.append(role_failure)
    if endpoint != "dreamer-follow-up-apply":
        for action in matching_refusal_actions(target, endpoint, reason, content):
            local_findings.append(
                annotate_finding(
                    ValidationFinding(
                        "DREAMER_REFUSAL_TIGHTENING_ACTIVE",
                        f"Active Dreamer refusal tightening blocks this operation: {action['pattern_reason']}",
                    )
                )
            )
    if previous:
        subject_payload = validate_subject_declaration_payload(previous, content, approval_status(approval_id) or "missing")
        local_findings.extend(
            annotate_findings(
                [ValidationFinding(item["code"], item["detail"], item["severity"], item.get("rule_refs", [])) for item in subject_payload["findings"]]
            )
        )
    findings = local_findings + validate_target(target, content, approval_id=approval_id, endpoint=endpoint, reason=reason)
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
        path.parent.mkdir(parents=True, exist_ok=True)
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
    role_failure = enforce_actor_operation(actor, "archive", target=target, endpoint=endpoint)
    if role_failure:
        return {"ok": False, "findings": [role_failure.as_dict()]}
    path = REPO_ROOT / target
    content = path.read_text(encoding="utf-8")
    entry_marker = f"- {entry_value}"
    if entry_marker not in content:
        finding = annotate_finding(ValidationFinding("ARCHIVE_ENTRY_NOT_FOUND", f"Entry not found for archive: {entry_value}"))
        return {"ok": False, "findings": [finding.as_dict()]}

    section_start = content.find(dimension_heading)
    if section_start == -1:
        finding = annotate_finding(ValidationFinding("ARCHIVE_DIMENSION_NOT_FOUND", f"Dimension not found: {dimension_heading}"))
        return {"ok": False, "findings": [finding.as_dict()]}

    next_section = content.find("\n## ", section_start + 1)
    dimension_section = content[section_start: next_section if next_section != -1 else len(content)]
    active_start = dimension_section.find("### Active")
    inactive_start = dimension_section.find("### Inactive")
    if active_start == -1 or inactive_start == -1:
        finding = annotate_finding(ValidationFinding("ARCHIVE_STRUCTURE_INVALID", f"Dimension missing Active/Inactive sections: {dimension_heading}"))
        return {"ok": False, "findings": [finding.as_dict()]}

    active_section = dimension_section[active_start:inactive_start]
    entry_block = _extract_entry_block(active_section, entry_value)
    if not entry_block:
        finding = annotate_finding(ValidationFinding("ARCHIVE_ACTIVE_ENTRY_NOT_FOUND", f"Active entry not found for archive: {entry_value}"))
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
    new_dimension_section = dimension_heading + "\n\n" + updated_active.lstrip("\n") + "\n\n" + inactive_section.lstrip("\n")
    new_content = content[:section_start] + new_dimension_section + content[next_section if next_section != -1 else len(content):]

    archive_heading = "## 700.Archive"
    archive_pos = new_content.find(archive_heading)
    if archive_pos == -1:
        finding = annotate_finding(ValidationFinding("ARCHIVE_BLOCK_MISSING", "700.Archive is missing from target SoT"))
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
        postcondition_failure = _archive_postcondition_failure(
            (REPO_ROOT / target).read_text(encoding="utf-8"),
            entry_value=entry_value,
            archived_reason=archived_reason,
            dimension_heading=dimension_heading,
        )
        if postcondition_failure:
            return {"ok": False, "findings": [postcondition_failure.as_dict()]}
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
    role_failure = enforce_actor_operation("grower", "growth-proposal", target=target, endpoint="growth-proposal")
    if role_failure:
        return {
            "ok": False,
            "target": "",
            "critique": critique,
            "findings": [role_failure.as_dict()],
            "approval_required": is_sovereign_target(target),
            "artifacts": [],
        }
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
        finding = annotate_finding(ValidationFinding("GROWTH_PROPOSAL_NOT_FOUND", f"Growth proposal not found: {proposal_target}"))
        return {"ok": False, "findings": [finding.as_dict()]}

    proposal_text = proposal_path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(proposal_text)
    assessed_target = str(frontmatter.get("target", "")).strip().strip('"')
    stage = str(frontmatter.get("recommended-stage", "")).strip().strip('"')
    route = str(frontmatter.get("route", "")).strip().strip('"')

    if not assessed_target or not stage:
        finding = annotate_finding(ValidationFinding(
            "GROWTH_PROPOSAL_METADATA_INVALID",
            f"{proposal_target} is missing required growth metadata",
        ))
        return {"ok": False, "findings": [finding.as_dict()]}

    role_failure = enforce_actor_operation(actor, "growth-apply", target=proposal_target, endpoint="growth-apply", stage=stage)
    if role_failure:
        append_event(
            EventRecord(
                source="vela",
                endpoint="growth-apply",
                actor=actor,
                target=proposal_target,
                status="blocked",
                reason=role_failure.detail,
                artifacts=[proposal_target],
                approval_required=stage == "spawn",
                validation_summary={"assessed_target": assessed_target, "stage": stage, "route": route},
            )
        )
        return {"ok": False, "findings": [role_failure.as_dict()], "approval_required": stage == "spawn"}

    growth_payload = validate_growth_stage_payload(stage, approval_status(approval_id) or "missing")
    growth_findings = annotate_findings(
        [ValidationFinding(item["code"], item["detail"], item["severity"], item.get("rule_refs", [])) for item in growth_payload["findings"]]
    )
    if growth_findings:
        finding = growth_findings[0]
        append_event(
            EventRecord(
                source="vela",
                endpoint="growth-apply",
                actor=actor,
                target=proposal_target,
                status="blocked",
                reason="spawn execution requires explicit human approval",
                artifacts=[proposal_target],
                approval_required=True,
                validation_summary={"assessed_target": assessed_target, "stage": stage, "route": route},
            )
        )
        return {"ok": False, "findings": [finding.as_dict()], "approval_required": True}

    if is_sovereign_target(assessed_target) and approval_status(approval_id) != "approved":
        finding = annotate_finding(ValidationFinding(
            "SOVEREIGN_APPROVAL_REQUIRED",
            "Growth execution targets a sovereign artifact and requires approval",
        ))
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
    if not execution["ok"]:
        return {"ok": False, "findings": execution["findings"]}
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

    source_update = _apply_growth_to_source(
        stage=stage,
        assessed_target=assessed_target,
        execution_target=execution["target"],
        proposal_target=proposal_target,
        actor=actor,
        approval_id=approval_id,
        execution=execution,
    )
    if not source_update["ok"]:
        return {
            "ok": False,
            "findings": source_update["findings"],
            "execution_target": execution["target"],
            "source_target": assessed_target,
        }

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
            artifacts=[
                proposal_target,
                execution["target"],
                assessed_target,
                *result.get("artifacts", []),
                *source_update.get("artifacts", []),
            ],
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
        "ok": result["ok"] and proposal_result["ok"] and source_update["ok"],
        "proposal_target": proposal_target,
        "execution_target": execution["target"],
        "source_target": assessed_target,
        "execution_kind": execution["kind"],
        "stage": stage,
        "findings": result["findings"] + source_update.get("findings", []) + proposal_result.get("findings", []),
    }


def route_inbox_entry(text: str) -> str | None:
    payload = route_inbox_payload(text)
    dimension = payload.get("dimension")
    return str(dimension) if dimension is not None else None


def build_pointer_entry(description: str, primary_target: str, dimension_heading: str, date: str) -> str:
    return f"- {description}. See: [[{primary_target}#{dimension_heading}]] ({date})"


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def create_cross_reference(
    *,
    claimant_target: str,
    claimant_dimension_heading: str,
    description: str,
    primary_target: str,
    primary_dimension_heading: str,
    actor: str,
    endpoint: str,
    reason: str,
    approval_id: str | None = None,
) -> dict[str, Any]:
    role_failure = enforce_actor_operation(actor, "cross-reference", target=claimant_target, endpoint=endpoint)
    if role_failure:
        return {"ok": False, "findings": [role_failure.as_dict()]}
    claimant_path = REPO_ROOT / claimant_target
    if not claimant_path.exists():
        finding = annotate_finding(
            ValidationFinding("CROSS_REFERENCE_TARGET_MISSING", f"Claimant SoT does not exist: {claimant_target}")
        )
        return {"ok": False, "findings": [finding.as_dict()]}

    content = claimant_path.read_text(encoding="utf-8")
    section = _section_by_heading(content, claimant_dimension_heading)
    if not section:
        finding = annotate_finding(
            ValidationFinding("CROSS_REFERENCE_DIMENSION_MISSING", f"Claimant dimension not found: {claimant_dimension_heading}")
        )
        return {"ok": False, "findings": [finding.as_dict()]}

    active = _subsection(section, "### Active")
    if not active:
        finding = annotate_finding(
            ValidationFinding("CROSS_REFERENCE_ACTIVE_SECTION_MISSING", f"Claimant Active section not found: {claimant_dimension_heading}")
        )
        return {"ok": False, "findings": [finding.as_dict()]}

    pointer = build_pointer_entry(description, Path(primary_target).stem, primary_dimension_heading, _today())
    if pointer not in active:
        if "(No active entries.)" in active:
            updated_active = active.replace("(No active entries.)", pointer)
        else:
            updated_active = active.rstrip() + f"\n\n{pointer}\n"
    else:
        updated_active = active

    updated_section = section.replace(active, updated_active, 1)
    updated_content = content.replace(section, updated_section, 1)
    result = write_text(
        claimant_target,
        updated_content,
        actor=actor,
        endpoint=endpoint,
        reason=reason,
        approval_id=approval_id,
    )
    if result["ok"]:
        append_event(
            EventRecord(
                source="vela",
                endpoint=endpoint,
                actor=actor,
                target=claimant_target,
                status="committed",
                reason=reason,
                artifacts=result.get("artifacts", [claimant_target]),
                approval_required=bool(approval_id),
                validation_summary={
                    "pointer": pointer,
                    "primary_target": primary_target,
                    "primary_dimension_heading": primary_dimension_heading,
                    "claimant_dimension_heading": claimant_dimension_heading,
                },
            )
        )
    return {
        "ok": result["ok"],
        "pointer": pointer,
        "target": claimant_target,
        "findings": result.get("findings", []),
        "artifacts": result.get("artifacts", [claimant_target]),
    }


def _build_growth_execution(stage: str, assessed_target: str, proposal_target: str) -> dict[str, str]:
    created = datetime.now(timezone.utc).date().isoformat()
    source_text = (REPO_ROOT / assessed_target).read_text(encoding="utf-8")
    payload = plan_growth_execution_payload(stage, assessed_target, proposal_target)
    plan = payload.get("plan")
    if not payload.get("ok") or not plan:
        findings = annotate_findings(
            [ValidationFinding(item["code"], item["detail"], item["severity"], item.get("rule_refs", [])) for item in payload.get("findings", [])]
        )
        return {"ok": False, "findings": [item.as_dict() for item in findings]}

    if stage == "fractal":
        content = _fractalize_source(source_text, assessed_target, proposal_target, created)
        return {"ok": True, "target": str(plan["target"]), "content": content, "kind": str(plan["kind"])}

    if stage == "reference-note":
        execution_target = str(plan["target"])
        extracted = {
            "dimension": str(plan.get("dimension", "")),
            "entries": list(plan.get("entries", [])),
        }
        content = _render_reference_note(
            execution_target=execution_target,
            assessed_target=assessed_target,
            proposal_target=proposal_target,
            created=created,
            extracted=extracted,
        )
        return {
            "ok": True,
            "target": execution_target,
            "content": content,
            "kind": str(plan["kind"]),
            "dimension": extracted["dimension"],
            "entries": extracted["entries"],
        }

    if stage == "spawn" and assessed_target.endswith("-SoT.md"):
        execution_target = str(plan["target"])
        content = _render_spawned_sot(execution_target, assessed_target, proposal_target, created)
        return {"ok": True, "target": execution_target, "content": content, "kind": str(plan["kind"])}

    execution_target = str(plan["target"])
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
    return {"ok": True, "target": execution_target, "content": content, "kind": str(plan["kind"])}


def _archive_postcondition_failure(content: str, entry_value: str, archived_reason: str, dimension_heading: str) -> ValidationFinding | None:
    payload = validate_archive_postconditions_payload(content, entry_value, archived_reason, dimension_heading)
    findings = annotate_findings(
        [ValidationFinding(item["code"], item["detail"], item["severity"], item.get("rule_refs", [])) for item in payload["findings"]]
    )
    return findings[0] if findings else None


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
        f"- Source Branch: [[{parent_name}]]\n"
        f"- Source Target: `{assessed_target}`\n"
        "- Cornerstone: [[Cornerstone.Knosence-SoT]]\n"
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


def _apply_growth_to_source(
    *,
    stage: str,
    assessed_target: str,
    execution_target: str,
    proposal_target: str,
    actor: str,
    approval_id: str | None,
    execution: dict[str, Any],
) -> dict[str, Any]:
    if stage not in {"reference-note", "spawn"}:
        return {"ok": True, "findings": [], "artifacts": [assessed_target]}

    path = REPO_ROOT / assessed_target
    source_text = path.read_text(encoding="utf-8")
    updated = _inject_growth_source_updates(
        source_text=source_text,
        assessed_target=assessed_target,
        execution_target=execution_target,
        proposal_target=proposal_target,
        stage=stage,
        execution=execution,
    )
    return write_text(
        assessed_target,
        updated,
        actor=actor,
        endpoint="growth-apply",
        reason=f"update source after growth proposal {proposal_target}",
        approval_id=approval_id,
    )


def _inject_growth_source_updates(
    *,
    source_text: str,
    assessed_target: str,
    execution_target: str,
    proposal_target: str,
    stage: str,
    execution: dict[str, Any],
) -> str:
    created = datetime.now(timezone.utc).date().isoformat()
    execution_name = Path(execution_target).stem
    parent_name = Path(assessed_target).stem
    stage_label = "reference note" if stage == "reference-note" else "spawned child SoT"
    link_line = (
        f"- Reference Note: [[{execution_name}]]"
        if stage == "reference-note"
        else f"- Spawned Child: [[{execution_name}]]"
    )
    decision_line = (
        f"- [{created}] Growth proposal `{proposal_target}` created a {stage_label} `[[{execution_name}]]`."
    )
    next_action_line = (
        f"- Route detailed branch material through `[[{execution_name}]]` before adding more weight to `{parent_name}`. ({created})\n"
        "  - Growth should redirect future detail toward the lighter-weight structural outcome. [AGENT:gpt-5]"
    )
    status_line = (
        f"- A governed growth step created `[[{execution_name}]]` as the next structural home. ({created})\n"
        "  - The parent remains canonical for its scope while redirecting deeper material through the new structure. [AGENT:gpt-5]"
    )

    updated = _append_line_to_section(source_text, "### Links", link_line)
    updated = _append_line_to_section(updated, "### Status", status_line)
    updated = _append_line_to_section(updated, "### Next Actions", next_action_line)
    updated = _append_line_to_section(updated, "### Decisions", decision_line)
    if stage == "reference-note":
        updated = _replace_entries_with_reference_pointer(
            updated,
            execution.get("dimension", ""),
            execution.get("entries", []),
            execution_name,
            created,
        )
    if stage == "spawn":
        updated = _insert_spawn_branch_pointer(updated, execution_name, created)
    return updated


def _append_line_to_section(text: str, heading: str, addition: str) -> str:
    start = text.find(heading)
    if start == -1:
        return text
    rest = text[start + len(heading):]
    next_heading_match = re.search(r"\n### |\n## ", rest)
    end = start + len(heading) + next_heading_match.start() if next_heading_match else len(text)
    section = text[start:end].rstrip("\n")
    if addition in section:
        return text
    section = f"{section}\n\n{addition}\n"
    return text[:start] + section + text[end:]


def _fractalize_source(source_text: str, assessed_target: str, proposal_target: str, created: str) -> str:
    if re.search(r"^##\s[1-6][1-9]0\.", source_text, flags=re.MULTILINE):
        return source_text

    counts = _dimension_entry_counts(source_text)
    if not counts:
        return source_text
    densest = max(counts, key=counts.get)
    subgroup_heading = f"## {int(densest) + 10:03d}.{_dimension_label(source_text, densest)}-Subgroup"
    subgroup = (
        f"{subgroup_heading}\n\n"
        "### Active\n\n"
        f"- Grouping scaffold created from `{proposal_target}`. ({created})\n"
        "  - This subgroup marks the first structural split inside the densest dimension. [AGENT:gpt-5]\n\n"
        "### Inactive\n\n"
        "(No inactive entries.)\n\n"
    )
    anchor = _next_top_level_heading_for_dimension(source_text, densest)
    if anchor:
        return source_text.replace(anchor, subgroup + anchor, 1)
    return source_text.rstrip() + "\n\n" + subgroup


def _dimension_entry_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    current_dimension = ""
    for line in text.splitlines():
        match = re.match(r"^##\s(\d{3})\.", line.strip())
        if match:
            current_dimension = match.group(1)
            if current_dimension in {"100", "200", "300", "400", "500", "600"}:
                counts.setdefault(current_dimension, 0)
            else:
                current_dimension = ""
            continue
        if current_dimension and line.startswith("- "):
            counts[current_dimension] += 1
    return counts


def _next_top_level_heading_for_dimension(text: str, dimension: str) -> str:
    current = int(dimension)
    for candidate in range(current + 100, 701, 100):
        marker = f"## {candidate:03d}."
        if marker in text:
            start = text.find(marker)
            end = text.find("\n", start)
            return text[start:end] if end != -1 else text[start:]
    return ""


def _dimension_label(text: str, dimension: str) -> str:
    match = re.search(rf"^##\s{dimension}\.[^.]+\.(.+)$", text, flags=re.MULTILINE)
    if not match:
        return "Grouping"
    raw = re.sub(r"[^A-Za-z0-9]+", "-", match.group(1)).strip("-")
    return raw or "Grouping"


def _extract_reference_entries(source_text: str) -> dict[str, Any]:
    counts = _dimension_entry_counts(source_text)
    if not counts:
        return {"dimension": "", "entries": []}
    densest = max(counts, key=lambda item: (counts[item], _dimension_preference(item)))
    section = _dimension_section(source_text, densest)
    active = _subsection(section, "### Active")
    entries = _entry_blocks(active)[:2]
    return {"dimension": _dimension_heading(source_text, densest), "entries": entries}


def _dimension_preference(dimension: str) -> int:
    order = {
        "200": 6,
        "500": 5,
        "300": 4,
        "400": 3,
        "600": 2,
        "100": 1,
    }
    return order.get(dimension, 0)


def _render_reference_note(
    *,
    execution_target: str,
    assessed_target: str,
    proposal_target: str,
    created: str,
    extracted: dict[str, Any],
) -> str:
    heading = extracted.get("dimension", "")
    entries = extracted.get("entries", [])
    entry_text = "\n\n".join(entries) if entries else "(No extracted entries.)"
    return (
        f"# Reference Note for {Path(execution_target).name}\n\n"
        "## This Reference Note Exists Because the Parent Artifact Has Exceeded a Flat Shape\n"
        f"The governed growth proposal `{proposal_target}` recommended extraction into a reference note.\n\n"
        "## This Reference Note Points Back to the Assessed Parent Artifact\n"
        f"- parent artifact: `{assessed_target}`\n"
        f"- proposal: `{proposal_target}`\n"
        f"- extracted from: `{heading}`\n"
        f"- created: `{created}`\n\n"
        "## This Reference Note Preserves the Extracted Active Entries\n"
        f"{entry_text}\n"
    )


def _replace_entries_with_reference_pointer(
    source_text: str,
    dimension_heading: str,
    entries: list[str],
    execution_name: str,
    created: str,
) -> str:
    if not dimension_heading or not entries:
        return source_text
    section = _section_by_heading(source_text, dimension_heading)
    if not section:
        return source_text
    active = _subsection(section, "### Active")
    updated_active = active
    for entry in entries:
        updated_active = updated_active.replace(entry, "").strip()
    pointer = (
        f"- Detailed entries moved to `[[{execution_name}]]`. ({created})\n"
        "  - The parent keeps the summary while the deeper detail now lives in the reference note. [AGENT:gpt-5]"
    )
    if pointer not in updated_active:
        updated_active = f"{updated_active}\n\n{pointer}".strip()
    section_updated = section.replace(active, updated_active, 1)
    return source_text.replace(section, section_updated, 1)


def _insert_spawn_branch_pointer(source_text: str, execution_name: str, created: str) -> str:
    counts = _dimension_entry_counts(source_text)
    if not counts:
        return source_text
    densest = max(counts, key=lambda item: (counts[item], _dimension_preference(item)))
    dimension_heading = _dimension_heading(source_text, densest)
    section = _section_by_heading(source_text, dimension_heading)
    if not section:
        return source_text
    active = _subsection(section, "### Active")
    pointer = (
        f"- Branch-specific detail now continues in `[[{execution_name}]]`. ({created})\n"
        "  - The parent retains the summary while the new child SoT carries the deeper branch structure. [AGENT:gpt-5]"
    )
    updated_active = active if pointer in active else f"{active.rstrip()}\n\n{pointer}\n"
    section_updated = section.replace(active, updated_active, 1)
    return source_text.replace(section, section_updated, 1)


def _dimension_heading(text: str, dimension: str) -> str:
    match = re.search(rf"^(##\s{dimension}\.[^\n]+)$", text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def _dimension_section(text: str, dimension: str) -> str:
    return _section_by_heading(text, _dimension_heading(text, dimension))


def _section_by_heading(text: str, heading: str) -> str:
    if not heading:
        return ""
    start = text.find(heading)
    if start == -1:
        return ""
    rest = text[start + len(heading):]
    next_heading_match = re.search(r"\n## ", rest)
    end = start + len(heading) + next_heading_match.start() if next_heading_match else len(text)
    return text[start:end]


def _subsection(section: str, heading: str) -> str:
    start = section.find(heading)
    if start == -1:
        return ""
    rest = section[start + len(heading):]
    next_heading_match = re.search(r"\n### |\n## ", rest)
    end = start + len(heading) + next_heading_match.start() if next_heading_match else len(section)
    return section[start:end]


def _entry_blocks(active_section: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in active_section.splitlines():
        if line.startswith("- "):
            if current:
                blocks.append("\n".join(current).strip())
            current = [line]
            continue
        if current:
            if line.startswith("### ") or line.startswith("## "):
                break
            if line.strip():
                current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [block for block in blocks if not block.startswith("- Detailed entries moved")]


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
