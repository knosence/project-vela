#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LineageStamp {
    pub source: String,
    pub route: String,
    pub planner: String,
    pub validator: String,
    pub approval_reference: Option<String>,
}

impl LineageStamp {
    pub fn is_complete(&self) -> bool {
        !self.source.trim().is_empty()
            && !self.route.trim().is_empty()
            && !self.planner.trim().is_empty()
            && !self.validator.trim().is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lineage_requires_route_and_validator_context() {
        let complete = LineageStamp {
            source: "vela".to_string(),
            route: "standard".to_string(),
            planner: "planner".to_string(),
            validator: "warden".to_string(),
            approval_reference: None,
        };

        let incomplete = LineageStamp {
            source: "vela".to_string(),
            route: String::new(),
            planner: "planner".to_string(),
            validator: "warden".to_string(),
            approval_reference: None,
        };

        assert!(complete.is_complete());
        assert!(!incomplete.is_complete());
    }
}
