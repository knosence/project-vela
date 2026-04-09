use std::fs;
use std::path::{Path, PathBuf};

use crate::models::{GovernedReference, MatrixSoT, Severity, ValidationFinding};
use crate::references::inspect_reference;

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

pub fn build_matrix_index(root: &Path) -> (Vec<MatrixSoT>, Vec<GovernedReference>, Vec<ValidationFinding>, String, String) {
    let entries = discover_sots(root);
    let (references, mut findings) = discover_references(root);
    findings.extend(validate_matrix_rules(&entries));

    for entry in &entries {
        let path = root.join(&entry.path);
        if let Ok(text) = fs::read_to_string(&path) {
            findings.extend(validate_sot_structure(&entry.path, &text));
            findings.extend(validate_parent_consistency(&entry.path, &text));
        }
    }

    let markdown = render_matrix_index(&entries, &references);
    let snapshot_json = render_matrix_snapshot_json(&entries, &references, &findings);
    (entries, references, findings, markdown, snapshot_json)
}

pub fn validate_sot_structure(path: &str, text: &str) -> Vec<ValidationFinding> {
    let frontmatter = parse_frontmatter(text);
    let is_cornerstone = path.ends_with("Cornerstone.Project-Vela-SoT.md");
    let mut findings = Vec::new();

    for field in REQUIRED_FRONTMATTER_FIELDS {
        if !frontmatter.iter().any(|(key, _)| key == field) {
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

fn discover_sots(root: &Path) -> Vec<MatrixSoT> {
    let mut paths = Vec::new();
    collect_files(&root.join("knowledge"), &mut paths);
    paths.sort();

    let mut entries = Vec::new();
    for path in paths {
        if !path.to_string_lossy().ends_with("-SoT.md") {
            continue;
        }
        let rel = relative_path(root, &path);
        let mut parts = rel.split('/');
        if parts.next() != Some("knowledge") {
            continue;
        }
        let area = parts.next().unwrap_or_default().to_string();
        if !matches!(area.as_str(), "cornerstone" | "dimensions" | "agents") {
            continue;
        }
        let Ok(text) = fs::read_to_string(&path) else {
            continue;
        };
        let frontmatter = parse_frontmatter(&text);
        entries.push(MatrixSoT {
            path: rel.clone(),
            title: extract_title(&text, "Untitled SoT"),
            sot_type: frontmatter_value(&frontmatter, "sot-type").unwrap_or("unknown").to_string(),
            parent: frontmatter_value(&frontmatter, "parent").unwrap_or_default().to_string(),
            domain: frontmatter_value(&frontmatter, "domain").unwrap_or("unknown").to_string(),
            status: frontmatter_value(&frontmatter, "status").unwrap_or("unknown").to_string(),
            area,
            is_cornerstone: rel.ends_with("Cornerstone.Project-Vela-SoT.md"),
        });
    }
    entries
}

fn discover_references(root: &Path) -> (Vec<GovernedReference>, Vec<ValidationFinding>) {
    let mut paths = Vec::new();
    collect_files(&root.join("knowledge/refs"), &mut paths);
    paths.sort();

    let mut references = Vec::new();
    let mut findings = Vec::new();
    for path in paths {
        let name = path.file_name().and_then(|item| item.to_str()).unwrap_or_default();
        if !name.starts_with("Ref.") || !name.ends_with(".md") || name == "Index.Project-Vela-Matrix-Ref.md" {
            continue;
        }
        let rel = relative_path(root, &path);
        let Ok(text) = fs::read_to_string(&path) else {
            continue;
        };
        let (reference, ref_findings) = inspect_reference(&rel, &text);
        if let Some(reference) = reference {
            references.push(reference);
        }
        findings.extend(ref_findings);
    }

    (references, findings)
}

fn validate_matrix_rules(entries: &[MatrixSoT]) -> Vec<ValidationFinding> {
    let mut findings = Vec::new();
    let cornerstone_count = entries.iter().filter(|item| item.is_cornerstone).count();

    if cornerstone_count != 1 {
        findings.push(ValidationFinding::error(
            "MATRIX_SINGLE_CORNERSTONE_REQUIRED",
            format!("Expected exactly one cornerstone, found {cornerstone_count}"),
        ));
    }

    for entry in entries {
        if !entry.is_cornerstone && entry.parent.trim().is_empty() {
            findings.push(ValidationFinding::error(
                "MATRIX_PARENT_REQUIRED",
                format!("{} is missing a parent link", entry.path),
            ));
        }
    }

    findings
}

fn render_matrix_index(entries: &[MatrixSoT], refs: &[GovernedReference]) -> String {
    let mut lines = vec![
        "---".to_string(),
        "sot-type: reference".to_string(),
        "created: 2026-04-08".to_string(),
        "last-rewritten: 2026-04-08".to_string(),
        "parent: \"[[Cornerstone.Project-Vela-SoT#000.Index]]\"".to_string(),
        "domain: matrix".to_string(),
        "status: active".to_string(),
        "tags: [\"matrix\",\"index\",\"reference\",\"registry\"]".to_string(),
        "---".to_string(),
        "".to_string(),
        "# Project Vela Matrix Index".to_string(),
        "".to_string(),
        "## This Registry Gives a Top Level View of Every Source of Truth in the Matrix".to_string(),
        "The index layer exists so the system can see the matrix as a whole, keep track of canonical homes, and verify that the tree still respects the root, parent, and indexing laws.".to_string(),
        "".to_string(),
        "## This Summary Shows the Current Shape of the Matrix at a Glance".to_string(),
        format!("- total SoTs: {}", entries.len()),
        format!("- total governed refs: {}", refs.len()),
        format!("- cornerstone count: {}", entries.iter().filter(|item| item.is_cornerstone).count()),
        format!("- indexed areas: {}", indexed_areas(entries)),
        "".to_string(),
    ];

    for area in ["agents", "cornerstone", "dimensions"] {
        let area_entries: Vec<&MatrixSoT> = entries.iter().filter(|item| item.area == area).collect();
        if area_entries.is_empty() {
            continue;
        }
        lines.push(format!(
            "## This Section Lists the {} SoTs Registered in the Matrix",
            capitalize(area)
        ));
        lines.push("| Title | Path | Type | Parent | Status |".to_string());
        lines.push("|---|---|---|---|---|".to_string());
        for item in area_entries {
            let parent = if item.parent.is_empty() { "Cornerstone" } else { item.parent.as_str() };
            lines.push(format!(
                "| {} | `{}` | `{}` | `{}` | `{}` |",
                item.title, item.path, item.sot_type, parent, item.status
            ));
        }
        lines.push(String::new());
    }

    if !refs.is_empty() {
        lines.push("## This Section Lists Governed References Registered in the Matrix".to_string());
        lines.push("| Title | Path | Type | Parent | Status |".to_string());
        lines.push("|---|---|---|---|---|".to_string());
        for item in refs {
            lines.push(format!(
                "| {} | `{}` | `{}` | `{}` | `{}` |",
                item.title, item.path, item.ref_type, item.parent, item.status
            ));
        }
        lines.push(String::new());
    }

    lines.extend([
        "## This Registry Points Back to the Root and the Governing Laws".to_string(),
        "- Root: [[Cornerstone.Project-Vela-SoT]]".to_string(),
        "- Laws: `docs/directives/matrix-laws.md`".to_string(),
        "".to_string(),
    ]);

    lines.join("\n")
}

fn render_matrix_snapshot_json(
    entries: &[MatrixSoT],
    refs: &[GovernedReference],
    findings: &[ValidationFinding],
) -> String {
    let entries_json = entries
        .iter()
        .map(|item| {
            format!(
                "{{\"path\":\"{}\",\"title\":\"{}\",\"sot_type\":\"{}\",\"parent\":\"{}\",\"domain\":\"{}\",\"status\":\"{}\",\"area\":\"{}\",\"is_cornerstone\":{}}}",
                json_escape(&item.path),
                json_escape(&item.title),
                json_escape(&item.sot_type),
                json_escape(&item.parent),
                json_escape(&item.domain),
                json_escape(&item.status),
                json_escape(&item.area),
                if item.is_cornerstone { "true" } else { "false" },
            )
        })
        .collect::<Vec<String>>()
        .join(",");
    let refs_json = refs
        .iter()
        .map(|item| {
            format!(
                "{{\"path\":\"{}\",\"title\":\"{}\",\"ref_type\":\"{}\",\"parent\":\"{}\",\"domain\":\"{}\",\"status\":\"{}\"}}",
                json_escape(&item.path),
                json_escape(&item.title),
                json_escape(&item.ref_type),
                json_escape(&item.parent),
                json_escape(&item.domain),
                json_escape(&item.status),
            )
        })
        .collect::<Vec<String>>()
        .join(",");
    let findings_json = findings
        .iter()
        .map(render_finding_json)
        .collect::<Vec<String>>()
        .join(",");
    format!(
        "{{\"entries\":[{entries_json}],\"references\":[{refs_json}],\"findings\":[{findings_json}]}}"
    )
}

fn render_finding_json(item: &ValidationFinding) -> String {
    let rule_refs = item
        .rule_refs
        .iter()
        .map(|rule| format!("\"{}\"", json_escape(rule)))
        .collect::<Vec<String>>()
        .join(",");
    format!(
        "{{\"code\":\"{}\",\"detail\":\"{}\",\"severity\":\"{}\",\"rule_refs\":[{}]}}",
        json_escape(&item.code),
        json_escape(&item.detail),
        severity_label(&item.severity),
        rule_refs
    )
}

fn severity_label(severity: &Severity) -> &'static str {
    match severity {
        Severity::Info => "info",
        Severity::Warning => "warning",
        Severity::Error => "error",
    }
}

fn json_escape(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
}

fn indexed_areas(entries: &[MatrixSoT]) -> String {
    let mut areas = entries.iter().map(|item| item.area.as_str()).collect::<Vec<&str>>();
    areas.sort();
    areas.dedup();
    areas.join(", ")
}

fn capitalize(value: &str) -> String {
    let mut chars = value.chars();
    match chars.next() {
        Some(first) => format!("{}{}", first.to_ascii_uppercase(), chars.as_str()),
        None => String::new(),
    }
}

fn extract_title(text: &str, fallback: &str) -> String {
    text.lines()
        .find_map(|line| line.strip_prefix("# ").map(str::trim))
        .unwrap_or(fallback)
        .to_string()
}

fn collect_files(dir: &Path, files: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect_files(&path, files);
        } else {
            files.push(path);
        }
    }
}

fn relative_path(root: &Path, path: &Path) -> String {
    path.strip_prefix(root)
        .unwrap_or(path)
        .to_string_lossy()
        .replace('\\', "/")
}

#[cfg(test)]
mod tests {
    use std::path::Path;

    use super::{build_matrix_index, validate_parent_consistency, validate_sot_structure};

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

    #[test]
    fn builds_matrix_index_from_repo_state() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().expect("workspace root");
        let (entries, references, findings, markdown, snapshot_json) = build_matrix_index(root);

        assert!(!entries.is_empty());
        assert!(markdown.contains("Project Vela Matrix Index"));
        assert!(markdown.contains("Cornerstone.Project-Vela-SoT"));
        assert!(snapshot_json.contains("\"entries\""));
        assert!(snapshot_json.contains("\"references\""));
        assert!(findings.is_empty() || findings.iter().all(|item| !item.code.is_empty()));
        let _ = references;
    }
}
