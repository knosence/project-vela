use crate::models::{
    DreamerAction, DreamerActionRegistry, OperationLockRecord, OperationStateEntry,
    OperationsState, ValidationFinding,
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DreamerActionMatch {
    pub pattern_reason: String,
    pub status: String,
}

pub fn default_operations_state() -> OperationsState {
    OperationsState {
        patrol: default_operation_state_entry(),
        night_cycle: default_operation_state_entry(),
    }
}

pub fn parse_operations_state(state_json: &str) -> (OperationsState, Vec<ValidationFinding>) {
    let mut findings = Vec::new();
    let mut state = default_operations_state();
    let trimmed = state_json.trim();
    if trimmed.is_empty() || trimmed == "{}" {
        return (state, findings);
    }

    state.patrol = extract_operation_state_entry(trimmed, "patrol", &mut findings);
    state.night_cycle = extract_operation_state_entry(trimmed, "night-cycle", &mut findings);
    (state, findings)
}

pub fn update_operations_state(
    state_json: &str,
    name: &str,
    status: &str,
    requested_by: &str,
    started_at: Option<&str>,
    completed_at: Option<&str>,
    last_report_target: Option<&str>,
    last_error: Option<&str>,
    increment_runs: bool,
) -> (OperationsState, Vec<ValidationFinding>) {
    let (mut state, mut findings) = parse_operations_state(state_json);
    let Some(entry) = operation_state_entry_mut(&mut state, name) else {
        findings.push(ValidationFinding::error(
            "OPERATIONS_STATE_NAME_INVALID",
            format!("Unsupported operations state entry: {name}"),
        ));
        return (state, findings);
    };
    findings.extend(validate_operation_request(name, requested_by));
    findings.extend(validate_operation_state_transition(&entry.status, status));
    entry.status = status.to_string();
    entry.requested_by = requested_by.to_string();
    if let Some(value) = started_at {
        entry.last_started = value.to_string();
    }
    if let Some(value) = completed_at {
        entry.last_completed = value.to_string();
    }
    if let Some(value) = last_report_target {
        entry.last_report_target = value.to_string();
    }
    if let Some(value) = last_error {
        entry.last_error = value.to_string();
    }
    if increment_runs {
        entry.run_count += 1;
    }
    (state, findings)
}

pub fn validate_operation_lock(
    lock_json: &str,
    expected_name: &str,
) -> (Option<OperationLockRecord>, Vec<ValidationFinding>) {
    let trimmed = lock_json.trim();
    if trimmed.is_empty() {
        return (
            None,
            vec![ValidationFinding::error(
                "OPERATION_LOCK_INVALID",
                format!("Operation lock for `{expected_name}` is empty"),
            )],
        );
    }

    let record = OperationLockRecord {
        name: extract_json_string(trimmed, "name").unwrap_or_default(),
        requested_by: extract_json_string(trimmed, "requested_by").unwrap_or_default(),
        started_at: extract_json_string(trimmed, "started_at").unwrap_or_default(),
    };

    let mut findings = Vec::new();
    if record.name.is_empty() || record.requested_by.is_empty() || record.started_at.is_empty() {
        findings.push(ValidationFinding::error(
            "OPERATION_LOCK_INVALID",
            format!("Operation lock for `{expected_name}` is missing required fields"),
        ));
    } else if record.name != expected_name {
        findings.push(ValidationFinding::error(
            "OPERATION_LOCK_INVALID",
            format!(
                "Operation lock for `{expected_name}` contains mismatched operation `{}`",
                record.name
            ),
        ));
    }

    (
        if findings.is_empty() {
            Some(record)
        } else {
            None
        },
        findings,
    )
}

pub fn validate_operation_request(name: &str, requested_by: &str) -> Vec<ValidationFinding> {
    if !matches!(name, "patrol" | "night-cycle") {
        return vec![ValidationFinding::error(
            "OPERATIONS_STATE_NAME_INVALID",
            format!("Unsupported operation: {name}"),
        )];
    }

    let allowed = match name {
        "patrol" => {
            matches!(requested_by, "human" | "system" | "n8n")
                || requested_by
                    .strip_prefix("night-cycle:")
                    .map(|item| matches!(item, "human" | "system" | "n8n"))
                    .unwrap_or(false)
        }
        "night-cycle" => matches!(requested_by, "human" | "system" | "n8n"),
        _ => false,
    };

    if allowed {
        Vec::new()
    } else {
        vec![ValidationFinding::error(
            "OPERATION_REQUEST_NOT_ALLOWED",
            format!("Requester `{requested_by}` may not start operation `{name}`"),
        )]
    }
}

pub fn validate_operation_state_transition(
    current_status: &str,
    next_status: &str,
) -> Vec<ValidationFinding> {
    let current = if current_status.trim().is_empty() {
        "idle"
    } else {
        current_status
    };
    let allowed = match (current, next_status) {
        ("idle", "running" | "blocked") => true,
        ("running", "completed" | "blocked") => true,
        ("completed", "running" | "blocked") => true,
        ("blocked", "running" | "blocked") => true,
        _ => false,
    };

    if allowed {
        Vec::new()
    } else {
        vec![ValidationFinding::error(
            "OPERATION_STATE_TRANSITION_INVALID",
            format!("Operation state may not transition from `{current}` to `{next_status}`"),
        )]
    }
}

pub fn validate_dreamer_review(current_status: &str, decision: &str) -> Vec<ValidationFinding> {
    let mut findings = Vec::new();
    if !matches!(decision, "approved" | "denied" | "needs-more-info") {
        findings.push(ValidationFinding::error(
            "DREAMER_REVIEW_DECISION_INVALID",
            format!("Unsupported decision: {decision}"),
        ));
    }
    if !matches!(current_status, "proposed" | "unknown" | "") {
        findings.push(ValidationFinding::error(
            "DREAMER_PROPOSAL_STATUS_INVALID",
            format!("Dreamer proposal may not be reviewed from status `{current_status}`"),
        ));
    }
    findings
}

pub fn validate_dreamer_follow_up_apply(
    current_status: &str,
    actor: &str,
) -> Vec<ValidationFinding> {
    let mut findings = Vec::new();
    if !matches!(actor, "human" | "system") {
        findings.push(ValidationFinding::error(
            "DREAMER_FOLLOW_UP_ACTOR_NOT_ALLOWED",
            format!("Actor `{actor}` may not apply Dreamer follow ups."),
        ));
    }
    if !matches!(current_status, "proposed" | "applied") {
        findings.push(ValidationFinding::error(
            "DREAMER_FOLLOW_UP_STATUS_INVALID",
            format!("Dreamer follow up is not executable from status `{current_status}`."),
        ));
    }
    findings
}

pub fn classify_dreamer_follow_up(reason: &str) -> String {
    let lowered = reason.to_lowercase();
    if [
        "validator",
        "validation",
        "rule",
        "frontmatter",
        "structure",
    ]
    .iter()
    .any(|token| lowered.contains(token))
    {
        "validator-change".to_string()
    } else if ["workflow", "triage", "route", "pipeline", "queue"]
        .iter()
        .any(|token| lowered.contains(token))
    {
        "workflow-change".to_string()
    } else {
        "refusal-tightening".to_string()
    }
}

pub fn validate_dreamer_follow_up_kind(kind: &str) -> Vec<ValidationFinding> {
    if matches!(
        kind,
        "validator-change" | "workflow-change" | "refusal-tightening"
    ) {
        Vec::new()
    } else {
        vec![ValidationFinding::error(
            "DREAMER_FOLLOW_UP_KIND_INVALID",
            format!("Unsupported Dreamer follow up kind: {kind}"),
        )]
    }
}

pub fn dreamer_follow_up_registry_mode(kind: &str) -> Result<&'static str, Vec<ValidationFinding>> {
    let findings = validate_dreamer_follow_up_kind(kind);
    if !findings.is_empty() {
        return Err(findings);
    }
    Ok(match kind {
        "validator-change" => "validator",
        "workflow-change" => "workflow",
        "refusal-tightening" => "refusal",
        _ => unreachable!(),
    })
}

pub fn dreamer_follow_up_queue_name(kind: &str) -> Result<&'static str, Vec<ValidationFinding>> {
    let findings = validate_dreamer_follow_up_kind(kind);
    if !findings.is_empty() {
        return Err(findings);
    }
    Ok(match kind {
        "validator-change" => "Validator-Change-Queue",
        "workflow-change" => "Workflow-Change-Queue",
        "refusal-tightening" => "Refusal-Tightening-Queue",
        _ => unreachable!(),
    })
}

pub fn parse_dreamer_action_registry(
    registry_json: &str,
) -> (DreamerActionRegistry, Vec<ValidationFinding>) {
    let validator_changes = extract_bucket_entries(registry_json, "validator_changes");
    let workflow_changes = extract_bucket_entries(registry_json, "workflow_changes");
    let refusal_tightenings = extract_bucket_entries(registry_json, "refusal_tightenings");
    let registry = DreamerActionRegistry {
        validator_changes,
        workflow_changes,
        refusal_tightenings,
    };

    let mut findings = Vec::new();
    for (bucket, actions) in [
        ("validator_changes", &registry.validator_changes),
        ("workflow_changes", &registry.workflow_changes),
        ("refusal_tightenings", &registry.refusal_tightenings),
    ] {
        for action in actions {
            if action.pattern_reason.trim().is_empty() {
                findings.push(ValidationFinding::error(
                    "DREAMER_ACTION_PATTERN_REQUIRED",
                    format!("Dreamer action in `{bucket}` is missing pattern_reason"),
                ));
            }
            if action.status.trim().is_empty() {
                findings.push(ValidationFinding::error(
                    "DREAMER_ACTION_STATUS_REQUIRED",
                    format!("Dreamer action in `{bucket}` is missing status"),
                ));
            }
        }
    }

    (registry, findings)
}

pub fn register_dreamer_action(
    registry_json: &str,
    kind: &str,
    action: DreamerAction,
) -> (DreamerActionRegistry, Vec<ValidationFinding>) {
    let (mut registry, mut findings) = parse_dreamer_action_registry(registry_json);
    let bucket = bucket_entries_mut(&mut registry, kind);
    if bucket.is_empty() && !matches!(kind, "validator" | "workflow" | "refusal") {
        findings.push(ValidationFinding::error(
            "DREAMER_ACTION_KIND_INVALID",
            format!("Unsupported Dreamer action kind: {kind}"),
        ));
        return (registry, findings);
    }
    if !bucket
        .iter()
        .any(|item| item.follow_up_target == action.follow_up_target)
    {
        bucket.push(action);
    }
    (registry, findings)
}

pub fn update_dreamer_action_status(
    registry_json: &str,
    follow_up_target: &str,
    status: &str,
) -> (DreamerActionRegistry, Vec<ValidationFinding>) {
    let (mut registry, mut findings) = parse_dreamer_action_registry(registry_json);
    let mut updated = false;
    for bucket in [
        &mut registry.validator_changes,
        &mut registry.workflow_changes,
        &mut registry.refusal_tightenings,
    ] {
        for action in bucket.iter_mut() {
            if action.follow_up_target == follow_up_target {
                action.status = status.to_string();
                updated = true;
            }
        }
    }
    if !updated {
        findings.push(ValidationFinding::error(
            "DREAMER_ACTION_NOT_FOUND",
            format!("Dreamer action not found for follow up target: {follow_up_target}"),
        ));
    }
    (registry, findings)
}

pub fn route_inbox_entry(text: &str) -> Option<&'static str> {
    let lowered = text.to_lowercase();
    let rules: [(&str, &[&str]); 6] = [
        (
            "100",
            &[
                "joined",
                "manages",
                "role",
                "team",
                "person",
                "owner",
                "assistant",
                "profile",
                "human",
            ],
        ),
        (
            "200",
            &[
                "definition",
                "scope",
                "deliverable",
                "component",
                "framework",
                "what is",
                "capabilities",
            ],
        ),
        (
            "300",
            &[
                "platform",
                "tool",
                "environment",
                "repository",
                "repo",
                "account",
                "deployed",
                "nixos",
                "obsidian",
            ],
        ),
        (
            "400",
            &[
                "deadline",
                "milestone",
                "quarterly",
                "cadence",
                "timeline",
                "started",
                "schedule",
                "date",
            ],
        ),
        (
            "500",
            &[
                "process",
                "procedure",
                "protocol",
                "method",
                "workflow",
                "convention",
                "how",
                "result types",
            ],
        ),
        (
            "600",
            &[
                "because",
                "reason",
                "rationale",
                "trade-off",
                "tradeoff",
                "why",
                "chose",
                "risk",
            ],
        ),
    ];

    for (dimension, markers) in rules {
        if markers.iter().any(|marker| lowered.contains(marker)) {
            return Some(dimension);
        }
    }
    None
}

pub fn subject_declaration_changed(before: &str, after: &str) -> bool {
    subject_declaration_block(before) != subject_declaration_block(after)
}

pub fn validate_subject_declaration_change(
    before: &str,
    after: &str,
    approval_granted: bool,
) -> Vec<ValidationFinding> {
    if !approval_granted && subject_declaration_changed(before, after) {
        return vec![ValidationFinding::error(
            "SUBJECT_DECLARATION_APPROVAL_REQUIRED",
            "Subject Declaration changes require explicit human approval",
        )];
    }
    Vec::new()
}

pub fn validate_growth_stage(stage: &str, approval_granted: bool) -> Vec<ValidationFinding> {
    if stage == "spawn" && !approval_granted {
        return vec![ValidationFinding::error(
            "SPAWN_APPROVAL_REQUIRED",
            "Spawn proposals require explicit human approval before a new SoT can be created",
        )];
    }
    Vec::new()
}

pub fn validate_archive_postconditions(
    content: &str,
    entry_value: &str,
    archived_reason: &str,
    dimension_heading: &str,
) -> Vec<ValidationFinding> {
    match archive_postcondition_failure(content, entry_value, archived_reason, dimension_heading) {
        Some(detail) => vec![ValidationFinding::error(
            "ARCHIVE_POSTCONDITION_FAILED",
            detail,
        )],
        None => Vec::new(),
    }
}

pub fn match_dreamer_actions(
    registry_json: &str,
    mode: &str,
    target: &str,
    endpoint: &str,
    reason: &str,
    content: &str,
) -> Vec<DreamerActionMatch> {
    let (registry, _) = parse_dreamer_action_registry(registry_json);
    let haystack = format!("{target} {endpoint} {reason} {content}").to_lowercase();
    bucket_entries(&registry, mode)
        .into_iter()
        .filter(|item| item.status == "active")
        .filter(|item| {
            let tokens = meaningful_tokens(&item.pattern_reason);
            !tokens.is_empty() && tokens.iter().any(|token| haystack.contains(token))
        })
        .map(|item| DreamerActionMatch {
            pattern_reason: item.pattern_reason.clone(),
            status: item.status.clone(),
        })
        .collect()
}

fn bucket_entries<'a>(registry: &'a DreamerActionRegistry, mode: &str) -> &'a [DreamerAction] {
    match mode {
        "validator" => &registry.validator_changes,
        "workflow" => &registry.workflow_changes,
        "refusal" => &registry.refusal_tightenings,
        _ => &[],
    }
}

fn bucket_entries_mut<'a>(
    registry: &'a mut DreamerActionRegistry,
    mode: &str,
) -> &'a mut Vec<DreamerAction> {
    match mode {
        "validator" => &mut registry.validator_changes,
        "workflow" => &mut registry.workflow_changes,
        "refusal" => &mut registry.refusal_tightenings,
        _ => &mut registry.workflow_changes,
    }
}

fn operation_state_entry_mut<'a>(
    state: &'a mut OperationsState,
    name: &str,
) -> Option<&'a mut OperationStateEntry> {
    match name {
        "patrol" => Some(&mut state.patrol),
        "night-cycle" => Some(&mut state.night_cycle),
        _ => None,
    }
}

fn default_operation_state_entry() -> OperationStateEntry {
    OperationStateEntry {
        status: "idle".to_string(),
        last_started: String::new(),
        last_completed: String::new(),
        last_report_target: String::new(),
        last_error: String::new(),
        requested_by: String::new(),
        run_count: 0,
    }
}

fn extract_operation_state_entry(
    state_json: &str,
    bucket: &str,
    findings: &mut Vec<ValidationFinding>,
) -> OperationStateEntry {
    let marker = format!("\"{bucket}\": {{");
    let Some(start) = state_json.find(&marker) else {
        findings.push(ValidationFinding::warning(
            "OPERATIONS_STATE_INVALID",
            format!("Operations state is missing `{bucket}` entry"),
        ));
        return default_operation_state_entry();
    };
    let slice = &state_json[start + marker.len()..];
    let Some(end) = slice.find('}') else {
        findings.push(ValidationFinding::warning(
            "OPERATIONS_STATE_INVALID",
            format!("Operations state entry `{bucket}` is malformed"),
        ));
        return default_operation_state_entry();
    };
    let section = &slice[..end];
    OperationStateEntry {
        status: extract_json_string(section, "status").unwrap_or_else(|| "idle".to_string()),
        last_started: extract_json_string(section, "last_started").unwrap_or_default(),
        last_completed: extract_json_string(section, "last_completed").unwrap_or_default(),
        last_report_target: extract_json_string(section, "last_report_target").unwrap_or_default(),
        last_error: extract_json_string(section, "last_error").unwrap_or_default(),
        requested_by: extract_json_string(section, "requested_by").unwrap_or_default(),
        run_count: extract_json_u32(section, "run_count").unwrap_or(0),
    }
}

fn extract_bucket_entries(registry_json: &str, bucket: &str) -> Vec<DreamerAction> {
    let marker = format!("\"{bucket}\": [");
    let Some(start) = registry_json.find(&marker) else {
        return Vec::new();
    };
    let slice = &registry_json[start + marker.len()..];
    let Some(end) = slice.find(']') else {
        return Vec::new();
    };
    let section = &slice[..end];
    let mut matches = Vec::new();
    for object in section.split("},") {
        let pattern_reason = extract_json_string(object, "pattern_reason").unwrap_or_default();
        let status = extract_json_string(object, "status").unwrap_or_default();
        if !pattern_reason.is_empty() || !status.is_empty() {
            matches.push(DreamerAction {
                follow_up_target: extract_json_string(object, "follow_up_target")
                    .unwrap_or_default(),
                execution_target: extract_json_string(object, "execution_target")
                    .unwrap_or_default(),
                pattern_reason,
                actor: extract_json_string(object, "actor").unwrap_or_default(),
                execution_reason: extract_json_string(object, "execution_reason")
                    .unwrap_or_default(),
                applied_at: extract_json_string(object, "applied_at").unwrap_or_default(),
                status,
            });
        }
    }
    matches
}

fn extract_json_string(text: &str, key: &str) -> Option<String> {
    let marker = format!("\"{key}\":");
    let start = text.find(&marker)? + marker.len();
    let remainder = text[start..].trim_start();
    let remainder = remainder.strip_prefix('"')?;
    let end = remainder.find('"')?;
    Some(remainder[..end].to_string())
}

fn extract_json_u32(text: &str, key: &str) -> Option<u32> {
    let marker = format!("\"{key}\":");
    let start = text.find(&marker)? + marker.len();
    let remainder = text[start..].trim_start();
    let end = remainder
        .find(|c: char| !c.is_ascii_digit())
        .unwrap_or(remainder.len());
    remainder[..end].parse::<u32>().ok()
}

fn meaningful_tokens(value: &str) -> Vec<String> {
    let stopwords = [
        "the", "and", "for", "with", "that", "this", "from", "into", "through", "when", "then",
        "than", "path", "change", "review", "blocked", "reason",
    ];
    let mut tokens: Vec<String> = Vec::new();
    for token in value
        .to_lowercase()
        .split(|c: char| !c.is_ascii_alphanumeric())
        .filter(|token| token.len() > 3 && !stopwords.contains(token))
    {
        if !tokens.iter().any(|item| item == token) {
            tokens.push(token.to_string());
        }
    }
    tokens
}

fn subject_declaration_block(text: &str) -> String {
    let mut inside = false;
    let mut block: Vec<&str> = Vec::new();
    for line in text.lines() {
        if line.trim() == "### Subject Declaration" {
            inside = true;
            block.push(line);
            continue;
        }
        if inside && line.starts_with("### ") {
            break;
        }
        if inside && line.starts_with("## ") && line.trim() != "## 000.Index" {
            break;
        }
        if inside {
            block.push(line);
        }
    }
    block.join("\n").trim().to_string()
}

fn archive_postcondition_failure(
    content: &str,
    entry_value: &str,
    archived_reason: &str,
    dimension_heading: &str,
) -> Option<String> {
    let section_start = content.find(dimension_heading)?;
    let next_section = content[section_start + 1..]
        .find("\n## ")
        .map(|position| section_start + 1 + position)
        .unwrap_or(content.len());
    let section = &content[section_start..next_section];
    let active_start = section.find("### Active")?;
    let inactive_start = section.find("### Inactive")?;
    let active = &section[active_start..inactive_start];
    let inactive = &section[inactive_start..];
    let marker = format!("- {entry_value}");

    if active.contains(&marker) {
        return Some("Entry still appears in Active after archive transaction".to_string());
    }
    if !inactive.contains(&marker)
        || !inactive.contains(&format!("Archived Reason: {archived_reason}"))
    {
        return Some(
            "Entry does not appear in Inactive with archived metadata after archive transaction"
                .to_string(),
        );
    }

    let archive_start = content.find("## 700.Archive")?;
    let archive_section = &content[archive_start..];
    if !archive_section.contains(&format!("FROM: {dimension_heading}"))
        || !archive_section.contains(&marker)
    {
        return Some(
            "Entry does not appear in 700.Archive with timestamp and source after archive transaction"
                .to_string(),
        );
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn routes_inbox_entries_by_first_match() {
        assert_eq!(
            route_inbox_entry("Alex joined the project team this week."),
            Some("100")
        );
        assert_eq!(
            route_inbox_entry("We chose Fidelity because of NAV DRIP."),
            Some("600")
        );
        assert_eq!(route_inbox_entry("Unsorted note needing review."), None);
    }

    #[test]
    fn detects_subject_declaration_changes() {
        let before =
            "## 000.Index\n\n### Subject Declaration\n\n**Subject:** Before\n\n### Links\n";
        let after = "## 000.Index\n\n### Subject Declaration\n\n**Subject:** After\n\n### Links\n";
        let findings = validate_subject_declaration_change(before, after, false);
        assert!(findings
            .iter()
            .any(|item| item.code == "SUBJECT_DECLARATION_APPROVAL_REQUIRED"));
    }

    #[test]
    fn requires_approval_for_spawn_stage() {
        let findings = validate_growth_stage("spawn", false);
        assert!(findings
            .iter()
            .any(|item| item.code == "SPAWN_APPROVAL_REQUIRED"));
    }

    #[test]
    fn validates_archive_postconditions() {
        let content = "## 100.WHO.Identity\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n- Sample archived value. (2026-04-08)\n  - Exists to verify archive movement. [AGENT:gpt-5]\n  - Archived: 2026-04-09\n  - Archived Reason: Replaced by newer fact\n\n## 700.Archive\n\n[202604090352] FROM: ## 100.WHO.Identity\n- Sample archived value. (2026-04-08)\n  - Exists to verify archive movement. [AGENT:gpt-5]\n  - Archived: 2026-04-09\n  - Archived Reason: Replaced by newer fact\n";
        let findings = validate_archive_postconditions(
            content,
            "Sample archived value. (2026-04-08)",
            "Replaced by newer fact",
            "## 100.WHO.Identity",
        );
        assert!(findings.is_empty());
    }

    #[test]
    fn matches_validator_actions_from_registry() {
        let registry = r#"{
  "validator_changes": [
    {
      "follow_up_target": "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.validator.md",
      "execution_target": "knowledge/ARTIFACTS/refs/Dreamer-Execution.validator.md",
      "pattern_reason": "frontmatter structure validation",
      "actor": "human",
      "execution_reason": "tighten validator behavior",
      "applied_at": "2026-04-09T00:00:00+00:00",
      "status": "active"
    }
  ],
  "workflow_changes": [],
  "refusal_tightenings": []
}"#;
        let matches = match_dreamer_actions(
            registry,
            "validator",
            "knowledge/210.WHAT.Vela-Capabilities-SoT.md",
            "test",
            "validator structure check",
            "frontmatter structure validation matters here",
        );
        assert_eq!(matches.len(), 1);
        assert_eq!(
            matches[0].pattern_reason,
            "frontmatter structure validation"
        );
    }

    #[test]
    fn matches_refusal_actions_from_registry() {
        let registry = r#"{
  "validator_changes": [],
  "workflow_changes": [],
  "refusal_tightenings": [
    {
      "follow_up_target": "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.refusal.md",
      "execution_target": "knowledge/ARTIFACTS/refs/Dreamer-Execution.refusal.md",
      "pattern_reason": "cross reference pointer",
      "actor": "human",
      "execution_reason": "tighten refusal behavior",
      "applied_at": "2026-04-09T00:00:00+00:00",
      "status": "active"
    }
  ]
}"#;
        let matches = match_dreamer_actions(
            registry,
            "refusal",
            "knowledge/ARTIFACTS/proposals/test.md",
            "cross-reference",
            "cross reference pointer update",
            "Cross reference pointer write.",
        );
        assert_eq!(matches.len(), 1);
        assert_eq!(matches[0].pattern_reason, "cross reference pointer");
    }

    #[test]
    fn parses_dreamer_action_registry() {
        let registry = r#"{
  "validator_changes": [
    {
      "follow_up_target": "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.validator.md",
      "execution_target": "knowledge/ARTIFACTS/refs/Dreamer-Execution.validator.md",
      "pattern_reason": "frontmatter structure validation",
      "actor": "human",
      "execution_reason": "tighten validator behavior",
      "applied_at": "2026-04-09T00:00:00+00:00",
      "status": "active"
    }
  ],
  "workflow_changes": [],
  "refusal_tightenings": []
}"#;
        let (parsed, findings) = parse_dreamer_action_registry(registry);
        assert!(findings.is_empty());
        assert_eq!(parsed.validator_changes.len(), 1);
        assert_eq!(
            parsed.validator_changes[0].execution_target,
            "knowledge/ARTIFACTS/refs/Dreamer-Execution.validator.md"
        );
    }

    #[test]
    fn registers_dreamer_action() {
        let registry = r#"{
  "validator_changes": [],
  "workflow_changes": [],
  "refusal_tightenings": []
}"#;
        let (updated, findings) = register_dreamer_action(
            registry,
            "workflow",
            DreamerAction {
                follow_up_target: "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.workflow.md"
                    .to_string(),
                execution_target: "knowledge/ARTIFACTS/refs/Dreamer-Execution.workflow.md"
                    .to_string(),
                pattern_reason: "triage route queue".to_string(),
                actor: "human".to_string(),
                execution_reason: "tighten routing".to_string(),
                applied_at: "2026-04-09T00:00:00+00:00".to_string(),
                status: "active".to_string(),
            },
        );
        assert!(findings.is_empty());
        assert_eq!(updated.workflow_changes.len(), 1);
    }

    #[test]
    fn updates_dreamer_action_status() {
        let registry = r#"{
  "validator_changes": [],
  "workflow_changes": [
    {
      "follow_up_target": "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.workflow.md",
      "execution_target": "knowledge/ARTIFACTS/refs/Dreamer-Execution.workflow.md",
      "pattern_reason": "triage route queue",
      "actor": "human",
      "execution_reason": "tighten routing",
      "applied_at": "2026-04-09T00:00:00+00:00",
      "status": "active"
    }
  ],
  "refusal_tightenings": []
}"#;
        let (updated, findings) = update_dreamer_action_status(
            registry,
            "knowledge/ARTIFACTS/proposals/Dreamer-Follow-Up.workflow.md",
            "inactive",
        );
        assert!(findings.is_empty());
        assert_eq!(updated.workflow_changes[0].status, "inactive");
    }

    #[test]
    fn operations_state_updates_runs_through_rust_core() {
        let (running_state, running_findings) = update_operations_state(
            "{}",
            "patrol",
            "running",
            "human",
            Some("2026-04-10T10:00:00Z"),
            None,
            None,
            Some(""),
            false,
        );
        let _ = running_findings;

        let running_state_json = format!(
            "{{\"patrol\":{{\"status\":\"{}\",\"last_started\":\"{}\",\"last_completed\":\"{}\",\"last_report_target\":\"{}\",\"last_error\":\"{}\",\"requested_by\":\"{}\",\"run_count\":{}}},\"night-cycle\":{{\"status\":\"{}\",\"last_started\":\"{}\",\"last_completed\":\"{}\",\"last_report_target\":\"{}\",\"last_error\":\"{}\",\"requested_by\":\"{}\",\"run_count\":{}}}}}",
            running_state.patrol.status,
            running_state.patrol.last_started,
            running_state.patrol.last_completed,
            running_state.patrol.last_report_target,
            running_state.patrol.last_error,
            running_state.patrol.requested_by,
            running_state.patrol.run_count,
            running_state.night_cycle.status,
            running_state.night_cycle.last_started,
            running_state.night_cycle.last_completed,
            running_state.night_cycle.last_report_target,
            running_state.night_cycle.last_error,
            running_state.night_cycle.requested_by,
            running_state.night_cycle.run_count,
        );
        let (state, findings) = update_operations_state(
            &running_state_json,
            "patrol",
            "completed",
            "human",
            None,
            Some("2026-04-10T10:10:00Z"),
            Some("knowledge/ARTIFACTS/refs/Warden-Patrol-20260410-1010.md"),
            Some(""),
            true,
        );
        let _ = findings;
        assert_eq!(state.patrol.status, "completed");
        assert_eq!(state.patrol.requested_by, "human");
        assert_eq!(state.patrol.run_count, 1);
    }

    #[test]
    fn malformed_operation_lock_is_rejected() {
        let (_, findings) = validate_operation_lock("{}", "patrol");
        assert!(findings
            .iter()
            .any(|item| item.code == "OPERATION_LOCK_INVALID"));
    }

    #[test]
    fn operation_request_rejects_disallowed_actor() {
        let findings = validate_operation_request("patrol", "vela");
        assert!(findings
            .iter()
            .any(|item| item.code == "OPERATION_REQUEST_NOT_ALLOWED"));
    }

    #[test]
    fn operation_transition_rejects_invalid_completion_jump() {
        let findings = validate_operation_state_transition("idle", "completed");
        assert!(findings
            .iter()
            .any(|item| item.code == "OPERATION_STATE_TRANSITION_INVALID"));
    }

    #[test]
    fn dreamer_review_rejects_invalid_decision() {
        let findings = validate_dreamer_review("proposed", "ship-it");
        assert!(findings
            .iter()
            .any(|item| item.code == "DREAMER_REVIEW_DECISION_INVALID"));
    }

    #[test]
    fn dreamer_follow_up_apply_rejects_invalid_actor() {
        let findings = validate_dreamer_follow_up_apply("proposed", "vela");
        assert!(findings
            .iter()
            .any(|item| item.code == "DREAMER_FOLLOW_UP_ACTOR_NOT_ALLOWED"));
    }

    #[test]
    fn classifies_dreamer_follow_up_kind() {
        assert_eq!(
            classify_dreamer_follow_up("validator structure regression"),
            "validator-change"
        );
        assert_eq!(
            classify_dreamer_follow_up("workflow queue routing drift"),
            "workflow-change"
        );
        assert_eq!(
            classify_dreamer_follow_up("need tighter refusal behavior"),
            "refusal-tightening"
        );
    }

    #[test]
    fn rejects_invalid_dreamer_follow_up_kind() {
        let findings = validate_dreamer_follow_up_kind("sandbox-change");
        assert!(findings
            .iter()
            .any(|item| item.code == "DREAMER_FOLLOW_UP_KIND_INVALID"));
    }
}
