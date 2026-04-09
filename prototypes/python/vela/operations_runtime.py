from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .governance import append_event, validate_target, write_text
from .growth import assess_growth
from .models import EventRecord
from .paths import EVENT_LOG_PATH, PATCH_LOG_PATH, REFS_DIR, REPO_ROOT
from .rust_bridge import matrix_inventory_payload


def run_warden_patrol(requested_by: str = "system") -> dict[str, Any]:
    targets = _patched_targets()
    checked: list[dict[str, Any]] = []
    structural_flags: list[dict[str, Any]] = []
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


def run_night_cycle(requested_by: str = "system") -> dict[str, Any]:
    patrol = run_warden_patrol(requested_by=requested_by)
    growth_candidates = _growth_candidates()
    dreamer_patterns = _dreamer_patterns()
    stamp = _stamp()
    report_target = f"knowledge/ARTIFACTS/refs/DC-Night-Report-{stamp}.md"
    report = _render_night_report(stamp, requested_by, patrol, growth_candidates, dreamer_patterns)
    result = write_text(report_target, report, actor="system", endpoint="night-cycle", reason="dc night cycle report")
    append_event(
        EventRecord(
            source="vela",
            endpoint="night-cycle",
            actor="dc",
            target=report_target,
            status="committed" if result["ok"] else "blocked",
            reason="dc night cycle executed",
            artifacts=result.get("artifacts", [report_target]),
            validation_summary={
                "requested_by": requested_by,
                "growth_candidates": len(growth_candidates),
                "dreamer_patterns": dreamer_patterns,
                "patrol_report": patrol.get("report_target", ""),
            },
        )
    )
    return {
        "ok": result["ok"],
        "report_target": report_target,
        "patrol": patrol,
        "growth_candidates": growth_candidates,
        "dreamer_patterns": dreamer_patterns,
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


def _dreamer_patterns() -> dict[str, int]:
    if not EVENT_LOG_PATH.exists():
        return {}
    counts: Counter[str] = Counter()
    for line in EVENT_LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("status") == "blocked":
            counts[str(record.get("reason", "blocked"))] += 1
    return dict(counts)


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
) -> str:
    growth_lines = "\n".join(
        f"- `{item['target']}` -> `{item['stage']}` ({item['inventory_role']})"
        for item in growth_candidates
    ) or "- No active growth candidates."
    pattern_lines = "\n".join(
        f"- `{reason}` -> {count}"
        for reason, count in sorted(dreamer_patterns.items())
    ) or "- No blocked-pattern signals recorded."
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
        f"{pattern_lines}\n\n"
        "## Blocked (Needs Dario)\n\n"
        "- Spawn recommendations and constitutional rule changes remain human-gated.\n"
    )


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
