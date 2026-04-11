from __future__ import annotations

import json
import re
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
    matrix_inventory_payload,
    parse_operations_state_payload,
    update_operations_state_payload,
    validate_operation_lock_payload,
    validate_operation_request_payload,
    validate_operation_transition_payload,
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
        dreamer_result = write_text(
            dreamer_report_target,
            dreamer_report,
            actor="reflector",
            endpoint="night-cycle",
            reason="dreamer pattern report",
        )
        report_target = f"knowledge/ARTIFACTS/refs/DC-Night-Report-{stamp}.md"
        report = _render_night_report(stamp, requested_by, patrol, growth_candidates, dreamer_patterns, blocked_items, dreamer_report_target, dreamer_proposals)
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
    items: list[dict[str, Any]] = []
    for path in sorted((REPO_ROOT / "knowledge/ARTIFACTS/proposals").glob("Dreamer-Proposal.*.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter = _parse_frontmatter(text)
        items.append(
            {
                "target": str(path.relative_to(REPO_ROOT)),
                "status": str(frontmatter.get("status", "unknown")),
                "created": str(frontmatter.get("created", "")),
                "reason": _proposal_reason(text),
            }
        )
    return {"ok": True, "items": items}


def list_dreamer_follow_ups() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for path in sorted((REPO_ROOT / "knowledge/ARTIFACTS/proposals").glob("Dreamer-Follow-Up.*.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter = _parse_frontmatter(text)
        items.append(
            {
                "target": str(path.relative_to(REPO_ROOT)),
                "status": str(frontmatter.get("status", "unknown")),
                "created": str(frontmatter.get("created", "")),
                "kind": _follow_up_kind(text),
                "reason": _follow_up_reason(text),
            }
        )
    return {"ok": True, "items": items}


def review_dreamer_proposal(target: str, decision: str, actor: str, reason: str) -> dict[str, Any]:
    path = REPO_ROOT / target
    if not path.exists():
        return {"ok": False, "findings": [{"code": "DREAMER_PROPOSAL_NOT_FOUND", "detail": f"Dreamer proposal not found: {target}"}]}
    if decision not in {"approved", "denied", "needs-more-info"}:
        return {"ok": False, "findings": [{"code": "DREAMER_REVIEW_DECISION_INVALID", "detail": f"Unsupported decision: {decision}"}]}

    record_approval(f"dreamer_{_slug(target)}_{_stamp()}", decision, actor, reason, target)
    current = path.read_text(encoding="utf-8")
    follow_up = _build_dreamer_follow_up(target, current, decision, actor)
    updated = _mark_dreamer_proposal_reviewed(current, decision, actor, reason, follow_up["target"] if follow_up else None)
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
    if actor not in {"human", "system"}:
        finding = {"code": "ROLE_ACTION_NOT_ALLOWED", "detail": f"Actor `{actor}` may not apply Dreamer follow ups."}
        append_event(
            EventRecord(
                source="vela",
                endpoint="dreamer-follow-up-apply",
                actor=actor,
                target=target,
                status="blocked",
                reason=finding["detail"],
                artifacts=[target],
                validation_summary={"reason": reason},
            )
        )
        return {"ok": False, "findings": [finding]}

    current = path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(current)
    status = str(frontmatter.get("status", "unknown"))
    if status == "applied":
        return {"ok": True, "target": target, "execution_target": _existing_execution_target(current), "kind": _follow_up_kind(current), "findings": []}
    if status != "proposed":
        return {"ok": False, "findings": [{"code": "DREAMER_FOLLOW_UP_STATUS_INVALID", "detail": f"Dreamer follow up is not executable from status `{status}`."}]}

    kind = _follow_up_kind(current)
    follow_up_reason = _follow_up_reason(current)
    execution = _build_follow_up_execution(target, kind, follow_up_reason, actor, reason)
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
        pattern_reason=follow_up_reason,
        actor=actor,
        execution_reason=reason,
    )

    updated = _mark_dreamer_follow_up_applied(current, actor, reason, execution["target"])
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
    checked_lines = "\n".join(f"- `{item['target']}`" for item in checked) or "- No patched targets were available."
    flag_lines = "\n".join(f"- `{item['target']}`" for item in structural_flags) or "- No structural flags."
    return (
        "# Warden Patrol Report\n\n"
        "## This Report Records the Latest Patrol Validation Pass Over Recent Day Shift Activity\n"
        f"Patrol `{stamp}` was requested by `{requested_by}` and validated the latest patched targets.\n\n"
        "## Checked Targets\n\n"
        f"{checked_lines}\n\n"
        "## Structural Flags\n\n"
        f"{flag_lines}\n\n"
        "## Cosmetic Fixes\n\n"
        "- No cosmetic fixes were applied in this skeleton patrol.\n"
    )


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
    growth_lines = "\n".join(
        f"- `{item['target']}` -> `{item['stage']}` ({item['inventory_role']})"
        for item in growth_candidates
    ) or "- No active growth candidates."
    pattern_lines = "\n".join(
        f"- `{reason}` -> {count}"
        for reason, count in sorted(dreamer_patterns.items())
    ) or "- No blocked-pattern signals recorded."
    blocked_lines = "\n".join(
        f"- `{item['target']}`\n  Attempted: `{item['endpoint']}` by `{item['actor']}`\n  Blocked because: {item['reason']}"
        for item in blocked_items[:5]
    ) or "- Spawn recommendations and constitutional rule changes remain human-gated."
    proposal_lines = "\n".join(
        f"- `[[{Path(item['target']).stem}]]` for `{item['reason']}` ({item['count']} strikes)"
        for item in dreamer_proposals
    ) or "- No Dreamer proposals opened this cycle."
    return (
        "# DC Night Report\n\n"
        "## This Report Records the Coordinated Night Cycle Across Patrol, Growth Review, and Pattern Review\n"
        f"Night cycle `{stamp}` was requested by `{requested_by}` and packaged the current operational state.\n\n"
        "## Warden Patrol Summary\n\n"
        f"- Patrol report: `[[{Path(patrol.get('report_target', '')).stem}]]`\n"
        f"- Files checked: {patrol.get('files_checked', 0)}\n"
        f"- Structural flags: {len(patrol.get('structural_flags', []))}\n\n"
        "## Grower Activity\n\n"
        f"{growth_lines}\n\n"
        "## Dreamer Activity\n\n"
        f"- Pattern report: `[[{Path(dreamer_report_target).stem}]]`\n"
        f"{pattern_lines}\n\n"
        "## Dreamer Proposals\n\n"
        f"{proposal_lines}\n\n"
        "## Blocked (Needs Dario)\n\n"
        f"{blocked_lines}\n"
    )


def _render_dreamer_report(
    stamp: str,
    requested_by: str,
    dreamer_patterns: dict[str, int],
    blocked_items: list[dict[str, str]],
    dreamer_proposals: list[dict[str, Any]],
) -> str:
    strike_lines = "\n".join(
        f"- `{reason}` -> {count} strikes"
        for reason, count in sorted(dreamer_patterns.items())
        if count >= 3
    ) or "- No 3-strike patterns detected."
    recent_lines = "\n".join(
        f"- `{item['reason']}` on `{item['target']}` via `{item['endpoint']}`"
        for item in blocked_items[:5]
    ) or "- No blocked items recorded."
    proposal_lines = "\n".join(
        f"- `[[{Path(item['target']).stem}]]` for `{item['reason']}`"
        for item in dreamer_proposals
    ) or "- No Dreamer proposals were created."
    return (
        "# Dreamer Pattern Report\n\n"
        "## This Report Records Repeated Blocked Patterns Worth Further Review\n"
        f"Dreamer review `{stamp}` was requested by `{requested_by}` and scanned recent blocked events.\n\n"
        "## Three Strike Patterns\n\n"
        f"{strike_lines}\n\n"
        "## Proposed Responses\n\n"
        f"{proposal_lines}\n\n"
        "## Recent Blocked Items\n\n"
        f"{recent_lines}\n"
    )


def _render_dreamer_proposal(
    stamp: str,
    requested_by: str,
    reason: str,
    count: int,
    blocked_items: list[dict[str, str]],
) -> str:
    matching = [item for item in blocked_items if item["reason"] == reason][:5]
    evidence_lines = "\n".join(
        f"- `{item['target']}` via `{item['endpoint']}` by `{item['actor']}`"
        for item in matching
    ) or "- No matching blocked items remained available."
    return (
        "---\n"
        "sot-type: proposal\n"
        f"created: {datetime.now(timezone.utc).date().isoformat()}\n"
        f"last-rewritten: {datetime.now(timezone.utc).date().isoformat()}\n"
        'parent: "[[100.WHO.Circle-SoT]]"\n'
        "domain: operations\n"
        "status: proposed\n"
        'tags: ["dreamer","proposal","night-cycle"]\n'
        "---\n\n"
        "# Dreamer Proposal\n\n"
        "## This Proposal Records a Repeated Night Cycle Failure Pattern That Merits Follow Up\n"
        f"Dreamer opened this proposal during `{stamp}` for `{requested_by}` after observing `{count}` repeated blocks.\n\n"
        "## Pattern\n\n"
        f"- reason: `{reason}`\n"
        f"- strikes: `{count}`\n\n"
        "## Evidence\n\n"
        f"{evidence_lines}\n\n"
        "## Proposed Response\n\n"
        f"- Review the validator or workflow path that is producing `{reason}`.\n"
        "- Decide whether the correct next step is a rule change, a workflow change, or a stricter refusal.\n"
    )


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


def _proposal_reason(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("- reason:"):
            return line.split(":", 1)[1].strip().strip("`")
    return ""


def _follow_up_kind(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("- kind:"):
            return line.split(":", 1)[1].strip().strip("`")
    return ""


def _follow_up_reason(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("- reason:"):
            return line.split(":", 1)[1].strip().strip("`")
    return ""


def _mark_dreamer_proposal_reviewed(text: str, decision: str, actor: str, reason: str, follow_up_target: str | None) -> str:
    status_map = {
        "approved": "approved",
        "denied": "denied",
        "needs-more-info": "needs-more-info",
    }
    updated = re.sub(r"^status:\s*\w[\w-]*$", f"status: {status_map[decision]}", text, count=1, flags=re.MULTILINE)
    review_section = (
        "\n## Review Outcome\n\n"
        f"- decision: `{decision}`\n"
        f"- actor: `{actor}`\n"
        f"- reason: {reason}\n"
    )
    if follow_up_target:
        review_section += f"- follow up: `[[{Path(follow_up_target).stem}]]`\n"
    if "## Review Outcome" in updated:
        updated = re.sub(r"\n## Review Outcome.*$", review_section, updated, flags=re.DOTALL)
    else:
        updated = updated.rstrip() + review_section
    return updated


def _build_dreamer_follow_up(target: str, proposal_text: str, decision: str, actor: str) -> dict[str, str] | None:
    if decision != "approved":
        return None
    reason = _proposal_reason(proposal_text)
    classification = _classify_dreamer_follow_up(reason)
    stem = Path(target).stem.replace("Dreamer-Proposal.", "Dreamer-Follow-Up.")
    follow_up_target = f"knowledge/ARTIFACTS/proposals/{stem}.md"
    return {
        "target": follow_up_target,
        "kind": classification,
        "content": _render_dreamer_follow_up(follow_up_target, target, reason, classification, actor),
    }


def _classify_dreamer_follow_up(reason: str) -> str:
    lowered = reason.lower()
    if any(token in lowered for token in ["validator", "validation", "rule", "frontmatter", "structure"]):
        return "validator-change"
    if any(token in lowered for token in ["workflow", "triage", "route", "pipeline", "queue"]):
        return "workflow-change"
    return "refusal-tightening"


def _render_dreamer_follow_up(
    follow_up_target: str,
    proposal_target: str,
    reason: str,
    classification: str,
    actor: str,
) -> str:
    created = datetime.now(timezone.utc).date().isoformat()
    return (
        "---\n"
        "sot-type: proposal\n"
        f"created: {created}\n"
        f"last-rewritten: {created}\n"
        f'parent: "[[{Path(proposal_target).stem}]]"\n'
        "domain: operations\n"
        "status: proposed\n"
        'tags: ["dreamer","follow-up","proposal"]\n'
        "---\n\n"
        "# Dreamer Follow Up\n\n"
        "## This Proposal Records the Concrete Follow Up Opened After an Approved Dreamer Review\n"
        f"Approved Dreamer proposal `[[{Path(proposal_target).stem}]]` opened this `{classification}` follow up.\n\n"
        "## Classification\n\n"
        f"- kind: `{classification}`\n"
        f"- reason: `{reason}`\n"
        f"- reviewed by: `{actor}`\n\n"
        "## Suggested Next Step\n\n"
        f"- Apply a targeted {classification} change and verify it against the repeated failure signal.\n"
    )


def _build_follow_up_execution(
    target: str,
    kind: str,
    follow_up_reason: str,
    actor: str,
    execution_reason: str,
) -> dict[str, str]:
    stem = Path(target).stem.replace("Dreamer-Follow-Up.", "Dreamer-Execution.")
    execution_target = f"knowledge/ARTIFACTS/refs/{stem}.md"
    created = datetime.now(timezone.utc).date().isoformat()
    queue_name = {
        "validator-change": "Validator-Change-Queue",
        "workflow-change": "Workflow-Change-Queue",
        "refusal-tightening": "Refusal-Tightening-Queue",
    }.get(kind, "Dreamer-Action-Queue")
    content = (
        "---\n"
        "sot-type: reference\n"
        f"created: {created}\n"
        f"last-rewritten: {created}\n"
        f'parent: "[[{Path(target).stem}]]"\n'
        "domain: operations\n"
        "status: active\n"
        'tags: ["dreamer","execution","operations"]\n'
        "---\n\n"
        "# Dreamer Execution\n\n"
        "## This Reference Records the Concrete Queue Item Opened from an Approved Dreamer Follow Up\n"
        f"Follow up `[[{Path(target).stem}]]` was executed by `{actor}` and opened a concrete `{kind}` queue item.\n\n"
        "## Classification\n\n"
        f"- kind: `{kind}`\n"
        f"- pattern: `{follow_up_reason}`\n"
        f"- queue: `[[{queue_name}]]`\n\n"
        "## Execution\n\n"
        f"- reason: {execution_reason}\n"
        "- next step: implement the queued change through the governed validation or workflow path.\n"
    )
    return {"target": execution_target, "content": content}


def _mark_dreamer_follow_up_applied(text: str, actor: str, reason: str, execution_target: str) -> str:
    updated = re.sub(r"^status:\s*\w[\w-]*$", "status: applied", text, count=1, flags=re.MULTILINE)
    execution_section = (
        "\n## Execution Outcome\n\n"
        "- decision: `applied`\n"
        f"- actor: `{actor}`\n"
        f"- reason: {reason}\n"
        f"- execution: `[[{Path(execution_target).stem}]]`\n"
    )
    if "## Execution Outcome" in updated:
        updated = re.sub(r"\n## Execution Outcome.*$", execution_section, updated, flags=re.DOTALL)
    else:
        updated = updated.rstrip() + execution_section
    return updated


def _existing_execution_target(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("- execution:"):
            return line.split("[[", 1)[1].split("]]", 1)[0]
    return None


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
    mode = {
        "validator-change": "validator",
        "workflow-change": "workflow",
        "refusal-tightening": "refusal",
    }.get(kind, "workflow")
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
