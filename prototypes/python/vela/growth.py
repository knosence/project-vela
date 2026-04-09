from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import REPO_ROOT
from .rust_bridge import matrix_inventory_payload


@dataclass
class GrowthAssessment:
    stage: str
    reason: str
    signals: dict[str, Any]
    inventory_role: str = "branch-sot"

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "reason": self.reason,
            "signals": self.signals,
            "inventory_role": self.inventory_role,
        }


def assess_growth(target: str) -> GrowthAssessment:
    inventory_role = _inventory_role_for_target(target)
    path = REPO_ROOT / target
    if not path.exists():
        return GrowthAssessment(
            stage="flat",
            reason="Target does not exist yet, so no growth signal can be assessed.",
            signals={"exists": False},
            inventory_role=inventory_role,
        )

    text = path.read_text(encoding="utf-8")
    line_count = len(text.splitlines())
    dimension_entry_counts = _dimension_entry_counts(text)
    densest_dimension = max(dimension_entry_counts.values(), default=0)
    has_subgroups = bool(re.search(r"##\s[12-6][1-9]0\.", text))
    living_record_mentions = sum(text.count(marker) for marker in ["### Status", "### Decisions", "### Open Questions", "### Next Actions"])

    if inventory_role == "cornerstone":
        if line_count > 260 or densest_dimension >= 10:
            return GrowthAssessment(
                stage="spawn",
                reason="The cornerstone should shed heavy branch detail into governed child SoTs rather than continue accumulating root complexity.",
                signals={
                    "line_count": line_count,
                    "densest_dimension_entries": densest_dimension,
                    "has_subgroups": has_subgroups,
                },
                inventory_role=inventory_role,
            )
        return GrowthAssessment(
            stage="flat",
            reason="The cornerstone should stay as stable as possible until branch pressure clearly warrants a governed spawn.",
            signals={
                "line_count": line_count,
                "densest_dimension_entries": densest_dimension,
            },
            inventory_role=inventory_role,
        )

    if inventory_role == "dimension-hub":
        if has_subgroups or densest_dimension >= 8 or line_count > 220:
            return GrowthAssessment(
                stage="spawn",
                reason="A dimension hub should branch outward into child SoTs once one concern becomes dense enough to deserve its own governed home.",
                signals={
                    "line_count": line_count,
                    "densest_dimension_entries": densest_dimension,
                    "has_subgroups": has_subgroups,
                },
                inventory_role=inventory_role,
            )
        return GrowthAssessment(
            stage="flat",
            reason="The hub remains light enough to keep collecting branch pointers without further structural change.",
            signals={
                "line_count": line_count,
                "densest_dimension_entries": densest_dimension,
            },
            inventory_role=inventory_role,
        )

    if inventory_role == "agent-identity":
        if has_subgroups or densest_dimension >= 10 or line_count > 240:
            return GrowthAssessment(
                stage="reference-note",
                reason="Identity branches should prefer clarifying companion references before spawning new structure, unless sovereignty explicitly requires a branch split.",
                signals={
                    "line_count": line_count,
                    "densest_dimension_entries": densest_dimension,
                    "has_subgroups": has_subgroups,
                },
                inventory_role=inventory_role,
            )
        return GrowthAssessment(
            stage="flat",
            reason="The identity branch should remain compact until interpretation pressure justifies a governed reference note.",
            signals={
                "line_count": line_count,
                "densest_dimension_entries": densest_dimension,
            },
            inventory_role=inventory_role,
        )

    if has_subgroups and (line_count > 220 or densest_dimension >= 10):
        return GrowthAssessment(
            stage="reference-note",
            reason="The SoT already shows subgrouping and is getting heavy enough that extraction into a reference note is warranted.",
            signals={
                "line_count": line_count,
                "densest_dimension_entries": densest_dimension,
                "has_subgroups": has_subgroups,
            },
            inventory_role=inventory_role,
        )

    if line_count > 320 or (densest_dimension >= 12 and living_record_mentions >= 4):
        return GrowthAssessment(
            stage="spawn",
            reason="The content is heavy enough and operational enough that it likely deserves its own SoT rather than remaining a section or ref.",
            signals={
                "line_count": line_count,
                "densest_dimension_entries": densest_dimension,
                "living_record_markers": living_record_mentions,
            },
            inventory_role=inventory_role,
        )

    if densest_dimension >= 8:
        return GrowthAssessment(
            stage="fractal",
            reason="One dimension has become dense enough that grouping by sub-blocks would likely improve scanability.",
            signals={
                "line_count": line_count,
                "densest_dimension_entries": densest_dimension,
            },
            inventory_role=inventory_role,
        )

    return GrowthAssessment(
        stage="flat",
        reason="The current SoT remains readable enough to stay flat.",
        signals={
            "line_count": line_count,
            "densest_dimension_entries": densest_dimension,
        },
        inventory_role=inventory_role,
    )


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


def render_growth_proposal(route: str, target: str, assessment: GrowthAssessment) -> str:
    created = datetime.now(timezone.utc).date().isoformat()
    target_name = Path(target).stem
    parent_link = f"[[{target_name}]]"
    return (
        "---\n"
        "sot-type: proposal\n"
        f"created: {created}\n"
        f"last-rewritten: {created}\n"
        f'parent: "{parent_link}"\n'
        "domain: governance\n"
        "status: proposed\n"
        f'target: "{target}"\n'
        f'route: "{route}"\n'
        f'recommended-stage: "{assessment.stage}"\n'
        'tags: ["growth","proposal","matrix","governance"]\n'
        "---\n\n"
        "# Growth Proposal\n\n"
        "## This Proposal Records the Matrix Growth Assessment After the Main Task\n"
        f"Route `{route}` touched `{target}` and triggered a structural review.\n\n"
        "## This Proposal States the Recommended Growth Path and the Reason for It\n"
        f"Recommended stage: `{assessment.stage}`.\n\n"
        f"Reason: {assessment.reason}\n\n"
        "## This Proposal Records the Signals That Triggered the Recommendation\n"
        f"- signals: `{assessment.signals}`\n\n"
        "## This Proposal Records the Matrix Role of the Target Under Review\n"
        f"- inventory role: `{assessment.inventory_role}`\n\n"
        "## This Proposal Identifies the Artifact That Would Be Affected If Approved\n"
        f"- target: `{target}`\n"
        f"- parent: `{parent_link}`\n"
    )


def _inventory_role_for_target(target: str) -> str:
    payload = matrix_inventory_payload()
    for item in payload.get("entries", []):
        if str(item.get("path", "")) == target:
            return str(item.get("inventory_role", "branch-sot"))
    name = Path(target).name
    if name == "Cornerstone.Knosence-SoT.md":
        return "cornerstone"
    if name.startswith("WHO.") or "Identity-SoT" in name:
        return "agent-identity"
    if re.match(r"^\d{3}\.[A-Z]+\..+-SoT\.md$", name):
        return "dimension-hub"
    return "branch-sot"
