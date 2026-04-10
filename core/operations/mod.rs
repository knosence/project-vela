use crate::models::{DreamerAction, DreamerActionRegistry, ValidationFinding};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DreamerActionMatch {
    pub pattern_reason: String,
    pub status: String,
}

pub fn parse_dreamer_action_registry(registry_json: &str) -> (DreamerActionRegistry, Vec<ValidationFinding>) {
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

pub fn route_inbox_entry(text: &str) -> Option<&'static str> {
    let lowered = text.to_lowercase();
    let rules: [(&str, &[&str]); 6] = [
        ("100", &["joined", "manages", "role", "team", "person", "owner", "assistant", "profile", "human"]),
        ("200", &["definition", "scope", "deliverable", "component", "framework", "what is", "capabilities"]),
        ("300", &["platform", "tool", "environment", "repository", "repo", "account", "deployed", "nixos", "obsidian"]),
        ("400", &["deadline", "milestone", "quarterly", "cadence", "timeline", "started", "schedule", "date"]),
        ("500", &["process", "procedure", "protocol", "method", "workflow", "convention", "how", "result types"]),
        ("600", &["because", "reason", "rationale", "trade-off", "tradeoff", "why", "chose", "risk"]),
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
        Some(detail) => vec![ValidationFinding::error("ARCHIVE_POSTCONDITION_FAILED", detail)],
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
                follow_up_target: extract_json_string(object, "follow_up_target").unwrap_or_default(),
                execution_target: extract_json_string(object, "execution_target").unwrap_or_default(),
                pattern_reason,
                actor: extract_json_string(object, "actor").unwrap_or_default(),
                execution_reason: extract_json_string(object, "execution_reason").unwrap_or_default(),
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
    if !inactive.contains(&marker) || !inactive.contains(&format!("Archived Reason: {archived_reason}")) {
        return Some(
            "Entry does not appear in Inactive with archived metadata after archive transaction"
                .to_string(),
        );
    }

    let archive_start = content.find("## 700.Archive")?;
    let archive_section = &content[archive_start..];
    if !archive_section.contains(&format!("FROM: {dimension_heading}")) || !archive_section.contains(&marker) {
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
        assert_eq!(route_inbox_entry("Alex joined the project team this week."), Some("100"));
        assert_eq!(route_inbox_entry("We chose Fidelity because of NAV DRIP."), Some("600"));
        assert_eq!(route_inbox_entry("Unsorted note needing review."), None);
    }

    #[test]
    fn detects_subject_declaration_changes() {
        let before = "## 000.Index\n\n### Subject Declaration\n\n**Subject:** Before\n\n### Links\n";
        let after = "## 000.Index\n\n### Subject Declaration\n\n**Subject:** After\n\n### Links\n";
        let findings = validate_subject_declaration_change(before, after, false);
        assert!(findings.iter().any(|item| item.code == "SUBJECT_DECLARATION_APPROVAL_REQUIRED"));
    }

    #[test]
    fn requires_approval_for_spawn_stage() {
        let findings = validate_growth_stage("spawn", false);
        assert!(findings.iter().any(|item| item.code == "SPAWN_APPROVAL_REQUIRED"));
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
        assert_eq!(matches[0].pattern_reason, "frontmatter structure validation");
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
}
