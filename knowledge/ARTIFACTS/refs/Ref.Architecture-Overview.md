---
sot-type: reference
created: 2026-04-08
last-rewritten: 2026-04-10
parent: "[[500.HOW.Method-SoT#500.HOW.Method]]"
domain: architecture
status: active
tags: ["architecture","overview","reference"]
---

# Architecture Overview

## This Architecture Keeps Governance in the Center and Adapters at the Edge
`core/` defines durable schemas, policy logic, lineage, validators, and state guards. `runtime/` hosts config, prompts, profile manifests, queues, and adapters. `knowledge/` stores canonical SoTs, refs, proposals, and logs.

## This Architecture Splits Operational Speed From Durable Core Evolution
Python under `prototypes/python` provides the working runtime, CLI, server, and verification harness now. Rust under `core/` defines the target shape for long-lived durable logic.

## This Architecture Reserves n8n for Orchestration Rather Than Constitutional Authority
`workflows/n8n/` describes the orchestration layer and endpoint contracts. n8n may trigger governed actions, but cannot bypass approval, validation, or profile registry rules.
