from __future__ import annotations

import re
from dataclasses import dataclass

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
