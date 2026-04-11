from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .rust_bridge import assess_growth_payload, plan_growth_proposal_payload


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


def plan_growth_proposal(route: str, target: str, assessment: GrowthAssessment) -> dict[str, Any]:
    payload = plan_growth_proposal_payload(
        route,
        target,
        assessment.stage,
        assessment.inventory_role,
        assessment.reason,
        json.dumps(assessment.signals, sort_keys=True),
    )
    return dict(payload.get("plan") or {})


def render_growth_proposal(route: str, target: str, assessment: GrowthAssessment) -> str:
    return str(plan_growth_proposal(route, target, assessment).get("content", ""))
