use crate::models::ValidationFinding;

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
}
