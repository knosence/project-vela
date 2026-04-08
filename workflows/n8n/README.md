# n8n Workflow Boundary

## This Directory Defines the External Orchestration Layer Without Owning Governance
n8n calls the governed HTTP endpoints under `/api/n8n` and receives standard response envelopes. Workflow automation may orchestrate but may not bypass approval, validation, or Source of Truth rules.

