use std::collections::HashSet;

#[derive(Default)]
pub struct WriteState {
    pub active_targets: HashSet<String>,
}

