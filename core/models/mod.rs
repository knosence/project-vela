#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProfileBinding {
    pub name: String,
    pub base_profile: Option<String>,
    pub active: bool,
    pub replaceable: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SystemIdentity {
    pub project_name: String,
    pub default_profile: String,
    pub active_profile: String,
    pub allow_replacement: bool,
    pub allow_multiple_profiles: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OnboardingConfig {
    pub assistant_choice: String,
    pub relationship_stance: String,
    pub support_critique_balance: String,
    pub subjectivity_boundaries: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuntimeConfig {
    pub owner_name: String,
    pub primary_provider: String,
    pub primary_model: String,
    pub deployment_target: String,
    pub setup_complete: bool,
    pub identity: SystemIdentity,
    pub onboarding: OnboardingConfig,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationFinding {
    pub code: String,
    pub detail: String,
    pub severity: Severity,
    pub rule_refs: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Severity {
    Info,
    Warning,
    Error,
}

impl ValidationFinding {
    pub fn error(code: impl Into<String>, detail: impl Into<String>) -> Self {
        let code = code.into();
        Self {
            rule_refs: rule_refs_for_code(&code),
            code,
            detail: detail.into(),
            severity: Severity::Error,
        }
    }

    pub fn warning(code: impl Into<String>, detail: impl Into<String>) -> Self {
        let code = code.into();
        Self {
            rule_refs: rule_refs_for_code(&code),
            code,
            detail: detail.into(),
            severity: Severity::Warning,
        }
    }
}

fn rule_refs_for_code(code: &str) -> Vec<String> {
    match code {
        "SOVEREIGN_APPROVAL_REQUIRED" => vec![
            "Pattern 18 Human Gate".to_string(),
            "Law 5 Sovereign Changes Shall Touch Roots and Rules Only Through Governed Paths".to_string(),
        ],
        "CONFIG_REQUIRED" | "SETUP_STATE_INCONSISTENT" => {
            vec!["Vela Setup Rule: Setup Mode Honesty".to_string()]
        }
        "NARRATIVE_HEADING_REQUIRED" | "NARRATIVE_HEADING_WEAK" | "NARRATIVE_OPENING_REQUIRED" => vec![
            "Pattern 17 SoT-Native Output".to_string(),
        ],
        "EVENT_ID_REQUIRED"
        | "EVENT_TIMESTAMP_REQUIRED"
        | "EVENT_SOURCE_REQUIRED"
        | "EVENT_ENDPOINT_REQUIRED"
        | "EVENT_ACTOR_REQUIRED"
        | "EVENT_TARGET_REQUIRED"
        | "EVENT_STATUS_REQUIRED"
        | "EVENT_REASON_REQUIRED" => vec![
            "Directive 8 Event Log Everything Important".to_string(),
        ],
        _ => Vec::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::ValidationFinding;

    #[test]
    fn sovereign_findings_carry_constitutional_rule_refs() {
        let finding = ValidationFinding::error(
            "SOVEREIGN_APPROVAL_REQUIRED",
            "Cornerstone or identity change attempted without human approval",
        );

        assert!(finding
            .rule_refs
            .iter()
            .any(|item| item == "Pattern 18 Human Gate"));
        assert!(finding.rule_refs.iter().any(|item| {
            item == "Law 5 Sovereign Changes Shall Touch Roots and Rules Only Through Governed Paths"
        }));
    }

    #[test]
    fn setup_findings_carry_setup_honesty_rule_ref() {
        let finding = ValidationFinding::error(
            "CONFIG_REQUIRED",
            "Missing required field: owner.name",
        );

        assert!(finding
            .rule_refs
            .iter()
            .any(|item| item == "Vela Setup Rule: Setup Mode Honesty"));
    }
}
