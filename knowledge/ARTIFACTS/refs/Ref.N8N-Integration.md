---
sot-type: reference
created: 2026-04-08
last-rewritten: 2026-04-10
parent: "[[500.HOW.Method-SoT#500.HOW.Method]]"
domain: integrations
status: active
tags: ["n8n","integration","reference"]
---

# n8n Integration

## This Integration Uses a Small Governed HTTP Contract Rather Than Raw File Mutation
The runtime exposes `/api/health` and `/api/n8n/*` endpoints. n8n sends machine-authenticated requests with `X-VELA-SECRET` and receives standard envelopes that include status, message, structured data, and structured errors.

## This Integration Preserves Sequential Governance Inside the Service Boundary
Repo-release, validation, reflection, approval, verification, and profile activation requests all pass through internal governed logic rather than writing repository files directly from the workflow layer.

## This Repo Release Flow Emits a Structured Artifact Chain for Provenance and Review
`POST /api/n8n/repo-release` writes a governed packet record, a machine-readable assessment, a structured reflection record, a structured validation record, a release-intelligence reference, and the human-readable release summary. That keeps the normalized input, derived judgment, review stages, and narrative output visible as separate artifacts instead of collapsing them into one file.

## This Integration Also Exposes Governed Growth Proposal Execution
`POST /api/n8n/growth/apply` accepts a proposal path plus an optional `approval_id` and applies the growth proposal through the same governed logic used by the CLI. The service blocks sovereign structural execution until approval exists, writes the resulting controlled artifact, updates the proposal status, and emits structured events.
