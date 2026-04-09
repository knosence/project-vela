use crate::models::{RuntimeConfig, Severity, ValidationFinding};

const REQUIRED_SENTINEL: &str = "<required>";

pub fn requires_setup(missing_fields: &[String]) -> bool {
    !missing_fields.is_empty()
}

pub fn missing_required_fields(config: &RuntimeConfig) -> Vec<String> {
    let mut missing = Vec::new();

    if is_missing(&config.owner_name) {
        missing.push("owner.name".to_string());
    }
    if is_missing(&config.primary_provider) {
        missing.push("providers.primary".to_string());
    }
    if is_missing(&config.primary_model) {
        missing.push("runtime.primary_model".to_string());
    }
    if is_missing(&config.deployment_target) {
        missing.push("deployment.target".to_string());
    }
    if is_missing(&config.onboarding.assistant_choice) {
        missing.push("onboarding.assistant_choice".to_string());
    }
    if is_missing(&config.onboarding.relationship_stance) {
        missing.push("onboarding.relationship_stance".to_string());
    }
    if is_missing(&config.onboarding.support_critique_balance) {
        missing.push("onboarding.support_critique_balance".to_string());
    }
    if is_missing(&config.onboarding.subjectivity_boundaries) {
        missing.push("onboarding.subjectivity_boundaries".to_string());
    }

    missing
}

pub fn validate_runtime_config(config: &RuntimeConfig) -> Vec<ValidationFinding> {
    let mut findings = Vec::new();

    for field in missing_required_fields(config) {
        findings.push(ValidationFinding::error(
            "CONFIG_REQUIRED",
            format!("Missing required field: {field}"),
        ));
    }

    if config.identity.active_profile.is_empty() {
        findings.push(ValidationFinding::error(
            "ACTIVE_PROFILE_REQUIRED",
            "An active profile must be selected",
        ));
    }

    if !config.identity.allow_multiple_profiles
        && config.identity.active_profile != config.identity.default_profile
    {
        findings.push(ValidationFinding::error(
            "PROFILE_SWITCH_FORBIDDEN",
            "Active profile differs from default while multiple profiles are disabled",
        ));
    }

    if config.setup_complete && !missing_required_fields(config).is_empty() {
        findings.push(ValidationFinding::error(
            "SETUP_STATE_INCONSISTENT",
            "Setup is marked complete while required values are still missing",
        ));
    }

    findings
}

pub fn validate_narrative_document(document: &str) -> Vec<ValidationFinding> {
    let mut findings = Vec::new();
    let headings: Vec<&str> = document
        .lines()
        .map(str::trim)
        .filter(|line| line.starts_with('#'))
        .collect();

    if headings.is_empty() {
        findings.push(ValidationFinding::error(
            "NARRATIVE_HEADING_REQUIRED",
            "Document must contain at least one narrative heading",
        ));
        return findings;
    }

    for heading in headings {
        let label = heading.trim_start_matches('#').trim();
        if label.split_whitespace().count() < 3 {
            findings.push(ValidationFinding::warning(
                "NARRATIVE_HEADING_WEAK",
                format!("Heading is too short to carry narrative meaning: {label}"),
            ));
        }
    }

    let mut current_heading: Option<&str> = None;
    let mut saw_content_after_heading = false;

    for line in document.lines().map(str::trim) {
        if line.starts_with('#') {
            if let Some(previous_heading) = current_heading {
                let previous_level = previous_heading.chars().take_while(|ch| *ch == '#').count();
                let new_level = line.chars().take_while(|ch| *ch == '#').count();
                if previous_level > 1 && !saw_content_after_heading && new_level <= previous_level {
                    findings.push(ValidationFinding::error(
                        "NARRATIVE_OPENING_REQUIRED",
                        "Each section heading must be followed by an opening line",
                    ));
                }
            }
            current_heading = Some(line);
            saw_content_after_heading = false;
            continue;
        }
        if current_heading.is_some() && !line.is_empty() {
            saw_content_after_heading = true;
        }
    }

    if let Some(last_heading) = current_heading {
        let last_level = last_heading.chars().take_while(|ch| *ch == '#').count();
        if last_level > 1 && !saw_content_after_heading {
            findings.push(ValidationFinding::error(
                "NARRATIVE_OPENING_REQUIRED",
                "Final section heading must be followed by an opening line",
            ));
        }
    }

    findings
}

pub fn has_blocking_findings(findings: &[ValidationFinding]) -> bool {
    findings.iter().any(|finding| finding.severity == Severity::Error)
}

fn is_missing(value: &str) -> bool {
    value.trim().is_empty() || value.trim() == REQUIRED_SENTINEL
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{OnboardingConfig, SystemIdentity};
    use crate::parser::build_runtime_config;

    fn sample_config() -> RuntimeConfig {
        build_runtime_config(
            "Ada",
            "openai",
            "gpt-5.4",
            "local-dev",
            false,
            SystemIdentity {
                project_name: "Project Vela".to_string(),
                default_profile: "vela".to_string(),
                active_profile: "vela".to_string(),
                allow_replacement: true,
                allow_multiple_profiles: true,
            },
            OnboardingConfig {
                assistant_choice: "keep-vela".to_string(),
                relationship_stance: "direct but respectful".to_string(),
                support_critique_balance: "balanced".to_string(),
                subjectivity_boundaries: "bounded".to_string(),
            },
        )
    }

    #[test]
    fn runtime_config_reports_missing_required_fields() {
        let mut config = sample_config();
        config.owner_name = "<required>".to_string();
        config.primary_model.clear();

        let missing = missing_required_fields(&config);

        assert!(missing.contains(&"owner.name".to_string()));
        assert!(missing.contains(&"runtime.primary_model".to_string()));
        assert!(requires_setup(&missing));
    }

    #[test]
    fn runtime_config_rejects_inconsistent_setup_state() {
        let mut config = sample_config();
        config.owner_name = "<required>".to_string();
        config.setup_complete = true;

        let findings = validate_runtime_config(&config);

        assert!(has_blocking_findings(&findings));
        assert!(findings.iter().any(|item| item.code == "SETUP_STATE_INCONSISTENT"));
    }

    #[test]
    fn narrative_validator_requires_headings_and_opening_lines() {
        let findings = validate_narrative_document("# Short\n\n## Another Heading");

        assert!(findings.iter().any(|item| item.code == "NARRATIVE_HEADING_WEAK"));
        assert!(findings.iter().any(|item| item.code == "NARRATIVE_OPENING_REQUIRED"));
    }

    #[test]
    fn narrative_validator_accepts_structured_document() {
        let findings = validate_narrative_document(
            "# System Governance Source of Truth\n\n## This Section Explains the Rule Clearly\nThe opening line narrows the section into detail.\n",
        );

        assert!(!has_blocking_findings(&findings));
    }
}
