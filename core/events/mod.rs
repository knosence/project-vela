#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EventRecord {
    pub event_id: String,
    pub endpoint: String,
    pub target: String,
    pub status: String,
}

