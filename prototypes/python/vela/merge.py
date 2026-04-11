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


def render_merge_spawned_sot(target: str, ref_target: str, owners: list[str]) -> str:
    created = datetime.now(timezone.utc).date().isoformat()
    filename = Path(target).name
    subject = Path(target).stem.split(".", 2)[-1].removesuffix("-SoT").replace("-", " ")
    parent_link = _hub_parent_link_for_target(filename)
    owner_lines = "\n".join(f"- Source owner: [[{Path(owner).name}]]" for owner in owners) or "- Source owner: (no owners recorded)"
    return (
        "---\n"
        "sot-type: system\n"
        f"created: {created}\n"
        f"last-rewritten: {created}\n"
        f'parent: "{parent_link}"\n'
        "domain: merge\n"
        "status: active\n"
        'tags: ["merge","canonical","sot"]\n'
        "---\n\n"
        f"# {subject} Source of Truth\n\n"
        "## 000.Index\n\n"
        "### Subject Declaration\n\n"
        f"**Subject:** This SoT is the canonical home for `{subject}` after governed merge consolidation.\n"
        "**Type:** system\n"
        f"**Created:** {created}\n"
        f"**Parent:** {parent_link}\n\n"
        "### Links\n\n"
        f"- Parent: {parent_link}\n"
        "- Cornerstone: [[Cornerstone.Knosence-SoT]]\n"
        f"- Origin Ref: [[{Path(ref_target).name}]]\n"
        f"{owner_lines}\n\n"
        "### Inbox\n\n"
        "No pending items.\n\n"
        "### Status\n\n"
        f"- `{subject}` has been merged into one canonical SoT. ({created})\n"
        "  - Repeated refs across multiple entities triggered governed consolidation. [HUMAN]\n\n"
        "### Open Questions\n\n"
        f"- Which details from the prior owners should remain here as dense canonical content? ({created})\n"
        "  - The merged SoT should deepen directly rather than re-fragment into repeated refs. [HUMAN]\n\n"
        "### Next Actions\n\n"
        "- Consolidate the repeated subject here and keep the former owners as one-line pointers only. "
        f"({created})\n"
        "  - Merge before spawn wins once a subject repeats broadly enough. [HUMAN]\n\n"
        "### Decisions\n\n"
        f"- [{created}] Canonical merge SoT created from repeated ref `[[{Path(ref_target).name}]]`.\n\n"
        "### Block Map — Single Source\n\n"
        "| ID | Question | Dimension | This SoT's Name |\n"
        "|----|----------|-----------|-----------------|\n"
        "| 000 | — | Index | Index |\n"
        "| 100 | Who | Circle | Circle |\n"
        "| 200 | What | Domain | Domain |\n"
        "| 300 | Where | Terrain | Terrain |\n"
        "| 400 | When | Chronicle | Chronicle |\n"
        "| 500 | How | Method | Method |\n"
        "| 600 | Why/Not | Compass | Compass |\n"
        "| 700 | — | Archive | Archive |\n\n"
        "---\n\n"
        "## 100.WHO.Circle\n\n### Active\n\n"
        f"- `{subject}` is now treated as one governed subject rather than a repeated ref. ({created})\n"
        "  - The merge establishes one canonical identity for the subject inside this matrix. [HUMAN]\n\n"
        "### Inactive\n\n(No inactive entries.)\n\n---\n\n"
        "## 200.WHAT.Domain\n\n### Active\n\n"
        f"- This SoT is the canonical home for content previously referenced through `[[{Path(ref_target).name}]]`. ({created})\n"
        "  - Prior entities should now point here instead of carrying the repeated ref. [HUMAN]\n\n"
        "### Inactive\n\n(No inactive entries.)\n\n---\n\n"
        "## 300.WHERE.Terrain\n\n### Active\n\n"
        "- Canonical merged knowledge lives in the flat matrix root with position determined by ID, context, and suffix. "
        f"({created})\n"
        "  - The matrix stays flat while the numbering carries structure. [HUMAN]\n\n"
        "### Inactive\n\n(No inactive entries.)\n\n---\n\n"
        "## 400.WHEN.Chronicle\n\n### Active\n\n"
        f"- This subject became a canonical SoT through merge governance on {created}. ({created})\n"
        "  - The merge threshold was triggered by repeated references across multiple entities. [AGENT:gpt-5]\n\n"
        "### Inactive\n\n(No inactive entries.)\n\n---\n\n"
        "## 500.HOW.Method\n\n### Active\n\n"
        "- Future updates should be merged here directly unless the growth ladder later justifies fractal, ref, or spawn. "
        f"({created})\n"
        "  - Merge happens before new proliferation. [HUMAN]\n\n"
        "### Inactive\n\n(No inactive entries.)\n\n---\n\n"
        "## 600.WHY.Compass\n\n### Active\n\n"
        "- This SoT exists to prevent fragmentation and restore one canonical place to look. "
        f"({created})\n"
        "  - The matrix stays coherent when repeated subjects consolidate. [HUMAN]\n\n"
        "### Inactive\n\n(No inactive entries.)\n\n---\n\n"
        "## 700.Archive\n\n(No archived entries.)\n"
    )


def render_applied_merge_follow_up(follow_up_text: str, execution_target: str, owners: list[str]) -> str:
    updated = re.sub(r"(?m)^status:\s*\S+\s*$", "status: applied", follow_up_text, count=1)
    owner_lines = "\n".join(f"- repointed owner: `[[{Path(owner).name}]]`" for owner in owners) or "- repointed owner: (none)"
    return updated.rstrip() + (
        "\n\n## Execution Outcome\n\n"
        f"- canonical target: `[[{Path(execution_target).name}]]`\n"
        f"{owner_lines}\n"
    )


def suggest_merge_target(ref_target: str) -> str:
    name = Path(ref_target).name
    if not name.endswith(".md"):
        name = f"{name}.md"
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


def replace_ref_with_sot_pointer(text: str, ref_target: str, sot_target: str) -> str:
    ref_name = Path(ref_target).name
    sot_name = Path(sot_target).name
    return text.replace(f"[[{ref_name}]]", f"[[{sot_name}]]")


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


def _hub_parent_link_for_target(filename: str) -> str:
    hub_prefix = filename[0]
    mapping = {
        "1": "[[100.WHO.Circle-SoT#100.WHO.Circle]]",
        "2": "[[200.WHAT.Domain-SoT#200.WHAT.Domain]]",
        "3": "[[300.WHERE.Terrain-SoT#300.WHERE.Terrain]]",
        "4": "[[400.WHEN.Chronicle-SoT#400.WHEN.Chronicle]]",
        "5": "[[500.HOW.Method-SoT#500.HOW.Method]]",
        "6": "[[600.WHY.Compass-SoT#600.WHY.Compass]]",
        "7": "[[700.ARCHIVE.Archive-SoT#700.Archive]]",
    }
    return mapping.get(hub_prefix, "[[200.WHAT.Domain-SoT#200.WHAT.Domain]]")


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
