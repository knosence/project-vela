---
sot-type: reference
created: 2026-04-08
last-rewritten: 2026-04-10
parent: "[[500.HOW.Method-SoT#500.HOW.Method]]"
domain: matrix
status: active
tags: ["matrix","index","reference"]
---

# Index Layer

## This Layer Gives the Matrix a Top Level Registry of Active Sources of Truth
The cornerstone is the root subject, but the index layer is the top-level view. It provides the registry that lets the system see which SoTs exist, where they live, what their parents are, and whether the matrix still respects the root and lineage laws.

## This Layer Is Generated From the Matrix Rather Than Maintained by Memory
`python3 -m prototypes.python.vela.cli index` scans the SoT files, validates the single-cornerstone and single-parent laws, and writes both a readable registry and a machine-readable snapshot.

## This Layer Supports Governance Instead of Replacing It
The index does not become a rival source of truth. It is a registry and visibility layer that points back to the cornerstone and the branch SoTs that remain the canonical homes.
