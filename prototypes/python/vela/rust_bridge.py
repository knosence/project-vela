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


def plan_inbox_entry_payload(text: str, source_name: str) -> dict[str, Any]:
    return _run(["plan-inbox-entry", source_name], stdin=text)


def plan_csv_inbox_payload(text: str, source_name: str) -> dict[str, Any]:
    return _run(["plan-csv-inbox", source_name], stdin=text)


def plan_companion_path_payload(source_rel: str, target_rel: str, date_stamp: str) -> dict[str, Any]:
    return _run(["plan-companion-path", source_rel, target_rel, date_stamp])


def plan_dimension_append_payload(content: str, dimension: str, value: str, context: str) -> dict[str, Any]:
    return _run(["plan-dimension-append", dimension, value, context], stdin=content)


def apply_growth_source_update_payload(source_text: str, stage: str, plan: dict[str, Any]) -> dict[str, Any]:
    replacement_entries = [str(item) for item in plan.get("replacement_entries", [])]
    replacement_blob = "\n===ENTRY===\n".join(replacement_entries)
    stdin = f"{source_text}\n===REPLACEMENTS===\n{replacement_blob}"
    return _run(
        [
            "apply-growth-source-update",
            stage,
            str(plan.get("link_line", "")),
            str(plan.get("status_line", "")),
            str(plan.get("next_action_line", "")),
            str(plan.get("decision_line", "")),
            str(plan.get("target_dimension", "")),
            str(plan.get("active_pointer_line", "")),
        ],
        stdin=stdin,
    )


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


def inspect_dreamer_proposal_payload(content: str) -> dict[str, Any]:
    return _run(["inspect-dreamer-proposal"], stdin=content)


def inspect_dreamer_follow_up_payload(content: str) -> dict[str, Any]:
    return _run(["inspect-dreamer-follow-up"], stdin=content)


def list_dreamer_queue_payload() -> dict[str, Any]:
    return _run(["list-dreamer-queue"])


def list_dreamer_follow_ups_payload() -> dict[str, Any]:
    return _run(["list-dreamer-follow-ups"])


def render_reviewed_dreamer_proposal_payload(
    content: str,
    decision: str,
    actor: str,
    reason: str,
    follow_up_target: str | None,
) -> dict[str, Any]:
    return _run(
        [
            "render-reviewed-dreamer-proposal",
            decision,
            actor,
            reason,
            follow_up_target or "",
        ],
        stdin=content,
    )


def render_applied_dreamer_follow_up_payload(
    content: str,
    actor: str,
    reason: str,
    execution_target: str,
) -> dict[str, Any]:
    return _run(
        ["render-applied-dreamer-follow-up", actor, reason, execution_target],
        stdin=content,
    )


def plan_dreamer_review_payload(
    target: str,
    content: str,
    decision: str,
    actor: str,
    reason: str,
    created: str,
) -> dict[str, Any]:
    return _run(
        ["plan-dreamer-review", target, decision, actor, reason, created],
        stdin=content,
    )


def plan_dreamer_follow_up_apply_payload(
    target: str,
    content: str,
    actor: str,
    reason: str,
    created: str,
) -> dict[str, Any]:
    return _run(
        ["plan-dreamer-follow-up-apply", target, actor, reason, created],
        stdin=content,
    )


def plan_warden_patrol_payload(
    stamp: str,
    requested_by: str,
    checked_targets: list[str],
    structural_flag_targets: list[str],
) -> dict[str, Any]:
    return _run(
        ["plan-warden-patrol", stamp, requested_by],
        stdin=f"{json.dumps(checked_targets)}\n===INPUT===\n{json.dumps(structural_flag_targets)}",
    )


def plan_night_cycle_payload(
    stamp: str,
    requested_by: str,
    patrol_report_target: str,
    files_checked: int,
    structural_flags_count: int,
    growth_candidates: list[dict[str, Any]],
    dreamer_patterns: dict[str, int],
    blocked_items: list[dict[str, str]],
    dreamer_proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    return _run(
        [
            "plan-night-cycle",
            stamp,
            requested_by,
            patrol_report_target,
            str(files_checked),
            str(structural_flags_count),
        ],
        stdin="\n===INPUT===\n".join(
            [
                json.dumps(growth_candidates),
                json.dumps(dreamer_patterns),
                json.dumps(blocked_items),
                json.dumps(dreamer_proposals),
            ]
        ),
    )


def plan_operation_start_payload(
    state_json: str,
    name: str,
    requested_by: str,
    started_at: str,
) -> dict[str, Any]:
    return _run(["plan-operation-start", name, requested_by, started_at], stdin=state_json)


def plan_operation_state_update_payload(
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
    release_lock: bool = False,
) -> dict[str, Any]:
    return _run(
        [
            "plan-operation-state-update",
            name,
            status,
            requested_by,
            started_at,
            completed_at,
            last_report_target,
            last_error,
            "true" if increment_runs else "false",
            "true" if release_lock else "false",
        ],
        stdin=state_json,
    )


def plan_scheduler_run_payload(
    state_json: str,
    name: str,
    requested_by: str,
    interval_seconds: int,
    max_runs: int,
) -> dict[str, Any]:
    return _run(
        [
            "plan-scheduler-run",
            name,
            requested_by,
            str(interval_seconds),
            str(max_runs),
        ],
        stdin=state_json,
    )


def plan_operation_audit_event_payload(
    kind: str,
    event: dict[str, Any],
) -> dict[str, Any]:
    return _run(
        [
            "plan-operation-audit-event",
            kind,
            str(event.get("event_id", "")),
            str(event.get("timestamp", "")),
            str(event.get("target", "")),
            str(event.get("reason", "")),
            "true" if bool(event.get("approval_required")) else "false",
        ],
        stdin=f"{json.dumps(event.get('artifacts', []))}\n===SUMMARY===\n{json.dumps(event.get('validation_summary', {}))}",
    )


def plan_dreamer_proposals_payload(
    stamp: str,
    blocked_items: list[dict[str, Any]],
) -> dict[str, Any]:
    return _run(["plan-dreamer-proposals", stamp], stdin=json.dumps(blocked_items))


def extract_blocked_items_payload(log_text: str) -> dict[str, Any]:
    return _run(["extract-blocked-items"], stdin=log_text)


def extract_patch_targets_payload(log_text: str) -> dict[str, Any]:
    return _run(["extract-patch-targets"], stdin=log_text)


def list_growth_targets_payload() -> dict[str, Any]:
    return _run(["list-growth-targets"])


def list_merge_candidates_payload() -> dict[str, Any]:
    return _run(["list-merge-candidates"])


def assess_growth_payload(target: str) -> dict[str, Any]:
    return _run(["assess-growth-target", target])


def plan_growth_execution_payload(
    stage: str,
    assessed_target: str,
    proposal_target: str,
    subject_hint: str = "",
) -> dict[str, Any]:
    return _run(["plan-growth-execution", stage, assessed_target, proposal_target, subject_hint])


def plan_growth_source_update_payload(
    stage: str,
    assessed_target: str,
    execution_target: str,
    proposal_target: str,
) -> dict[str, Any]:
    return _run(
        ["plan-growth-source-update", stage, assessed_target, execution_target, proposal_target]
    )


def render_growth_reference_note_payload(
    execution_target: str,
    assessed_target: str,
    proposal_target: str,
    created: str,
    dimension: str,
    entries: list[str],
) -> dict[str, Any]:
    return _run(
        [
            "render-growth-reference-note",
            execution_target,
            assessed_target,
            proposal_target,
            created,
            dimension,
        ],
        stdin=json.dumps(entries),
    )


def render_growth_spawned_sot_payload(
    execution_target: str,
    assessed_target: str,
    proposal_target: str,
    created: str,
) -> dict[str, Any]:
    return _run(
        [
            "render-growth-spawned-sot",
            execution_target,
            assessed_target,
            proposal_target,
            created,
        ]
    )


def render_applied_growth_action_payload(
    stage: str,
    assessed_target: str,
    proposal_target: str,
) -> dict[str, Any]:
    return _run(
        ["render-applied-growth-action", stage, assessed_target, proposal_target]
    )


def render_applied_growth_proposal_payload(
    proposal_text: str,
    execution_target: str,
    stage: str,
) -> dict[str, Any]:
    return _run(
        ["render-applied-growth-proposal", execution_target, stage],
        stdin=proposal_text,
    )


def render_growth_fractalized_source_payload(
    source_text: str,
    proposal_target: str,
    created: str,
) -> dict[str, Any]:
    return _run(
        ["render-growth-fractalized-source", proposal_target, created],
        stdin=source_text,
    )


def plan_archive_transaction_payload(
    content: str,
    dimension_heading: str,
    entry_value: str,
    archived_reason: str,
    archived_date: str,
    archive_stamp: str,
) -> dict[str, Any]:
    return _run(
        [
            "plan-archive-transaction",
            dimension_heading,
            entry_value,
            archived_reason,
            archived_date,
            archive_stamp,
        ],
        stdin=content,
    )


def plan_cross_reference_update_payload(
    content: str,
    claimant_dimension_heading: str,
    description: str,
    primary_target_stem: str,
    primary_dimension_heading: str,
    date: str,
) -> dict[str, Any]:
    return _run(
        [
            "plan-cross-reference-update",
            claimant_dimension_heading,
            description,
            primary_target_stem,
            primary_dimension_heading,
            date,
        ],
        stdin=content,
    )


def validate_dreamer_execution_artifact_payload(content: str) -> dict[str, Any]:
    return _run(["validate-dreamer-execution-artifact"], stdin=content)


def validate_warden_patrol_report_payload(content: str) -> dict[str, Any]:
    return _run(["validate-warden-patrol-report"], stdin=content)


def validate_dc_night_report_payload(content: str) -> dict[str, Any]:
    return _run(["validate-dc-night-report"], stdin=content)


def validate_dreamer_pattern_report_payload(content: str) -> dict[str, Any]:
    return _run(["validate-dreamer-pattern-report"], stdin=content)


def render_warden_patrol_report_payload(
    stamp: str,
    requested_by: str,
    checked_targets: list[str],
    structural_flag_targets: list[str],
) -> dict[str, Any]:
    return _run(
        ["render-warden-patrol-report", stamp, requested_by],
        stdin=f"{json.dumps(checked_targets)}\n===INPUT===\n{json.dumps(structural_flag_targets)}",
    )


def render_dreamer_pattern_report_payload(
    stamp: str,
    requested_by: str,
    dreamer_patterns: dict[str, int],
    blocked_items: list[dict[str, str]],
    dreamer_proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    return _run(
        ["render-dreamer-pattern-report", stamp, requested_by],
        stdin="\n===INPUT===\n".join(
            [
                json.dumps(dreamer_patterns),
                json.dumps(blocked_items),
                json.dumps(dreamer_proposals),
            ]
        ),
    )


def render_dc_night_report_payload(
    stamp: str,
    requested_by: str,
    patrol_report_target: str,
    files_checked: int,
    structural_flags_count: int,
    growth_candidates: list[dict[str, Any]],
    dreamer_patterns: dict[str, int],
    blocked_items: list[dict[str, str]],
    dreamer_report_target: str,
    dreamer_proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    return _run(
        [
            "render-dc-night-report",
            stamp,
            requested_by,
            patrol_report_target,
            str(files_checked),
            str(structural_flags_count),
            dreamer_report_target,
        ],
        stdin="\n===INPUT===\n".join(
            [
                json.dumps(growth_candidates),
                json.dumps(dreamer_patterns),
                json.dumps(blocked_items),
                json.dumps(dreamer_proposals),
            ]
        ),
    )


def render_dreamer_proposal_payload(
    created: str,
    stamp: str,
    requested_by: str,
    reason: str,
    count: int,
    blocked_items: list[dict[str, str]],
) -> dict[str, Any]:
    return _run(
        ["render-dreamer-proposal", created, stamp, requested_by, reason, str(count)],
        stdin=json.dumps(blocked_items),
    )


def render_dreamer_follow_up_payload(
    created: str,
    proposal_target: str,
    reason: str,
    classification: str,
    actor: str,
) -> dict[str, Any]:
    return _run(
        ["render-dreamer-follow-up", created, proposal_target, reason, classification, actor]
    )


def render_dreamer_execution_artifact_payload(
    created: str,
    follow_up_target: str,
    actor: str,
    kind: str,
    follow_up_reason: str,
    queue_name: str,
    execution_reason: str,
) -> dict[str, Any]:
    return _run(
        [
            "render-dreamer-execution-artifact",
            created,
            follow_up_target,
            actor,
            kind,
            follow_up_reason,
            queue_name,
            execution_reason,
        ]
    )


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


def render_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    return _run(
        [
            "render-event",
            str(event.get("event_id", "")),
            str(event.get("timestamp", "")),
            str(event.get("source", "")),
            str(event.get("endpoint", "")),
            str(event.get("actor", "")),
            str(event.get("target", "")),
            str(event.get("status", "")),
            str(event.get("reason", "")),
            "true" if bool(event.get("approval_required")) else "false",
        ],
        stdin=f"{json.dumps(event.get('artifacts', []))}\n===SUMMARY===\n{json.dumps(event.get('validation_summary', {}))}",
    )


def plan_event_append_payload(event: dict[str, Any]) -> dict[str, Any]:
    return _run(
        [
            "plan-event-append",
            str(event.get("event_id", "")),
            str(event.get("timestamp", "")),
            str(event.get("source", "")),
            str(event.get("endpoint", "")),
            str(event.get("actor", "")),
            str(event.get("target", "")),
            str(event.get("status", "")),
            str(event.get("reason", "")),
            "true" if bool(event.get("approval_required")) else "false",
        ],
        stdin=f"{json.dumps(event.get('artifacts', []))}\n===SUMMARY===\n{json.dumps(event.get('validation_summary', {}))}",
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
