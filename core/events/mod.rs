use crate::models::ValidationFinding;

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
        matches!(self.status.as_str(), "committed" | "blocked" | "accepted" | "rejected")
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
        assert!(findings.iter().any(|item| item.code == "EVENT_REASON_REQUIRED"));
    }
}
