<p align="center">
  <h1 align="center">Project Vela</h1>
  <p align="center">
    <strong>A governed assistant system built on canonical Sources of Truth.</strong>
  </p>
  <p align="center">
    Vela is the system. Vela is also the default bundled assistant.<br>
    The profile is replaceable. The architecture is not.
  </p>
</p>

---

## Overview

Project Vela is a SoT-governed assistant framework where every mutation flows through a sequential agent pipeline, emits structured events, and respects sovereign approval boundaries.

The system ships with a default assistant profile named **Vela**, but the profile is a swappable persona layer — the governance, verification, and pipeline architecture underneath is the durable core.

### Design Principles

- **Governance above adapters.** The constitution lives in the core, not in any adapter or profile.
- **Safe boot.** The runtime starts in setup mode until required onboarding values exist.
- **Verify early.** Every meaningful mutation passes through structured verification before commit.
- **Refuse premature readiness.** No shortcuts — the system doesn't claim ready until it is.

---

## Architecture

```
vela/
├── core/               # Rust — durable schemas, validation, policy, lineage
│   ├── models/         #   Domain models and type definitions
│   ├── validator/      #   SoT validation boundaries
│   ├── policy/         #   Approval and governance rules
│   ├── lineage/        #   Content lineage and provenance tracking
│   ├── events/         #   Structured event definitions
│   ├── state/          #   State machine and transitions
│   ├── parser/         #   SoT document parser
│   ├── matrix/         #   Matrix vault interface
│   ├── references/     #   Cross-reference resolution
│   └── repo_watch/     #   File system watcher
│
├── prototypes/python/  # Python — executable runtime, CLI, HTTP, verification
│
├── agents/             # Agent pipeline
│   ├── router/         #   Intent classification and dispatch
│   ├── scribe/         #   Content creation and formatting
│   ├── warden/         #   Governance enforcement
│   ├── worker/         #   Task execution
│   ├── growers/        #   SoT growth detection and proposals
│   ├── planner/        #   Multi-step planning
│   └── reflector/      #   Self-evaluation and correction
│
├── runtime/            # Runtime configuration
│   ├── adapters/       #   Provider adapters (model backends)
│   ├── config/         #   System configuration
│   ├── personas/       #   Swappable assistant profiles
│   ├── prompts/        #   Prompt templates
│   └── queues/         #   Event and task queues
│
├── knowledge/          # Knowledge base (SoT-governed)
│   ├── cornerstone/    #   The Holy Trinity root
│   ├── dimensions/     #   Dimension hubs (WHO, WHAT, WHERE, WHEN, HOW, WHY)
│   ├── refs/           #   Reference notes
│   ├── agents/         #   Agent skill definitions
│   ├── templates/      #   SoT templates
│   ├── inbox/          #   Intake queue
│   ├── proposals/      #   Growth proposals awaiting approval
│   ├── archive/        #   Archived content
│   └── logs/           #   Operational logs
│
├── integrations/       # External integrations
│   ├── discord/        #   Discord bot adapter
│   ├── git/            #   Git operations
│   ├── github/         #   GitHub API
│   ├── localfs/        #   Local filesystem operations
│   └── webhook/        #   Webhook endpoints
│
├── apps/               # Application adapters
│   └── pi-adapter/     #   Pi runtime adapter
│
├── workflows/          # Automation workflows
│   └── n8n/            #   n8n workflow definitions
│
├── ops/                # Operations
│   ├── bootstrap/      #   First-run setup
│   ├── deploy/         #   Deployment configurations
│   ├── monitoring/     #   Health checks and alerting
│   └── scripts/        #   Utility scripts
│
└── docs/               # Documentation
```

### Two-Layer Runtime

| Layer | Language | Purpose |
|-------|----------|---------|
| **Durable Core** | Rust | Schemas, validation, policy, lineage, queue interfaces. The constitution. |
| **Operational Runtime** | Python | CLI, HTTP service, verification harness, agent pipeline. Fast iteration. |

The Python runtime is the current executable layer. The Rust core captures what the system *must* enforce — it's the target for hardening as the architecture matures.

---

## Quick Start

```bash
# Initialize the system
python3 -m prototypes.python.vela.cli init

# Run guided setup (onboards required values)
python3 -m prototypes.python.vela.cli setup

# Index the knowledge base
python3 -m prototypes.python.vela.cli index

# Dry boot (verify without committing)
python3 -m prototypes.python.vela.cli dry-boot

# Run full verification suite
python3 -m prototypes.python.vela.cli verify --scenario full

# Apply a growth proposal
python3 -m prototypes.python.vela.cli growth apply <proposal>
```

---

## Agent Pipeline

Every request flows through a sequential agent pipeline:

```
Input → Router → [Scribe | Worker | Planner | Grower] → Warden → Reflector → Output
          │                                                 │          │
          ├─ classifies intent                              ├─ enforces policy
          └─ dispatches to specialist                       └─ self-evaluates
```

| Agent | Role |
|-------|------|
| **Router** | Classifies intent, dispatches to the right specialist agent |
| **Scribe** | Creates and formats SoT content — entries, refs, companions |
| **Worker** | Executes tasks — file operations, integrations, tool calls |
| **Planner** | Breaks complex requests into multi-step plans |
| **Growers** | Detects when SoTs need growth (fractal, ref note, spawn) |
| **Warden** | Enforces governance — validates mutations against policy |
| **Reflector** | Self-evaluates output quality, flags corrections |

---

## Governance Model

The system is governed by the **Holy Trinity** — three canonical Sources of Truth:

| SoT | Role | Governs |
|-----|------|---------|
| **Cornerstone** | The root | WHO — the person, all dimensions of life |
| **Key** | The framework | WHAT — what an SoT is, the rules |
| **System** | The engine | HOW/WHEN/WHY — vault operations, automation |

Every agent reads the Trinity before work, logs intent, and verifies the Trinity is accurate after work. This is the pre-flight / post-flight ritual — non-negotiable.

---

## Personas

The default persona is **Vela** — an adaptive AI companion with equal voice, crew command authority, and pattern learning. But the persona layer is swappable:

```
runtime/personas/
├── vela.yaml       # Default: adaptive companion
└── (your-own).yaml # Custom: define tone, constraints, escalation rules
```

The persona defines *how* the assistant communicates. The governance layer defines *what* the assistant is allowed to do. Swapping personas doesn't change the rules.

---

## Requirements

- Python >= 3.11
- Rust (for core development)
- An LLM provider (OpenRouter, Anthropic, or local via Ollama)

---

## License

TBD

---

<p align="center">
  <sub>Built by NaDario Seays. Governed by Sources of Truth. Always Be Compounding.</sub>
</p>
