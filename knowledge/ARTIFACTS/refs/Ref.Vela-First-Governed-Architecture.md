---
sot-type: reference
created: 2026-04-08
last-rewritten: 2026-04-10
parent: "[[Cornerstone.Knosence-SoT#000.Index]]"
domain: architecture
status: active
tags: ["architecture","adr","reference"]
---

# ADR 0001 Vela First Governed Architecture

## This Decision Establishes the Repository as Vela First Rather Than Pi First
The repository centers a governed architecture with replaceable profiles. Pi is explicitly confined to adapter roles, and donor mechanics from OpenCode remain isolated behind harness boundaries.

## This Decision Prefers Clear Boundaries Over Hidden Framework Magic
The first implementation uses plain Python and simple Rust contracts so architectural decisions remain visible and testable.
