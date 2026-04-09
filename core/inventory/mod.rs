use std::fs;
use std::path::{Path, PathBuf};

use crate::models::{GovernedReference, MatrixSoT, ValidationFinding};
use crate::references::inspect_reference;

pub fn discover_matrix_inventory(root: &Path) -> (Vec<MatrixSoT>, Vec<GovernedReference>, Vec<ValidationFinding>) {
    let entries = discover_sots(root);
    let (references, findings) = discover_references(root);
    (entries, references, findings)
}

pub fn inventory_area_for_path(path: &str) -> Option<&'static str> {
    let normalized = path.replace('\\', "/");
    if normalized == "knowledge/Cornerstone.Knosence-SoT.md" {
        Some("cornerstone")
    } else if normalized.starts_with("knowledge/ARTIFACTS/refs/") {
        Some("references")
    } else if normalized.starts_with("knowledge/ARTIFACTS/") {
        Some("artifacts")
    } else if normalized.starts_with("knowledge/INBOX/") {
        Some("inbox")
    } else if normalized.starts_with("knowledge/") && normalized.ends_with("-SoT.md") {
        let name = normalized.rsplit('/').next().unwrap_or(normalized.as_str());
        if is_dimension_hub_name(name) {
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
        } else if (name.starts_with("WHO.") || name.contains("Identity-SoT")) && name.ends_with(".md") {
            Some("agent-identity")
        } else if is_dimension_hub(path) {
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
        if path.parent() != Some(&root.join("knowledge")) || !path.to_string_lossy().ends_with("-SoT.md") {
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
        let area = inventory_area_for_path(&rel).unwrap_or("knowledge").to_string();
        let inventory_role = classify_sot_role(&rel, &area).to_string();
        entries.push(MatrixSoT {
            path: rel.clone(),
            title: extract_title(&text, "Untitled SoT"),
            sot_type: frontmatter_value(&frontmatter, "sot-type").unwrap_or("unknown").to_string(),
            inventory_role,
            parent: frontmatter_value(&frontmatter, "parent").unwrap_or_default().to_string(),
            domain: frontmatter_value(&frontmatter, "domain").unwrap_or("unknown").to_string(),
            status: frontmatter_value(&frontmatter, "status").unwrap_or("unknown").to_string(),
            area,
            is_cornerstone: rel.ends_with("Cornerstone.Knosence-SoT.md"),
        });
    }
    entries
}

fn discover_references(root: &Path) -> (Vec<GovernedReference>, Vec<ValidationFinding>) {
    let mut paths = Vec::new();
    collect_files(&root.join("knowledge/ARTIFACTS/refs"), &mut paths);
    paths.sort();

    let mut references = Vec::new();
    let mut findings = Vec::new();
    for path in paths {
        let name = path.file_name().and_then(|item| item.to_str()).unwrap_or_default();
        if !name.starts_with("Ref.") || !name.ends_with(".md") || name == "Index.Knosence-Matrix-Ref.md" {
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

fn classify_sot_role(path: &str, area: &str) -> &'static str {
    if path.ends_with("Cornerstone.Knosence-SoT.md") {
        return "cornerstone";
    }
    if area == "dimensions" && is_dimension_hub(path) {
        return "dimension-hub";
    }
    if area == "agents" && is_agent_identity_name(path.rsplit('/').next().unwrap_or(path)) {
        return "agent-identity";
    }
    "branch-sot"
}

fn is_dimension_hub(path: &str) -> bool {
    let name = path.rsplit('/').next().unwrap_or(path);
    is_dimension_hub_name(name)
}

fn is_dimension_hub_name(name: &str) -> bool {
    matches!(
        name,
        "100.WHO.Circle-SoT.md"
            | "200.WHAT.Domain-SoT.md"
            | "300.WHERE.Terrain-SoT.md"
            | "400.WHEN.Chronicle-SoT.md"
            | "500.HOW.Method-SoT.md"
            | "600.WHY.Compass-SoT.md"
    )
}

fn is_agent_identity_name(name: &str) -> bool {
    (name.starts_with("WHO.")
        || name.starts_with("100.WHO.")
        || name.starts_with("110.WHO.")
        || name.starts_with("111.WHO.")
        || name.starts_with("112.WHO."))
        && name.contains("Identity-SoT")
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
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().expect("workspace root");
        let (entries, references, findings) = discover_matrix_inventory(root);

        assert!(!entries.is_empty());
        assert!(entries.iter().any(|item| item.is_cornerstone));
        assert!(entries.iter().any(|item| item.inventory_role == "cornerstone"));
        assert!(entries.iter().any(|item| item.inventory_role == "dimension-hub"));
        assert!(entries.iter().any(|item| item.inventory_role == "agent-identity"));
        assert!(entries.iter().any(|item| item.inventory_role == "branch-sot"));
        assert!(references.iter().all(|item| item.inventory_role == "governed-reference"));
        assert!(findings.is_empty() || findings.iter().all(|item| !item.code.is_empty()));
    }
}
