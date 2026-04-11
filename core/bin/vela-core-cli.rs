use std::env;
use std::io::{self, Read};

use vela_core::events::{
    extract_blocked_items as extract_blocked_items_policy,
    extract_patch_targets as extract_patch_targets_policy, plan_event_append,
    render_event_record_json, validate_event_record, EventRecord, ValidationSummary,
};
use vela_core::inventory::{
    discover_matrix_inventory, list_growth_targets as list_growth_targets_policy,
};
use vela_core::matrix::{
    build_matrix_index, validate_parent_consistency as validate_matrix_parent_consistency,
    validate_sot_structure as validate_matrix_sot_structure,
};
use vela_core::models::{
    BlockedItemSummary, DreamerProposalCandidate, GrowthTarget, OnboardingConfig,
    OperationLifecyclePlan, OperationLockRecord, OperationStateEntry, OperationsState, PatchTarget,
    SchedulerPlan, Severity, ValidationFinding,
};
use vela_core::operations::{
    classify_dreamer_follow_up as classify_dreamer_follow_up_policy,
    dreamer_existing_execution_target as dreamer_existing_execution_target_policy,
    dreamer_follow_up_kind as dreamer_follow_up_kind_policy,
    dreamer_follow_up_queue_name as dreamer_follow_up_queue_name_policy,
    dreamer_follow_up_reason as dreamer_follow_up_reason_policy,
    dreamer_follow_up_registry_mode as dreamer_follow_up_registry_mode_policy,
    dreamer_proposal_reason as dreamer_proposal_reason_policy,
    list_dreamer_follow_ups as list_dreamer_follow_ups_policy,
    list_dreamer_proposals as list_dreamer_proposals_policy,
    match_dreamer_actions as match_dreamer_actions_policy,
    parse_dreamer_action_registry as parse_dreamer_action_registry_policy,
    parse_operations_state as parse_operations_state_policy,
    plan_dreamer_follow_up_apply as plan_dreamer_follow_up_apply_policy,
    plan_dreamer_proposals as plan_dreamer_proposals_policy,
    plan_dreamer_review as plan_dreamer_review_policy, plan_night_cycle as plan_night_cycle_policy,
    plan_operation_audit_event as plan_operation_audit_event_policy,
    plan_operation_start as plan_operation_start_policy,
    plan_operation_state_update as plan_operation_state_update_policy,
    plan_scheduler_run as plan_scheduler_run_policy,
    plan_warden_patrol as plan_warden_patrol_policy,
    register_dreamer_action as register_dreamer_action_policy,
    render_applied_dreamer_follow_up as render_applied_dreamer_follow_up_policy,
    render_dc_night_report as render_dc_night_report_policy,
    render_dreamer_execution_artifact as render_dreamer_execution_artifact_policy,
    render_dreamer_follow_up as render_dreamer_follow_up_policy,
    render_dreamer_pattern_report as render_dreamer_pattern_report_policy,
    render_dreamer_proposal as render_dreamer_proposal_policy,
    render_reviewed_dreamer_proposal as render_reviewed_dreamer_proposal_policy,
    render_warden_patrol_report as render_warden_patrol_report_policy,
    route_inbox_entry as route_inbox_dimension,
    update_dreamer_action_status as update_dreamer_action_status_policy,
    update_operations_state as update_operations_state_policy,
    validate_archive_postconditions as validate_archive_outcome,
    validate_dc_night_report as validate_dc_night_report_policy,
    validate_dreamer_execution_artifact as validate_dreamer_execution_artifact_policy,
    validate_dreamer_follow_up_apply as validate_dreamer_follow_up_apply_policy,
    validate_dreamer_pattern_report as validate_dreamer_pattern_report_policy,
    validate_dreamer_review as validate_dreamer_review_policy,
    validate_growth_stage as validate_growth_stage_policy,
    validate_operation_lock as validate_operation_lock_policy,
    validate_operation_request as validate_operation_request_policy,
    validate_operation_state_transition as validate_operation_state_transition_policy,
    validate_subject_declaration_change as validate_subject_declaration_policy,
    validate_warden_patrol_report as validate_warden_patrol_report_policy,
};
use vela_core::parser::{build_runtime_config, parse_system_identity};
use vela_core::policy::{route_for_target, validate_commit_policy};
use vela_core::references::inspect_reference;
use vela_core::repo_watch::assess_release;
use vela_core::validator::{
    has_blocking_findings, missing_required_fields, validate_narrative_document,
    validate_runtime_config,
};

fn main() {
    if let Err(message) = run() {
        eprintln!("{message}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let command = args.next().ok_or_else(|| "missing command".to_string())?;

    match command.as_str() {
        "validate-target" => {
            let target = args.next().ok_or_else(|| "missing target".to_string())?;
            let approval_status = args
                .next()
                .ok_or_else(|| "missing approval status".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;

            let mut findings = validate_narrative_document(&content);
            findings.extend(validate_commit_policy(
                &target,
                approval_status == "approved",
            ));
            print_findings(&findings, Some(route_for_target("write", &target)));
        }
        "route" => {
            let task_type = args.next().ok_or_else(|| "missing task type".to_string())?;
            let target = args.next().ok_or_else(|| "missing target".to_string())?;
            println!(
                "{{\"ok\":true,\"route\":\"{}\"}}",
                escape_json(route_for_target(&task_type, &target))
            );
        }
        "route-inbox" => {
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let route = route_inbox_dimension(&content)
                .map(|item| format!("\"{}\"", escape_json(item)))
                .unwrap_or_else(|| "null".to_string());
            println!("{{\"ok\":true,\"dimension\":{route}}}");
        }
        "validate-subject-declaration" => {
            let approval_status = args
                .next()
                .ok_or_else(|| "missing approval status".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (before, after) = content
                .split_once("\n===AFTER===\n")
                .ok_or_else(|| "missing subject declaration split marker".to_string())?;
            let findings =
                validate_subject_declaration_policy(before, after, approval_status == "approved");
            print_findings(&findings, None);
        }
        "validate-growth-stage" => {
            let stage = args.next().ok_or_else(|| "missing stage".to_string())?;
            let approval_status = args
                .next()
                .ok_or_else(|| "missing approval status".to_string())?;
            let findings = validate_growth_stage_policy(&stage, approval_status == "approved");
            print_findings(&findings, None);
        }
        "validate-archive-postconditions" => {
            let entry_value = args
                .next()
                .ok_or_else(|| "missing entry value".to_string())?;
            let archived_reason = args
                .next()
                .ok_or_else(|| "missing archived reason".to_string())?;
            let dimension_heading = args
                .next()
                .ok_or_else(|| "missing dimension heading".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let findings = validate_archive_outcome(
                &content,
                &entry_value,
                &archived_reason,
                &dimension_heading,
            );
            print_findings(&findings, None);
        }
        "match-dreamer-actions" => {
            let mode = args.next().ok_or_else(|| "missing mode".to_string())?;
            let target = args.next().unwrap_or_default();
            let endpoint = args.next().unwrap_or_default();
            let reason = args.next().unwrap_or_default();
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (registry_json, text) = content
                .split_once("\n===INPUT===\n")
                .ok_or_else(|| "missing dreamer action split marker".to_string())?;
            let matches = match_dreamer_actions_policy(
                registry_json,
                &mode,
                &target,
                &endpoint,
                &reason,
                text,
            );
            println!(
                "{{\"ok\":true,\"matches\":[{}]}}",
                matches
                    .iter()
                    .map(|item| format!(
                        "{{\"pattern_reason\":\"{}\",\"status\":\"{}\"}}",
                        escape_json(&item.pattern_reason),
                        escape_json(&item.status),
                    ))
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "parse-dreamer-actions" => {
            let mut registry_json = String::new();
            io::stdin()
                .read_to_string(&mut registry_json)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (registry, findings) = parse_dreamer_action_registry_policy(&registry_json);
            println!(
                "{{\"ok\":{},\"registry\":{{\"validator_changes\":[{}],\"workflow_changes\":[{}],\"refusal_tightenings\":[{}]}},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) { "true" } else { "false" },
                registry.validator_changes.iter().map(render_dreamer_action).collect::<Vec<String>>().join(","),
                registry.workflow_changes.iter().map(render_dreamer_action).collect::<Vec<String>>().join(","),
                registry.refusal_tightenings.iter().map(render_dreamer_action).collect::<Vec<String>>().join(","),
                findings.iter().map(render_finding).collect::<Vec<String>>().join(",")
            );
        }
        "register-dreamer-action" => {
            let kind = args.next().ok_or_else(|| "missing kind".to_string())?;
            let follow_up_target = args
                .next()
                .ok_or_else(|| "missing follow up target".to_string())?;
            let execution_target = args
                .next()
                .ok_or_else(|| "missing execution target".to_string())?;
            let pattern_reason = args
                .next()
                .ok_or_else(|| "missing pattern reason".to_string())?;
            let actor = args.next().ok_or_else(|| "missing actor".to_string())?;
            let execution_reason = args
                .next()
                .ok_or_else(|| "missing execution reason".to_string())?;
            let applied_at = args
                .next()
                .ok_or_else(|| "missing applied_at".to_string())?;
            let status = args.next().ok_or_else(|| "missing status".to_string())?;
            let mut registry_json = String::new();
            io::stdin()
                .read_to_string(&mut registry_json)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (registry, findings) = register_dreamer_action_policy(
                &registry_json,
                &kind,
                vela_core::models::DreamerAction {
                    follow_up_target,
                    execution_target,
                    pattern_reason,
                    actor,
                    execution_reason,
                    applied_at,
                    status,
                },
            );
            print_dreamer_registry(&registry, &findings);
        }
        "update-dreamer-action-status" => {
            let follow_up_target = args
                .next()
                .ok_or_else(|| "missing follow up target".to_string())?;
            let status = args.next().ok_or_else(|| "missing status".to_string())?;
            let mut registry_json = String::new();
            io::stdin()
                .read_to_string(&mut registry_json)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (registry, findings) =
                update_dreamer_action_status_policy(&registry_json, &follow_up_target, &status);
            print_dreamer_registry(&registry, &findings);
        }
        "parse-operations-state" => {
            let mut state_json = String::new();
            io::stdin()
                .read_to_string(&mut state_json)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (state, findings) = parse_operations_state_policy(&state_json);
            print_operations_state(&state, &findings);
        }
        "update-operations-state" => {
            let name = args.next().ok_or_else(|| "missing name".to_string())?;
            let status = args.next().ok_or_else(|| "missing status".to_string())?;
            let requested_by = args
                .next()
                .ok_or_else(|| "missing requested_by".to_string())?;
            let started_at = args.next().unwrap_or_default();
            let completed_at = args.next().unwrap_or_default();
            let last_report_target = args.next().unwrap_or_default();
            let last_error = args.next().unwrap_or_default();
            let increment_runs = parse_bool(
                &args
                    .next()
                    .ok_or_else(|| "missing increment_runs".to_string())?,
            )?;
            let mut state_json = String::new();
            io::stdin()
                .read_to_string(&mut state_json)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (state, findings) = update_operations_state_policy(
                &state_json,
                &name,
                &status,
                &requested_by,
                if started_at.is_empty() {
                    None
                } else {
                    Some(started_at.as_str())
                },
                if completed_at.is_empty() {
                    None
                } else {
                    Some(completed_at.as_str())
                },
                if last_report_target.is_empty() {
                    None
                } else {
                    Some(last_report_target.as_str())
                },
                if last_error.is_empty() {
                    None
                } else {
                    Some(last_error.as_str())
                },
                increment_runs,
            );
            print_operations_state(&state, &findings);
        }
        "validate-operation-lock" => {
            let expected_name = args
                .next()
                .ok_or_else(|| "missing expected name".to_string())?;
            let mut lock_json = String::new();
            io::stdin()
                .read_to_string(&mut lock_json)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (record, findings) = validate_operation_lock_policy(&lock_json, &expected_name);
            println!(
                "{{\"ok\":{},\"record\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                record
                    .as_ref()
                    .map(render_operation_lock)
                    .unwrap_or_else(|| "null".to_string()),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "validate-operation-request" => {
            let name = args.next().ok_or_else(|| "missing name".to_string())?;
            let requested_by = args
                .next()
                .ok_or_else(|| "missing requested_by".to_string())?;
            let findings = validate_operation_request_policy(&name, &requested_by);
            print_findings(&findings, None);
        }
        "validate-operation-transition" => {
            let current_status = args
                .next()
                .ok_or_else(|| "missing current status".to_string())?;
            let next_status = args
                .next()
                .ok_or_else(|| "missing next status".to_string())?;
            let findings =
                validate_operation_state_transition_policy(&current_status, &next_status);
            print_findings(&findings, None);
        }
        "validate-dreamer-review" => {
            let current_status = args
                .next()
                .ok_or_else(|| "missing current status".to_string())?;
            let decision = args.next().ok_or_else(|| "missing decision".to_string())?;
            let findings = validate_dreamer_review_policy(&current_status, &decision);
            print_findings(&findings, None);
        }
        "validate-dreamer-follow-up-apply" => {
            let current_status = args
                .next()
                .ok_or_else(|| "missing current status".to_string())?;
            let actor = args.next().ok_or_else(|| "missing actor".to_string())?;
            let findings = validate_dreamer_follow_up_apply_policy(&current_status, &actor);
            print_findings(&findings, None);
        }
        "classify-dreamer-follow-up" => {
            let reason = args.next().ok_or_else(|| "missing reason".to_string())?;
            let kind = classify_dreamer_follow_up_policy(&reason);
            let queue_name = match dreamer_follow_up_queue_name_policy(&kind) {
                Ok(value) => value.to_string(),
                Err(findings) => {
                    print_findings(&findings, None);
                    return Ok(());
                }
            };
            let registry_mode = match dreamer_follow_up_registry_mode_policy(&kind) {
                Ok(value) => value.to_string(),
                Err(findings) => {
                    print_findings(&findings, None);
                    return Ok(());
                }
            };
            println!(
                "{{\"ok\":true,\"kind\":\"{}\",\"queue_name\":\"{}\",\"registry_mode\":\"{}\"}}",
                escape_json(&kind),
                escape_json(&queue_name),
                escape_json(&registry_mode),
            );
        }
        "inspect-dreamer-follow-up-kind" => {
            let kind = args.next().ok_or_else(|| "missing kind".to_string())?;
            let queue_name = match dreamer_follow_up_queue_name_policy(&kind) {
                Ok(value) => value.to_string(),
                Err(findings) => {
                    print_findings(&findings, None);
                    return Ok(());
                }
            };
            let registry_mode = match dreamer_follow_up_registry_mode_policy(&kind) {
                Ok(value) => value.to_string(),
                Err(findings) => {
                    print_findings(&findings, None);
                    return Ok(());
                }
            };
            println!(
                "{{\"ok\":true,\"kind\":\"{}\",\"queue_name\":\"{}\",\"registry_mode\":\"{}\"}}",
                escape_json(&kind),
                escape_json(&queue_name),
                escape_json(&registry_mode),
            );
        }
        "validate-dreamer-execution-artifact" => {
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let findings = validate_dreamer_execution_artifact_policy(&content);
            print_findings(&findings, None);
        }
        "validate-warden-patrol-report" => {
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let findings = validate_warden_patrol_report_policy(&content);
            print_findings(&findings, None);
        }
        "validate-dc-night-report" => {
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let findings = validate_dc_night_report_policy(&content);
            print_findings(&findings, None);
        }
        "validate-dreamer-pattern-report" => {
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let findings = validate_dreamer_pattern_report_policy(&content);
            print_findings(&findings, None);
        }
        "render-warden-patrol-report" => {
            let stamp = args.next().ok_or_else(|| "missing stamp".to_string())?;
            let requested_by = args
                .next()
                .ok_or_else(|| "missing requested_by".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (checked_json, structural_json) = content
                .split_once("\n===INPUT===\n")
                .ok_or_else(|| "missing patrol render split marker".to_string())?;
            let checked_targets = extract_json_string_list(checked_json);
            let structural_targets = extract_json_string_list(structural_json);
            let rendered = render_warden_patrol_report_policy(
                &stamp,
                &requested_by,
                &checked_targets,
                &structural_targets,
            );
            let findings = validate_warden_patrol_report_policy(&rendered);
            println!(
                "{{\"ok\":{},\"content\":\"{}\",\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                escape_json(&rendered),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "render-dreamer-pattern-report" => {
            let stamp = args.next().ok_or_else(|| "missing stamp".to_string())?;
            let requested_by = args
                .next()
                .ok_or_else(|| "missing requested_by".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let parts: Vec<&str> = content.split("\n===INPUT===\n").collect();
            if parts.len() != 3 {
                return Err("missing dreamer pattern render split markers".to_string());
            }
            let rendered = render_dreamer_pattern_report_policy(
                &stamp,
                &requested_by,
                parts[0],
                parts[1],
                parts[2],
            );
            let findings = validate_dreamer_pattern_report_policy(&rendered);
            println!(
                "{{\"ok\":{},\"content\":\"{}\",\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                escape_json(&rendered),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "render-dc-night-report" => {
            let stamp = args.next().ok_or_else(|| "missing stamp".to_string())?;
            let requested_by = args
                .next()
                .ok_or_else(|| "missing requested_by".to_string())?;
            let patrol_report_target = args
                .next()
                .ok_or_else(|| "missing patrol report target".to_string())?;
            let files_checked = args
                .next()
                .ok_or_else(|| "missing files checked".to_string())?
                .parse::<usize>()
                .map_err(|err| format!("invalid files checked: {err}"))?;
            let structural_flags_count = args
                .next()
                .ok_or_else(|| "missing structural flags count".to_string())?
                .parse::<usize>()
                .map_err(|err| format!("invalid structural flags count: {err}"))?;
            let dreamer_report_target = args
                .next()
                .ok_or_else(|| "missing dreamer report target".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let parts: Vec<&str> = content.split("\n===INPUT===\n").collect();
            if parts.len() != 4 {
                return Err("missing dc night render split markers".to_string());
            }
            let rendered = render_dc_night_report_policy(
                &stamp,
                &requested_by,
                &patrol_report_target,
                files_checked,
                structural_flags_count,
                parts[0],
                parts[1],
                parts[2],
                &dreamer_report_target,
                parts[3],
            );
            let findings = validate_dc_night_report_policy(&rendered);
            println!(
                "{{\"ok\":{},\"content\":\"{}\",\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                escape_json(&rendered),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "render-dreamer-proposal" => {
            let created = args.next().ok_or_else(|| "missing created".to_string())?;
            let stamp = args.next().ok_or_else(|| "missing stamp".to_string())?;
            let requested_by = args
                .next()
                .ok_or_else(|| "missing requested_by".to_string())?;
            let reason = args.next().ok_or_else(|| "missing reason".to_string())?;
            let count = args
                .next()
                .ok_or_else(|| "missing count".to_string())?
                .parse::<usize>()
                .map_err(|err| format!("invalid count: {err}"))?;
            let mut blocked_items_json = String::new();
            io::stdin()
                .read_to_string(&mut blocked_items_json)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let rendered = render_dreamer_proposal_policy(
                &created,
                &stamp,
                &requested_by,
                &reason,
                count,
                &blocked_items_json,
            );
            println!("{{\"ok\":true,\"content\":\"{}\"}}", escape_json(&rendered));
        }
        "render-dreamer-follow-up" => {
            let created = args.next().ok_or_else(|| "missing created".to_string())?;
            let proposal_target = args
                .next()
                .ok_or_else(|| "missing proposal target".to_string())?;
            let reason = args.next().ok_or_else(|| "missing reason".to_string())?;
            let classification = args
                .next()
                .ok_or_else(|| "missing classification".to_string())?;
            let actor = args.next().ok_or_else(|| "missing actor".to_string())?;
            let rendered = render_dreamer_follow_up_policy(
                &created,
                &proposal_target,
                &reason,
                &classification,
                &actor,
            );
            println!("{{\"ok\":true,\"content\":\"{}\"}}", escape_json(&rendered));
        }
        "render-dreamer-execution-artifact" => {
            let created = args.next().ok_or_else(|| "missing created".to_string())?;
            let follow_up_target = args
                .next()
                .ok_or_else(|| "missing follow up target".to_string())?;
            let actor = args.next().ok_or_else(|| "missing actor".to_string())?;
            let kind = args.next().ok_or_else(|| "missing kind".to_string())?;
            let follow_up_reason = args
                .next()
                .ok_or_else(|| "missing follow up reason".to_string())?;
            let queue_name = args
                .next()
                .ok_or_else(|| "missing queue name".to_string())?;
            let execution_reason = args
                .next()
                .ok_or_else(|| "missing execution reason".to_string())?;
            let rendered = render_dreamer_execution_artifact_policy(
                &created,
                &follow_up_target,
                &actor,
                &kind,
                &follow_up_reason,
                &queue_name,
                &execution_reason,
            );
            let findings = validate_dreamer_execution_artifact_policy(&rendered);
            println!(
                "{{\"ok\":{},\"content\":\"{}\",\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                escape_json(&rendered),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "inspect-dreamer-proposal" => {
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            println!(
                "{{\"ok\":true,\"reason\":\"{}\"}}",
                escape_json(&dreamer_proposal_reason_policy(&content))
            );
        }
        "list-dreamer-queue" => {
            let repo_root = env::current_dir()
                .map_err(|err| format!("failed reading current dir: {err}"))?
                .to_string_lossy()
                .to_string();
            let items = list_dreamer_proposals_policy(&repo_root);
            println!(
                "{{\"ok\":true,\"items\":[{}]}}",
                items
                    .iter()
                    .map(render_dreamer_proposal_summary)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "list-dreamer-follow-ups" => {
            let repo_root = env::current_dir()
                .map_err(|err| format!("failed reading current dir: {err}"))?
                .to_string_lossy()
                .to_string();
            let items = list_dreamer_follow_ups_policy(&repo_root);
            println!(
                "{{\"ok\":true,\"items\":[{}]}}",
                items
                    .iter()
                    .map(render_dreamer_follow_up_summary)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "inspect-dreamer-follow-up" => {
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let execution_target = dreamer_existing_execution_target_policy(&content)
                .map(|item| format!("\"{}\"", escape_json(&item)))
                .unwrap_or_else(|| "null".to_string());
            println!(
                "{{\"ok\":true,\"kind\":\"{}\",\"reason\":\"{}\",\"execution_target\":{}}}",
                escape_json(&dreamer_follow_up_kind_policy(&content)),
                escape_json(&dreamer_follow_up_reason_policy(&content)),
                execution_target
            );
        }
        "render-reviewed-dreamer-proposal" => {
            let decision = args.next().ok_or_else(|| "missing decision".to_string())?;
            let actor = args.next().ok_or_else(|| "missing actor".to_string())?;
            let reason = args.next().ok_or_else(|| "missing reason".to_string())?;
            let follow_up_target = args.next().unwrap_or_default();
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let rendered = render_reviewed_dreamer_proposal_policy(
                &content,
                &decision,
                &actor,
                &reason,
                if follow_up_target.is_empty() {
                    None
                } else {
                    Some(follow_up_target.as_str())
                },
            );
            println!("{{\"ok\":true,\"content\":\"{}\"}}", escape_json(&rendered));
        }
        "render-applied-dreamer-follow-up" => {
            let actor = args.next().ok_or_else(|| "missing actor".to_string())?;
            let reason = args.next().ok_or_else(|| "missing reason".to_string())?;
            let execution_target = args
                .next()
                .ok_or_else(|| "missing execution target".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let rendered = render_applied_dreamer_follow_up_policy(
                &content,
                &actor,
                &reason,
                &execution_target,
            );
            println!("{{\"ok\":true,\"content\":\"{}\"}}", escape_json(&rendered));
        }
        "plan-dreamer-review" => {
            let target = args.next().ok_or_else(|| "missing target".to_string())?;
            let decision = args.next().ok_or_else(|| "missing decision".to_string())?;
            let actor = args.next().ok_or_else(|| "missing actor".to_string())?;
            let reason = args.next().ok_or_else(|| "missing reason".to_string())?;
            let created = args.next().ok_or_else(|| "missing created".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (plan, findings) =
                plan_dreamer_review_policy(&target, &content, &decision, &actor, &reason, &created);
            println!(
                "{{\"ok\":{},\"plan\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                plan.as_ref()
                    .map(render_dreamer_review_plan)
                    .unwrap_or_else(|| "null".to_string()),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "plan-dreamer-follow-up-apply" => {
            let target = args.next().ok_or_else(|| "missing target".to_string())?;
            let actor = args.next().ok_or_else(|| "missing actor".to_string())?;
            let reason = args.next().ok_or_else(|| "missing reason".to_string())?;
            let created = args.next().ok_or_else(|| "missing created".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (plan, findings) =
                plan_dreamer_follow_up_apply_policy(&target, &content, &actor, &reason, &created);
            println!(
                "{{\"ok\":{},\"plan\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                plan.as_ref()
                    .map(render_dreamer_apply_plan)
                    .unwrap_or_else(|| "null".to_string()),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "plan-warden-patrol" => {
            let stamp = args.next().ok_or_else(|| "missing stamp".to_string())?;
            let requested_by = args
                .next()
                .ok_or_else(|| "missing requested_by".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (checked_targets_json, structural_flag_targets_json) = content
                .split_once("\n===INPUT===\n")
                .ok_or_else(|| "missing patrol plan split marker".to_string())?;
            let (plan, findings) = plan_warden_patrol_policy(
                &stamp,
                &requested_by,
                checked_targets_json,
                structural_flag_targets_json,
            );
            println!(
                "{{\"ok\":{},\"plan\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                plan.as_ref()
                    .map(render_patrol_plan)
                    .unwrap_or_else(|| "null".to_string()),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "plan-night-cycle" => {
            let stamp = args.next().ok_or_else(|| "missing stamp".to_string())?;
            let requested_by = args
                .next()
                .ok_or_else(|| "missing requested_by".to_string())?;
            let patrol_report_target = args
                .next()
                .ok_or_else(|| "missing patrol report target".to_string())?;
            let files_checked = args
                .next()
                .ok_or_else(|| "missing files checked".to_string())?
                .parse::<usize>()
                .map_err(|err| format!("invalid files checked: {err}"))?;
            let structural_flags_count = args
                .next()
                .ok_or_else(|| "missing structural flags count".to_string())?
                .parse::<usize>()
                .map_err(|err| format!("invalid structural flags count: {err}"))?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let parts: Vec<&str> = content.split("\n===INPUT===\n").collect();
            if parts.len() != 4 {
                return Err("missing night-cycle plan split markers".to_string());
            }
            let (plan, findings) = plan_night_cycle_policy(
                &stamp,
                &requested_by,
                &patrol_report_target,
                files_checked,
                structural_flags_count,
                parts[0],
                parts[1],
                parts[2],
                parts[3],
            );
            println!(
                "{{\"ok\":{},\"plan\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                plan.as_ref()
                    .map(render_night_cycle_plan)
                    .unwrap_or_else(|| "null".to_string()),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "plan-operation-start" => {
            let name = args.next().ok_or_else(|| "missing name".to_string())?;
            let requested_by = args
                .next()
                .ok_or_else(|| "missing requested_by".to_string())?;
            let started_at = args
                .next()
                .ok_or_else(|| "missing started_at".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (plan, findings) =
                plan_operation_start_policy(&content, &name, &requested_by, &started_at);
            println!(
                "{{\"ok\":{},\"plan\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                plan.as_ref()
                    .map(render_operation_lifecycle_plan)
                    .unwrap_or_else(|| "null".to_string()),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "plan-operation-state-update" => {
            let name = args.next().ok_or_else(|| "missing name".to_string())?;
            let status = args.next().ok_or_else(|| "missing status".to_string())?;
            let requested_by = args
                .next()
                .ok_or_else(|| "missing requested_by".to_string())?;
            let started_at = args.next().unwrap_or_default();
            let completed_at = args.next().unwrap_or_default();
            let last_report_target = args.next().unwrap_or_default();
            let last_error = args.next().unwrap_or_default();
            let increment_runs = parse_bool(&args.next().unwrap_or_else(|| "false".to_string()))?;
            let release_lock = parse_bool(&args.next().unwrap_or_else(|| "false".to_string()))?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (plan, findings) = plan_operation_state_update_policy(
                &content,
                &name,
                &status,
                &requested_by,
                if started_at.is_empty() {
                    None
                } else {
                    Some(started_at.as_str())
                },
                if completed_at.is_empty() {
                    None
                } else {
                    Some(completed_at.as_str())
                },
                if last_report_target.is_empty() {
                    None
                } else {
                    Some(last_report_target.as_str())
                },
                if last_error.is_empty() {
                    None
                } else {
                    Some(last_error.as_str())
                },
                increment_runs,
                release_lock,
            );
            println!(
                "{{\"ok\":{},\"plan\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                plan.as_ref()
                    .map(render_operation_lifecycle_plan)
                    .unwrap_or_else(|| "null".to_string()),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "plan-scheduler-run" => {
            let name = args.next().ok_or_else(|| "missing name".to_string())?;
            let requested_by = args
                .next()
                .ok_or_else(|| "missing requested_by".to_string())?;
            let interval_seconds = args
                .next()
                .ok_or_else(|| "missing interval_seconds".to_string())?
                .parse::<i64>()
                .map_err(|err| format!("invalid interval_seconds: {err}"))?;
            let max_runs = args
                .next()
                .ok_or_else(|| "missing max_runs".to_string())?
                .parse::<i32>()
                .map_err(|err| format!("invalid max_runs: {err}"))?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (plan, findings) = plan_scheduler_run_policy(
                &content,
                &name,
                &requested_by,
                interval_seconds,
                max_runs,
            );
            println!(
                "{{\"ok\":{},\"plan\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                plan.as_ref()
                    .map(render_scheduler_plan)
                    .unwrap_or_else(|| "null".to_string()),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "plan-operation-audit-event" => {
            let kind = args.next().ok_or_else(|| "missing kind".to_string())?;
            let event_id = args.next().ok_or_else(|| "missing event_id".to_string())?;
            let timestamp = args.next().ok_or_else(|| "missing timestamp".to_string())?;
            let target = args.next().ok_or_else(|| "missing target".to_string())?;
            let reason = args.next().ok_or_else(|| "missing reason".to_string())?;
            let approval_required = parse_bool(
                &args
                    .next()
                    .ok_or_else(|| "missing approval_required".to_string())?,
            )?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (artifacts_json, validation_summary_json) = content
                .split_once("\n===SUMMARY===\n")
                .ok_or_else(|| "missing summary split marker".to_string())?;
            let (plan, findings) = plan_operation_audit_event_policy(
                &kind,
                &event_id,
                &timestamp,
                &target,
                &reason,
                artifacts_json,
                validation_summary_json,
                approval_required,
            );
            println!(
                "{{\"ok\":{},\"plan\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                plan.as_ref()
                    .map(render_event_append_plan)
                    .unwrap_or_else(|| "null".to_string()),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "plan-dreamer-proposals" => {
            let stamp = args.next().ok_or_else(|| "missing stamp".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let items = plan_dreamer_proposals_policy(&stamp, &content);
            println!(
                "{{\"ok\":true,\"items\":[{}]}}",
                items
                    .iter()
                    .map(render_dreamer_proposal_candidate)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "extract-blocked-items" => {
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let items = extract_blocked_items_policy(&content);
            println!(
                "{{\"ok\":true,\"items\":[{}]}}",
                items
                    .iter()
                    .map(render_blocked_item_summary)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "extract-patch-targets" => {
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let items = extract_patch_targets_policy(&content);
            println!(
                "{{\"ok\":true,\"items\":[{}]}}",
                items
                    .iter()
                    .map(render_patch_target)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "list-growth-targets" => {
            let repo_root = env::current_dir()
                .map_err(|err| format!("failed to determine repo root: {err}"))?
                .to_string_lossy()
                .to_string();
            let items = list_growth_targets_policy(std::path::Path::new(&repo_root));
            println!(
                "{{\"ok\":true,\"items\":[{}]}}",
                items
                    .iter()
                    .map(render_growth_target)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "validate-config" => {
            let owner_name = args
                .next()
                .ok_or_else(|| "missing owner name".to_string())?;
            let primary_provider = args
                .next()
                .ok_or_else(|| "missing primary provider".to_string())?;
            let primary_model = args
                .next()
                .ok_or_else(|| "missing primary model".to_string())?;
            let deployment_target = args
                .next()
                .ok_or_else(|| "missing deployment target".to_string())?;
            let assistant_choice = args
                .next()
                .ok_or_else(|| "missing assistant choice".to_string())?;
            let relationship_stance = args
                .next()
                .ok_or_else(|| "missing relationship stance".to_string())?;
            let support_critique_balance = args
                .next()
                .ok_or_else(|| "missing support critique balance".to_string())?;
            let subjectivity_boundaries = args
                .next()
                .ok_or_else(|| "missing subjectivity boundaries".to_string())?;
            let project_name = args
                .next()
                .ok_or_else(|| "missing project name".to_string())?;
            let default_profile = args
                .next()
                .ok_or_else(|| "missing default profile".to_string())?;
            let active_profile = args
                .next()
                .ok_or_else(|| "missing active profile".to_string())?;
            let allow_replacement = parse_bool(
                &args
                    .next()
                    .ok_or_else(|| "missing allow replacement".to_string())?,
            )?;
            let allow_multiple_profiles = parse_bool(
                &args
                    .next()
                    .ok_or_else(|| "missing allow multiple profiles".to_string())?,
            )?;
            let setup_complete = parse_bool(
                &args
                    .next()
                    .ok_or_else(|| "missing setup complete".to_string())?,
            )?;

            let config = build_runtime_config(
                &owner_name,
                &primary_provider,
                &primary_model,
                &deployment_target,
                setup_complete,
                parse_system_identity(
                    &project_name,
                    &default_profile,
                    &active_profile,
                    allow_replacement,
                    allow_multiple_profiles,
                ),
                OnboardingConfig {
                    assistant_choice,
                    relationship_stance,
                    support_critique_balance,
                    subjectivity_boundaries,
                },
            );

            let findings = validate_runtime_config(&config);
            let missing = missing_required_fields(&config);
            println!(
                "{{\"ok\":{},\"setup_required\":{},\"missing_fields\":[{}],\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                if !missing.is_empty() { "true" } else { "false" },
                missing
                    .iter()
                    .map(|item| format!("\"{}\"", escape_json(item)))
                    .collect::<Vec<String>>()
                    .join(","),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "validate-event" => {
            let event_id = args.next().ok_or_else(|| "missing event id".to_string())?;
            let timestamp = args.next().ok_or_else(|| "missing timestamp".to_string())?;
            let source = args.next().ok_or_else(|| "missing source".to_string())?;
            let endpoint = args.next().ok_or_else(|| "missing endpoint".to_string())?;
            let actor = args.next().ok_or_else(|| "missing actor".to_string())?;
            let target = args.next().ok_or_else(|| "missing target".to_string())?;
            let status = args.next().ok_or_else(|| "missing status".to_string())?;
            let reason = args.next().ok_or_else(|| "missing reason".to_string())?;

            let event = EventRecord {
                event_id,
                timestamp,
                source,
                endpoint,
                actor,
                target,
                status,
                reason,
                artifacts: Vec::new(),
                approval_required: false,
                validation_summary: ValidationSummary {
                    finding_codes: Vec::new(),
                    blocking: false,
                },
            };
            let findings = validate_event_record(&event);
            println!(
                "{{\"ok\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "render-event" => {
            let event_id = args.next().ok_or_else(|| "missing event id".to_string())?;
            let timestamp = args.next().ok_or_else(|| "missing timestamp".to_string())?;
            let source = args.next().ok_or_else(|| "missing source".to_string())?;
            let endpoint = args.next().ok_or_else(|| "missing endpoint".to_string())?;
            let actor = args.next().ok_or_else(|| "missing actor".to_string())?;
            let target = args.next().ok_or_else(|| "missing target".to_string())?;
            let status = args.next().ok_or_else(|| "missing status".to_string())?;
            let reason = args.next().ok_or_else(|| "missing reason".to_string())?;
            let approval_required = parse_bool(
                &args
                    .next()
                    .ok_or_else(|| "missing approval required".to_string())?,
            )?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (artifacts_json, validation_summary_json) = content
                .split_once("\n===SUMMARY===\n")
                .ok_or_else(|| "missing event render split marker".to_string())?;
            let event = EventRecord {
                event_id,
                timestamp,
                source,
                endpoint,
                actor,
                target,
                status,
                reason,
                artifacts: Vec::new(),
                approval_required,
                validation_summary: ValidationSummary {
                    finding_codes: Vec::new(),
                    blocking: false,
                },
            };
            let findings = validate_event_record(&event);
            println!(
                "{{\"ok\":{},\"line\":\"{}\",\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                escape_json(&render_event_record_json(
                    &event,
                    artifacts_json,
                    validation_summary_json,
                )),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "plan-event-append" => {
            let event_id = args.next().ok_or_else(|| "missing event id".to_string())?;
            let timestamp = args.next().ok_or_else(|| "missing timestamp".to_string())?;
            let source = args.next().ok_or_else(|| "missing source".to_string())?;
            let endpoint = args.next().ok_or_else(|| "missing endpoint".to_string())?;
            let actor = args.next().ok_or_else(|| "missing actor".to_string())?;
            let target = args.next().ok_or_else(|| "missing target".to_string())?;
            let status = args.next().ok_or_else(|| "missing status".to_string())?;
            let reason = args.next().ok_or_else(|| "missing reason".to_string())?;
            let approval_required = parse_bool(
                &args
                    .next()
                    .ok_or_else(|| "missing approval required".to_string())?,
            )?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (artifacts_json, validation_summary_json) = content
                .split_once("\n===SUMMARY===\n")
                .ok_or_else(|| "missing event append split marker".to_string())?;
            let event = EventRecord {
                event_id,
                timestamp,
                source,
                endpoint,
                actor,
                target,
                status,
                reason,
                artifacts: Vec::new(),
                approval_required,
                validation_summary: ValidationSummary {
                    finding_codes: Vec::new(),
                    blocking: false,
                },
            };
            let (plan, findings) =
                plan_event_append(&event, artifacts_json, validation_summary_json);
            println!(
                "{{\"ok\":{},\"plan\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                plan.as_ref()
                    .map(render_event_append_plan)
                    .unwrap_or_else(|| "null".to_string()),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "analyze-release" => {
            let repo = args.next().ok_or_else(|| "missing repo".to_string())?;
            let version = args.next().ok_or_else(|| "missing version".to_string())?;
            let notes = args.next().ok_or_else(|| "missing notes".to_string())?;
            let context = args.next().unwrap_or_default();
            let context_markers: Vec<String> = if context.is_empty() {
                Vec::new()
            } else {
                context
                    .split(',')
                    .filter(|item| !item.is_empty())
                    .map(|item| item.to_string())
                    .collect()
            };
            let mut watchlist = String::new();
            io::stdin()
                .read_to_string(&mut watchlist)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let assessment = assess_release(&repo, &notes, &watchlist, &context_markers);
            println!(
                "{{\"ok\":true,\"repo\":\"{}\",\"version\":\"{}\",\"watched\":{},\"risk\":{{\"level\":\"{}\",\"signals\":[{}]}},\"relevance\":{{\"level\":\"{}\",\"signals\":[{}],\"watch_reason\":\"{}\"}},\"local_impact\":{{\"level\":\"{}\",\"signals\":[{}],\"context_markers\":[{}]}}}}",
                escape_json(&repo),
                escape_json(&version),
                if assessment.watched { "true" } else { "false" },
                escape_json(&assessment.risk_level),
                assessment
                    .risk_signals
                    .iter()
                    .map(|item| format!("\"{}\"", escape_json(item)))
                    .collect::<Vec<String>>()
                    .join(","),
                escape_json(&assessment.relevance_level),
                assessment
                    .relevance_signals
                    .iter()
                    .map(|item| format!("\"{}\"", escape_json(item)))
                    .collect::<Vec<String>>()
                    .join(","),
                escape_json(&assessment.watch_reason),
                escape_json(&assessment.impact_level),
                assessment
                    .impact_signals
                    .iter()
                    .map(|item| format!("\"{}\"", escape_json(item)))
                    .collect::<Vec<String>>()
                    .join(","),
                context_markers
                    .iter()
                    .map(|item| format!("\"{}\"", escape_json(item)))
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "inspect-reference" => {
            let path = args.next().ok_or_else(|| "missing path".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let (reference, findings) = inspect_reference(&path, &content);
            let reference_json = reference
                .map(|item| {
                    format!(
                        "{{\"path\":\"{}\",\"title\":\"{}\",\"ref_type\":\"{}\",\"parent\":\"{}\",\"domain\":\"{}\",\"status\":\"{}\"}}",
                        escape_json(&item.path),
                        escape_json(&item.title),
                        escape_json(&item.ref_type),
                        escape_json(&item.parent),
                        escape_json(&item.domain),
                        escape_json(&item.status),
                    )
                })
                .unwrap_or_else(|| "null".to_string());
            println!(
                "{{\"ok\":{},\"reference\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                reference_json,
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "validate-parent" => {
            let path = args.next().ok_or_else(|| "missing path".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let findings = validate_matrix_parent_consistency(&path, &content);
            println!(
                "{{\"ok\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "validate-sot" => {
            let path = args.next().ok_or_else(|| "missing path".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;
            let findings = validate_matrix_sot_structure(&path, &content);
            println!(
                "{{\"ok\":{},\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        "render-matrix-index" => {
            let root = args.next().ok_or_else(|| "missing repo root".to_string())?;
            let root = std::path::Path::new(&root);
            let (entries, references, findings, markdown, snapshot_json) = build_matrix_index(root);
            println!(
                "{{\"ok\":true,\"markdown\":\"{}\",\"snapshot_json\":\"{}\",\"entries\":{},\"references\":{},\"findings\":[{}]}}",
                escape_json(&markdown),
                escape_json(&snapshot_json),
                entries.len(),
                references.len(),
                findings.iter().map(render_finding).collect::<Vec<String>>().join(",")
            );
        }
        "inventory" => {
            let root = args.next().ok_or_else(|| "missing repo root".to_string())?;
            let root = std::path::Path::new(&root);
            let (entries, references, findings) = discover_matrix_inventory(root);
            println!(
                "{{\"ok\":{},\"entries\":[{}],\"references\":[{}],\"findings\":[{}]}}",
                if !has_blocking_findings(&findings) {
                    "true"
                } else {
                    "false"
                },
                entries
                    .iter()
                    .map(render_matrix_sot)
                    .collect::<Vec<String>>()
                    .join(","),
                references
                    .iter()
                    .map(render_reference)
                    .collect::<Vec<String>>()
                    .join(","),
                findings
                    .iter()
                    .map(render_finding)
                    .collect::<Vec<String>>()
                    .join(",")
            );
        }
        other => return Err(format!("unknown command: {other}")),
    }

    Ok(())
}

fn extract_json_string_list(text: &str) -> Vec<String> {
    let trimmed = text.trim();
    if trimmed.len() < 2 || !trimmed.starts_with('[') || !trimmed.ends_with(']') {
        return Vec::new();
    }
    let inner = &trimmed[1..trimmed.len() - 1];
    if inner.trim().is_empty() {
        return Vec::new();
    }
    inner
        .split(',')
        .filter_map(|part| {
            let item = part.trim().trim_matches('"');
            if item.is_empty() {
                None
            } else {
                Some(item.to_string())
            }
        })
        .collect()
}

fn parse_bool(value: &str) -> Result<bool, String> {
    match value {
        "true" => Ok(true),
        "false" => Ok(false),
        _ => Err(format!("invalid boolean value: {value}")),
    }
}

fn print_findings(findings: &[ValidationFinding], route: Option<&str>) {
    let route_json = route
        .map(|item| format!("\"{}\"", escape_json(item)))
        .unwrap_or_else(|| "null".to_string());
    println!(
        "{{\"ok\":{},\"route\":{},\"findings\":[{}]}}",
        if !has_blocking_findings(findings) {
            "true"
        } else {
            "false"
        },
        route_json,
        findings
            .iter()
            .map(render_finding)
            .collect::<Vec<String>>()
            .join(",")
    );
}

fn render_finding(finding: &ValidationFinding) -> String {
    format!(
        "{{\"code\":\"{}\",\"detail\":\"{}\",\"severity\":\"{}\",\"rule_refs\":[{}]}}",
        escape_json(&finding.code),
        escape_json(&finding.detail),
        severity_label(&finding.severity),
        finding
            .rule_refs
            .iter()
            .map(|item| format!("\"{}\"", escape_json(item)))
            .collect::<Vec<String>>()
            .join(",")
    )
}

fn render_dreamer_action(action: &vela_core::models::DreamerAction) -> String {
    format!(
        "{{\"follow_up_target\":\"{}\",\"execution_target\":\"{}\",\"pattern_reason\":\"{}\",\"actor\":\"{}\",\"execution_reason\":\"{}\",\"applied_at\":\"{}\",\"status\":\"{}\"}}",
        escape_json(&action.follow_up_target),
        escape_json(&action.execution_target),
        escape_json(&action.pattern_reason),
        escape_json(&action.actor),
        escape_json(&action.execution_reason),
        escape_json(&action.applied_at),
        escape_json(&action.status),
    )
}

fn render_dreamer_proposal_summary(item: &vela_core::models::DreamerProposalSummary) -> String {
    format!(
        "{{\"target\":\"{}\",\"status\":\"{}\",\"created\":\"{}\",\"reason\":\"{}\"}}",
        escape_json(&item.target),
        escape_json(&item.status),
        escape_json(&item.created),
        escape_json(&item.reason),
    )
}

fn render_dreamer_proposal_candidate(item: &DreamerProposalCandidate) -> String {
    format!(
        "{{\"target\":\"{}\",\"reason\":\"{}\",\"count\":{}}}",
        escape_json(&item.target),
        escape_json(&item.reason),
        item.count,
    )
}

fn render_blocked_item_summary(item: &BlockedItemSummary) -> String {
    format!(
        "{{\"target\":\"{}\",\"reason\":\"{}\",\"actor\":\"{}\",\"endpoint\":\"{}\"}}",
        escape_json(&item.target),
        escape_json(&item.reason),
        escape_json(&item.actor),
        escape_json(&item.endpoint),
    )
}

fn render_patch_target(item: &PatchTarget) -> String {
    format!("{{\"path\":\"{}\"}}", escape_json(&item.path))
}

fn render_growth_target(item: &GrowthTarget) -> String {
    format!(
        "{{\"path\":\"{}\",\"inventory_role\":\"{}\"}}",
        escape_json(&item.path),
        escape_json(&item.inventory_role),
    )
}

fn render_dreamer_follow_up_summary(item: &vela_core::models::DreamerFollowUpSummary) -> String {
    format!(
        "{{\"target\":\"{}\",\"status\":\"{}\",\"created\":\"{}\",\"kind\":\"{}\",\"reason\":\"{}\"}}",
        escape_json(&item.target),
        escape_json(&item.status),
        escape_json(&item.created),
        escape_json(&item.kind),
        escape_json(&item.reason),
    )
}

fn render_dreamer_review_plan(item: &vela_core::models::DreamerReviewPlan) -> String {
    format!(
        "{{\"target\":\"{}\",\"decision\":\"{}\",\"follow_up_target\":\"{}\",\"follow_up_kind\":\"{}\",\"updated_content\":\"{}\",\"follow_up_content\":\"{}\"}}",
        escape_json(&item.target),
        escape_json(&item.decision),
        escape_json(&item.follow_up_target),
        escape_json(&item.follow_up_kind),
        escape_json(&item.updated_content),
        escape_json(&item.follow_up_content),
    )
}

fn render_dreamer_apply_plan(item: &vela_core::models::DreamerApplyPlan) -> String {
    format!(
        "{{\"target\":\"{}\",\"kind\":\"{}\",\"execution_target\":\"{}\",\"execution_content\":\"{}\",\"updated_follow_up_content\":\"{}\",\"already_applied\":{}}}",
        escape_json(&item.target),
        escape_json(&item.kind),
        escape_json(&item.execution_target),
        escape_json(&item.execution_content),
        escape_json(&item.updated_follow_up_content),
        if item.already_applied { "true" } else { "false" },
    )
}

fn render_event_append_plan(item: &vela_core::models::EventAppendPlan) -> String {
    format!(
        "{{\"line\":\"{}\",\"event_id\":\"{}\",\"timestamp\":\"{}\"}}",
        escape_json(&item.line),
        escape_json(&item.event_id),
        escape_json(&item.timestamp),
    )
}

fn render_patrol_plan(item: &vela_core::models::PatrolPlan) -> String {
    format!(
        "{{\"report_target\":\"{}\",\"report_content\":\"{}\",\"files_checked\":{},\"structural_flags_count\":{}}}",
        escape_json(&item.report_target),
        escape_json(&item.report_content),
        item.files_checked,
        item.structural_flags_count,
    )
}

fn render_night_cycle_plan(item: &vela_core::models::NightCyclePlan) -> String {
    format!(
        "{{\"report_target\":\"{}\",\"report_content\":\"{}\",\"dreamer_report_target\":\"{}\",\"dreamer_report_content\":\"{}\",\"growth_candidates_count\":{},\"blocked_items_count\":{}}}",
        escape_json(&item.report_target),
        escape_json(&item.report_content),
        escape_json(&item.dreamer_report_target),
        escape_json(&item.dreamer_report_content),
        item.growth_candidates_count,
        item.blocked_items_count,
    )
}

fn render_operation_lifecycle_plan(item: &OperationLifecyclePlan) -> String {
    format!(
        "{{\"state_json\":\"{}\",\"state_status\":\"{}\",\"lock_target\":\"{}\",\"lock_content\":\"{}\",\"release_lock\":{}}}",
        escape_json(&item.state_json),
        escape_json(&item.state_status),
        escape_json(&item.lock_target),
        escape_json(&item.lock_content),
        if item.release_lock { "true" } else { "false" },
    )
}

fn render_scheduler_plan(item: &SchedulerPlan) -> String {
    format!(
        "{{\"operation\":\"{}\",\"requested_by\":\"{}\",\"interval_seconds\":{},\"max_runs\":{},\"unbounded\":{},\"current_status\":\"{}\"}}",
        escape_json(&item.operation),
        escape_json(&item.requested_by),
        item.interval_seconds,
        item.max_runs,
        if item.unbounded { "true" } else { "false" },
        escape_json(&item.current_status),
    )
}

fn print_dreamer_registry(
    registry: &vela_core::models::DreamerActionRegistry,
    findings: &[ValidationFinding],
) {
    println!(
        "{{\"ok\":{},\"registry\":{{\"validator_changes\":[{}],\"workflow_changes\":[{}],\"refusal_tightenings\":[{}]}},\"findings\":[{}]}}",
        if !has_blocking_findings(findings) { "true" } else { "false" },
        registry.validator_changes.iter().map(render_dreamer_action).collect::<Vec<String>>().join(","),
        registry.workflow_changes.iter().map(render_dreamer_action).collect::<Vec<String>>().join(","),
        registry.refusal_tightenings.iter().map(render_dreamer_action).collect::<Vec<String>>().join(","),
        findings.iter().map(render_finding).collect::<Vec<String>>().join(",")
    );
}

fn render_operation_state_entry(entry: &OperationStateEntry) -> String {
    format!(
        "{{\"status\":\"{}\",\"last_started\":\"{}\",\"last_completed\":\"{}\",\"last_report_target\":\"{}\",\"last_error\":\"{}\",\"requested_by\":\"{}\",\"run_count\":{}}}",
        escape_json(&entry.status),
        escape_json(&entry.last_started),
        escape_json(&entry.last_completed),
        escape_json(&entry.last_report_target),
        escape_json(&entry.last_error),
        escape_json(&entry.requested_by),
        entry.run_count,
    )
}

fn print_operations_state(state: &OperationsState, findings: &[ValidationFinding]) {
    println!(
        "{{\"ok\":{},\"state\":{{\"patrol\":{},\"night-cycle\":{}}},\"findings\":[{}]}}",
        if !has_blocking_findings(findings) {
            "true"
        } else {
            "false"
        },
        render_operation_state_entry(&state.patrol),
        render_operation_state_entry(&state.night_cycle),
        findings
            .iter()
            .map(render_finding)
            .collect::<Vec<String>>()
            .join(",")
    );
}

fn render_operation_lock(record: &OperationLockRecord) -> String {
    format!(
        "{{\"name\":\"{}\",\"requested_by\":\"{}\",\"started_at\":\"{}\"}}",
        escape_json(&record.name),
        escape_json(&record.requested_by),
        escape_json(&record.started_at),
    )
}

fn render_matrix_sot(item: &vela_core::models::MatrixSoT) -> String {
    format!(
        "{{\"path\":\"{}\",\"title\":\"{}\",\"sot_type\":\"{}\",\"inventory_role\":\"{}\",\"parent\":\"{}\",\"domain\":\"{}\",\"status\":\"{}\",\"area\":\"{}\",\"is_cornerstone\":{}}}",
        escape_json(&item.path),
        escape_json(&item.title),
        escape_json(&item.sot_type),
        escape_json(&item.inventory_role),
        escape_json(&item.parent),
        escape_json(&item.domain),
        escape_json(&item.status),
        escape_json(&item.area),
        if item.is_cornerstone { "true" } else { "false" },
    )
}

fn render_reference(item: &vela_core::models::GovernedReference) -> String {
    format!(
        "{{\"path\":\"{}\",\"title\":\"{}\",\"ref_type\":\"{}\",\"inventory_role\":\"{}\",\"parent\":\"{}\",\"domain\":\"{}\",\"status\":\"{}\"}}",
        escape_json(&item.path),
        escape_json(&item.title),
        escape_json(&item.ref_type),
        escape_json(&item.inventory_role),
        escape_json(&item.parent),
        escape_json(&item.domain),
        escape_json(&item.status),
    )
}

fn severity_label(severity: &Severity) -> &'static str {
    match severity {
        Severity::Info => "info",
        Severity::Warning => "warning",
        Severity::Error => "error",
    }
}

fn escape_json(value: &str) -> String {
    let mut escaped = String::new();
    for ch in value.chars() {
        match ch {
            '\\' => escaped.push_str("\\\\"),
            '"' => escaped.push_str("\\\""),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            _ => escaped.push(ch),
        }
    }
    escaped
}
