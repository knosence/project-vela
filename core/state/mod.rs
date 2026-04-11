use std::collections::HashSet;

#[derive(Debug, Default)]
pub struct WriteState {
    active_targets: HashSet<String>,
}

impl WriteState {
    pub fn acquire(&mut self, target: &str) -> bool {
        self.active_targets.insert(target.to_string())
    }

    pub fn release(&mut self, target: &str) -> bool {
        self.active_targets.remove(target)
    }

    pub fn is_locked(&self, target: &str) -> bool {
        self.active_targets.contains(target)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn write_state_enforces_single_writer_discipline() {
        let mut state = WriteState::default();

        assert!(state.acquire("knowledge/ARTIFACTS/refs/test.md"));
        assert!(state.is_locked("knowledge/ARTIFACTS/refs/test.md"));
        assert!(!state.acquire("knowledge/ARTIFACTS/refs/test.md"));
        assert!(state.release("knowledge/ARTIFACTS/refs/test.md"));
        assert!(!state.is_locked("knowledge/ARTIFACTS/refs/test.md"));
    }
}
