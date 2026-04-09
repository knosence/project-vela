<h1 align="center">Project Vela</h1>

<p align="center">
<strong>A governed assistant system built on canonical Sources of Truth.</strong><br>
<em>Vela is the system. Vela is also the default bundled assistant.<br>
The profile is replaceable. The architecture is not.</em>
</p>

<p align="center">
<a href="#quick-start">Quick Start</a> · <a href="#how-it-works">How It Works</a> · <a href="#architecture">Architecture</a> · <a href="#governance">Governance</a>
</p>

---

Most assistant frameworks start with a model and wrap features around it. Vela starts with a **constitution** and lets models serve under it. The governance layer — schemas, validation, policy, lineage — is the product. The LLM is a replaceable engine underneath.

The system ships with a default persona named Vela: an adaptive companion with equal voice, crew command authority, and the ability to learn patterns over time. But swap the persona file and the same governed pipeline serves a completely different personality. The rules don't change when the voice does.

---

## Quick Start

```bash
python3 -m prototypes.python.vela.cli init          # scaffold the system
python3 -m prototypes.python.vela.cli setup         # onboard required values
python3 -m prototypes.python.vela.cli index         # index the knowledge base
python3 -m prototypes.python.vela.cli dry-boot      # verify without committing
python3 -m prototypes.python.vela.cli verify --scenario full   # run the full test suite
python3 -m prototypes.python.vela.cli growth apply <proposal>  # apply a growth proposal
```

The system boots into setup mode and refuses to claim readiness until every required value exists. There are no shortcuts past onboarding.

---

## How It Works

Every request enters a sequential agent pipeline. The pipeline classifies intent, dispatches to a specialist, enforces governance, and self-evaluates before anything reaches the outside world.

```
Input → Router → [ Scribe | Worker | Planner | Grower ] → Warden → Reflector → Output
```

**Router** reads the request and decides who handles it. **Scribe** creates and formats content. **Worker** executes file operations and tool calls. **Planner** breaks complex requests into steps. **Growers** detect when a Source of Truth has outgrown its current structure and propose expansion.

Nothing leaves the pipeline without passing through the **Warden**, which validates every mutation against governance policy. The **Reflector** then evaluates the output's quality and flags anything that needs correction before delivery.

The pipeline emits structured events at every stage. Every mutation is traceable. Every decision has lineage.

---

## Governance

Three canonical Sources of Truth form the **Holy Trinity** — the constitution that governs the entire system:

| | Role | What It Governs |
|---|------|----------------|
| **Cornerstone** | The root | The person. All dimensions of life, work, and growth. Everything else spawns from here. |
| **Key** | The framework | What a Source of Truth *is*. The structural rules every document must follow. |
| **System** | The engine | How information enters the vault, when processing happens, where infrastructure lives. |

Every agent reads the Trinity before doing work, logs its intent, executes, then returns to verify the Trinity is still accurate afterward. This pre-flight / post-flight ritual is non-negotiable. If the Trinity drifts, every downstream operation inherits the drift.

The governance model enforces a clear separation: **the persona defines how the assistant communicates**. The governance layer defines **what the assistant is allowed to do**. Swapping personas doesn't change the rules. The Warden doesn't care about tone — it cares about policy.

---

## Architecture

The system is split into two layers. The **durable core** is Rust — it captures schemas, validation boundaries, policy logic, lineage contracts, and queue interfaces that the system is expected to harden into over time. The **operational runtime** is Python — it provides the executable CLI, HTTP service, agent pipeline, and verification harness for fast iteration.

The Python layer is where work happens today. The Rust layer is where the constitution lives permanently.

```
vela/
│
├── core/                # Rust — the constitution
│   ├── models/          #   domain types and schemas
│   ├── validator/       #   SoT validation rules
│   ├── policy/          #   approval and governance logic
│   ├── lineage/         #   content provenance tracking
│   ├── events/          #   structured event definitions
│   ├── state/           #   state machine transitions
│   ├── parser/          #   SoT document parser
│   └── matrix/          #   vault interface
│
├── prototypes/python/   # Python — the runtime
│
├── agents/              # the pipeline
│   ├── router/          #   intent → specialist
│   ├── scribe/          #   content creation
│   ├── worker/          #   task execution
│   ├── planner/         #   multi-step decomposition
│   ├── growers/         #   growth detection
│   ├── warden/          #   governance enforcement
│   └── reflector/       #   self-evaluation
│
├── runtime/             # configuration and persona layer
│   ├── adapters/        #   model provider backends
│   ├── personas/        #   swappable assistant profiles
│   ├── prompts/         #   prompt templates
│   └── queues/          #   event and task queues
│
├── knowledge/           # SoT-governed knowledge base
│   ├── cornerstone/     #   the Trinity root
│   ├── dimensions/      #   WHO, WHAT, WHERE, WHEN, HOW, WHY
│   ├── refs/            #   reference notes
│   ├── inbox/           #   intake queue
│   ├── proposals/       #   growth proposals awaiting approval
│   └── archive/         #   archived content
│
├── integrations/        # external connections
│   ├── discord/         #   Discord bot
│   ├── github/          #   GitHub API
│   ├── webhook/         #   inbound webhooks
│   └── localfs/         #   filesystem operations
│
├── workflows/           # automation
│   └── n8n/             #   n8n workflow definitions
│
├── apps/                # adapter applications
│   └── pi-adapter/      #   Pi runtime bridge
│
└── ops/                 # operations
    ├── bootstrap/       #   first-run setup
    ├── deploy/          #   deployment configs
    └── monitoring/      #   health and alerting
```

---

## Personas

```
runtime/personas/
├── vela.yaml            # ships as default — adaptive, opinionated, learns patterns
└── your-own.yaml        # swap in any personality without touching governance
```

A persona file defines voice, tone, escalation behavior, and communication style. It does not define what the assistant can do — that boundary belongs to the Warden and the governance policy layer. You can build a playful assistant, a terse one, a formal one, or a domain-specific expert, all running on the same governed pipeline.

---

## Requirements

- **Python** >= 3.11 (operational runtime)
- **Rust** (durable core development)
- **An LLM provider** — OpenRouter, Anthropic, or local via Ollama

---

## License

TBD

---

<p align="center">
<sub>Built by NaDario Seays · Governed by Sources of Truth · Always Be Compounding</sub>
</p>
