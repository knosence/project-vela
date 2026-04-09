---
sot-type: dimension
created: 2026-04-08
last-rewritten: 2026-04-08
parent: "[[200.WHAT.Domain-SoT#200.WHAT.Domain]]"
domain: dimensions
status: active
tags: ["watchlist","repo","sot"]
---

# Repo Watchlist Source of Truth

## 000.Index

### Subject Declaration

**Subject:** This SoT defines the canonical repo watch scope for Project Vela.
**Type:** dimension
**Created:** 2026-04-08
**Parent:** [[200.WHAT.Domain-SoT#200.WHAT.Domain]]

### Links

- Parent: [[200.WHAT.Domain-SoT#200.WHAT.Domain]]
- Dimension hub: [[200.WHAT.Domain-SoT]]
- Cornerstone: [[Cornerstone.Project-Vela-SoT]]

### Inbox

No pending items.

### Status

Repo watch scope is active.

### Open Questions

- Which upstream repositories should be added or removed as local relevance changes? (2026-04-08)
  - The watchlist should remain deliberate rather than accidental. [AGENT:gpt-5]

### Next Actions

- Review watch scope against actual integrations and runtime priorities over time. (2026-04-08)
  - Canonical scope should follow lived relevance. [AGENT:gpt-5]

### Decisions

- [2026-04-08] Repo watchlist SoT established as the canonical watch scope.

### Block Map — Single Source

| ID | Question | Dimension | This SoT's Name |
|----|----------|-----------|-----------------|
| 000 | — | Index | Index |
| 100 | Who | Circle | Owners |
| 200 | What | Domain | Watch Scope |
| 300 | Where | Terrain | Sources |
| 400 | When | Chronicle | Cadence |
| 500 | How | Method | Intake Method |
| 600 | Why/Not | Compass | Relevance |
| 700 | — | Archive | Archive |

---

## 100.WHO.Owners

### Active

- Project Vela owns this watchlist as the canonical home for repo monitoring scope. (2026-04-08)
  - The watchlist belongs to the system root rather than to a transient workflow. [AGENT:gpt-5]

### Inactive

(No inactive entries.)

---

## 200.WHAT.Watch Scope

### Active

- openai/openai-python. (2026-04-08)
  - Python SDK changes are relevant to the current operational runtime. [AGENT:gpt-5]
- openai/openai-agents-python. (2026-04-08)
  - Agent framework changes may influence future integration choices. [AGENT:gpt-5]
- n8n-io/n8n. (2026-04-08)
  - Workflow orchestration changes affect the dashboard and integration layer. [AGENT:gpt-5]
- modelcontextprotocol/servers. (2026-04-08)
  - MCP server changes affect integration and tool surface expectations. [AGENT:gpt-5]

### Inactive

(No inactive entries.)

---

## 300.WHERE.Sources

### Active

- Release data enters through polling or webhook paths and lands in governed services. (2026-04-08)
  - The watch scope spans external upstream repositories rather than local-only events. [AGENT:gpt-5]

### Inactive

(No inactive entries.)

---

## 400.WHEN.Cadence

### Active

- Repo release checks happen when new release packets arrive or scheduled watch cycles run. (2026-04-08)
  - Monitoring is event-driven when possible and scheduled when needed. [AGENT:gpt-5]

### Inactive

(No inactive entries.)

---

## 500.HOW.Intake Method

### Active

- Repo release events are reflected, validated, and written through the governed pipeline before becoming durable artifacts. (2026-04-08)
  - The watchlist is only scope; interpretation and mutation still pass through the workflow path. [AGENT:gpt-5]

### Inactive

(No inactive entries.)

---

## 600.WHY.Relevance

### Active

- Other workflow files may point here, but this file remains the canonical home for repo watch scope. (2026-04-08)
  - One home with many pointers prevents the watch scope from fragmenting across integrations. [AGENT:gpt-5]

### Inactive

(No inactive entries.)

---

## 700.Archive

(No archived entries.)
