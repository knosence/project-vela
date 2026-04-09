use crate::models::ValidationFinding;

pub fn is_sovereign_target(path: &str) -> bool {
    path == "knowledge/cornerstone/Cornerstone.Project-Vela-SoT.md"
        || path == "knowledge/proposals/TEST.Sovereign-Guardrail-Fixture.md"
        || path == "knowledge/dimensions/WHAT.Repo-Watchlist-SoT.md"
        || path.contains("Identity-SoT")
}

pub fn requires_human_approval(path: &str) -> bool {
    is_sovereign_target(path)
}

pub fn validate_commit_policy(path: &str, approval_granted: bool) -> Vec<ValidationFinding> {
    let mut findings = Vec::new();

    if requires_human_approval(path) && !approval_granted {
        findings.push(ValidationFinding::error(
            "SOVEREIGN_APPROVAL_REQUIRED",
            "Cornerstone or identity change attempted without human approval",
        ));
    }

    findings
}

pub fn route_for_target(task_type: &str, target: &str) -> &'static str {
    if is_sovereign_target(target) {
        "sovereign-change"
    } else if task_type == "repo-release" {
        "repo-watch"
    } else if task_type == "validate" {
        "validation"
    } else {
        "standard"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sovereign_targets_require_approval() {
        let findings = validate_commit_policy(
            "knowledge/cornerstone/Cornerstone.Project-Vela-SoT.md",
            false,
        );

        assert_eq!(route_for_target("write", "knowledge/cornerstone/Cornerstone.Project-Vela-SoT.md"), "sovereign-change");
        assert!(findings.iter().any(|item| item.code == "SOVEREIGN_APPROVAL_REQUIRED"));
    }

    #[test]
    fn repo_release_routes_to_repo_watch() {
        assert_eq!(
            route_for_target("repo-release", "knowledge/refs/repo-watch.md"),
            "repo-watch"
        );
    }

    #[test]
    fn standard_targets_can_commit_without_approval() {
        let findings = validate_commit_policy("knowledge/refs/operational-note.md", false);
        assert!(findings.is_empty());
    }
}
