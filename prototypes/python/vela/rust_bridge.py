from __future__ import annotations

import json
import subprocess
from typing import Any

from .paths import REPO_ROOT


def _run(args: list[str], stdin: str | None = None) -> dict[str, Any]:
    command = ["cargo", "run", "--quiet", "--bin", "vela-core-cli", "--", *args]
    result = subprocess.run(
        command,
        input=stdin,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        check=True,
    )
    return json.loads(result.stdout)


def validate_target(target: str, content: str, approval_status: str) -> dict[str, Any]:
    return _run(["validate-target", target, approval_status], stdin=content)


def route_for_target(task_type: str, target: str) -> str:
    payload = _run(["route", task_type, target])
    return str(payload["route"])


def match_dreamer_actions_payload(
    registry_json: str,
    mode: str,
    target: str,
    endpoint: str,
    reason: str,
    content: str,
) -> dict[str, Any]:
    return _run(
        ["match-dreamer-actions", mode, target, endpoint, reason],
        stdin=f"{registry_json}\n===INPUT===\n{content}",
    )


def parse_dreamer_actions_payload(registry_json: str) -> dict[str, Any]:
    return _run(["parse-dreamer-actions"], stdin=registry_json)


def register_dreamer_action_payload(
    registry_json: str,
    kind: str,
    follow_up_target: str,
    execution_target: str,
    pattern_reason: str,
    actor: str,
    execution_reason: str,
    applied_at: str,
    status: str,
) -> dict[str, Any]:
    return _run(
        [
            "register-dreamer-action",
            kind,
            follow_up_target,
            execution_target,
            pattern_reason,
            actor,
            execution_reason,
            applied_at,
            status,
        ],
        stdin=registry_json,
    )


def update_dreamer_action_status_payload(
    registry_json: str,
    follow_up_target: str,
    status: str,
) -> dict[str, Any]:
    return _run(
        ["update-dreamer-action-status", follow_up_target, status],
        stdin=registry_json,
    )


def parse_operations_state_payload(state_json: str) -> dict[str, Any]:
    return _run(["parse-operations-state"], stdin=state_json)


def update_operations_state_payload(
    state_json: str,
    name: str,
    status: str,
    requested_by: str,
    *,
    started_at: str = "",
    completed_at: str = "",
    last_report_target: str = "",
    last_error: str = "",
    increment_runs: bool = False,
) -> dict[str, Any]:
    return _run(
        [
            "update-operations-state",
            name,
            status,
            requested_by,
            started_at,
            completed_at,
            last_report_target,
            last_error,
            "true" if increment_runs else "false",
        ],
        stdin=state_json,
    )


def validate_operation_lock_payload(lock_json: str, expected_name: str) -> dict[str, Any]:
    return _run(["validate-operation-lock", expected_name], stdin=lock_json)


def validate_operation_request_payload(name: str, requested_by: str) -> dict[str, Any]:
    return _run(["validate-operation-request", name, requested_by])


def validate_operation_transition_payload(current_status: str, next_status: str) -> dict[str, Any]:
    return _run(["validate-operation-transition", current_status, next_status])


def validate_dreamer_review_payload(current_status: str, decision: str) -> dict[str, Any]:
    return _run(["validate-dreamer-review", current_status, decision])


def validate_dreamer_follow_up_apply_payload(current_status: str, actor: str) -> dict[str, Any]:
    return _run(["validate-dreamer-follow-up-apply", current_status, actor])


def classify_dreamer_follow_up_payload(reason: str) -> dict[str, Any]:
    return _run(["classify-dreamer-follow-up", reason])


def inspect_dreamer_follow_up_kind_payload(kind: str) -> dict[str, Any]:
    return _run(["inspect-dreamer-follow-up-kind", kind])


def validate_dreamer_execution_artifact_payload(content: str) -> dict[str, Any]:
    return _run(["validate-dreamer-execution-artifact"], stdin=content)


def validate_warden_patrol_report_payload(content: str) -> dict[str, Any]:
    return _run(["validate-warden-patrol-report"], stdin=content)


def validate_dc_night_report_payload(content: str) -> dict[str, Any]:
    return _run(["validate-dc-night-report"], stdin=content)


def validate_dreamer_pattern_report_payload(content: str) -> dict[str, Any]:
    return _run(["validate-dreamer-pattern-report"], stdin=content)


def route_inbox_payload(content: str) -> dict[str, Any]:
    return _run(["route-inbox"], stdin=content)


def validate_subject_declaration_payload(before: str, after: str, approval_status: str) -> dict[str, Any]:
    return _run(["validate-subject-declaration", approval_status], stdin=f"{before}\n===AFTER===\n{after}")


def validate_growth_stage_payload(stage: str, approval_status: str) -> dict[str, Any]:
    return _run(["validate-growth-stage", stage, approval_status])


def validate_archive_postconditions_payload(
    content: str,
    entry_value: str,
    archived_reason: str,
    dimension_heading: str,
) -> dict[str, Any]:
    return _run(
        ["validate-archive-postconditions", entry_value, archived_reason, dimension_heading],
        stdin=content,
    )


def validate_config_payload(config: dict[str, Any]) -> dict[str, Any]:
    return _run(
        [
            "validate-config",
            str(config.get("owner", {}).get("name", "")),
            str(config.get("providers", {}).get("primary", "")),
            str(config.get("runtime", {}).get("primary_model", "")),
            str(config.get("deployment", {}).get("target", "")),
            str(config.get("onboarding", {}).get("assistant_choice", "")),
            str(config.get("onboarding", {}).get("relationship_stance", "")),
            str(config.get("onboarding", {}).get("support_critique_balance", "")),
            str(config.get("onboarding", {}).get("subjectivity_boundaries", "")),
            str(config.get("project", {}).get("name", "")),
            str(config.get("assistant", {}).get("default_profile", "")),
            str(config.get("assistant", {}).get("active_profile", "")),
            "true" if bool(config.get("assistant", {}).get("allow_replacement")) else "false",
            "true" if bool(config.get("assistant", {}).get("allow_multiple_profiles")) else "false",
            "true" if bool(config.get("project", {}).get("setup_complete")) else "false",
        ]
    )


def validate_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    return _run(
        [
            "validate-event",
            str(event.get("event_id", "")),
            str(event.get("timestamp", "")),
            str(event.get("source", "")),
            str(event.get("endpoint", "")),
            str(event.get("actor", "")),
            str(event.get("target", "")),
            str(event.get("status", "")),
            str(event.get("reason", "")),
        ]
    )


def analyze_release_payload(repo: str, version: str, notes: str, watchlist_text: str, context_markers: list[str]) -> dict[str, Any]:
    return _run(["analyze-release", repo, version, notes, ",".join(context_markers)], stdin=watchlist_text)


def inspect_reference_payload(path: str, content: str) -> dict[str, Any]:
    return _run(["inspect-reference", path], stdin=content)


def validate_parent_payload(path: str, content: str) -> dict[str, Any]:
    return _run(["validate-parent", path], stdin=content)


def validate_sot_payload(path: str, content: str) -> dict[str, Any]:
    return _run(["validate-sot", path], stdin=content)


def render_matrix_index_payload() -> dict[str, Any]:
    return _run(["render-matrix-index", str(REPO_ROOT)])


def matrix_inventory_payload() -> dict[str, Any]:
    return _run(["inventory", str(REPO_ROOT)])
