# n8n Integration

## This Integration Uses a Small Governed HTTP Contract Rather Than Raw File Mutation
The runtime exposes `/api/health` and `/api/n8n/*` endpoints. n8n sends machine-authenticated requests with `X-VELA-SECRET` and receives standard envelopes that include status, message, structured data, and structured errors.

## This Integration Preserves Sequential Governance Inside the Service Boundary
Repo-release, validation, reflection, approval, verification, and profile activation requests all pass through internal governed logic rather than writing repository files directly from the workflow layer.

