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
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Severity {
    Info,
    Warning,
    Error,
}

impl ValidationFinding {
    pub fn error(code: impl Into<String>, detail: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            detail: detail.into(),
            severity: Severity::Error,
        }
    }

    pub fn warning(code: impl Into<String>, detail: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            detail: detail.into(),
            severity: Severity::Warning,
        }
    }
}

