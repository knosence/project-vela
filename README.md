# Project Vela

## Vela Is the System and Vela Is Also the Default Bundled Assistant
Project Vela is a Vela-first assistant system governed by canonical Sources of Truth. The system ships with a default bundled assistant profile named `vela`, but the profile is replaceable without replacing the architecture.

## The Repository Keeps Governance Above Adapters and Profiles
The durable architecture lives in the governed core, runtime, knowledge, workflows, and verification layers. Pi may act as an adapter, and OpenCode may donate harness mechanics, but neither is allowed to define the constitution of the system.

## The Runtime Starts Safe, Verifies Early, and Refuses Premature Readiness
The repository boots into setup mode until required onboarding values exist. Every meaningful mutation flows through a sequential agent pipeline, emits structured events, and respects sovereign approval boundaries.

## The Current Operational Runtime Is Python While Rust Defines the Durable Core Target
Python under `prototypes/python` provides the executable runtime, CLI, HTTP service, and verification harness for fast iteration. Rust under `core/` captures the durable schemas, validation boundaries, policy logic, lineage contracts, and queue interfaces that the system is expected to harden into.

## The Fastest Path to Exercise the System Is Through the Provided Commands
Run `python3 -m prototypes.python.vela.cli init`, `python3 -m prototypes.python.vela.cli setup`, `python3 -m prototypes.python.vela.cli dry-boot`, and `python3 -m prototypes.python.vela.cli verify --scenario full` from the repository root.

