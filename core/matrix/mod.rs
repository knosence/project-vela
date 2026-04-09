use crate::models::ValidationFinding;

pub fn validate_parent_consistency(path: &str, text: &str) -> Vec<ValidationFinding> {
    let frontmatter = parse_frontmatter(text);
    let fm_parent = normalize_parent(
        frontmatter_value(&frontmatter, "parent")
            .unwrap_or_default()
            .to_string(),
    );
    let declaration_parent = normalize_parent(extract_declaration_parent(text));
    let is_cornerstone = path.ends_with("Cornerstone.Project-Vela-SoT.md");

    let mut findings = Vec::new();

    if is_cornerstone {
        if !matches!(declaration_parent.as_str(), "" | "none") {
            findings.push(ValidationFinding::error(
                "MATRIX_CORNERSTONE_DECLARATION_PARENT_INVALID",
                format!("{path} must declare `Parent: None` in the Subject Declaration"),
            ));
        }
        return findings;
    }

    if !fm_parent.is_empty() && !declaration_parent.is_empty() && fm_parent != declaration_parent {
        findings.push(ValidationFinding::error(
            "MATRIX_PARENT_DECLARATION_MISMATCH",
            format!("{path} frontmatter parent does not match Subject Declaration parent"),
        ));
    }

    if requires_hub_parent(path, frontmatter_value(&frontmatter, "domain").unwrap_or_default())
        && fm_parent.contains("cornerstone.project-vela-sot#")
    {
        findings.push(ValidationFinding::error(
            "MATRIX_HUB_PARENT_REQUIRED",
            format!("{path} should attach to a dimension hub or governed local parent instead of directly to the cornerstone"),
        ));
    }

    findings
}

fn parse_frontmatter(text: &str) -> Vec<(String, String)> {
    let mut lines = text.lines();
    if lines.next() != Some("---") {
        return Vec::new();
    }

    let mut entries = Vec::new();
    for line in lines {
        if line == "---" {
            break;
        }
        if let Some((key, value)) = line.split_once(':') {
            entries.push((key.trim().to_string(), value.trim().to_string()));
        }
    }
    entries
}

fn frontmatter_value<'a>(frontmatter: &'a [(String, String)], key: &str) -> Option<&'a str> {
    frontmatter
        .iter()
        .find(|(candidate, _)| candidate == key)
        .map(|(_, value)| value.as_str())
}

fn extract_declaration_parent(text: &str) -> String {
    text.lines()
        .map(str::trim)
        .find_map(|line| line.strip_prefix("**Parent:**").map(str::trim))
        .unwrap_or_default()
        .to_string()
}

fn normalize_parent(value: String) -> String {
    value.trim().trim_matches('"').trim_matches('\'').to_lowercase()
}

fn requires_hub_parent(path: &str, domain: &str) -> bool {
    if domain.trim() == "agents" {
        return true;
    }
    if domain.trim() == "dimensions" {
        return !is_dimension_hub(path);
    }
    false
}

fn is_dimension_hub(path: &str) -> bool {
    let name = path.rsplit('/').next().unwrap_or(path);
    let bytes = name.as_bytes();
    bytes.len() >= 12
        && bytes[0].is_ascii_digit()
        && bytes[1].is_ascii_digit()
        && bytes[2].is_ascii_digit()
        && bytes[3] == b'.'
        && name.ends_with("-SoT.md")
}

#[cfg(test)]
mod tests {
    use super::validate_parent_consistency;

    #[test]
    fn rejects_direct_root_attachment_for_agent_branch() {
        let text = "---\n\
sot-type: system\n\
created: 2026-04-08\n\
last-rewritten: 2026-04-08\n\
parent: \"[[Cornerstone.Project-Vela-SoT#100.WHO.Circle]]\"\n\
domain: agents\n\
status: active\n\
tags: [\"agent\"]\n\
---\n\n\
# Example\n\n\
## 000.Index\n\n\
### Subject Declaration\n\n\
**Parent:** [[Cornerstone.Project-Vela-SoT#100.WHO.Circle]]\n";

        let findings = validate_parent_consistency("knowledge/agents/example/WHO.Example-Identity-SoT.md", text);
        assert!(findings.iter().any(|item| item.code == "MATRIX_HUB_PARENT_REQUIRED"));
    }

    #[test]
    fn rejects_direct_root_attachment_for_dimension_branch() {
        let text = "---\n\
sot-type: dimension\n\
created: 2026-04-08\n\
last-rewritten: 2026-04-08\n\
parent: \"[[Cornerstone.Project-Vela-SoT#200.WHAT.Domain]]\"\n\
domain: dimensions\n\
status: active\n\
tags: [\"dimension\"]\n\
---\n\n\
# Example\n\n\
## 000.Index\n\n\
### Subject Declaration\n\n\
**Parent:** [[Cornerstone.Project-Vela-SoT#200.WHAT.Domain]]\n";

        let findings = validate_parent_consistency("knowledge/dimensions/WHAT.Example-Branch-SoT.md", text);
        assert!(findings.iter().any(|item| item.code == "MATRIX_HUB_PARENT_REQUIRED"));
    }
}
