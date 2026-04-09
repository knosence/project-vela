use crate::models::{OnboardingConfig, RuntimeConfig, SystemIdentity};

pub fn parse_system_identity(
    project_name: &str,
    default_profile: &str,
    active_profile: &str,
    allow_replacement: bool,
    allow_multiple_profiles: bool,
) -> SystemIdentity {
    SystemIdentity {
        project_name: project_name.to_string(),
        default_profile: default_profile.to_string(),
        active_profile: active_profile.to_string(),
        allow_replacement,
        allow_multiple_profiles,
    }
}

pub fn build_runtime_config(
    owner_name: &str,
    primary_provider: &str,
    primary_model: &str,
    deployment_target: &str,
    setup_complete: bool,
    identity: SystemIdentity,
    onboarding: OnboardingConfig,
) -> RuntimeConfig {
    RuntimeConfig {
        owner_name: owner_name.to_string(),
        primary_provider: primary_provider.to_string(),
        primary_model: primary_model.to_string(),
        deployment_target: deployment_target.to_string(),
        setup_complete,
        identity,
        onboarding,
    }
}

