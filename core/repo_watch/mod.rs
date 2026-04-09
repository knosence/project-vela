#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReleaseAssessment {
    pub watched: bool,
    pub risk_level: String,
    pub risk_signals: Vec<String>,
    pub relevance_level: String,
    pub relevance_signals: Vec<String>,
    pub watch_reason: String,
}

pub fn assess_release(repo: &str, notes: &str, watchlist_text: &str) -> ReleaseAssessment {
    let watchlist = parse_watchlist_entries(watchlist_text);
    let risk = assess_breaking_change_risk(notes);
    let relevance = assess_local_relevance(repo, notes, &watchlist, &risk.level);
    let watch_reason = watchlist
        .iter()
        .find(|item| item.repo == repo)
        .map(|item| item.reason.clone())
        .unwrap_or_default();

    ReleaseAssessment {
        watched: watchlist.iter().any(|item| item.repo == repo),
        risk_level: risk.level,
        risk_signals: risk.signals,
        relevance_level: relevance.level,
        relevance_signals: relevance.signals,
        watch_reason,
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct WatchEntry {
    repo: String,
    reason: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct LevelSignals {
    level: String,
    signals: Vec<String>,
}

fn parse_watchlist_entries(watchlist_text: &str) -> Vec<WatchEntry> {
    let mut entries = Vec::new();
    let mut current_repo = String::new();

    for line in watchlist_text.lines().map(str::trim) {
        if let Some(repo) = parse_repo_line(line) {
            current_repo = repo.to_string();
            continue;
        }
        if !current_repo.is_empty() && line.starts_with("- ") {
            entries.push(WatchEntry {
                repo: current_repo.clone(),
                reason: line.trim_start_matches("- ").to_string(),
            });
            current_repo.clear();
        }
    }

    entries
}

fn parse_repo_line(line: &str) -> Option<&str> {
    if !line.starts_with("- ") || !line.contains(". (") {
        return None;
    }
    let repo = line.trim_start_matches("- ").split(". (").next()?;
    if repo.contains('/') {
        Some(repo)
    } else {
        None
    }
}

fn assess_breaking_change_risk(notes: &str) -> LevelSignals {
    let lowered = notes.to_lowercase();
    let high_keywords = [
        "breaking",
        "migration",
        "removed",
        "deprecat",
        "rename",
        "drop support",
        "incompatib",
    ];
    let medium_keywords = [
        "changed",
        "updated",
        "refactor",
        "new default",
        "new auth",
        "retry",
        "timeout",
    ];

    let high_matches = match_keywords(&lowered, &high_keywords);
    if !high_matches.is_empty() {
        return LevelSignals {
            level: "high".to_string(),
            signals: high_matches,
        };
    }

    let medium_matches = match_keywords(&lowered, &medium_keywords);
    if !medium_matches.is_empty() {
        return LevelSignals {
            level: "medium".to_string(),
            signals: medium_matches,
        };
    }

    LevelSignals {
        level: "low".to_string(),
        signals: vec!["no obvious breaking-change markers detected".to_string()],
    }
}

fn assess_local_relevance(repo: &str, notes: &str, watchlist: &[WatchEntry], risk_level: &str) -> LevelSignals {
    let lowered = notes.to_lowercase();
    let watch_reason = watchlist.iter().find(|item| item.repo == repo);
    let keywords = match repo {
        "openai/openai-python" => vec!["python", "sdk", "client", "responses", "chat", "embedding", "api key"],
        "openai/openai-agents-python" => vec!["agent", "tool", "handoff", "workflow", "runner"],
        "n8n-io/n8n" => vec!["workflow", "webhook", "node", "trigger", "credential", "dashboard"],
        "modelcontextprotocol/servers" => vec!["mcp", "server", "tool", "connector", "transport"],
        _ => vec![],
    };

    let matches = match_keywords(&lowered, &keywords);
    if watch_reason.is_some() && !matches.is_empty() {
        return LevelSignals {
            level: "high".to_string(),
            signals: matches,
        };
    }
    if watch_reason.is_some() && risk_level == "high" {
        return LevelSignals {
            level: "high".to_string(),
            signals: vec!["high breakage risk on a canonically watched repo".to_string()],
        };
    }
    if watch_reason.is_some() {
        return LevelSignals {
            level: "medium".to_string(),
            signals: vec!["repo is explicitly watched even though release notes did not hit local keywords".to_string()],
        };
    }
    LevelSignals {
        level: "low".to_string(),
        signals: vec!["repo is not on the canonical watchlist".to_string()],
    }
}

fn match_keywords(lowered: &str, keywords: &[&str]) -> Vec<String> {
    keywords
        .iter()
        .filter(|item| lowered.contains(**item))
        .map(|item| item.to_string())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    const WATCHLIST: &str = r#"
- openai/openai-python. (2026-04-08)
  - Python SDK changes are relevant to the current operational runtime. [AGENT:gpt-5]
- n8n-io/n8n. (2026-04-08)
  - Workflow orchestration changes affect the dashboard and integration layer. [AGENT:gpt-5]
"#;

    #[test]
    fn assesses_high_risk_and_high_relevance_for_watched_breaking_repo() {
        let assessment = assess_release(
            "openai/openai-python",
            "Breaking migration removes the old client construction path.",
            WATCHLIST,
        );

        assert!(assessment.watched);
        assert_eq!(assessment.risk_level, "high");
        assert_eq!(assessment.relevance_level, "high");
        assert!(assessment.risk_signals.iter().any(|item| item == "breaking"));
        assert!(assessment.watch_reason.contains("Python SDK changes are relevant"));
    }

    #[test]
    fn assigns_low_relevance_to_unwatched_repo() {
        let assessment = assess_release("example/repo", "Minor docs update.", WATCHLIST);

        assert!(!assessment.watched);
        assert_eq!(assessment.relevance_level, "low");
    }
}
