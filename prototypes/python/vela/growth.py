from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import REPO_ROOT


@dataclass
class GrowthAssessment:
    stage: str
    reason: str
    signals: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "reason": self.reason, "signals": self.signals}


def assess_growth(target: str) -> GrowthAssessment:
    path = REPO_ROOT / target
    if not path.exists():
        return GrowthAssessment(
            stage="flat",
            reason="Target does not exist yet, so no growth signal can be assessed.",
            signals={"exists": False},
        )

    text = path.read_text(encoding="utf-8")
    line_count = len(text.splitlines())
    dimension_entry_counts = _dimension_entry_counts(text)
    densest_dimension = max(dimension_entry_counts.values(), default=0)
    has_subgroups = bool(re.search(r"##\s[12-6][1-9]0\.", text))
    living_record_mentions = sum(text.count(marker) for marker in ["### Status", "### Decisions", "### Open Questions", "### Next Actions"])

    if has_subgroups and (line_count > 220 or densest_dimension >= 10):
        return GrowthAssessment(
            stage="reference-note",
            reason="The SoT already shows subgrouping and is getting heavy enough that extraction into a reference note is warranted.",
            signals={
                "line_count": line_count,
                "densest_dimension_entries": densest_dimension,
                "has_subgroups": has_subgroups,
            },
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
        )

    if densest_dimension >= 8:
        return GrowthAssessment(
            stage="fractal",
            reason="One dimension has become dense enough that grouping by sub-blocks would likely improve scanability.",
            signals={
                "line_count": line_count,
                "densest_dimension_entries": densest_dimension,
            },
        )

    return GrowthAssessment(
        stage="flat",
        reason="The current SoT remains readable enough to stay flat.",
        signals={
            "line_count": line_count,
            "densest_dimension_entries": densest_dimension,
        },
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
        "## This Proposal Identifies the Artifact That Would Be Affected If Approved\n"
        f"- target: `{target}`\n"
        f"- parent: `{parent_link}`\n"
    )
