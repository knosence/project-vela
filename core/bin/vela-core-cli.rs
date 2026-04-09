use std::env;
use std::io::{self, Read};

use vela_core::events::{validate_event_record, EventRecord, ValidationSummary};
use vela_core::models::{OnboardingConfig, Severity, ValidationFinding};
use vela_core::parser::{build_runtime_config, parse_system_identity};
use vela_core::policy::{route_for_target, validate_commit_policy};
use vela_core::validator::{
    has_blocking_findings, missing_required_fields, validate_narrative_document, validate_runtime_config,
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
            let approval_status = args.next().ok_or_else(|| "missing approval status".to_string())?;
            let mut content = String::new();
            io::stdin()
                .read_to_string(&mut content)
                .map_err(|err| format!("failed reading stdin: {err}"))?;

            let mut findings = validate_narrative_document(&content);
            findings.extend(validate_commit_policy(&target, approval_status == "approved"));
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
        "validate-config" => {
            let owner_name = args.next().ok_or_else(|| "missing owner name".to_string())?;
            let primary_provider = args.next().ok_or_else(|| "missing primary provider".to_string())?;
            let primary_model = args.next().ok_or_else(|| "missing primary model".to_string())?;
            let deployment_target = args.next().ok_or_else(|| "missing deployment target".to_string())?;
            let assistant_choice = args.next().ok_or_else(|| "missing assistant choice".to_string())?;
            let relationship_stance = args.next().ok_or_else(|| "missing relationship stance".to_string())?;
            let support_critique_balance =
                args.next().ok_or_else(|| "missing support critique balance".to_string())?;
            let subjectivity_boundaries =
                args.next().ok_or_else(|| "missing subjectivity boundaries".to_string())?;
            let project_name = args.next().ok_or_else(|| "missing project name".to_string())?;
            let default_profile = args.next().ok_or_else(|| "missing default profile".to_string())?;
            let active_profile = args.next().ok_or_else(|| "missing active profile".to_string())?;
            let allow_replacement = parse_bool(&args.next().ok_or_else(|| "missing allow replacement".to_string())?)?;
            let allow_multiple_profiles =
                parse_bool(&args.next().ok_or_else(|| "missing allow multiple profiles".to_string())?)?;
            let setup_complete = parse_bool(&args.next().ok_or_else(|| "missing setup complete".to_string())?)?;

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
                if !has_blocking_findings(&findings) { "true" } else { "false" },
                if !missing.is_empty() { "true" } else { "false" },
                missing
                    .iter()
                    .map(|item| format!("\"{}\"", escape_json(item)))
                    .collect::<Vec<String>>()
                    .join(","),
                findings.iter().map(render_finding).collect::<Vec<String>>().join(",")
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
                if !has_blocking_findings(&findings) { "true" } else { "false" },
                findings.iter().map(render_finding).collect::<Vec<String>>().join(",")
            );
        }
        other => return Err(format!("unknown command: {other}")),
    }

    Ok(())
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
        if !has_blocking_findings(findings) { "true" } else { "false" },
        route_json,
        findings.iter().map(render_finding).collect::<Vec<String>>().join(",")
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
