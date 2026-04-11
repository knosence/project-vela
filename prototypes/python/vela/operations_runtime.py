from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

from .dreamer_actions import load_dreamer_actions
from .dreamer_actions import register_dreamer_action as register_dreamer_action_runtime
from .governance import append_event, record_approval, validate_target, write_text
from .growth import assess_growth
from .models import EventRecord
from .paths import DREAMER_ACTIONS_PATH, EVENT_LOG_PATH, OPERATIONS_STATE_PATH, PATCH_LOG_PATH, QUEUE_DIR, REFS_DIR, REPO_ROOT
from .rust_bridge import (
    inspect_dreamer_follow_up_payload,
    inspect_dreamer_follow_up_kind_payload,
    inspect_dreamer_proposal_payload,
    list_dreamer_follow_ups_payload,
    list_dreamer_queue_payload,
    matrix_inventory_payload,
    plan_dreamer_follow_up_apply_payload,
    plan_dreamer_review_payload,
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
    update_operations_state_payload,
    validate_operation_lock_payload,
    validate_operation_request_payload,
    validate_operation_transition_payload,
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
        append_event(
            EventRecord(
                source="vela",
                endpoint="patrol",
                actor="warden",
                target="runtime/config/operations-state.json",
                status="blocked",
                reason=request_findings[0]["detail"],
                artifacts=["runtime/config/operations-state.json"],
                validation_summary={"requested_by": requested_by},
            )
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
        append_event(
            EventRecord(
                source="vela",
                endpoint="patrol",
                actor="warden",
                target=lock["target"],
                status="blocked",
                reason=lock["detail"],
                artifacts=[lock["target"]],
                validation_summary={"requested_by": requested_by},
            )
        )
        return {"ok": False, "report_target": "", "files_checked": 0, "structural_flags": [], "cosmetic_fixes": [], "findings": [lock]}
    _update_operation_state("patrol", status="running", requested_by=requested_by, started_at=started_at)
    targets = _patched_targets()
    checked: list[dict[str, Any]] = []
    structural_flags: list[dict[str, Any]] = []
    report_target = ""
    try:
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
        report_target = f"knowledge/ARTIFACTS/refs/Warden-Patrol-{stamp}.md"
        report = _render_patrol_report(stamp, requested_by, checked, structural_flags)
        report_findings = validate_warden_patrol_report_payload(report).get("findings", [])
        if report_findings:
            return {
                "ok": False,
                "report_target": report_target,
                "files_checked": len(checked),
                "structural_flags": structural_flags,
                "cosmetic_fixes": [],
                "findings": report_findings,
            }
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
        )
        append_event(
            EventRecord(
                source="vela",
                endpoint="patrol",
                actor="warden",
                target=report_target,
                status="committed" if result["ok"] else "blocked",
                reason="warden patrol executed",
                artifacts=result.get("artifacts", [report_target]),
                validation_summary={
                    "requested_by": requested_by,
                    "files_checked": len(checked),
                    "structural_flags": len(structural_flags),
                },
            )
        )
        return {
            "ok": result["ok"],
            "report_target": report_target,
            "files_checked": len(checked),
            "structural_flags": structural_flags,
            "cosmetic_fixes": [],
        }
    finally:
        _release_operation_lock("patrol")


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
        append_event(
            EventRecord(
                source="vela",
                endpoint="night-cycle",
                actor="dc",
                target="runtime/config/operations-state.json",
                status="blocked",
                reason=request_findings[0]["detail"],
                artifacts=["runtime/config/operations-state.json"],
                validation_summary={"requested_by": requested_by},
            )
        )
        return {
            "ok": False,
            "report_target": "",
            "dreamer_report_target": "",
            "patrol": {"ok": False},
            "growth_candidates": [],
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
        append_event(
            EventRecord(
                source="vela",
                endpoint="night-cycle",
                actor="dc",
                target=lock["target"],
                status="blocked",
                reason=lock["detail"],
                artifacts=[lock["target"]],
                validation_summary={"requested_by": requested_by},
            )
        )
        return {
            "ok": False,
            "report_target": "",
            "dreamer_report_target": "",
            "patrol": {"ok": False},
            "growth_candidates": [],
            "dreamer_patterns": {},
            "blocked_items": [],
            "dreamer_proposals": [],
            "findings": [lock],
        }
    _update_operation_state("night-cycle", status="running", requested_by=requested_by, started_at=started_at)
    report_target = ""
    dreamer_report_target = ""
    try:
        patrol = run_warden_patrol(requested_by=f"night-cycle:{requested_by}")
        if not patrol["ok"]:
            _update_operation_state(
                "night-cycle",
                status="blocked",
                requested_by=requested_by,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                last_error="night cycle could not acquire dependent patrol execution",
            )
            return {
                "ok": False,
                "report_target": "",
                "dreamer_report_target": "",
                "patrol": patrol,
                "growth_candidates": [],
                "dreamer_patterns": {},
                "blocked_items": [],
                "dreamer_proposals": [],
                "findings": patrol.get("findings", []),
            }
        growth_candidates = _growth_candidates()
        blocked_items = _blocked_items()
        dreamer_patterns = _dreamer_patterns(blocked_items)
        stamp = _stamp()
        dreamer_proposals = _write_dreamer_proposals(stamp, requested_by, dreamer_patterns, blocked_items)
        dreamer_report_target = f"knowledge/ARTIFACTS/refs/Dreamer-Pattern-Report-{stamp}.md"
        dreamer_report = _render_dreamer_report(stamp, requested_by, dreamer_patterns, blocked_items, dreamer_proposals)
        dreamer_report_findings = validate_dreamer_pattern_report_payload(dreamer_report).get("findings", [])
        if dreamer_report_findings:
            return {
                "ok": False,
                "report_target": "",
                "dreamer_report_target": dreamer_report_target,
                "patrol": patrol,
                "growth_candidates": growth_candidates,
                "dreamer_patterns": dreamer_patterns,
                "blocked_items": blocked_items,
                "dreamer_proposals": dreamer_proposals,
                "findings": dreamer_report_findings,
            }
        dreamer_result = write_text(
            dreamer_report_target,
            dreamer_report,
            actor="reflector",
            endpoint="night-cycle",
            reason="dreamer pattern report",
        )
        report_target = f"knowledge/ARTIFACTS/refs/DC-Night-Report-{stamp}.md"
        report = _render_night_report(stamp, requested_by, patrol, growth_candidates, dreamer_patterns, blocked_items, dreamer_report_target, dreamer_proposals)
        report_findings = validate_dc_night_report_payload(report).get("findings", [])
        if report_findings:
            return {
                "ok": False,
                "report_target": report_target,
                "dreamer_report_target": dreamer_report_target,
                "patrol": patrol,
                "growth_candidates": growth_candidates,
                "dreamer_patterns": dreamer_patterns,
                "blocked_items": blocked_items,
                "dreamer_proposals": dreamer_proposals,
                "findings": report_findings,
            }
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
        )
        append_event(
            EventRecord(
                source="vela",
                endpoint="night-cycle",
                actor="dc",
                target=report_target,
                status="committed" if result["ok"] else "blocked",
                reason="dc night cycle executed",
                artifacts=[
                    dreamer_report_target,
                    report_target,
                    *dreamer_result.get("artifacts", [dreamer_report_target]),
                    *result.get("artifacts", [report_target]),
                ],
                validation_summary={
                    "requested_by": requested_by,
                    "growth_candidates": len(growth_candidates),
                    "dreamer_patterns": dreamer_patterns,
                    "blocked_items": len(blocked_items),
                    "patrol_report": patrol.get("report_target", ""),
                    "dreamer_report": dreamer_report_target,
                    "dreamer_proposals": [item["target"] for item in dreamer_proposals],
                },
            )
        )
        return {
            "ok": result["ok"] and dreamer_result["ok"],
            "report_target": report_target,
            "dreamer_report_target": dreamer_report_target,
            "patrol": patrol,
            "growth_candidates": growth_candidates,
            "dreamer_patterns": dreamer_patterns,
            "blocked_items": blocked_items,
            "dreamer_proposals": dreamer_proposals,
        }
    finally:
        _release_operation_lock("night-cycle")


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


def list_dreamer_queue() -> dict[str, Any]:
    payload = list_dreamer_queue_payload()
    return {"ok": bool(payload.get("ok")), "items": list(payload.get("items", []))}


def list_dreamer_follow_ups() -> dict[str, Any]:
    payload = list_dreamer_follow_ups_payload()
    return {"ok": bool(payload.get("ok")), "items": list(payload.get("items", []))}


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
    targets: list[str] = []
    for line in PATCH_LOG_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("  TARGET: "):
            target = line.split(":", 1)[1].strip()
            if target not in targets:
                targets.append(target)
        if line.startswith("  DETAIL: Extracted into "):
            detail_target = line.split("Extracted into ", 1)[1].split(" ", 1)[0].strip()
            if detail_target not in targets:
                targets.append(detail_target)
    return targets


def _growth_candidates() -> list[dict[str, Any]]:
    inventory = matrix_inventory_payload()
    candidates: list[dict[str, Any]] = []
    for item in inventory.get("items", []):
        path = str(item.get("path", ""))
        role = str(item.get("inventory_role", ""))
        if role == "governed-reference" or path.startswith("knowledge/ARTIFACTS/"):
            continue
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


def _blocked_items() -> list[dict[str, str]]:
    if not EVENT_LOG_PATH.exists():
        return []
    items: list[dict[str, str]] = []
    for line in EVENT_LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("status") == "blocked":
            items.append(
                {
                    "target": str(record.get("target", "")),
                    "reason": str(record.get("reason", "blocked")),
                    "actor": str(record.get("actor", "")),
                    "endpoint": str(record.get("endpoint", "")),
                }
            )
    return items


def _dreamer_patterns(blocked_items: list[dict[str, str]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in blocked_items:
        counts[item["reason"]] += 1
    return dict(counts)


def _write_dreamer_proposals(
    stamp: str,
    requested_by: str,
    dreamer_patterns: dict[str, int],
    blocked_items: list[dict[str, str]],
) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for reason, count in sorted(dreamer_patterns.items()):
        if count < 3:
            continue
        slug = _slug(reason)
        target = f"knowledge/ARTIFACTS/proposals/Dreamer-Proposal.{stamp}.{slug}.md"
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
    lock_path.write_text(
        json.dumps({"name": name, "requested_by": requested_by, "started_at": started_at}, indent=2),
        encoding="utf-8",
    )
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
) -> None:
    current_state = "{}"
    current_status = "idle"
    if OPERATIONS_STATE_PATH.exists():
        current_state = OPERATIONS_STATE_PATH.read_text(encoding="utf-8")
        current_status = parse_operations_state_payload(current_state).get("state", {}).get(name, {}).get("status", "idle")
    transition = validate_operation_transition_payload(current_status, status)
    if transition.get("findings"):
        return
    payload = update_operations_state_payload(
        current_state,
        name,
        status,
        requested_by,
        started_at=started_at or "",
        completed_at=completed_at or "",
        last_report_target=last_report_target or "",
        last_error=last_error or "",
        increment_runs=increment_runs,
    )
    _write_operations_state(payload.get("state", _default_operations_state()))


def _run_scheduler(name: str, *, requested_by: str, interval_seconds: int, max_runs: int) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    executed = 0
    while max_runs <= 0 or executed < max_runs:
        if name == "patrol":
            result = run_warden_patrol(requested_by=requested_by)
        else:
            result = run_night_cycle(requested_by=requested_by)
        runs.append(result)
        executed += 1
        if not result.get("ok", False):
            break
        if max_runs > 0 and executed >= max_runs:
            break
        time.sleep(interval_seconds)
    return {
        "ok": all(item.get("ok", False) for item in runs),
        "operation": name,
        "interval_seconds": interval_seconds,
        "runs_attempted": executed,
        "runs": runs,
        "state": operations_state().get(name, {}),
    }


def operations_state() -> dict[str, Any]:
    return _load_operations_state()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
