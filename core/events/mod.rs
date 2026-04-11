use crate::models::{BlockedItemSummary, EventAppendPlan, ValidationFinding};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationSummary {
    pub finding_codes: Vec<String>,
    pub blocking: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EventRecord {
    pub event_id: String,
    pub timestamp: String,
    pub source: String,
    pub endpoint: String,
    pub actor: String,
    pub target: String,
    pub status: String,
    pub reason: String,
    pub artifacts: Vec<String>,
    pub approval_required: bool,
    pub validation_summary: ValidationSummary,
}

impl EventRecord {
    pub fn new(
        event_id: impl Into<String>,
        timestamp: impl Into<String>,
        source: impl Into<String>,
        endpoint: impl Into<String>,
        actor: impl Into<String>,
        target: impl Into<String>,
        status: impl Into<String>,
        reason: impl Into<String>,
    ) -> Self {
        Self {
            event_id: event_id.into(),
            timestamp: timestamp.into(),
            source: source.into(),
            endpoint: endpoint.into(),
            actor: actor.into(),
            target: target.into(),
            status: status.into(),
            reason: reason.into(),
            artifacts: Vec::new(),
            approval_required: false,
            validation_summary: ValidationSummary {
                finding_codes: Vec::new(),
                blocking: false,
            },
        }
    }

    pub fn is_meaningful_mutation(&self) -> bool {
        matches!(
            self.status.as_str(),
            "committed" | "blocked" | "accepted" | "rejected"
        )
    }
}

pub fn validate_event_record(record: &EventRecord) -> Vec<ValidationFinding> {
    let mut findings = Vec::new();

    if record.event_id.trim().is_empty() {
        findings.push(ValidationFinding::error(
            "EVENT_ID_REQUIRED",
            "Event record must include an event_id",
        ));
    }
    if record.timestamp.trim().is_empty() {
        findings.push(ValidationFinding::error(
            "EVENT_TIMESTAMP_REQUIRED",
            "Event record must include a timestamp",
        ));
    }
    if record.source.trim().is_empty() {
        findings.push(ValidationFinding::error(
            "EVENT_SOURCE_REQUIRED",
            "Event record must include a source",
        ));
    }
    if record.endpoint.trim().is_empty() {
        findings.push(ValidationFinding::error(
            "EVENT_ENDPOINT_REQUIRED",
            "Event record must include an endpoint",
        ));
    }
    if record.actor.trim().is_empty() {
        findings.push(ValidationFinding::error(
            "EVENT_ACTOR_REQUIRED",
            "Event record must include an actor",
        ));
    }
    if record.target.trim().is_empty() {
        findings.push(ValidationFinding::error(
            "EVENT_TARGET_REQUIRED",
            "Event record must include a target",
        ));
    }
    if record.status.trim().is_empty() {
        findings.push(ValidationFinding::error(
            "EVENT_STATUS_REQUIRED",
            "Event record must include a status",
        ));
    }
    if record.reason.trim().is_empty() {
        findings.push(ValidationFinding::error(
            "EVENT_REASON_REQUIRED",
            "Event record must include a reason",
        ));
    }

    findings
}

pub fn render_event_record_json(
    record: &EventRecord,
    artifacts_json: &str,
    validation_summary_json: &str,
) -> String {
    let artifacts = if artifacts_json.trim().is_empty() {
        "[]".to_string()
    } else {
        artifacts_json.trim().to_string()
    };
    let validation_summary = if validation_summary_json.trim().is_empty() {
        "{\"finding_codes\":[],\"blocking\":false}".to_string()
    } else {
        validation_summary_json.trim().to_string()
    };
    format!(
        "{{\"event_id\":\"{}\",\"timestamp\":\"{}\",\"source\":\"{}\",\"endpoint\":\"{}\",\"actor\":\"{}\",\"target\":\"{}\",\"status\":\"{}\",\"reason\":\"{}\",\"artifacts\":{},\"approval_required\":{},\"validation_summary\":{}}}",
        escape_json(&record.event_id),
        escape_json(&record.timestamp),
        escape_json(&record.source),
        escape_json(&record.endpoint),
        escape_json(&record.actor),
        escape_json(&record.target),
        escape_json(&record.status),
        escape_json(&record.reason),
        artifacts,
        if record.approval_required { "true" } else { "false" },
        validation_summary,
    )
}

pub fn plan_event_append(
    record: &EventRecord,
    artifacts_json: &str,
    validation_summary_json: &str,
) -> (Option<EventAppendPlan>, Vec<ValidationFinding>) {
    let findings = validate_event_record(record);
    if !findings.is_empty() {
        return (None, findings);
    }
    let line = render_event_record_json(record, artifacts_json, validation_summary_json);
    (
        Some(EventAppendPlan {
            line,
            event_id: record.event_id.clone(),
            timestamp: record.timestamp.clone(),
        }),
        Vec::new(),
    )
}

pub fn extract_blocked_items(log_text: &str) -> Vec<BlockedItemSummary> {
    log_text
        .lines()
        .filter_map(|line| {
            let trimmed = line.trim();
            if trimmed.is_empty() || !trimmed.contains("\"status\":\"blocked\"") {
                return None;
            }
            Some(BlockedItemSummary {
                target: extract_json_string(trimmed, "target").unwrap_or_default(),
                reason: extract_json_string(trimmed, "reason")
                    .unwrap_or_else(|| "blocked".to_string()),
                actor: extract_json_string(trimmed, "actor").unwrap_or_default(),
                endpoint: extract_json_string(trimmed, "endpoint").unwrap_or_default(),
            })
        })
        .collect()
}

fn extract_json_string(text: &str, field: &str) -> Option<String> {
    let pattern = format!("\"{field}\":\"");
    let start = text.find(&pattern)? + pattern.len();
    let tail = &text[start..];
    let end = tail.find('"')?;
    Some(tail[..end].replace("\\\"", "\"").replace("\\\\", "\\"))
}

fn escape_json(value: &str) -> String {
    let mut escaped = String::new();
    for ch in value.chars() {
        match ch {
            '\\' => escaped.push_str("\\\\"),
            '"' => escaped.push_str("\\\""),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            _ => escaped.push(ch),
        }
    }
    escaped
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn event_record_marks_meaningful_mutations() {
        let event = EventRecord::new(
            "evt_123",
            "2026-04-08T00:00:00Z",
            "vela",
            "verify",
            "scribe",
            "knowledge/ARTIFACTS/refs/test.md",
            "committed",
            "test write",
        );

        assert!(event.is_meaningful_mutation());
    }

    #[test]
    fn event_record_requires_core_fields() {
        let mut event = EventRecord::new("", "", "", "", "", "", "", "");
        event.reason.clear();

        let findings = validate_event_record(&event);

        assert!(findings.iter().any(|item| item.code == "EVENT_ID_REQUIRED"));
        assert!(findings
            .iter()
            .any(|item| item.code == "EVENT_REASON_REQUIRED"));
    }

    #[test]
    fn renders_event_record_json() {
        let event = EventRecord::new(
            "evt_123",
            "2026-04-11T01:00:00Z",
            "vela",
            "verify",
            "scribe",
            "knowledge/ARTIFACTS/refs/test.md",
            "committed",
            "test write",
        );
        let rendered = render_event_record_json(
            &event,
            "[\"knowledge/ARTIFACTS/refs/test.md\"]",
            "{\"finding_codes\":[\"OK\"],\"blocking\":false}",
        );
        assert!(rendered.contains("\"event_id\":\"evt_123\""));
        assert!(rendered.contains("\"artifacts\":[\"knowledge/ARTIFACTS/refs/test.md\"]"));
        assert!(rendered
            .contains("\"validation_summary\":{\"finding_codes\":[\"OK\"],\"blocking\":false}"));
    }

    #[test]
    fn plans_event_append() {
        let event = EventRecord::new(
            "evt_123",
            "2026-04-11T01:00:00Z",
            "vela",
            "verify",
            "scribe",
            "knowledge/ARTIFACTS/refs/test.md",
            "committed",
            "test write",
        );
        let (plan, findings) = plan_event_append(
            &event,
            "[\"knowledge/ARTIFACTS/refs/test.md\"]",
            "{\"finding_codes\":[\"OK\"],\"blocking\":false}",
        );
        assert!(findings.is_empty());
        let plan = plan.expect("plan should exist");
        assert!(plan.line.contains("\"event_id\":\"evt_123\""));
        assert_eq!(plan.event_id, "evt_123");
    }

    #[test]
    fn extracts_blocked_items_from_jsonl() {
        let items = extract_blocked_items(
            "{\"event_id\":\"evt_1\",\"timestamp\":\"2026-04-11T01:00:00Z\",\"source\":\"vela\",\"endpoint\":\"patrol\",\"actor\":\"warden\",\"target\":\"knowledge/a.md\",\"status\":\"blocked\",\"reason\":\"lock conflict\",\"artifacts\":[],\"approval_required\":false,\"validation_summary\":{\"finding_codes\":[],\"blocking\":false}}\n{\"event_id\":\"evt_2\",\"timestamp\":\"2026-04-11T01:01:00Z\",\"source\":\"vela\",\"endpoint\":\"patrol\",\"actor\":\"warden\",\"target\":\"knowledge/b.md\",\"status\":\"committed\",\"reason\":\"ok\",\"artifacts\":[],\"approval_required\":false,\"validation_summary\":{\"finding_codes\":[],\"blocking\":false}}",
        );
        assert_eq!(items.len(), 1);
        assert_eq!(items[0].target, "knowledge/a.md");
        assert_eq!(items[0].reason, "lock conflict");
        assert_eq!(items[0].endpoint, "patrol");
    }
}
