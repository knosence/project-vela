<h1 align="center">Project Vela</h1>

<p align="center">
<strong>A governed assistant system where the constitution comes before the model.</strong><br>
<em>Vela is the system. Vela is also the default bundled assistant.<br>
The profile is replaceable. The architecture is not.</em>
</p>

<p align="center">
<a href="#quick-start">Quick Start</a> · <a href="#how-it-works">How It Works</a> · <a href="#the-knowledge-layer">Knowledge</a> · <a href="#governance">Governance</a> · <a href="#architecture">Architecture</a>
</p>

---

Most assistant frameworks start with a model and wrap features around it. Vela starts with a **constitution** — schemas, validation boundaries, policy logic, content lineage — and lets models serve under it. Swap the LLM, swap the persona, swap the adapter. The governance doesn't move.

The system ships with a default persona named Vela: an adaptive companion with equal voice, crew command authority, and the ability to learn patterns over time. But the persona is a YAML file in `runtime/personas/`. Replace it and the same governed pipeline serves a completely different personality. The rules don't change when the voice does.

---

## Quick Start

```bash
python3 -m prototypes.python.vela.cli init                    # scaffold the system
python3 -m prototypes.python.vela.cli setup                   # onboard required values
python3 -m prototypes.python.vela.cli index                   # index the knowledge base
python3 -m prototypes.python.vela.cli dry-boot                # verify without committing
python3 -m prototypes.python.vela.cli verify --scenario full  # full test suite
python3 -m prototypes.python.vela.cli growth apply <proposal> # apply a growth proposal
```

The runtime boots into setup mode and refuses to claim readiness until every required onboarding value exists. No shortcuts.

---

## How It Works

Every request enters a sequential agent pipeline. The pipeline classifies intent, dispatches to a specialist, enforces governance, and self-evaluates — all before anything reaches the outside world.

```
Input → Router → [ Scribe | Worker | Planner | Grower ] → Warden → Reflector → Output
```

**Router** reads the request and decides who handles it. **Scribe** creates and formats SoT content. **Worker** executes file operations and tool calls. **Planner** decomposes complex requests into steps. **Growers** detect when a Source of Truth has outgrown its structure and propose expansion.

Nothing exits the pipeline without passing through the **Warden**, which validates every mutation against governance policy. The **Reflector** then evaluates output quality and flags anything that needs correction before delivery.

Every stage emits structured events. Every mutation is traceable. Every decision has lineage.

---

## The Knowledge Layer

Vela's knowledge base is itself governed by Sources of Truth. A **Cornerstone** document sits at the root, and every other piece of knowledge connects to it through a dimensional hierarchy:

```
knowledge/
├── Cornerstone.Knosence-SoT.md            # the root index
├── 100.WHO.Circle-SoT.md                  # WHO hub
├── 200.WHAT.Domain-SoT.md                 # WHAT hub
├── 230.DOMAIN.SoT-Source-of-Truth-SoT.md  # The Key
├── 240.DOMAIN.Matrix-SoT.md               # The System
├── 300.WHERE.Terrain-SoT.md               # WHERE hub
├── 400.WHEN.Chronicle-SoT.md              # WHEN hub
├── 500.HOW.Method-SoT.md                  # HOW hub
├── 600.WHY.Compass-SoT.md                 # WHY hub
├── 110.WHO.Vela-Identity-SoT.md           # Vela branch
├── 210.WHAT.Vela-Capabilities-SoT.md      # Vela capability branch
├── 220.WHAT.Repo-Watchlist-SoT.md         # repo-watch branch
├── 610.WHY.Vela-Intent-SoT.md             # Vela rationale branch
├── INBOX/                                 # intake queue
└── ARTIFACTS/
    ├── refs/                              # reference notes and registries
    ├── proposals/                         # growth and review proposals
    └── archive/                           # backups and archived support files
```

Files follow the `{ID}.{Context}.{Subject}-SoT.md` naming convention. The ID encodes hierarchy — `200` is a dimension hub, `210` is its first child, `211` is a grandchild. The Cornerstone is the only exception: it carries no numeric ID because everything else descends from it.

Knowledge enters through the inbox, gets classified by the Router, formatted by the Scribe, validated by the Warden, and integrated by the Growers. When a document outgrows its current form, the system proposes a growth stage: flat → fractal → reference note → full SoT. Proposals require approval before execution.

---

## Governance

Three canonical Sources of Truth form the **Holy Trinity** — the constitution that governs the entire system:

| | Role | What It Governs |
|---|------|----------------|
| **Cornerstone** | The root | `Cornerstone.Knosence-SoT.md` — the owner and root index. |
| **Key** | The framework | `230.DOMAIN.SoT-Source-of-Truth-SoT.md` — what a Source of Truth is and how it is built. |
| **System** | The engine | `240.DOMAIN.Matrix-SoT.md` — who maintains the matrix and how that work runs. |

Every agent reads the Trinity before doing work, logs its intent, executes, then returns to verify the Trinity is still accurate afterward. This pre-flight / post-flight ritual is non-negotiable. If the Trinity drifts, every downstream operation inherits the drift.

The governance model enforces a hard separation between persona and policy. The persona defines *how* the assistant communicates — tone, pushback style, escalation behavior. The governance layer defines *what* the assistant is allowed to do — what it can mutate, what requires approval, what it must never touch. The Warden enforces the latter regardless of which persona is loaded.

---

## Architecture

The system is split into two layers that serve different timescales. The **durable core** is Rust — it captures the contracts that must hold permanently: schemas, validation boundaries, policy logic, content lineage, event definitions, and state transitions. The **operational runtime** is Python — it provides the executable CLI, HTTP service, agent pipeline, and verification harness where iteration happens fast.

Today, Python does the work. Over time, the Rust core hardens what the Python layer proves out.

```
vela/
│
├── core/                 Rust — the constitution
│   ├── models/           domain types and schemas
│   ├── validator/        SoT validation rules
│   ├── policy/           approval and governance logic
│   ├── lineage/          content provenance tracking
│   ├── events/           structured event definitions
│   ├── state/            state machine transitions
│   ├── parser/           SoT document parser
│   ├── matrix/           vault interface
│   ├── inventory/        knowledge base indexing
│   ├── operations/       core operation definitions
│   ├── references/       cross-reference resolution
│   └── repo_watch/       filesystem watcher
│
├── prototypes/python/    Python — the runtime
│
├── agents/               the pipeline
│   ├── router/           intent classification and dispatch
│   ├── scribe/           content creation and formatting
│   ├── worker/           task execution
│   ├── planner/          multi-step decomposition
│   ├── growers/          growth detection and proposals
│   ├── warden/           governance enforcement
│   └── reflector/        self-evaluation and correction
│
├── runtime/              configuration and persona layer
│   ├── adapters/         model provider backends
│   ├── personas/         swappable assistant profiles
│   ├── prompts/          prompt templates
│   ├── config/           system configuration
│   └── queues/           event and task queues
│
├── knowledge/            SoT-governed knowledge base
│
├── integrations/         external connections
│   ├── discord/          Discord bot
│   ├── github/           GitHub API
│   ├── git/              git operations
│   ├── webhook/          inbound webhooks
│   └── localfs/          filesystem operations
│
├── apps/                 adapter applications
│   └── pi-adapter/       Pi runtime bridge
│
├── workflows/            automation
│   └── n8n/              n8n workflow definitions
│
├── ops/                  operations and deployment
│   ├── bootstrap/        first-run setup
│   ├── deploy/           deployment configs
│   ├── monitoring/       health and alerting
│   └── scripts/          utility scripts
│
└── docs/                 documentation
    ├── architecture/     system design
    ├── agent-specs/      agent behavior contracts
    ├── adr/              architecture decision records
    ├── directives/       operational directives
    ├── onboarding/       getting started guides
    └── testing/          test strategy and scenarios
```

---

## Personas

```yaml
# runtime/personas/vela.yaml — the default
name: Vela
tone: adaptive        # warm when brainstorming, sharp when correcting
authority: equal      # pushes back when the owner is wrong
learning: true        # absorbs patterns over time
```

A persona file controls voice, not power. Build a playful assistant, a terse one, a domain expert — they all run on the same governed pipeline. The Warden doesn't read the persona file. It reads the policy.

---

## Requirements

- **Python** >= 3.11
- **Rust** (for core development)
- **An LLM provider** — OpenRouter, Anthropic, or local via Ollama

---

## License

TBD

---

<p align="center">
<sub>Built by NaDario Seays · Governed by Sources of Truth · Always Be Compounding</sub>
</p>
