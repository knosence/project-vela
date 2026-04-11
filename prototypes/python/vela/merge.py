from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import PROPOSALS_DIR, REPO_ROOT
from .rust_bridge import list_merge_candidates_payload

REF_LINK_PATTERN = re.compile(r"\[\[([^\]#]+-Ref)(?:#[^\]]+)?\]\]")


@dataclass
class MergeCandidate:
    ref_target: str
    owners: list[str]
    count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "ref_target": self.ref_target,
            "owners": self.owners,
            "count": self.count,
        }


def detect_merge_candidates() -> list[MergeCandidate]:
    payload = list_merge_candidates_payload()
    items = payload.get("items", [])
    return [
        MergeCandidate(
            ref_target=str(item.get("ref_target", "")),
            owners=[str(owner) for owner in item.get("owners", [])],
            count=int(item.get("count", 0)),
        )
        for item in items
    ]


def list_merge_proposals() -> dict[str, object]:
    items: list[dict[str, object]] = []
    for path in sorted(PROPOSALS_DIR.glob("Merge-Proposal.*.md")):
        relative_target = str(path.relative_to(REPO_ROOT))
        frontmatter = _parse_frontmatter(path.read_text(encoding="utf-8"))
        items.append(
            {
                "target": relative_target,
                "ref_target": str(frontmatter.get("ref-target", "")),
                "count": int(str(frontmatter.get("entity-count", "0")) or 0),
                "status": str(frontmatter.get("status", "unknown")),
            }
        )
    return {"ok": True, "items": items}


def list_merge_follow_ups() -> dict[str, object]:
    items: list[dict[str, object]] = []
    for path in sorted(PROPOSALS_DIR.glob("Merge-Follow-Up.*.md")):
        relative_target = str(path.relative_to(REPO_ROOT))
        frontmatter = _parse_frontmatter(path.read_text(encoding="utf-8"))
        items.append(
            {
                "target": relative_target,
                "proposal_target": str(frontmatter.get("parent", "")).strip("[]"),
                "ref_target": str(frontmatter.get("ref-target", "")),
                "status": str(frontmatter.get("status", "unknown")),
                "suggested_target": str(frontmatter.get("suggested-target", "")),
            }
        )
    return {"ok": True, "items": items}


def render_merge_proposal(candidate: MergeCandidate) -> str:
    created = datetime.now(timezone.utc).date().isoformat()
    owner_lines = "\n".join(f"- owner: `{owner}`" for owner in candidate.owners)
    return (
        "---\n"
        "sot-type: proposal\n"
        f"created: {created}\n"
        f"last-rewritten: {created}\n"
        f'parent: "[[{candidate.ref_target}]]"\n'
        "domain: governance\n"
        "status: proposed\n"
        f'ref-target: "{candidate.ref_target}"\n'
        f'entity-count: "{candidate.count}"\n'
        'tags: ["merge","proposal","matrix","governance"]\n'
        "---\n\n"
        "# Merge Proposal\n\n"
        "## This Proposal Records A Repeated Ref Subject That Should Become One Canonical Source Of Truth\n"
        f"`[[{candidate.ref_target}]]` now appears in `{candidate.count}` distinct entities.\n\n"
        "## This Proposal Applies Merge Before Spawn\n"
        "The subject should stop fragmenting as a repeated ref and earn one canonical SoT, with the prior entities keeping pointers instead of carrying the repeated subject indirectly.\n\n"
        "## This Proposal Records The Entities That Currently Carry The Shared Ref Subject\n"
        f"{owner_lines}\n\n"
        "## This Proposal Requests Governed Consolidation\n"
        f"- repeated ref: `[[{candidate.ref_target}]]`\n"
        f"- entity count: `{candidate.count}`\n"
        "- next step: identify the proper canonical SoT home and merge through governed review\n"
    )


def merge_proposal_target(candidate: MergeCandidate) -> str:
    created = datetime.now(timezone.utc).date().isoformat()
    stem = candidate.ref_target.replace(".md", "").replace("[[", "").replace("]]", "")
    safe = re.sub(r"[^A-Za-z0-9.-]+", "-", Path(stem).stem).strip("-") or "shared-ref"
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    return str((PROPOSALS_DIR / f"Merge-Proposal.{created}.{safe}.md").relative_to(REPO_ROOT))


def merge_follow_up_target(proposal_target: str) -> str:
    created = datetime.now(timezone.utc).date().isoformat()
    stem = Path(proposal_target).stem.replace("Merge-Proposal.", "")
    safe = re.sub(r"[^A-Za-z0-9.-]+", "-", stem).strip("-") or "shared-ref"
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    return str((PROPOSALS_DIR / f"Merge-Follow-Up.{created}.{safe}.md").relative_to(REPO_ROOT))


def render_reviewed_merge_proposal(
    proposal_text: str,
    decision: str,
    actor: str,
    reason: str,
    follow_up_target: str | None = None,
) -> str:
    updated = proposal_text
    updated = re.sub(r"(?m)^status:\s*\S+\s*$", f"status: {decision}", updated, count=1)
    outcome_lines = [
        "## Review Outcome",
        "",
        f"- decision: `{decision}`",
        f"- actor: `{actor}`",
        f"- reason: {reason or 'No reason recorded.'}",
    ]
    if follow_up_target:
        outcome_lines.append(f"- follow-up: `[[{Path(follow_up_target).name}]]`")
    return updated.rstrip() + "\n\n" + "\n".join(outcome_lines) + "\n"


def render_merge_follow_up(
    proposal_target: str,
    ref_target: str,
    count: int,
    actor: str,
    reason: str,
    suggested_target: str,
) -> str:
    created = datetime.now(timezone.utc).date().isoformat()
    return (
        "---\n"
        "sot-type: proposal\n"
        f"created: {created}\n"
        f"last-rewritten: {created}\n"
        f'parent: "[[{Path(proposal_target).name}]]"\n'
        "domain: governance\n"
        "status: proposed\n"
        f'ref-target: "{ref_target}"\n'
        f'entity-count: "{count}"\n'
        f'suggested-target: "{suggested_target}"\n'
        'tags: ["merge","follow-up","matrix","governance"]\n'
        "---\n\n"
        "# Merge Follow Up\n\n"
        "## This Follow Up Reserves The Governed Consolidation Step\n"
        f"The repeated ref `[[{ref_target}]]` has been approved for merge review and now needs a canonical SoT home.\n\n"
        "## This Follow Up Records The Suggested Canonical Target\n"
        f"- suggested target: `[[{Path(suggested_target).name}]]`\n"
        f"- source proposal: `[[{Path(proposal_target).name}]]`\n"
        f"- repeated entity count: `{count}`\n\n"
        "## This Follow Up Records The Review Context\n"
        f"- reviewer: `{actor}`\n"
        f"- reason: {reason or 'No reason recorded.'}\n\n"
        "## This Follow Up Leaves Apply Work For Governed Execution\n"
        "- next step: create the canonical SoT at the suggested target, then repoint the prior entities to that SoT through governed mutation.\n"
    )


def suggest_merge_target(ref_target: str) -> str:
    name = Path(ref_target).name
    match = re.match(r"^([0-9a-z]{3})([a-z])?\.([A-Z-]+)\.(.+)-Ref\.md$", name)
    if not match:
        return ""
    numeric_id, _, _, subject = match.groups()
    hub_prefix = numeric_id[0]
    next_id = _next_available_direct_child_id(hub_prefix)
    context = {
        "1": "WHO",
        "2": "WHAT",
        "3": "WHERE",
        "4": "WHEN",
        "5": "HOW",
        "6": "WHY",
        "7": "ARCHIVE",
        "0": "INDEX",
    }.get(hub_prefix, "WHAT")
    subject = subject.replace("-Ref", "")
    return f"knowledge/{next_id}.{context}.{subject}-SoT.md"


def _next_available_direct_child_id(hub_prefix: str) -> str:
    used: set[str] = set()
    for path in (REPO_ROOT / "knowledge").glob("*.md"):
        match = re.match(r"^([0-9a-z]{3})\.", path.name)
        if not match:
            continue
        matrix_id = match.group(1)
        if len(matrix_id) == 3 and matrix_id[0] == hub_prefix and matrix_id[2] == "0" and matrix_id != f"{hub_prefix}00":
            used.add(matrix_id)
    for digit in "123456789abcdefghijklmnopqrstuvwxyz":
        candidate = f"{hub_prefix}{digit}0"
        if candidate not in used:
            return candidate
    return f"{hub_prefix}z0"


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
