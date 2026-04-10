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
pub struct GovernedReference {
    pub path: String,
    pub title: String,
    pub ref_type: String,
    pub inventory_role: String,
    pub parent: String,
    pub domain: String,
    pub status: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MatrixSoT {
    pub path: String,
    pub title: String,
    pub sot_type: String,
    pub inventory_role: String,
    pub parent: String,
    pub domain: String,
    pub status: String,
    pub area: String,
    pub is_cornerstone: bool,
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
        "SPAWN_APPROVAL_REQUIRED" => vec![
            "Pattern 12 Sovereign Spawn".to_string(),
            "Pattern 18 Human Gate".to_string(),
        ],
        "SUBJECT_DECLARATION_APPROVAL_REQUIRED" => vec![
            "Pattern 6 Protected/Fluid Zones".to_string(),
            "Pattern 9 Declaration Anchor".to_string(),
            "Pattern 18 Human Gate".to_string(),
        ],
        "CONFIG_REQUIRED" | "SETUP_STATE_INCONSISTENT" => {
            vec!["Vela Setup Rule: Setup Mode Honesty".to_string()]
        }
        "MATRIX_SINGLE_CORNERSTONE_REQUIRED" => {
            vec!["Law 1 Exactly One Cornerstone Shall Exist".to_string()]
        }
        "MATRIX_PARENT_REQUIRED" => vec![
            "Pattern 3 Single Parent".to_string(),
            "Law 2 Every Non Cornerstone Source of Truth Shall Declare One Parent".to_string(),
        ],
        "MATRIX_HUB_PARENT_REQUIRED" => vec![
            "Pattern 15 Three-Hop Ceiling".to_string(),
            "Law 6 Branch Sources of Truth Shall Prefer Hub Lineage Over Direct Root Attachment".to_string(),
        ],
        "MATRIX_PARENT_DECLARATION_MISMATCH" | "MATRIX_CORNERSTONE_DECLARATION_PARENT_INVALID" => vec![
            "Pattern 3 Single Parent".to_string(),
            "Law 2 Every Non Cornerstone Source of Truth Shall Declare One Parent".to_string(),
        ],
        "MATRIX_FRONTMATTER_REQUIRED" | "MATRIX_CORNERSTONE_PARENT_MUST_BE_EMPTY" => vec![
            "Pattern 16 Frontmatter Contract".to_string(),
            "Law 2 Every Non Cornerstone Source of Truth Shall Declare One Parent".to_string(),
        ],
        "MATRIX_HEADING_REQUIRED"
        | "MATRIX_ACTIVE_SECTION_REQUIRED"
        | "MATRIX_INACTIVE_SECTION_REQUIRED" => vec![
            "Pattern 17 SoT-Native Output".to_string(),
            "Pattern 7 Single Source Block Map".to_string(),
        ],
        "ARCHIVE_POSTCONDITION_FAILED" => vec![
            "Pattern 10 Dual Archive".to_string(),
            "Pattern 13 Extraction Before Deletion".to_string(),
        ],
        "GRAPH_EMPTY_FILE" | "GRAPH_MISSING_TARGET" => vec![
            "Pattern 14 One Home, Many Pointers".to_string(),
            "Pattern 17 SoT-Native Output".to_string(),
        ],
        "MATRIX_REFERENCE_FRONTMATTER_REQUIRED" | "MATRIX_REFERENCE_TYPE_REQUIRED" => vec![
            "Pattern 16 Frontmatter Contract".to_string(),
        ],
        "MATRIX_REFERENCE_PARENT_REQUIRED" => vec![
            "Pattern 3 Single Parent".to_string(),
            "Law 2 Every Non Cornerstone Source of Truth Shall Declare One Parent".to_string(),
        ],
        "MATRIX_REFERENCE_HEADING_REQUIRED" => vec![
            "Pattern 17 SoT-Native Output".to_string(),
        ],
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
        "DREAMER_VALIDATOR_CHANGE_ACTIVE" => vec![
            "SoT Operations Reference: Dreamer Feedback Loop".to_string(),
            "SoT Operations Reference: Three-Tier Vault Maintenance".to_string(),
        ],
        "DREAMER_REFUSAL_TIGHTENING_ACTIVE" => vec![
            "SoT Operations Reference: Dreamer Feedback Loop".to_string(),
            "SoT Operations Reference: Immutable Rules".to_string(),
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
