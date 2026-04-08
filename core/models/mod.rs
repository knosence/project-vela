#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProfileBinding {
    pub name: String,
    pub base_profile: Option<String>,
    pub active: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SystemIdentity {
    pub project_name: String,
    pub default_profile: String,
    pub allow_replacement: bool,
}

