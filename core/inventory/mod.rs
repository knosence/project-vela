use std::fs;
use std::path::{Path, PathBuf};

use crate::models::{GovernedReference, GrowthTarget, MatrixSoT, ValidationFinding};
use crate::references::inspect_reference;

const BASE36_CHILD_SLOTS: &str = "123456789abcdefghijklmnopqrstuvwxyz";
const REF_SUFFIX_SLOTS: &str = "abcdefghijklmnopqrstuvwxyz";
const HUB_IDS: [&str; 7] = ["100", "200", "300", "400", "500", "600", "700"];

pub fn discover_matrix_inventory(
    root: &Path,
) -> (
    Vec<MatrixSoT>,
    Vec<GovernedReference>,
    Vec<ValidationFinding>,
) {
    let entries = discover_sots(root);
    let (references, findings) = discover_references(root);
    (entries, references, findings)
}

pub fn list_growth_targets(root: &Path) -> Vec<GrowthTarget> {
    discover_sots(root)
        .into_iter()
        .filter(|item| item.inventory_role != "governed-reference")
        .filter(|item| !item.path.starts_with("knowledge/ARTIFACTS/"))
        .map(|item| GrowthTarget {
            path: item.path,
            inventory_role: item.inventory_role,
        })
        .collect()
}

pub fn inventory_area_for_path(path: &str) -> Option<&'static str> {
    let normalized = path.replace('\\', "/");
    if normalized == "knowledge/Cornerstone.Knosence-SoT.md" {
        Some("cornerstone")
    } else if normalized.starts_with("knowledge/")
        && normalized.matches('/').count() == 1
        && normalized.ends_with("-Ref.md")
    {
        Some("references")
    } else if normalized.starts_with("knowledge/ARTIFACTS/refs/") {
        Some("artifacts")
    } else if normalized.starts_with("knowledge/ARTIFACTS/") {
        Some("artifacts")
    } else if normalized.starts_with("knowledge/INBOX/") {
        Some("inbox")
    } else if normalized.starts_with("knowledge/") && normalized.ends_with("-SoT.md") {
        let name = normalized.rsplit('/').next().unwrap_or(normalized.as_str());
        if matrix_id_kind_for_name(name) == Some("hub") {
            Some("dimensions")
        } else if is_agent_identity_name(name) {
            Some("agents")
        } else {
            Some("knowledge")
        }
    } else if normalized.starts_with("knowledge/") {
        Some("knowledge")
    } else {
        None
    }
}

pub fn inventory_role_for_path(path: &str) -> Option<&'static str> {
    let area = inventory_area_for_path(path)?;
    if matches!(area, "artifacts" | "references" | "inbox") {
        return None;
    }
    Some(classify_sot_role(path, area))
}

pub fn inferred_inventory_role_for_path(path: &str) -> Option<&'static str> {
    inventory_role_for_path(path).or_else(|| {
        let name = path.rsplit('/').next().unwrap_or(path);
        if name == "Cornerstone.Knosence-SoT.md" {
            Some("cornerstone")
        } else if is_agent_identity_name(name) {
            Some("agent-identity")
        } else if matrix_id_kind_for_name(name) == Some("hub") {
            Some("dimension-hub")
        } else if name.ends_with("-SoT.md") {
            Some("branch-sot")
        } else {
            None
        }
    })
}

fn discover_sots(root: &Path) -> Vec<MatrixSoT> {
    let mut paths = Vec::new();
    collect_files(&root.join("knowledge"), &mut paths);
    paths.sort();

    let mut entries = Vec::new();
    for path in paths {
        if path.parent() != Some(&root.join("knowledge"))
            || !path.to_string_lossy().ends_with("-SoT.md")
        {
            continue;
        }
        let rel = relative_path(root, &path);
        if !rel.starts_with("knowledge/") {
            continue;
        }
        let Ok(text) = fs::read_to_string(&path) else {
            continue;
        };
        let frontmatter = parse_frontmatter(&text);
        let area = inventory_area_for_path(&rel)
            .unwrap_or("knowledge")
            .to_string();
        let inventory_role = classify_sot_role(&rel, &area).to_string();
        entries.push(MatrixSoT {
            path: rel.clone(),
            title: extract_title(&text, "Untitled SoT"),
            sot_type: frontmatter_value(&frontmatter, "sot-type")
                .unwrap_or("unknown")
                .to_string(),
            inventory_role,
            parent: frontmatter_value(&frontmatter, "parent")
                .unwrap_or_default()
                .to_string(),
            domain: frontmatter_value(&frontmatter, "domain")
                .unwrap_or("unknown")
                .to_string(),
            status: frontmatter_value(&frontmatter, "status")
                .unwrap_or("unknown")
                .to_string(),
            area,
            is_cornerstone: rel.ends_with("Cornerstone.Knosence-SoT.md"),
        });
    }
    entries
}

fn discover_references(root: &Path) -> (Vec<GovernedReference>, Vec<ValidationFinding>) {
    let mut paths = Vec::new();
    collect_files(&root.join("knowledge"), &mut paths);
    paths.sort();

    let mut references = Vec::new();
    let mut findings = Vec::new();
    for path in paths {
        if path.parent() != Some(&root.join("knowledge")) {
            continue;
        }
        let name = path
            .file_name()
            .and_then(|item| item.to_str())
            .unwrap_or_default();
        if !is_governed_reference_name(name) {
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

fn is_governed_reference_name(name: &str) -> bool {
    if !name.ends_with(".md") {
        return false;
    }
    if matches!(
        name,
        "000.INDEX.Knosence-Matrix-Ref.md" | "Index.Knosence-Matrix-Ref.md"
    ) {
        return false;
    }
    name.ends_with("-Ref.md") && matrix_id_kind_for_name(name) == Some("ref")
}

pub fn next_available_direct_child_id(root: &Path, hub_id: &str) -> Option<String> {
    if !HUB_IDS.contains(&hub_id) {
        return None;
    }
    let knowledge_dir = root.join("knowledge");
    let mut used = std::collections::BTreeSet::new();
    let Ok(entries) = fs::read_dir(&knowledge_dir) else {
        return None;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let Some(name) = path.file_name().and_then(|item| item.to_str()) else {
            continue;
        };
        if matrix_id_kind_for_name(name) != Some("direct-child") {
            continue;
        }
        let Some(id) = matrix_numeric_id_for_name(name) else {
            continue;
        };
        if hub_id_for_numeric_id(&id).as_deref() == Some(hub_id) {
            used.insert(id);
        }
    }
    for slot in BASE36_CHILD_SLOTS.chars() {
        let candidate = format!("{}{}0", &hub_id[0..1], slot);
        if !used.contains(&candidate) {
            return Some(candidate);
        }
    }
    None
}

pub fn next_available_ref_id(root: &Path, parent_numeric_id: &str) -> Option<String> {
    if parent_numeric_id.len() != 3 || !parent_numeric_id.chars().all(is_base36_lower) {
        return None;
    }
    let mut used = std::collections::BTreeSet::new();
    let Ok(entries) = fs::read_dir(root.join("knowledge")) else {
        return None;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let Some(name) = path.file_name().and_then(|item| item.to_str()) else {
            continue;
        };
        if matrix_id_kind_for_name(name) != Some("ref") {
            continue;
        }
        let Some(token) = matrix_id_token(name) else {
            continue;
        };
        if token.starts_with(parent_numeric_id) {
            used.insert(token);
        }
    }
    for suffix in REF_SUFFIX_SLOTS.chars() {
        let candidate = format!("{parent_numeric_id}{suffix}");
        if !used.contains(&candidate) {
            return Some(candidate);
        }
    }
    None
}

pub fn hub_id_for_numeric_id(id: &str) -> Option<String> {
    match id.len() {
        3 => {
            let first = id.chars().next()?;
            Some(format!("{first}00"))
        }
        4 => {
            let numeric: String = id.chars().take(3).collect();
            hub_id_for_numeric_id(&numeric)
        }
        _ => None,
    }
}

pub fn matrix_context_for_name(name: &str) -> Option<String> {
    let stem = name.strip_suffix(".md")?;
    let mut parts = stem.split('.');
    let _id = parts.next()?;
    let context = parts.next()?;
    if context.is_empty() {
        return None;
    }
    Some(context.to_string())
}

pub fn matrix_subject_for_name(name: &str) -> Option<String> {
    let stem = name.strip_suffix(".md")?;
    let mut parts = stem.splitn(3, '.');
    let _id = parts.next()?;
    let _context = parts.next()?;
    let subject_and_type = parts.next()?;
    let subject = subject_and_type
        .strip_suffix("-SoT")
        .or_else(|| subject_and_type.strip_suffix("-Ref"))
        .unwrap_or(subject_and_type);
    Some(subject.to_string())
}

fn classify_sot_role(path: &str, area: &str) -> &'static str {
    if path.ends_with("Cornerstone.Knosence-SoT.md") {
        return "cornerstone";
    }
    if area == "dimensions" && matrix_id_kind_for_path(path) == Some("hub") {
        return "dimension-hub";
    }
    if area == "agents" && is_agent_identity_name(path.rsplit('/').next().unwrap_or(path)) {
        return "agent-identity";
    }
    "branch-sot"
}

pub fn matrix_numeric_id_for_path(path: &str) -> Option<String> {
    let name = path.rsplit('/').next().unwrap_or(path);
    matrix_numeric_id_for_name(name)
}

pub fn matrix_numeric_id_for_name(name: &str) -> Option<String> {
    let token = matrix_id_token(name)?;
    match token.len() {
        3 => Some(token),
        4 => Some(token.chars().take(3).collect()),
        _ => None,
    }
}

pub fn matrix_id_kind_for_path(path: &str) -> Option<&'static str> {
    let name = path.rsplit('/').next().unwrap_or(path);
    matrix_id_kind_for_name(name)
}

pub fn matrix_id_kind_for_name(name: &str) -> Option<&'static str> {
    if is_index_reference_name(name) {
        return Some("ref");
    }
    let token = matrix_id_token(name)?;
    match token.len() {
        3 if HUB_IDS.contains(&token.as_str()) => Some("hub"),
        3 if token.ends_with('0') => Some("direct-child"),
        3 => Some("grandchild"),
        4 if token
            .chars()
            .last()
            .is_some_and(|item| item.is_ascii_lowercase()) =>
        {
            Some("ref")
        }
        _ => None,
    }
}

fn matrix_id_token(name: &str) -> Option<String> {
    if name == "Cornerstone.Knosence-SoT.md" {
        return Some("Cornerstone".to_string());
    }
    let stem = name.strip_suffix(".md")?;
    let token = stem.split_once('.')?.0;
    if token.len() == 3 && token.chars().all(is_base36_lower) {
        return Some(token.to_string());
    }
    if token.len() == 4 {
        let mut chars = token.chars();
        let prefix: String = chars.by_ref().take(3).collect();
        let suffix = chars.next()?;
        if prefix.chars().all(is_base36_lower) && suffix.is_ascii_lowercase() {
            return Some(token.to_string());
        }
    }
    None
}

fn is_index_reference_name(name: &str) -> bool {
    if !name.ends_with("-Ref.md") {
        return false;
    }
    let stem = match name.strip_suffix(".md") {
        Some(value) => value,
        None => return false,
    };
    let mut parts = stem.splitn(3, '.');
    let Some(token) = parts.next() else {
        return false;
    };
    let Some(context) = parts.next() else {
        return false;
    };
    token.len() == 3
        && token.starts_with("00")
        && token.chars().all(is_base36_lower)
        && context == "INDEX"
}

fn is_base36_lower(value: char) -> bool {
    value.is_ascii_digit() || value.is_ascii_lowercase()
}

fn is_agent_identity_name(name: &str) -> bool {
    name.ends_with("-Identity-SoT.md") && matrix_id_kind_for_name(name).is_some()
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
            entries.push((
                key.trim().to_string(),
                value.trim().trim_matches('"').to_string(),
            ));
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

    use super::discover_matrix_inventory;

    #[test]
    fn discovers_matrix_inventory_from_repo_state() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("workspace root");
        let (entries, references, findings) = discover_matrix_inventory(root);

        assert!(!entries.is_empty());
        assert!(entries.iter().any(|item| item.is_cornerstone));
        assert!(entries
            .iter()
            .any(|item| item.inventory_role == "cornerstone"));
        assert!(entries
            .iter()
            .any(|item| item.inventory_role == "dimension-hub"));
        assert!(entries
            .iter()
            .any(|item| item.inventory_role == "agent-identity"));
        assert!(entries
            .iter()
            .any(|item| item.inventory_role == "branch-sot"));
        assert!(references
            .iter()
            .all(|item| item.inventory_role == "governed-reference"));
        assert!(findings.is_empty() || findings.iter().all(|item| !item.code.is_empty()));
    }
}
