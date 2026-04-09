# SoT Operations Reference

This note records the active mechanical operating rules for Vela's local Matrix implementation.

## Operations Stay Protocol Driven

- Route Inbox material by primary subject using the dimension router.
- Leave ambiguous material in Inbox rather than forcing a dimension.
- Treat Subject Declaration and dimension structure as protected.
- Treat Inbox, Status, Open Questions, Next Actions, and Decisions as fluid.
- Verify archive postconditions before considering an archive transaction complete.
- Keep one home for full content and use pointer entries everywhere else.
- Treat spawn as approval-gated structural evolution.

## Dimension Router Follows First Match Wins

- `100.WHO` for people, roles, teams, assistants, and owners.
- `200.WHAT` for definitions, scope, components, and capabilities.
- `300.WHERE` for tools, platforms, repositories, and environments.
- `400.WHEN` for dates, milestones, schedules, and cadence.
- `500.HOW` for process, method, workflow, and protocol.
- `600.WHY` for reasons, rationale, and trade-offs.

## Archive Transaction Must Verify All Three Outcomes

- The entry leaves `### Active`.
- The entry appears in `### Inactive` with `Archived` and `Archived Reason`.
- The entry appears in `## 700.Archive` with timestamp and source.

## Spawn Requires Explicit Human Approval

- Grower may recommend spawn.
- Scribe may execute spawn only after explicit approval is recorded.
- Subject Declaration changes are blocked without explicit approval as well.

## Patrol And Night Cycle Use Explicit Runtime Entry Points

- `vela patrol run` executes the Warden patrol skeleton.
- `vela night-cycle run` executes the DC night-cycle skeleton.
- `/api/n8n/patrol/run` triggers patrol through the service layer.
- `/api/n8n/night-cycle/run` triggers the night cycle through the service layer.
- Patrol writes artifact-space reports only.
- Night cycle packages patrol status, growth candidates, and blocked-pattern counts into a DC report.
