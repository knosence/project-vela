# Profile Replacement

## This Flow Allows the Assistant Profile to Change Without Rewriting the System
The profile registry reads manifests from `runtime/personas/<name>/profile.yaml` and tracks the active profile through `runtime/config/project-vela.yaml`. Switching profiles changes the active assistant binding without mutating system-level SoTs.

## This Flow Supports Base and Derived Profile Patterns
Each profile manifest may name a `base_profile` so a derived persona can inherit operational expectations while keeping its own agent-specific SoTs under `knowledge/agents/<name>/`.

