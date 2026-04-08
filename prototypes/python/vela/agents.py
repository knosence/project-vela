from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .governance import propose_growth, write_text
from .models import ValidationFinding


@dataclass
class PipelineResult:
    route: str
    plan: list[str]
    draft: str
    critique: list[str]
    findings: list[dict[str, Any]]
    committed: bool
    target: str


class Router:
    permissions = "read-only"

    def classify(self, task_type: str, target: str) -> str:
        if target.startswith("knowledge/cornerstone/"):
            return "sovereign-change"
        if task_type == "repo-release":
            return "repo-watch"
        if task_type == "validate":
            return "validation"
        return "standard"


class Planner:
    permissions = "read+propose"

    def plan(self, route: str, target: str) -> list[str]:
        base = [
            "draft useful first pass",
            "reflect on ambiguity and gaps",
            "validate policy, lineage, and structure",
            "commit only when allowed",
        ]
        if route == "repo-watch":
            return ["classify release", "summarize release", "assess breaking risk", "assess local relevance"] + base
        if route == "sovereign-change":
            return ["flag approval boundary"] + base
        return base


class Worker:
    permissions = "read+write-draft"

    def draft(self, title: str, body: str) -> str:
        return f"# {title}\n\n## This Draft Captures the First Useful Pass\n{body.strip()}\n"


class Reflector:
    permissions = "read+critique+propose"

    def critique(self, draft: str, route: str) -> list[str]:
        notes = []
        if "TODO" in draft:
            notes.append("Draft still contains unresolved TODO markers")
        if route == "repo-watch" and "breaking" not in draft.lower():
            notes.append("Release summary should state breaking-change risk explicitly")
        if not notes:
            notes.append("No blocking ambiguity detected")
        return notes


class Warden:
    permissions = "read+validate+block-allow"

    def validate(self, draft: str, target: str, approval_id: str | None = None) -> list[ValidationFinding]:
        from .governance import validate_target

        return validate_target(target, draft, approval_id=approval_id)


class Scribe:
    permissions = "read+write+commit"

    def commit(self, target: str, draft: str, reason: str, approval_id: str | None = None) -> dict[str, Any]:
        return write_text(target, draft, actor="scribe", endpoint="pipeline", reason=reason, approval_id=approval_id)


class Grower:
    permissions = "read+propose-structural-change"

    def propose(self, route: str, target: str) -> str:
        body = (
            "# Structural Evolution Proposal\n\n"
            "## This Proposal Records Conservative Growth After the Main Task\n"
            f"Route `{route}` touched `{target}`. Consider whether a dedicated validator or template should be added before similar changes scale.\n"
        )
        proposal_path = propose_growth(f"proposal-{route}", body)
        return str(proposal_path)


class SequentialPipeline:
    def __init__(self) -> None:
        self.router = Router()
        self.planner = Planner()
        self.worker = Worker()
        self.reflector = Reflector()
        self.warden = Warden()
        self.scribe = Scribe()
        self.grower = Grower()

    def run(self, *, task_type: str, title: str, body: str, target: str, approval_id: str | None = None) -> PipelineResult:
        route = self.router.classify(task_type, target)
        plan = self.planner.plan(route, target)
        draft = self.worker.draft(title, body)
        critique = self.reflector.critique(draft, route)
        findings = [item.as_dict() for item in self.warden.validate(draft, target, approval_id=approval_id)]
        committed = False
        if not any(item["severity"] == "error" for item in findings):
            committed = bool(self.scribe.commit(target, draft, reason=f"{task_type} pipeline", approval_id=approval_id)["ok"])
        self.grower.propose(route, target)
        return PipelineResult(route=route, plan=plan, draft=draft, critique=critique, findings=findings, committed=committed, target=target)

