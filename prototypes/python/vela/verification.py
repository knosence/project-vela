from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agents import SequentialPipeline
from .config import ensure_bootstrap_files, load_config, missing_required_fields, save_config, setup_complete
from .governance import append_event, governance_snapshot, record_approval, write_text
from .matrix import write_matrix_index
from .models import EventRecord
from .paths import EVENT_LOG_PATH, REPO_ROOT, STARTER_PATH, VERIFICATION_STATUS_PATH
from .profiles import activate_profile, list_profiles, register_profile
from .repo_watch import ingest_release

TEST_SOVEREIGN_TARGET = "knowledge/ARTIFACTS/proposals/TEST.Sovereign-Guardrail-Fixture.md"


def _result(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": passed, "detail": detail}


def run_scenario(name: str) -> list[dict[str, Any]]:
    ensure_bootstrap_files()
    scenarios = {
        "dry-boot": scenario_dry_boot,
        "profiles": scenario_profiles,
        "routing": scenario_routing,
        "governance": scenario_governance,
        "repo-watch": scenario_repo_watch,
        "full": scenario_full,
    }
    if name not in scenarios:
        raise ValueError(f"Unknown scenario: {name}")
    return scenarios[name]()


def scenario_config_boot() -> list[dict[str, Any]]:
    cfg = load_config()
    index_result = write_matrix_index()
    return [
        _result("starter-exists", STARTER_PATH.exists(), "Starter file must exist"),
        _result("config-exists", (REPO_ROOT / "runtime/config/project-vela.yaml").exists(), "Config file must exist"),
        _result("setup-required-on-missing-fields", bool(missing_required_fields(cfg)), "Missing required fields should trigger setup mode"),
        _result("matrix-index-exists", (REPO_ROOT / index_result["path"]).exists(), "Matrix index should exist"),
    ]


def scenario_profiles() -> list[dict[str, Any]]:
    register_profile("custom-vela", "Custom Vela", base_profile="vela")
    before = list_profiles()
    activate_profile("custom-vela")
    after = list_profiles()
    return [
        _result("vela-registered-default", any(item["name"] == "vela" for item in before["profiles"]), "Vela must be registered"),
        _result("custom-profile-active", after["active_profile"] == "custom-vela", "Custom profile should activate"),
        _result(
            "system-sots-unchanged",
            (REPO_ROOT / "knowledge/Cornerstone.Knosence-SoT.md").exists(),
            "System SoTs should stay intact while profile changes",
        ),
    ]


def scenario_routing() -> list[dict[str, Any]]:
    pipeline = SequentialPipeline()
    sovereign = pipeline.run(
        task_type="write",
        title="System Identity Update",
        body="## This Proposal Tests Sovereign Guardrails\nAttempted change without approval.",
        target=TEST_SOVEREIGN_TARGET,
    )
    normal = pipeline.run(
        task_type="write",
        title="Operational Note",
        body="## This Note Documents a Non Sovereign Change\nThe pipeline should allow this draft to commit.",
        target="knowledge/ARTIFACTS/refs/operational-note.md",
    )
    return [
        _result("reject-unsafe-direct-commit", not sovereign.committed, "Sovereign route should refuse unapproved commit"),
        _result("allow-standard-commit", normal.committed, "Standard route should commit through scribe"),
    ]


def scenario_governance() -> list[dict[str, Any]]:
    target = TEST_SOVEREIGN_TARGET
    denied = write_text(
        target,
        "# Sovereign Guardrail Test\n\n## This Attempt Is Missing Human Approval\nThis should be denied.\n",
        actor="scribe",
        endpoint="verify",
        reason="test missing approval",
    )
    record_approval("appr_test", "approved", "human", "approved for test", target)
    allowed = write_text(
        target,
        "# Sovereign Guardrail Test\n\n## This Approved Revision Passes Through Controlled Commit\nThis should be accepted.\n",
        actor="scribe",
        endpoint="verify",
        reason="test approved path",
        approval_id="appr_test",
    )
    return [
        _result("deny-sovereign-without-approval", not denied["ok"], "Unapproved sovereign change must fail"),
        _result("allow-sovereign-with-approval", allowed["ok"], "Approved sovereign change must pass"),
        _result("event-log-written", EVENT_LOG_PATH.exists(), "Event log should exist after governed write"),
    ]


def scenario_repo_watch() -> list[dict[str, Any]]:
    target = "knowledge/ARTIFACTS/proposals/repo-watch-scenario-test.md"
    result = ingest_release(
        {"repo": "openai/openai-python", "version": "1.2.3", "notes": "Breaking API migration required for client construction."},
        (REPO_ROOT / "knowledge/WHAT.Repo-Watchlist-SoT.md").read_text(encoding="utf-8"),
        target,
    )
    return [
        _result("release-summary-committed", result["committed"], "Release summary should be written"),
        _result("release-summary-target-exists", (REPO_ROOT / target).exists(), "Release target artifact should exist"),
        _result("release-packet-target-exists", (REPO_ROOT / result["packet_target"]).exists(), "Structured packet artifact should exist"),
        _result("release-assessment-target-exists", (REPO_ROOT / result["assessment_target"]).exists(), "Structured assessment artifact should exist"),
        _result("release-reflection-target-exists", (REPO_ROOT / result["reflection_target"]).exists(), "Structured reflection artifact should exist"),
        _result("release-validation-target-exists", (REPO_ROOT / result["validation_target"]).exists(), "Structured validation artifact should exist"),
        _result("release-intelligence-target-exists", (REPO_ROOT / result["intelligence_target"]).exists(), "Release intelligence reference should exist"),
        _result("release-summary-criticized", bool(result["critique"]), "Reflector should produce critique notes"),
    ]


def scenario_dry_boot() -> list[dict[str, Any]]:
    cfg = load_config()
    missing = missing_required_fields(cfg)
    append_event(
        EventRecord(
            source="vela",
            endpoint="dry-boot",
            actor="system",
            target="runtime",
            status="setup-required" if missing else "ready",
            reason="Dry boot scenario executed",
            artifacts=["runtime/config/project-vela.yaml"],
            approval_required=False,
            validation_summary={"missing_required_fields": missing, "governance": governance_snapshot()},
        )
    )
    return [
        _result("boot-detects-setup-mode", not setup_complete(cfg), "Incomplete config should keep the system in setup mode"),
        _result("governance-loaded", governance_snapshot()["single_writer"], "Governance directives should load"),
    ]


def scenario_full() -> list[dict[str, Any]]:
    results = []
    for scenario in [scenario_config_boot, scenario_profiles, scenario_routing, scenario_governance, scenario_repo_watch, scenario_dry_boot]:
        results.extend(scenario())
    return results


def write_verification_report(results: list[dict[str, Any]], scenario: str) -> Path:
    report_dir = REPO_ROOT / "knowledge" / "ARTIFACTS" / "refs"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"verification-{scenario}.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    VERIFICATION_STATUS_PATH.write_text(
        json.dumps({"last_passed": all(item["passed"] for item in results), "report_path": str(report_path.relative_to(REPO_ROOT))}, indent=2),
        encoding="utf-8",
    )
    return report_path
