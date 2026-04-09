use crate::models::{GovernedReference, ValidationFinding};

pub fn inspect_reference(path: &str, text: &str) -> (Option<GovernedReference>, Vec<ValidationFinding>) {
    let mut findings = Vec::new();
    let frontmatter = parse_frontmatter(text);

    let required_fields = [
        "sot-type",
        "created",
        "last-rewritten",
        "parent",
        "domain",
        "status",
        "tags",
    ];
    for field in required_fields {
        if !frontmatter.iter().any(|(key, _)| key == field) {
            findings.push(ValidationFinding::error(
                "MATRIX_REFERENCE_FRONTMATTER_REQUIRED",
                format!("{path} is missing required frontmatter field `{field}`"),
            ));
        }
    }

    let ref_type = frontmatter_value(&frontmatter, "sot-type").unwrap_or_default();
    if ref_type != "reference" {
        findings.push(ValidationFinding::error(
            "MATRIX_REFERENCE_TYPE_REQUIRED",
            format!("{path} must declare `sot-type: reference`"),
        ));
    }

    let parent = frontmatter_value(&frontmatter, "parent").unwrap_or_default();
    if parent.trim().is_empty() {
        findings.push(ValidationFinding::error(
            "MATRIX_REFERENCE_PARENT_REQUIRED",
            format!("{path} must declare a non-empty parent"),
        ));
    }

    for heading in [
        "## This Reference Declares the Release Packet and the Review Chain",
        "## This Reference Links the Governing Inputs and Outputs",
        "## This Reference States the Release Judgment Clearly",
    ] {
        if !text.contains(heading) {
            findings.push(ValidationFinding::error(
                "MATRIX_REFERENCE_HEADING_REQUIRED",
                format!("{path} is missing required heading `{heading}`"),
            ));
        }
    }

    let reference = if findings.is_empty() {
        Some(GovernedReference {
            path: path.to_string(),
            title: extract_title(text),
            ref_type: ref_type.to_string(),
            inventory_role: "governed-reference".to_string(),
            parent: parent.to_string(),
            domain: frontmatter_value(&frontmatter, "domain").unwrap_or_default().to_string(),
            status: frontmatter_value(&frontmatter, "status").unwrap_or_default().to_string(),
        })
    } else {
        None
    };

    (reference, findings)
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
            entries.push((key.trim().to_string(), value.trim().trim_matches('"').to_string()));
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

fn extract_title(text: &str) -> String {
    text.lines()
        .find_map(|line| line.strip_prefix("# ").map(str::trim))
        .unwrap_or("Untitled Reference")
        .to_string()
}

#[cfg(test)]
mod tests {
    use super::inspect_reference;

    #[test]
    fn inspects_valid_release_intelligence_reference() {
        let text = "---\n\
sot-type: reference\n\
created: 2026-04-08\n\
last-rewritten: 2026-04-08\n\
parent: \"[[WHAT.Repo-Watchlist-SoT#200.WHAT.Scope]]\"\n\
domain: repo-watch\n\
status: active\n\
tags: [\"repo-watch\",\"release\",\"reference\"]\n\
---\n\n\
# Release Intelligence openai/openai-python 1.2.3\n\n\
## This Reference Declares the Release Packet and the Review Chain\n\
The packet exists.\n\n\
## This Reference Links the Governing Inputs and Outputs\n\
- Packet: `knowledge/refs/x.packet.json`\n\n\
## This Reference States the Release Judgment Clearly\n\
- Breaking change risk: `high`\n";

        let (reference, findings) =
            inspect_reference("knowledge/refs/Ref.example.Release-Intelligence.md", text);

        assert!(findings.is_empty());
        let reference = reference.expect("reference should parse");
        assert_eq!(reference.domain, "repo-watch");
        assert_eq!(reference.ref_type, "reference");
    }

    #[test]
    fn rejects_reference_missing_required_heading() {
        let text = "---\n\
sot-type: reference\n\
created: 2026-04-08\n\
last-rewritten: 2026-04-08\n\
parent: \"[[WHAT.Repo-Watchlist-SoT#200.WHAT.Scope]]\"\n\
domain: repo-watch\n\
status: active\n\
tags: [\"repo-watch\",\"release\",\"reference\"]\n\
---\n\n\
# Release Intelligence openai/openai-python 1.2.3\n";

        let (_, findings) =
            inspect_reference("knowledge/refs/Ref.example.Release-Intelligence.md", text);

        assert!(findings
            .iter()
            .any(|item| item.code == "MATRIX_REFERENCE_HEADING_REQUIRED"));
    }
}
