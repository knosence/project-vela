use crate::models::SystemIdentity;

pub fn parse_system_identity(project_name: &str, default_profile: &str) -> SystemIdentity {
    SystemIdentity {
        project_name: project_name.to_string(),
        default_profile: default_profile.to_string(),
        allow_replacement: true,
    }
}

