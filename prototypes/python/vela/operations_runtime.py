from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

from .dreamer_actions import load_dreamer_actions
from .dreamer_actions import register_dreamer_action as register_dreamer_action_runtime
from .governance import append_event, record_approval, validate_target, write_text
from .growth import assess_growth
from .merge import (
    detect_merge_candidates,
    list_merge_follow_ups as list_merge_follow_ups_runtime,
    list_merge_proposals as list_merge_proposals_runtime,
    merge_follow_up_target,
    merge_proposal_target,
    replace_ref_with_sot_pointer,
    render_applied_merge_follow_up,
    render_merge_follow_up,
    render_merge_proposal,
    render_merge_spawned_sot,
    render_reviewed_merge_proposal,
    suggest_merge_target,
)
from .models import EventRecord
from .paths import DREAMER_ACTIONS_PATH, EVENT_LOG_PATH, OPERATIONS_STATE_PATH, PATCH_LOG_PATH, QUEUE_DIR, REFS_DIR, REPO_ROOT
from .rust_bridge import (
    inspect_dreamer_follow_up_payload,
    inspect_dreamer_follow_up_kind_payload,
    inspect_dreamer_proposal_payload,
    extract_blocked_items_payload,
    extract_patch_targets_payload,
    list_dreamer_follow_ups_payload,
    list_dreamer_queue_payload,
    list_growth_targets_payload,
    matrix_inventory_payload,
    plan_night_cycle_payload,
    plan_dreamer_follow_up_apply_payload,
    plan_dreamer_review_payload,
    plan_operation_start_payload,
    plan_operation_state_update_payload,
    plan_operation_audit_event_payload,
    plan_dreamer_proposals_payload,
    plan_scheduler_run_payload,
    plan_warden_patrol_payload,
    render_dc_night_report_payload,
    render_dreamer_pattern_report_payload,
    render_dreamer_proposal_payload,
    render_warden_patrol_report_payload,
    validate_dc_night_report_payload,
    validate_dreamer_follow_up_apply_payload,
    validate_dreamer_pattern_report_payload,
    validate_dreamer_execution_artifact_payload,
    validate_dreamer_review_payload,
    parse_operations_state_payload,
    validate_operation_lock_payload,
    validate_operation_request_payload,
    validate_warden_patrol_report_payload,
)

PATROL_INTERVAL_SECONDS = 4 * 60 * 60
NIGHT_CYCLE_INTERVAL_SECONDS = 24 * 60 * 60


def run_warden_patrol(requested_by: str = "system") -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    request_findings = validate_operation_request_payload("patrol", requested_by).get("findings", [])
    if request_findings:
        _update_operation_state(
            "patrol",
            status="blocked",
            requested_by=requested_by,
            started_at=started_at,
            last_error=request_findings[0]["detail"],
        )
        _append_operation_event(
            "patrol-blocked",
            target="runtime/config/operations-state.json",
            reason=request_findings[0]["detail"],
            artifacts=["runtime/config/operations-state.json"],
            validation_summary={"requested_by": requested_by},
        )
        return {
            "ok": False,
            "report_target": "",
            "files_checked": 0,
            "structural_flags": [],
            "cosmetic_fixes": [],
            "findings": request_findings,
        }
    lock = _acquire_operation_lock("patrol", requested_by, started_at)
    if not lock["ok"]:
        _update_operation_state(
            "patrol",
            status="blocked",
            requested_by=requested_by,
            started_at=started_at,
            last_error=lock["detail"],
        )
        _append_operation_event(
            "patrol-blocked",
            target=lock["target"],
            reason=lock["detail"],
            artifacts=[lock["target"]],
            validation_summary={"requested_by": requested_by},
        )
        return {"ok": False, "report_target": "", "files_checked": 0, "structural_flags": [], "cosmetic_fixes": [], "findings": [lock]}
    targets = _patched_targets()
    checked: list[dict[str, Any]] = []
    structural_flags: list[dict[str, Any]] = []
    report_target = ""
    for target in targets:
        path = REPO_ROOT / target
        if not path.exists() or not path.is_file():
            continue
        if path.suffix not in {".md", ".json"}:
            continue
        content = path.read_text(encoding="utf-8")
        findings = [item.as_dict() for item in validate_target(target, content)]
        if any(item["severity"] == "error" for item in findings):
            structural_flags.append({"target": target, "findings": findings})
        checked.append({"target": target, "findings": findings})

    stamp = _stamp()
    plan_payload = plan_warden_patrol_payload(
        stamp,
        requested_by,
        [item["target"] for item in checked],
        [item["target"] for item in structural_flags],
    )
    plan = plan_payload.get("plan")
    plan_findings = plan_payload.get("findings", [])
    if not plan_payload.get("ok") or not plan:
        _update_operation_state(
            "patrol",
            status="blocked",
            requested_by=requested_by,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            last_error=plan_findings[0]["detail"] if plan_findings else "warden patrol planning failed",
            release_lock=True,
        )
        return {
            "ok": False,
            "report_target": plan["report_target"] if plan else "",
            "files_checked": len(checked),
            "structural_flags": structural_flags,
            "cosmetic_fixes": [],
            "findings": plan_findings,
        }
    report_target = str(plan["report_target"])
    report = str(plan["report_content"])
    result = write_text(report_target, report, actor="warden", endpoint="patrol", reason="warden patrol report")
    _update_operation_state(
        "patrol",
        status="completed" if result["ok"] else "blocked",
        requested_by=requested_by,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc).isoformat(),
        last_report_target=report_target,
        last_error="" if result["ok"] else "warden patrol blocked",
        increment_runs=result["ok"],
        release_lock=True,
    )
    _append_operation_event(
        "patrol-completed" if result["ok"] else "patrol-blocked",
        target=report_target,
        reason="warden patrol executed" if result["ok"] else "warden patrol blocked",
        artifacts=result.get("artifacts", [report_target]),
        validation_summary={
            "requested_by": requested_by,
            "files_checked": len(checked),
            "structural_flags": len(structural_flags),
        },
    )
    return {
        "ok": result["ok"],
        "report_target": report_target,
        "files_checked": len(checked),
        "structural_flags": structural_flags,
        "cosmetic_fixes": [],
    }
def run_night_cycle(requested_by: str = "system") -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    request_findings = validate_operation_request_payload("night-cycle", requested_by).get("findings", [])
    if request_findings:
        _update_operation_state(
            "night-cycle",
            status="blocked",
            requested_by=requested_by,
            started_at=started_at,
            last_error=request_findings[0]["detail"],
        )
        _append_operation_event(
            "night-cycle-blocked",
            target="runtime/config/operations-state.json",
            reason=request_findings[0]["detail"],
            artifacts=["runtime/config/operations-state.json"],
            validation_summary={"requested_by": requested_by},
        )
        return {
            "ok": False,
            "report_target": "",
            "dreamer_report_target": "",
            "patrol": {"ok": False},
            "growth_candidates": [],
            "merge_proposals": [],
            "dreamer_patterns": {},
            "blocked_items": [],
            "dreamer_proposals": [],
            "findings": request_findings,
        }
    lock = _acquire_operation_lock("night-cycle", requested_by, started_at)
    if not lock["ok"]:
        _update_operation_state(
            "night-cycle",
            status="blocked",
            requested_by=requested_by,
            started_at=started_at,
            last_error=lock["detail"],
        )
        _append_operation_event(
            "night-cycle-blocked",
            target=lock["target"],
            reason=lock["detail"],
            artifacts=[lock["target"]],
            validation_summary={"requested_by": requested_by},
        )
        return {
            "ok": False,
            "report_target": "",
            "dreamer_report_target": "",
            "patrol": {"ok": False},
            "growth_candidates": [],
            "merge_proposals": [],
            "dreamer_patterns": {},
            "blocked_items": [],
            "dreamer_proposals": [],
            "findings": [lock],
        }
    report_target = ""
    dreamer_report_target = ""
    patrol = run_warden_patrol(requested_by=f"night-cycle:{requested_by}")
    if not patrol["ok"]:
        _update_operation_state(
            "night-cycle",
            status="blocked",
            requested_by=requested_by,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            last_error="night cycle could not acquire dependent patrol execution",
            release_lock=True,
        )
        return {
            "ok": False,
            "report_target": "",
            "dreamer_report_target": "",
            "patrol": patrol,
            "growth_candidates": [],
            "merge_proposals": [],
            "dreamer_patterns": {},
            "blocked_items": [],
            "dreamer_proposals": [],
            "findings": patrol.get("findings", []),
        }
    growth_candidates = _growth_candidates()
    merge_proposals = _write_merge_proposals(requested_by)
    blocked_items = _blocked_items()
    stamp = _stamp()
    dreamer_proposals = _write_dreamer_proposals(stamp, requested_by, blocked_items)
    dreamer_patterns = _dreamer_patterns(dreamer_proposals)
    plan_payload = plan_night_cycle_payload(
        stamp,
        requested_by,
        patrol.get("report_target", ""),
        int(patrol.get("files_checked", 0)),
        len(patrol.get("structural_flags", [])),
        growth_candidates,
        dreamer_patterns,
        blocked_items,
        dreamer_proposals,
    )
    plan = plan_payload.get("plan")
    plan_findings = plan_payload.get("findings", [])
    if not plan_payload.get("ok") or not plan:
        _update_operation_state(
            "night-cycle",
            status="blocked",
            requested_by=requested_by,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            last_error=plan_findings[0]["detail"] if plan_findings else "night cycle planning failed",
            release_lock=True,
        )
        return {
            "ok": False,
            "report_target": "",
            "dreamer_report_target": plan["dreamer_report_target"] if plan else "",
            "patrol": patrol,
            "growth_candidates": growth_candidates,
            "merge_proposals": merge_proposals,
            "dreamer_patterns": dreamer_patterns,
            "blocked_items": blocked_items,
            "dreamer_proposals": dreamer_proposals,
            "findings": plan_findings,
        }
    dreamer_report_target = str(plan["dreamer_report_target"])
    dreamer_report = str(plan["dreamer_report_content"])
    dreamer_result = write_text(
        dreamer_report_target,
        dreamer_report,
        actor="reflector",
        endpoint="night-cycle",
        reason="dreamer pattern report",
    )
    report_target = str(plan["report_target"])
    report = str(plan["report_content"])
    result = write_text(report_target, report, actor="system", endpoint="night-cycle", reason="dc night cycle report")
    _update_operation_state(
        "night-cycle",
        status="completed" if result["ok"] and dreamer_result["ok"] else "blocked",
        requested_by=requested_by,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc).isoformat(),
        last_report_target=report_target,
        last_error="" if result["ok"] and dreamer_result["ok"] else "night cycle blocked",
        increment_runs=result["ok"] and dreamer_result["ok"],
        release_lock=True,
    )
    _append_operation_event(
        "night-cycle-completed" if result["ok"] else "night-cycle-blocked",
        target=report_target,
        reason="dc night cycle executed" if result["ok"] else "night cycle blocked",
        artifacts=[
            dreamer_report_target,
            report_target,
            *dreamer_result.get("artifacts", [dreamer_report_target]),
            *result.get("artifacts", [report_target]),
        ],
        validation_summary={
            "requested_by": requested_by,
            "growth_candidates": len(growth_candidates),
            "merge_proposals": [item["target"] for item in merge_proposals],
            "dreamer_patterns": dreamer_patterns,
            "blocked_items": len(blocked_items),
            "patrol_report": patrol.get("report_target", ""),
            "dreamer_report": dreamer_report_target,
            "dreamer_proposals": [item["target"] for item in dreamer_proposals],
        },
    )
    return {
        "ok": result["ok"] and dreamer_result["ok"],
        "report_target": report_target,
        "dreamer_report_target": dreamer_report_target,
        "patrol": patrol,
        "growth_candidates": growth_candidates,
        "merge_proposals": merge_proposals,
        "dreamer_patterns": dreamer_patterns,
        "blocked_items": blocked_items,
        "dreamer_proposals": dreamer_proposals,
    }


def run_warden_patrol_scheduler(
    *,
    requested_by: str = "system",
    interval_seconds: int = PATROL_INTERVAL_SECONDS,
    max_runs: int = 1,
) -> dict[str, Any]:
    return _run_scheduler("patrol", requested_by=requested_by, interval_seconds=interval_seconds, max_runs=max_runs)


def run_night_cycle_scheduler(
    *,
    requested_by: str = "system",
    interval_seconds: int = NIGHT_CYCLE_INTERVAL_SECONDS,
    max_runs: int = 1,
) -> dict[str, Any]:
    return _run_scheduler("night-cycle", requested_by=requested_by, interval_seconds=interval_seconds, max_runs=max_runs)


def operations_state() -> dict[str, Any]:
    return _load_operations_state()


def _append_operation_event(
    kind: str,
    *,
    target: str,
    reason: str,
    artifacts: list[str],
    validation_summary: dict[str, Any],
) -> None:
    event = EventRecord(
        source="vela",
        endpoint="operations",
        actor="system",
        target=target,
        status="planned",
        reason=reason,
        artifacts=artifacts,
        validation_summary=validation_summary,
    )
    payload = plan_operation_audit_event_payload(kind, event.as_dict())
    if not payload.get("ok"):
        raise ValueError(f"Invalid operation audit event plan: {payload.get('findings', [])}")
    EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(str(payload["plan"]["line"]) + "\n")


def list_dreamer_queue() -> dict[str, Any]:
    payload = list_dreamer_queue_payload()
    return {"ok": bool(payload.get("ok")), "items": list(payload.get("items", []))}


def list_dreamer_follow_ups() -> dict[str, Any]:
    payload = list_dreamer_follow_ups_payload()
    return {"ok": bool(payload.get("ok")), "items": list(payload.get("items", []))}


def list_merge_candidates() -> dict[str, Any]:
    return {"ok": True, "items": [item.as_dict() for item in detect_merge_candidates()]}


def list_merge_proposals() -> dict[str, Any]:
    payload = list_merge_proposals_runtime()
    return {"ok": bool(payload.get("ok")), "items": list(payload.get("items", []))}


def list_merge_follow_ups() -> dict[str, Any]:
    payload = list_merge_follow_ups_runtime()
    return {"ok": bool(payload.get("ok")), "items": list(payload.get("items", []))}


def review_merge_proposal(target: str, decision: str, actor: str, reason: str) -> dict[str, Any]:
    if decision not in {"approved", "denied", "needs-more-info"}:
        return {"ok": False, "findings": [{"code": "MERGE_REVIEW_DECISION_INVALID", "detail": f"Unsupported merge review decision: {decision}"}]}
    path = REPO_ROOT / target
    if not path.exists():
        return {"ok": False, "findings": [{"code": "MERGE_PROPOSAL_NOT_FOUND", "detail": f"Merge proposal not found: {target}"}]}
    current = path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(current)
    if str(frontmatter.get("status", "unknown")) != "proposed":
        return {"ok": False, "findings": [{"code": "MERGE_PROPOSAL_STATE_INVALID", "detail": f"Merge proposal `{target}` is not in proposed state"}]}
    record_approval(f"merge_{_slug(target)}_{_stamp()}", decision, actor, reason, target)
    ref_target = str(frontmatter.get("ref-target", ""))
    count = int(str(frontmatter.get("entity-count", "0")) or 0)
    follow_up_target = None
    follow_up_result: dict[str, Any] = {"ok": True, "artifacts": []}
    if decision == "approved":
        follow_up_target = merge_follow_up_target(target)
        follow_up_result = write_text(
            follow_up_target,
            render_merge_follow_up(
                target,
                ref_target,
                count,
                actor,
                reason,
                suggest_merge_target(ref_target),
            ),
            actor="system",
            endpoint="merge-review",
            reason=f"merge follow up for {target}",
        )
    updated = render_reviewed_merge_proposal(current, decision, actor, reason, follow_up_target=follow_up_target)
    proposal_result = write_text(target, updated, actor="system", endpoint="merge-review", reason=f"merge proposal {decision}")
    append_event(
        EventRecord(
            source="vela",
            endpoint="merge-review",
            actor=actor,
            target=target,
            status="committed" if proposal_result["ok"] and follow_up_result["ok"] else "blocked",
            reason=reason,
            artifacts=[
                target,
                *proposal_result.get("artifacts", [target]),
                *([follow_up_target] if follow_up_target and follow_up_result["ok"] else []),
                *follow_up_result.get("artifacts", []),
            ],
            validation_summary={"decision": decision, "ref_target": ref_target, "follow_up_target": follow_up_target},
        )
    )
    return {
        "ok": proposal_result["ok"] and follow_up_result["ok"],
        "target": target,
        "decision": decision,
        "follow_up_target": follow_up_target,
        "suggested_target": suggest_merge_target(ref_target) if follow_up_target else None,
        "findings": proposal_result.get("findings", []) + follow_up_result.get("findings", []),
    }


def apply_merge_follow_up(target: str, actor: str, reason: str) -> dict[str, Any]:
    path = REPO_ROOT / target
    if not path.exists():
        return {"ok": False, "findings": [{"code": "MERGE_FOLLOW_UP_NOT_FOUND", "detail": f"Merge follow up not found: {target}"}]}
    current = path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(current)
    status = str(frontmatter.get("status", "unknown"))
    if status == "applied":
        return {
            "ok": True,
            "target": target,
            "execution_target": str(frontmatter.get("suggested-target", "")),
            "findings": [],
        }
    if actor not in {"human", "system"}:
        return {"ok": False, "findings": [{"code": "MERGE_FOLLOW_UP_ACTOR_NOT_ALLOWED", "detail": f"Actor `{actor}` cannot apply merge follow ups"}]}
    if status != "proposed":
        return {"ok": False, "findings": [{"code": "MERGE_FOLLOW_UP_STATE_INVALID", "detail": f"Merge follow up `{target}` is not in proposed state"}]}

    ref_target = str(frontmatter.get("ref-target", ""))
    execution_target = suggest_merge_target(ref_target)
    candidate = next((item for item in detect_merge_candidates() if item.ref_target == ref_target), None)
    owners = list(candidate.owners) if candidate else []
    execution_content = render_merge_spawned_sot(execution_target, ref_target, owners)
    execution_result = write_text(
        execution_target,
        execution_content,
        actor=actor,
        endpoint="merge-follow-up-apply",
        reason=f"execute merge follow up {target}",
    )
    owner_results: list[dict[str, Any]] = []
    for owner in owners:
        owner_path = REPO_ROOT / owner
        if not owner_path.exists():
            continue
        updated_owner = replace_ref_with_sot_pointer(owner_path.read_text(encoding="utf-8"), ref_target, execution_target)
        owner_results.append(
            write_text(
                owner,
                updated_owner,
                actor=actor,
                endpoint="merge-follow-up-apply",
                reason=f"repoint merged subject from {ref_target} to {execution_target}",
            )
        )
    follow_up_result = write_text(
        target,
        render_applied_merge_follow_up(current, execution_target, owners),
        actor=actor,
        endpoint="merge-follow-up-apply",
        reason=f"mark merge follow up applied {target}",
    )
    ok = execution_result["ok"] and follow_up_result["ok"] and all(item["ok"] for item in owner_results)
    append_event(
        EventRecord(
            source="vela",
            endpoint="merge-follow-up-apply",
            actor=actor,
            target=target,
            status="committed" if ok else "blocked",
            reason=reason,
            artifacts=[
                target,
                execution_target,
                *owners,
            ],
            validation_summary={"ref_target": ref_target, "execution_target": execution_target, "owner_count": len(owners)},
        )
    )
    findings: list[dict[str, Any]] = []
    findings.extend(execution_result.get("findings", []))
    findings.extend(follow_up_result.get("findings", []))
    for item in owner_results:
        findings.extend(item.get("findings", []))
    return {
        "ok": ok,
        "target": target,
        "execution_target": execution_target,
        "owners": owners,
        "findings": findings,
    }


def review_dreamer_proposal(target: str, decision: str, actor: str, reason: str) -> dict[str, Any]:
    path = REPO_ROOT / target
    if not path.exists():
        return {"ok": False, "findings": [{"code": "DREAMER_PROPOSAL_NOT_FOUND", "detail": f"Dreamer proposal not found: {target}"}]}
    current = path.read_text(encoding="utf-8")
    current_status = str(_parse_frontmatter(current).get("status", "unknown"))
    review_findings = validate_dreamer_review_payload(current_status, decision).get("findings", [])
    if review_findings:
        return {"ok": False, "findings": review_findings}
    record_approval(f"dreamer_{_slug(target)}_{_stamp()}", decision, actor, reason, target)
    created = datetime.now(timezone.utc).date().isoformat()
    review_plan_payload = plan_dreamer_review_payload(
        target,
        current,
        decision,
        actor,
        reason,
        created,
    )
    if not review_plan_payload.get("ok"):
        return {"ok": False, "findings": review_plan_payload.get("findings", [])}
    review_plan = review_plan_payload.get("plan") or {}
    follow_up = None
    if review_plan.get("follow_up_target"):
        follow_up = {
            "target": str(review_plan.get("follow_up_target", "")),
            "kind": str(review_plan.get("follow_up_kind", "")),
            "content": str(review_plan.get("follow_up_content", "")),
        }
    updated = str(review_plan.get("updated_content", current))
    result = write_text(target, updated, actor="system", endpoint="dreamer-review", reason=f"dreamer proposal {decision}")
    follow_up_result = {"ok": True, "target": None, "kind": None}
    if result["ok"] and follow_up:
        follow_up_result = write_text(
            follow_up["target"],
            follow_up["content"],
            actor="system",
            endpoint="dreamer-review",
            reason=f"dreamer follow up for {target}",
        )
    append_event(
        EventRecord(
            source="vela",
            endpoint="dreamer-review",
            actor=actor,
            target=target,
            status="committed" if result["ok"] and follow_up_result["ok"] else "blocked",
            reason=reason,
            artifacts=[
                target,
                *result.get("artifacts", [target]),
                *([follow_up["target"]] if follow_up and follow_up_result["ok"] else []),
                *follow_up_result.get("artifacts", []),
            ],
            validation_summary={"decision": decision, "follow_up_kind": follow_up["kind"] if follow_up else None},
        )
    )
    return {
        "ok": result["ok"] and follow_up_result["ok"],
        "target": target,
        "decision": decision,
        "follow_up_target": follow_up["target"] if follow_up else None,
        "follow_up_kind": follow_up["kind"] if follow_up else None,
        "findings": result.get("findings", []) + follow_up_result.get("findings", []),
    }


def apply_dreamer_follow_up(target: str, actor: str, reason: str) -> dict[str, Any]:
    path = REPO_ROOT / target
    if not path.exists():
        return {"ok": False, "findings": [{"code": "DREAMER_FOLLOW_UP_NOT_FOUND", "detail": f"Dreamer follow up not found: {target}"}]}

    current = path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(current)
    status = str(frontmatter.get("status", "unknown"))
    apply_findings = validate_dreamer_follow_up_apply_payload(status, actor).get("findings", [])
    if apply_findings:
        append_event(
            EventRecord(
                source="vela",
                endpoint="dreamer-follow-up-apply",
                actor=actor,
                target=target,
                status="blocked",
                reason=apply_findings[0]["detail"],
                artifacts=[target],
                validation_summary={"reason": reason},
            )
        )
        return {"ok": False, "findings": apply_findings}
    if status == "applied":
        follow_up_payload = inspect_dreamer_follow_up_payload(current)
        return {
            "ok": True,
            "target": target,
            "execution_target": follow_up_payload.get("execution_target"),
            "kind": str(follow_up_payload.get("kind", "")),
            "findings": [],
        }

    created = datetime.now(timezone.utc).date().isoformat()
    apply_plan_payload = plan_dreamer_follow_up_apply_payload(
        target,
        current,
        actor,
        reason,
        created,
    )
    if not apply_plan_payload.get("ok"):
        return {"ok": False, "findings": apply_plan_payload.get("findings", [])}
    apply_plan = apply_plan_payload.get("plan") or {}
    kind = str(apply_plan.get("kind", ""))
    execution = {
        "target": str(apply_plan.get("execution_target", "")),
        "content": str(apply_plan.get("execution_content", "")),
    }
    if bool(apply_plan.get("already_applied")):
        return {
            "ok": True,
            "target": target,
            "execution_target": apply_plan.get("execution_target"),
            "kind": kind,
            "findings": [],
        }
    execution_result = write_text(
        execution["target"],
        execution["content"],
        actor=actor,
        endpoint="dreamer-follow-up-apply",
        reason=f"execute dreamer follow up {target}",
    )
    if not execution_result["ok"]:
        return {"ok": False, "findings": execution_result.get("findings", [])}

    registry_result = _register_dreamer_action(
        follow_up_target=target,
        execution_target=execution["target"],
        kind=kind,
        pattern_reason=str(inspect_dreamer_follow_up_payload(current).get("reason", "")),
        actor=actor,
        execution_reason=reason,
    )

    updated = str(apply_plan.get("updated_follow_up_content", current))
    follow_up_result = write_text(
        target,
        updated,
        actor=actor,
        endpoint="dreamer-follow-up-apply",
        reason=f"mark dreamer follow up applied {target}",
    )
    append_event(
        EventRecord(
            source="vela",
            endpoint="dreamer-follow-up-apply",
            actor=actor,
            target=target,
            status="applied" if execution_result["ok"] and follow_up_result["ok"] else "blocked",
            reason=reason,
            artifacts=[
                target,
                execution["target"],
                registry_result["target"],
                *execution_result.get("artifacts", [execution["target"]]),
                *follow_up_result.get("artifacts", [target]),
            ],
            validation_summary={"kind": kind, "execution_target": execution["target"], "registry_target": registry_result["target"]},
        )
    )
    return {
        "ok": execution_result["ok"] and follow_up_result["ok"] and registry_result["ok"],
        "target": target,
        "execution_target": execution["target"],
        "registry_target": registry_result["target"],
        "kind": kind,
        "findings": execution_result.get("findings", []) + follow_up_result.get("findings", []) + registry_result.get("findings", []),
    }


def _patched_targets() -> list[str]:
    if not PATCH_LOG_PATH.exists():
        return []
    payload = extract_patch_targets_payload(PATCH_LOG_PATH.read_text(encoding="utf-8"))
    return [str(item.get("path", "")) for item in payload.get("items", []) if str(item.get("path", ""))]


def _growth_candidates() -> list[dict[str, Any]]:
    payload = list_growth_targets_payload()
    candidates: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        path = str(item.get("path", ""))
        assessment = assess_growth(path)
        if assessment.stage != "flat":
            candidates.append(
                {
                    "target": path,
                    "stage": assessment.stage,
                    "inventory_role": assessment.inventory_role,
                    "reason": assessment.reason,
                }
            )
    return candidates


def _write_merge_proposals(requested_by: str) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for candidate in detect_merge_candidates():
        target = merge_proposal_target(candidate)
        content = render_merge_proposal(candidate)
        result = write_text(target, content, actor="grower", endpoint="merge-proposal", reason="merge before spawn")
        proposals.append(
            {
                "target": target,
                "ref_target": candidate.ref_target,
                "count": candidate.count,
                "ok": result["ok"],
                "requested_by": requested_by,
            }
        )
    return proposals


def _blocked_items() -> list[dict[str, str]]:
    if not EVENT_LOG_PATH.exists():
        return []
    payload = extract_blocked_items_payload(EVENT_LOG_PATH.read_text(encoding="utf-8"))
    return list(payload.get("items", []))


def _dreamer_patterns(dreamer_proposals: list[dict[str, Any]]) -> dict[str, int]:
    return {str(item["reason"]): int(item["count"]) for item in dreamer_proposals}


def _write_dreamer_proposals(
    stamp: str,
    requested_by: str,
    blocked_items: list[dict[str, str]],
) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    plan_payload = plan_dreamer_proposals_payload(stamp, blocked_items)
    for item in plan_payload.get("items", []):
        reason = str(item.get("reason", ""))
        count = int(item.get("count", 0))
        target = str(item.get("target", ""))
        if not target:
            continue
        content = _render_dreamer_proposal(stamp, requested_by, reason, count, blocked_items)
        result = write_text(target, content, actor="reflector", endpoint="night-cycle", reason="dreamer proposal")
        proposals.append(
            {
                "target": target,
                "reason": reason,
                "count": count,
                "ok": result["ok"],
            }
        )
    return proposals


def _render_patrol_report(
    stamp: str,
    requested_by: str,
    checked: list[dict[str, Any]],
    structural_flags: list[dict[str, Any]],
) -> str:
    rendered = render_warden_patrol_report_payload(
        stamp,
        requested_by,
        [item["target"] for item in checked],
        [item["target"] for item in structural_flags],
    )
    if not rendered.get("ok"):
        raise ValueError(f"Failed to render patrol report: {rendered.get('findings', [])}")
    return str(rendered["content"])


def _render_night_report(
    stamp: str,
    requested_by: str,
    patrol: dict[str, Any],
    growth_candidates: list[dict[str, Any]],
    dreamer_patterns: dict[str, int],
    blocked_items: list[dict[str, str]],
    dreamer_report_target: str,
    dreamer_proposals: list[dict[str, Any]],
) -> str:
    rendered = render_dc_night_report_payload(
        stamp,
        requested_by,
        str(patrol.get("report_target", "")),
        int(patrol.get("files_checked", 0)),
        len(patrol.get("structural_flags", [])),
        growth_candidates,
        dreamer_patterns,
        blocked_items,
        dreamer_report_target,
        dreamer_proposals,
    )
    if not rendered.get("ok"):
        raise ValueError(f"Failed to render DC night report: {rendered.get('findings', [])}")
    return str(rendered["content"])


def _render_dreamer_report(
    stamp: str,
    requested_by: str,
    dreamer_patterns: dict[str, int],
    blocked_items: list[dict[str, str]],
    dreamer_proposals: list[dict[str, Any]],
) -> str:
    rendered = render_dreamer_pattern_report_payload(
        stamp,
        requested_by,
        dreamer_patterns,
        blocked_items,
        dreamer_proposals,
    )
    if not rendered.get("ok"):
        raise ValueError(f"Failed to render Dreamer pattern report: {rendered.get('findings', [])}")
    return str(rendered["content"])


def _render_dreamer_proposal(
    stamp: str,
    requested_by: str,
    reason: str,
    count: int,
    blocked_items: list[dict[str, str]],
) -> str:
    created = datetime.now(timezone.utc).date().isoformat()
    rendered = render_dreamer_proposal_payload(
        created,
        stamp,
        requested_by,
        reason,
        count,
        blocked_items,
    )
    return str(rendered["content"])


def _slug(value: str) -> str:
    return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else "-" for ch in value).split("-") if part) or "pattern"


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---\n", 2)
    if len(parts) != 3:
        return {}
    data: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def _load_dreamer_actions() -> dict[str, Any]:
    return load_dreamer_actions()


def _register_dreamer_action(
    *,
    follow_up_target: str,
    execution_target: str,
    kind: str,
    pattern_reason: str,
    actor: str,
    execution_reason: str,
) -> dict[str, Any]:
    kind_payload = inspect_dreamer_follow_up_kind_payload(kind)
    mode = str(kind_payload.get("registry_mode", "workflow"))
    result = register_dreamer_action_runtime(
        kind=mode,
        follow_up_target=follow_up_target,
        execution_target=execution_target,
        pattern_reason=pattern_reason,
        actor=actor,
        execution_reason=execution_reason,
    )
    return {
        "ok": result["ok"],
        "target": str(DREAMER_ACTIONS_PATH.relative_to(REPO_ROOT)),
        "findings": result.get("findings", []),
    }


def _operation_lock_path(name: str) -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    return QUEUE_DIR / f"operation-{name}.lock"


def _acquire_operation_lock(name: str, requested_by: str, started_at: str) -> dict[str, Any]:
    lock_path = _operation_lock_path(name)
    if lock_path.exists():
        findings = validate_operation_lock_payload(lock_path.read_text(encoding="utf-8"), name).get("findings", [])
        return {
            "ok": False,
            "code": "OPERATION_ALREADY_RUNNING",
            "detail": f"Operation `{name}` is already running.",
            "target": str(lock_path.relative_to(REPO_ROOT)),
            "findings": findings,
        }
    current_state = "{}"
    if OPERATIONS_STATE_PATH.exists():
        current_state = OPERATIONS_STATE_PATH.read_text(encoding="utf-8")
    payload = plan_operation_start_payload(current_state, name, requested_by, started_at)
    plan = payload.get("plan")
    findings = payload.get("findings", [])
    if not payload.get("ok") or not plan:
        return {
            "ok": False,
            "code": "OPERATION_START_REJECTED",
            "detail": findings[0]["detail"] if findings else f"Operation `{name}` could not start.",
            "target": str(lock_path.relative_to(REPO_ROOT)),
            "findings": findings,
        }
    _write_operations_state_json(str(plan["state_json"]))
    lock_path.write_text(str(plan["lock_content"]), encoding="utf-8")
    return {"ok": True, "target": str(lock_path.relative_to(REPO_ROOT))}


def _release_operation_lock(name: str) -> None:
    lock_path = _operation_lock_path(name)
    if lock_path.exists():
        lock_path.unlink()


def _default_operations_state() -> dict[str, Any]:
    return parse_operations_state_payload("{}").get("state", {})


def _load_operations_state() -> dict[str, Any]:
    if not OPERATIONS_STATE_PATH.exists():
        return _default_operations_state()
    payload = parse_operations_state_payload(OPERATIONS_STATE_PATH.read_text(encoding="utf-8"))
    return payload.get("state", _default_operations_state())


def _write_operations_state(state: dict[str, Any]) -> None:
    OPERATIONS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = parse_operations_state_payload(json.dumps(state, indent=2))
    OPERATIONS_STATE_PATH.write_text(json.dumps(payload.get("state", _default_operations_state()), indent=2), encoding="utf-8")


def _write_operations_state_json(state_json: str) -> None:
    OPERATIONS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = parse_operations_state_payload(state_json)
    OPERATIONS_STATE_PATH.write_text(
        json.dumps(payload.get("state", _default_operations_state()), indent=2),
        encoding="utf-8",
    )


def _update_operation_state(
    name: str,
    *,
    status: str,
    requested_by: str,
    started_at: str | None = None,
    completed_at: str | None = None,
    last_report_target: str | None = None,
    last_error: str | None = None,
    increment_runs: bool = False,
    release_lock: bool = False,
) -> None:
    current_state = "{}"
    if OPERATIONS_STATE_PATH.exists():
        current_state = OPERATIONS_STATE_PATH.read_text(encoding="utf-8")
    payload = plan_operation_state_update_payload(
        current_state,
        name,
        status,
        requested_by,
        started_at=started_at or "",
        completed_at=completed_at or "",
        last_report_target=last_report_target or "",
        last_error=last_error or "",
        increment_runs=increment_runs,
        release_lock=release_lock,
    )
    plan = payload.get("plan")
    if not payload.get("ok") or not plan:
        return
    _write_operations_state_json(str(plan["state_json"]))
    if bool(plan.get("release_lock")):
        _release_operation_lock(name)


def _run_scheduler(name: str, *, requested_by: str, interval_seconds: int, max_runs: int) -> dict[str, Any]:
    current_state = "{}"
    if OPERATIONS_STATE_PATH.exists():
        current_state = OPERATIONS_STATE_PATH.read_text(encoding="utf-8")
    schedule_plan_payload = plan_scheduler_run_payload(
        current_state,
        name,
        requested_by,
        interval_seconds,
        max_runs,
    )
    schedule_plan = schedule_plan_payload.get("plan")
    if not schedule_plan_payload.get("ok") or not schedule_plan:
        return {
            "ok": False,
            "operation": name,
            "interval_seconds": interval_seconds,
            "runs_attempted": 0,
            "runs": [],
            "state": operations_state().get(name, {}),
            "findings": schedule_plan_payload.get("findings", []),
        }
    runs: list[dict[str, Any]] = []
    executed = 0
    effective_interval = int(schedule_plan["interval_seconds"])
    effective_max_runs = int(schedule_plan["max_runs"])
    unbounded = bool(schedule_plan["unbounded"])
    while unbounded or executed < effective_max_runs:
        if name == "patrol":
            result = run_warden_patrol(requested_by=requested_by)
        else:
            result = run_night_cycle(requested_by=requested_by)
        runs.append(result)
        executed += 1
        if not result.get("ok", False):
            break
        if not unbounded and executed >= effective_max_runs:
            break
        time.sleep(effective_interval)
    return {
        "ok": all(item.get("ok", False) for item in runs),
        "operation": name,
        "interval_seconds": effective_interval,
        "runs_attempted": executed,
        "runs": runs,
        "state": operations_state().get(name, {}),
    }


def operations_state() -> dict[str, Any]:
    return _load_operations_state()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
