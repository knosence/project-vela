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
pub struct DreamerAction {
    pub follow_up_target: String,
    pub execution_target: String,
    pub pattern_reason: String,
    pub actor: String,
    pub execution_reason: String,
    pub applied_at: String,
    pub status: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DreamerActionRegistry {
    pub validator_changes: Vec<DreamerAction>,
    pub workflow_changes: Vec<DreamerAction>,
    pub refusal_tightenings: Vec<DreamerAction>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DreamerProposalSummary {
    pub target: String,
    pub status: String,
    pub created: String,
    pub reason: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DreamerProposalCandidate {
    pub target: String,
    pub reason: String,
    pub count: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MergeCandidateSummary {
    pub ref_target: String,
    pub owners: Vec<String>,
    pub count: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MergeFollowUpSummary {
    pub target: String,
    pub status: String,
    pub ref_target: String,
    pub suggested_target: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BlockedItemSummary {
    pub target: String,
    pub reason: String,
    pub actor: String,
    pub endpoint: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GrowthTarget {
    pub path: String,
    pub inventory_role: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GrowthAssessment {
    pub stage: String,
    pub reason: String,
    pub inventory_role: String,
    pub exists: bool,
    pub line_count: usize,
    pub densest_dimension_entries: usize,
    pub has_subgroups: bool,
    pub living_record_markers: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GrowthExecutionPlan {
    pub target: String,
    pub kind: String,
    pub dimension: String,
    pub entries: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GrowthSourceUpdatePlan {
    pub link_line: String,
    pub status_line: String,
    pub next_action_line: String,
    pub decision_line: String,
    pub target_dimension: String,
    pub replacement_entries: Vec<String>,
    pub active_pointer_line: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GrowthSourceApplyPlan {
    pub updated_content: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ArchiveTransactionPlan {
    pub updated_content: String,
    pub archived_entry: String,
    pub archive_entry: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CrossReferencePlan {
    pub pointer: String,
    pub updated_content: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InboxTriagePlan {
    pub target: String,
    pub dimension: String,
    pub value: String,
    pub context: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CsvInboxEntry {
    pub dimension: String,
    pub value: String,
    pub context: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CsvInboxPlan {
    pub target: String,
    pub entries: Vec<CsvInboxEntry>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CompanionPathPlan {
    pub destination: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DimensionAppendPlan {
    pub updated_content: String,
    pub anchor: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PatchTarget {
    pub path: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DreamerFollowUpSummary {
    pub target: String,
    pub status: String,
    pub created: String,
    pub kind: String,
    pub reason: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DreamerReviewPlan {
    pub target: String,
    pub decision: String,
    pub follow_up_target: String,
    pub follow_up_kind: String,
    pub updated_content: String,
    pub follow_up_content: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DreamerApplyPlan {
    pub target: String,
    pub kind: String,
    pub execution_target: String,
    pub execution_content: String,
    pub updated_follow_up_content: String,
    pub already_applied: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MergeReviewPlan {
    pub target: String,
    pub decision: String,
    pub follow_up_target: String,
    pub suggested_target: String,
    pub updated_content: String,
    pub follow_up_content: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MergeApplyPlan {
    pub target: String,
    pub execution_target: String,
    pub ref_target: String,
    pub owners: Vec<String>,
    pub execution_content: String,
    pub updated_follow_up_content: String,
    pub already_applied: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EventAppendPlan {
    pub line: String,
    pub event_id: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PatrolPlan {
    pub report_target: String,
    pub report_content: String,
    pub files_checked: usize,
    pub structural_flags_count: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NightCyclePlan {
    pub report_target: String,
    pub report_content: String,
    pub dreamer_report_target: String,
    pub dreamer_report_content: String,
    pub growth_candidates_count: usize,
    pub blocked_items_count: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OperationStateEntry {
    pub status: String,
    pub last_started: String,
    pub last_completed: String,
    pub last_report_target: String,
    pub last_error: String,
    pub requested_by: String,
    pub run_count: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OperationsState {
    pub patrol: OperationStateEntry,
    pub night_cycle: OperationStateEntry,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OperationLockRecord {
    pub name: String,
    pub requested_by: String,
    pub started_at: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OperationLifecyclePlan {
    pub state_json: String,
    pub state_status: String,
    pub lock_target: String,
    pub lock_content: String,
    pub release_lock: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SchedulerPlan {
    pub operation: String,
    pub requested_by: String,
    pub interval_seconds: u64,
    pub max_runs: i32,
    pub unbounded: bool,
    pub current_status: String,
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
            "Law 5 Sovereign Changes Shall Touch Roots and Rules Only Through Governed Paths"
                .to_string(),
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
            "Law 6 Branch Sources of Truth Shall Prefer Hub Lineage Over Direct Root Attachment"
                .to_string(),
        ],
        "MATRIX_PARENT_DECLARATION_MISMATCH" | "MATRIX_CORNERSTONE_DECLARATION_PARENT_INVALID" => {
            vec![
                "Pattern 3 Single Parent".to_string(),
                "Law 2 Every Non Cornerstone Source of Truth Shall Declare One Parent".to_string(),
            ]
        }
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
        "MATRIX_REFERENCE_FRONTMATTER_REQUIRED" | "MATRIX_REFERENCE_TYPE_REQUIRED" => {
            vec!["Pattern 16 Frontmatter Contract".to_string()]
        }
        "MATRIX_REFERENCE_PARENT_REQUIRED" => vec![
            "Pattern 3 Single Parent".to_string(),
            "Law 2 Every Non Cornerstone Source of Truth Shall Declare One Parent".to_string(),
        ],
        "MATRIX_REFERENCE_HEADING_REQUIRED" => vec!["Pattern 17 SoT-Native Output".to_string()],
        "NARRATIVE_HEADING_REQUIRED" | "NARRATIVE_HEADING_WEAK" | "NARRATIVE_OPENING_REQUIRED" => {
            vec!["Pattern 17 SoT-Native Output".to_string()]
        }
        "EVENT_ID_REQUIRED"
        | "EVENT_TIMESTAMP_REQUIRED"
        | "EVENT_SOURCE_REQUIRED"
        | "EVENT_ENDPOINT_REQUIRED"
        | "EVENT_ACTOR_REQUIRED"
        | "EVENT_TARGET_REQUIRED"
        | "EVENT_STATUS_REQUIRED"
        | "EVENT_REASON_REQUIRED" => vec!["Directive 8 Event Log Everything Important".to_string()],
        "DREAMER_VALIDATOR_CHANGE_ACTIVE" => vec![
            "SoT Operations Reference: Dreamer Feedback Loop".to_string(),
            "SoT Operations Reference: Three-Tier Vault Maintenance".to_string(),
        ],
        "DREAMER_REFUSAL_TIGHTENING_ACTIVE" => vec![
            "SoT Operations Reference: Dreamer Feedback Loop".to_string(),
            "SoT Operations Reference: Immutable Rules".to_string(),
        ],
        "DREAMER_ACTION_PATTERN_REQUIRED" | "DREAMER_ACTION_STATUS_REQUIRED" => vec![
            "SoT Operations Reference: Dreamer Feedback Loop".to_string(),
            "Directive 8 Event Log Everything Important".to_string(),
        ],
        "DREAMER_ACTION_KIND_INVALID" | "DREAMER_ACTION_NOT_FOUND" => vec![
            "SoT Operations Reference: Dreamer Feedback Loop".to_string(),
            "Role Purity".to_string(),
        ],
        "OPERATION_ALREADY_RUNNING" | "OPERATION_LOCK_INVALID" => vec![
            "SoT Operations Reference: Three-Tier Vault Maintenance".to_string(),
            "Sequential Interplay Over Parallel Chaos".to_string(),
        ],
        "OPERATIONS_STATE_INVALID" | "OPERATIONS_STATE_NAME_INVALID" => vec![
            "SoT Operations Reference: Three-Tier Vault Maintenance".to_string(),
            "Pure Core, Impure Edges".to_string(),
        ],
        "OPERATION_REQUEST_NOT_ALLOWED" | "OPERATION_STATE_TRANSITION_INVALID" => vec![
            "SoT Operations Reference: Three-Tier Vault Maintenance".to_string(),
            "Role Purity".to_string(),
            "Sequential Interplay Over Parallel Chaos".to_string(),
        ],
        "OPERATION_EVENT_KIND_INVALID" => vec![
            "SoT Operations Reference: Three-Tier Vault Maintenance".to_string(),
            "Directive 8 Event Log Everything Important".to_string(),
        ],
        "SCHEDULER_INTERVAL_INVALID" => vec![
            "SoT Operations Reference: Three-Tier Vault Maintenance".to_string(),
            "Sequential Interplay Over Parallel Chaos".to_string(),
        ],
        "DREAMER_REVIEW_DECISION_INVALID"
        | "DREAMER_PROPOSAL_STATUS_INVALID"
        | "DREAMER_FOLLOW_UP_STATUS_INVALID" => vec![
            "SoT Operations Reference: Dreamer Feedback Loop".to_string(),
            "Role Purity".to_string(),
            "Sequential Interplay Over Parallel Chaos".to_string(),
        ],
        "DREAMER_FOLLOW_UP_ACTOR_NOT_ALLOWED" => vec![
            "SoT Operations Reference: Dreamer Feedback Loop".to_string(),
            "Role Purity".to_string(),
        ],
        "DREAMER_FOLLOW_UP_KIND_INVALID" => vec![
            "SoT Operations Reference: Dreamer Feedback Loop".to_string(),
            "Role Purity".to_string(),
            "One Home, Many Pointers".to_string(),
        ],
        "DREAMER_EXECUTION_SHAPE_INVALID"
        | "WARDEN_PATROL_REPORT_INVALID"
        | "DC_NIGHT_REPORT_INVALID"
        | "DREAMER_PATTERN_REPORT_INVALID" => vec![
            "SoT Operations Reference: Three-Tier Vault Maintenance".to_string(),
            "Pattern 17 SoT-Native Output".to_string(),
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
        let finding =
            ValidationFinding::error("CONFIG_REQUIRED", "Missing required field: owner.name");

        assert!(finding
            .rule_refs
            .iter()
            .any(|item| item == "Vela Setup Rule: Setup Mode Honesty"));
    }
}
