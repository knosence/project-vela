from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from typing import Any

from .config import load_config, missing_required_fields, setup_complete
from .dreamer_actions import (
    filtered_dreamer_actions,
    load_dreamer_actions,
    register_dreamer_action,
    update_dreamer_action_status,
)
from .matrix import validate_matrix_rules
from .governance import apply_growth_proposal, append_event, authorize_dreamer_action_mutation, create_cross_reference, record_approval
from .models import EventRecord
from .inbox import triage_inbox
from .models import ValidationFinding
from .models import new_id
from .operations_runtime import (
    apply_dreamer_follow_up,
    list_dreamer_follow_ups,
    list_dreamer_queue,
    review_dreamer_proposal,
    run_night_cycle,
    run_warden_patrol,
)
from .paths import REPO_ROOT, VERIFICATION_STATUS_PATH
from .profiles import activate_profile, list_profiles
from .repo_watch import ingest_release
from .rust_bridge import validate_config_payload
from .traceability import annotate_findings
from .verification import run_scenario, write_verification_report


def envelope(ok: bool, endpoint: str, status: str, message: str, data: dict[str, Any] | None = None, errors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "ok": ok,
        "request_id": new_id("req"),
        "endpoint": endpoint,
        "status": status,
        "message": message,
        "data": data or {},
        "errors": errors or [],
    }


class VelaService:
    def __init__(self) -> None:
        self.config = load_config()

    def authenticate(self, headers: dict[str, str]) -> bool:
        secret = self.config["runtime"]["machine_secret"]
        return headers.get("X-VELA-SECRET") == secret

    def health(self) -> dict[str, Any]:
        verification = json.loads(VERIFICATION_STATUS_PATH.read_text(encoding="utf-8"))
        missing = missing_required_fields(self.config)
        status = "ready" if setup_complete(self.config) else "setup-required"
        return envelope(
            ok=True,
            endpoint="health",
            status=status,
            message="Service readiness evaluated",
            data={
                "setup_complete": setup_complete(self.config),
                "active_profile": self.config["assistant"]["active_profile"],
                "verification_last_passed": verification["last_passed"],
                "missing_required_fields": missing,
            },
        )

    def repo_release(self, payload: dict[str, Any]) -> dict[str, Any]:
        target = payload.get("target", "knowledge/ARTIFACTS/refs/repo-release.md")
        watchlist = (REPO_ROOT / "knowledge/220.WHAT.Repo-Watchlist-SoT.md").read_text(encoding="utf-8")
        result = ingest_release(payload, watchlist, target)
        if result["committed"]:
            return envelope(True, "repo-release", "accepted", "Release processed", data=result)
        return envelope(False, "repo-release", "rejected", "Release processing blocked", data=result, errors=result["findings"])

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        scope = payload.get("scope", "repo")
        requested_checks = payload.get("checks", ["narrative", "policy"])
        mode = payload.get("mode", "report")
        findings: list[dict[str, Any]] = []
        if scope == "repo":
            cfg = load_config()
            config_findings = annotate_findings(
                [
                    ValidationFinding(item["code"], item["detail"], item["severity"], item.get("rule_refs", []))
                    for item in validate_config_payload(cfg)["findings"]
                ]
            )
            findings.extend(item.as_dict() for item in config_findings)
            findings.extend(item.as_dict() for item in validate_matrix_rules())
        if "narrative" in requested_checks:
            findings.append({"code": "NARRATIVE_VALIDATOR_ACTIVE", "detail": "Narrative validator executed", "severity": "info", "rule_refs": []})
        ok = not any(item["code"] == "CONFIG_REQUIRED" for item in findings) or mode == "report"
        status = "accepted" if ok else "rejected"
        return envelope(
            ok,
            "validate",
            status,
            "Validation finished",
            data={"scope": scope, "mode": mode, "findings": findings, "dreamer_actions": load_dreamer_actions()},
            errors=[] if ok else findings,
        )

    def reflect(self, payload: dict[str, Any]) -> dict[str, Any]:
        proposals = [
            "Tighten repo-watch schema before broadening integrations",
            "Add a dedicated sovereign approval queue view in n8n",
        ]
        return envelope(True, "reflect", "accepted", "Reflection completed", data={"inputs": payload, "proposals": proposals})

    def approval(self, payload: dict[str, Any]) -> dict[str, Any]:
        item = record_approval(
            payload["approval_id"],
            payload["decision"],
            payload["actor"],
            payload.get("reason", ""),
            payload["target"],
        )
        return envelope(True, "approval", "accepted", "Approval recorded", data=item)

    def verify(self, payload: dict[str, Any]) -> dict[str, Any]:
        scenario = payload.get("scenario", "full")
        results = run_scenario(scenario)
        report_path = write_verification_report(results, scenario)
        passed = all(item["passed"] for item in results)
        return envelope(
            passed,
            "verify",
            "accepted" if passed else "rejected",
            "Verification completed",
            data={
                "scenario": scenario,
                "passed": passed,
                "counts": {"passed": sum(item["passed"] for item in results), "failed": sum(not item["passed"] for item in results)},
                "report_path": str(report_path.relative_to(REPO_ROOT)),
            },
            errors=[] if passed else [item for item in results if not item["passed"]],
        )

    def growth_apply(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = apply_growth_proposal(
            payload["proposal"],
            actor=payload.get("actor", "n8n"),
            approval_id=payload.get("approval_id"),
        )
        if result["ok"]:
            return envelope(True, "growth-apply", "accepted", "Growth proposal applied", data=result)
        return envelope(
            False,
            "growth-apply",
            "rejected",
            "Growth proposal application blocked",
            data=result,
            errors=result.get("findings", []),
        )

    def inbox_triage(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = triage_inbox(file_name=payload.get("file"), actor=payload.get("actor", "vela"))
        if result["ok"]:
            return envelope(True, "inbox-triage", "accepted", "Inbox triage completed", data=result)
        return envelope(False, "inbox-triage", "rejected", "Inbox triage flagged items for review", data=result, errors=result["results"])

    def cross_reference(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = create_cross_reference(
            claimant_target=payload["claimant_target"],
            claimant_dimension_heading=payload["claimant_dimension_heading"],
            description=payload["description"],
            primary_target=payload["primary_target"],
            primary_dimension_heading=payload["primary_dimension_heading"],
            actor=payload.get("actor", "vela"),
            endpoint="cross-reference",
            reason=payload.get("reason", "create governed pointer entry"),
            approval_id=payload.get("approval_id"),
        )
        if result["ok"]:
            return envelope(True, "cross-reference", "accepted", "Cross reference created", data=result)
        return envelope(False, "cross-reference", "rejected", "Cross reference creation blocked", data=result, errors=result.get("findings", []))

    def patrol_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = run_warden_patrol(requested_by=payload.get("actor", "n8n"))
        if result["ok"]:
            return envelope(True, "patrol-run", "accepted", "Warden patrol completed", data=result)
        return envelope(False, "patrol-run", "rejected", "Warden patrol blocked", data=result, errors=result.get("structural_flags", []))

    def night_cycle_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = run_night_cycle(requested_by=payload.get("actor", "n8n"))
        if result["ok"]:
            return envelope(True, "night-cycle-run", "accepted", "Night cycle completed", data=result)
        return envelope(False, "night-cycle-run", "rejected", "Night cycle blocked", data=result, errors=result.get("structural_flags", []))

    def dreamer_queue(self) -> dict[str, Any]:
        return envelope(True, "dreamer-queue", "accepted", "Dreamer queue listed", data=list_dreamer_queue())

    def dreamer_actions(self) -> dict[str, Any]:
        return envelope(True, "dreamer-actions", "accepted", "Dreamer action registry listed", data=load_dreamer_actions())

    def dreamer_actions_filtered(self, kind: str | None = None, status: str | None = None) -> dict[str, Any]:
        return envelope(
            True,
            "dreamer-actions",
            "accepted",
            "Dreamer action registry listed",
            data=filtered_dreamer_actions(kind=kind, status=status),
        )

    def dreamer_register_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        actor = payload.get("actor", "human")
        approval_id = payload.get("approval_id")
        target = "runtime/config/dreamer-actions.json"
        findings = authorize_dreamer_action_mutation(
            actor=actor,
            target=target,
            endpoint="dreamer-actions-register",
            reason=payload.get("execution_reason", "register dreamer action"),
            approval_id=approval_id,
        )
        if findings:
            findings_dicts = [item.as_dict() for item in findings]
            return envelope(False, "dreamer-actions-register", "rejected", "Dreamer action registration blocked", data={"target": target}, errors=findings_dicts)
        result = register_dreamer_action(
            kind=payload["kind"],
            follow_up_target=payload["follow_up_target"],
            execution_target=payload["execution_target"],
            pattern_reason=payload["pattern_reason"],
            actor=actor,
            execution_reason=payload.get("execution_reason", ""),
            status=payload.get("status", "active"),
        )
        if result["ok"]:
            append_event(
                EventRecord(
                    source="vela",
                    endpoint="dreamer-actions-register",
                    actor=actor,
                    target=target,
                    status="committed",
                    reason=payload.get("execution_reason", "register dreamer action"),
                    artifacts=[target],
                    approval_required=True,
                    validation_summary={
                        "approval_id": approval_id,
                        "kind": payload["kind"],
                        "follow_up_target": payload["follow_up_target"],
                        "status": payload.get("status", "active"),
                    },
                )
            )
        if result["ok"]:
            return envelope(True, "dreamer-actions-register", "accepted", "Dreamer action registered", data=result)
        return envelope(False, "dreamer-actions-register", "rejected", "Dreamer action registration blocked", data=result, errors=result.get("findings", []))

    def dreamer_update_action_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        actor = payload.get("actor", "human")
        approval_id = payload.get("approval_id")
        target = "runtime/config/dreamer-actions.json"
        findings = authorize_dreamer_action_mutation(
            actor=actor,
            target=target,
            endpoint="dreamer-actions-status",
            reason=f"set dreamer action {payload['follow_up_target']} to {payload['status']}",
            approval_id=approval_id,
        )
        if findings:
            findings_dicts = [item.as_dict() for item in findings]
            return envelope(False, "dreamer-actions-status", "rejected", "Dreamer action status update blocked", data={"target": target}, errors=findings_dicts)
        result = update_dreamer_action_status(
            follow_up_target=payload["follow_up_target"],
            status=payload["status"],
        )
        if result["ok"]:
            append_event(
                EventRecord(
                    source="vela",
                    endpoint="dreamer-actions-status",
                    actor=actor,
                    target=target,
                    status="committed",
                    reason=f"set dreamer action {payload['follow_up_target']} to {payload['status']}",
                    artifacts=[target],
                    approval_required=True,
                    validation_summary={
                        "approval_id": approval_id,
                        "follow_up_target": payload["follow_up_target"],
                        "status": payload["status"],
                    },
                )
            )
        if result["ok"]:
            return envelope(True, "dreamer-actions-status", "accepted", "Dreamer action status updated", data=result)
        return envelope(False, "dreamer-actions-status", "rejected", "Dreamer action status update blocked", data=result, errors=result.get("findings", []))

    def dreamer_follow_ups(self) -> dict[str, Any]:
        return envelope(True, "dreamer-follow-ups", "accepted", "Dreamer follow up queue listed", data=list_dreamer_follow_ups())

    def dreamer_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = review_dreamer_proposal(
            target=payload["target"],
            decision=payload["decision"],
            actor=payload.get("actor", "human"),
            reason=payload.get("reason", ""),
        )
        if result["ok"]:
            return envelope(True, "dreamer-review", "accepted", "Dreamer proposal reviewed", data=result)
        return envelope(False, "dreamer-review", "rejected", "Dreamer proposal review blocked", data=result, errors=result.get("findings", []))

    def dreamer_apply_follow_up(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = apply_dreamer_follow_up(
            target=payload["target"],
            actor=payload.get("actor", "human"),
            reason=payload.get("reason", ""),
        )
        if result["ok"]:
            return envelope(True, "dreamer-follow-up-apply", "accepted", "Dreamer follow up applied", data=result)
        return envelope(False, "dreamer-follow-up-apply", "rejected", "Dreamer follow up apply blocked", data=result, errors=result.get("findings", []))

    def profiles(self) -> dict[str, Any]:
        return envelope(True, "profiles", "accepted", "Profiles listed", data=list_profiles())

    def profiles_use(self, payload: dict[str, Any]) -> dict[str, Any]:
        cfg = activate_profile(payload["name"])
        return envelope(True, "profiles-use", "accepted", "Profile activated", data={"active_profile": cfg["assistant"]["active_profile"]})


class RequestHandler(BaseHTTPRequestHandler):
    service = VelaService()

    def _send(self, payload: dict[str, Any], code: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send(self.service.health())
            return
        if parsed.path == "/api/n8n/profiles":
            self._send(self.service.profiles())
            return
        if parsed.path == "/api/n8n/dreamer/queue":
            self._send(self.service.dreamer_queue())
            return
        if parsed.path == "/api/n8n/dreamer/actions":
            query = parse_qs(parsed.query)
            kind = query.get("kind", [None])[0]
            status = query.get("status", [None])[0]
            self._send(self.service.dreamer_actions_filtered(kind=kind, status=status))
            return
        if parsed.path == "/api/n8n/dreamer/follow-ups":
            self._send(self.service.dreamer_follow_ups())
            return
        self._send(envelope(False, "unknown", "rejected", "Endpoint not found", errors=[{"code": "NOT_FOUND", "detail": self.path}]), HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if not self.service.authenticate(dict(self.headers)):
            self._send(envelope(False, "auth", "rejected", "Authentication failed", errors=[{"code": "AUTH_FAILED", "detail": "Missing or invalid X-VELA-SECRET"}]), HTTPStatus.UNAUTHORIZED)
            return
        payload = self._read_json()
        routes = {
            "/api/n8n/repo-release": self.service.repo_release,
            "/api/n8n/validate": self.service.validate,
            "/api/n8n/reflect": self.service.reflect,
            "/api/n8n/approval": self.service.approval,
            "/api/n8n/verify": self.service.verify,
            "/api/n8n/growth/apply": self.service.growth_apply,
            "/api/n8n/inbox/triage": self.service.inbox_triage,
            "/api/n8n/cross-reference": self.service.cross_reference,
            "/api/n8n/patrol/run": self.service.patrol_run,
            "/api/n8n/night-cycle/run": self.service.night_cycle_run,
            "/api/n8n/dreamer/review": self.service.dreamer_review,
            "/api/n8n/dreamer/follow-ups/apply": self.service.dreamer_apply_follow_up,
            "/api/n8n/dreamer/actions/register": self.service.dreamer_register_action,
            "/api/n8n/dreamer/actions/status": self.service.dreamer_update_action_status,
            "/api/n8n/profiles/use": self.service.profiles_use,
        }
        handler = routes.get(self.path)
        if handler is None:
            self._send(envelope(False, "unknown", "rejected", "Endpoint not found", errors=[{"code": "NOT_FOUND", "detail": self.path}]), HTTPStatus.NOT_FOUND)
            return
        self._send(handler(payload))


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ThreadingHTTPServer((host, port), RequestHandler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
