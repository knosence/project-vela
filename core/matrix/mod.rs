use crate::models::ValidationFinding;

const REQUIRED_FRONTMATTER_FIELDS: [&str; 7] = [
    "sot-type",
    "created",
    "last-rewritten",
    "domain",
    "status",
    "tags",
    "parent",
];
const REQUIRED_HEADINGS: [&str; 16] = [
    "## 000.Index",
    "### Subject Declaration",
    "### Links",
    "### Inbox",
    "### Status",
    "### Open Questions",
    "### Next Actions",
    "### Decisions",
    "### Block Map",
    "## 100.",
    "## 200.",
    "## 300.",
    "## 400.",
    "## 500.",
    "## 600.",
    "## 700.",
];

pub fn validate_sot_structure(path: &str, text: &str) -> Vec<ValidationFinding> {
    let frontmatter = parse_frontmatter(text);
    let is_cornerstone = path.ends_with("Cornerstone.Project-Vela-SoT.md");
    let mut findings = Vec::new();

    for field in REQUIRED_FRONTMATTER_FIELDS {
        if frontmatter_value(&frontmatter, field).unwrap_or_default().is_empty() {
            findings.push(ValidationFinding::error(
                "MATRIX_FRONTMATTER_REQUIRED",
                format!("{path} is missing required frontmatter field `{field}`"),
            ));
        }
    }

    let parent_value = frontmatter_value(&frontmatter, "parent").unwrap_or_default().trim();
    if is_cornerstone {
        let normalized_parent = normalize_parent(parent_value.to_string());
        if !matches!(normalized_parent.as_str(), "" | "none") {
            findings.push(ValidationFinding::error(
                "MATRIX_CORNERSTONE_PARENT_MUST_BE_EMPTY",
                format!("{path} must declare an empty parent because the cornerstone is the root"),
            ));
        }
    } else if parent_value.is_empty() {
        findings.push(ValidationFinding::error(
            "MATRIX_PARENT_REQUIRED",
            format!("{path} must declare exactly one non-empty parent"),
        ));
    }

    for heading in REQUIRED_HEADINGS {
        if !text.contains(heading) {
            findings.push(ValidationFinding::error(
                "MATRIX_HEADING_REQUIRED",
                format!("{path} is missing required heading `{heading}`"),
            ));
        }
    }

    for dimension in ["100", "200", "300", "400", "500", "600"] {
        if let Some(section) = section_for_dimension(text, dimension) {
            if !section.contains("### Active") {
                findings.push(ValidationFinding::error(
                    "MATRIX_ACTIVE_SECTION_REQUIRED",
                    format!("{path} is missing `### Active` in dimension {dimension}"),
                ));
            }
            if !section.contains("### Inactive") {
                findings.push(ValidationFinding::error(
                    "MATRIX_INACTIVE_SECTION_REQUIRED",
                    format!("{path} is missing `### Inactive` in dimension {dimension}"),
                ));
            }
        }
    }

    findings
}

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

fn section_for_dimension<'a>(text: &'a str, dimension: &str) -> Option<&'a str> {
    let heading = format!("## {dimension}.");
    let start = text.find(&heading)?;
    let mut end = text.len();
    for candidate in ["200", "300", "400", "500", "600", "700"] {
        if candidate <= dimension {
            continue;
        }
        let marker = format!("## {candidate}.");
        if let Some(position) = text[start + 1..].find(&marker) {
            end = end.min(start + 1 + position);
        }
    }
    Some(&text[start..end])
}

#[cfg(test)]
mod tests {
    use super::{validate_parent_consistency, validate_sot_structure};

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

    #[test]
    fn rejects_missing_required_frontmatter_and_headings() {
        let text = "# Example\n\n## 000.Index\n\n### Subject Declaration\n\n**Parent:** None\n";

        let findings = validate_sot_structure("knowledge/cornerstone/Cornerstone.Project-Vela-SoT.md", text);
        assert!(findings.iter().any(|item| item.code == "MATRIX_FRONTMATTER_REQUIRED"));
        assert!(findings.iter().any(|item| item.code == "MATRIX_HEADING_REQUIRED"));
    }

    #[test]
    fn rejects_missing_active_and_inactive_dimension_sections() {
        let text = "---\n\
sot-type: system\n\
created: 2026-04-08\n\
last-rewritten: 2026-04-08\n\
parent: None\n\
domain: cornerstone\n\
status: active\n\
tags: [\"cornerstone\"]\n\
---\n\n\
# Example\n\n\
## 000.Index\n\n\
### Subject Declaration\n\n\
**Parent:** None\n\n\
### Links\n\n\
Links open the matrix into its governed branches.\n\n\
### Inbox\n\n\
Inbox captures unprocessed demand.\n\n\
### Status\n\n\
Status reports what remains true right now.\n\n\
### Open Questions\n\n\
Open questions preserve uncertainty explicitly.\n\n\
### Next Actions\n\n\
Next actions keep movement visible.\n\n\
### Decisions\n\n\
Decisions preserve committed turns.\n\n\
### Block Map\n\n\
The block map names the structural blocks once.\n\n\
## 100.WHO.Circle\n\n\
Circle identifies the living participants.\n\n\
## 200.WHAT.Domain\n\n\
Domain names the governed subject matter.\n\n\
### Active\n\n\
- Entry. (2026-04-08)\n  - Context.\n\n\
### Inactive\n\n\
- Prior entry. (2026-04-07)\n  - Context.\n\n\
## 300.WHERE.Terrain\n\n\
Terrain names the operational ground.\n\n\
### Active\n\n\
- Entry. (2026-04-08)\n  - Context.\n\n\
### Inactive\n\n\
- Prior entry. (2026-04-07)\n  - Context.\n\n\
## 400.WHEN.Chronicle\n\n\
Chronicle keeps timing legible.\n\n\
### Active\n\n\
- Entry. (2026-04-08)\n  - Context.\n\n\
### Inactive\n\n\
- Prior entry. (2026-04-07)\n  - Context.\n\n\
## 500.HOW.Method\n\n\
Method states how governed work happens.\n\n\
### Active\n\n\
- Entry. (2026-04-08)\n  - Context.\n\n\
### Inactive\n\n\
- Prior entry. (2026-04-07)\n  - Context.\n\n\
## 600.WHY.Compass\n\n\
Compass preserves purpose and refusal.\n\n\
### Active\n\n\
- Entry. (2026-04-08)\n  - Context.\n\n\
### Inactive\n\n\
- Prior entry. (2026-04-07)\n  - Context.\n\n\
## 700.Archive\n\n\
Archive preserves extracted history.\n";

        let findings = validate_sot_structure("knowledge/cornerstone/Cornerstone.Project-Vela-SoT.md", text);
        assert!(findings.iter().any(|item| item.code == "MATRIX_ACTIVE_SECTION_REQUIRED"));
        assert!(findings.iter().any(|item| item.code == "MATRIX_INACTIVE_SECTION_REQUIRED"));
    }
}
