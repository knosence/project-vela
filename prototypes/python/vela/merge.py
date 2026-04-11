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
