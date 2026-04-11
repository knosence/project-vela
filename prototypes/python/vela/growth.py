from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .rust_bridge import assess_growth_payload


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
    payload = assess_growth_payload(target)
    assessment = payload["assessment"]
    return GrowthAssessment(
        stage=assessment["stage"],
        reason=assessment["reason"],
        signals=assessment["signals"],
        inventory_role=assessment["inventory_role"],
    )


def render_growth_proposal(route: str, target: str, assessment: GrowthAssessment) -> str:
    created = datetime.now(timezone.utc).date().isoformat()
    target_name = Path(target).stem
    parent_link = f"[[{target_name}]]"
    subject_hint = "-".join(
        part
        for part in target_name.replace("_", "-").split("-")
        if part and part.lower() not in {"sot", "ref", "identity", "capabilities", "intent"}
    ) or target_name
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
        f'subject-hint: "{subject_hint}"\n'
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
