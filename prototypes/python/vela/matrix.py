from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ValidationFinding
from .paths import MATRIX_INDEX_JSON_PATH, MATRIX_INDEX_PATH, REPO_ROOT
from .rust_bridge import inspect_reference_payload
from .rust_bridge import validate_parent_payload
from .rust_bridge import validate_sot_payload
from .simple_yaml import loads
from .traceability import annotate_finding, annotate_findings


@dataclass
class MatrixSoT:
    path: str
    title: str
    sot_type: str
    parent: str
    domain: str
    status: str
    area: str
    is_cornerstone: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "title": self.title,
            "sot_type": self.sot_type,
            "parent": self.parent,
            "domain": self.domain,
            "status": self.status,
            "area": self.area,
            "is_cornerstone": self.is_cornerstone,
        }


@dataclass
class MatrixReference:
    path: str
    title: str
    ref_type: str
    parent: str
    domain: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "title": self.title,
            "ref_type": self.ref_type,
            "parent": self.parent,
            "domain": self.domain,
            "status": self.status,
        }


def _reference_payloads() -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in sorted((REPO_ROOT / "knowledge" / "refs").glob("Ref.*.md")):
        if path == MATRIX_INDEX_PATH:
            continue
        text = path.read_text(encoding="utf-8")
        payload = inspect_reference_payload(str(path.relative_to(REPO_ROOT)), text)
        payloads.append(payload)
    return payloads


def _parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        return {}
    try:
        _, frontmatter, _ = text.split("---\n", 2)
    except ValueError:
        return {}
    return loads(frontmatter)


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled SoT"


def discover_sots() -> list[MatrixSoT]:
    entries: list[MatrixSoT] = []
    for path in sorted((REPO_ROOT / "knowledge").rglob("*-SoT.md")):
        rel = str(path.relative_to(REPO_ROOT))
        area = Path(rel).parts[1]
        if area not in {"cornerstone", "dimensions", "agents"}:
            continue
        text = path.read_text(encoding="utf-8")
        frontmatter = _parse_frontmatter(text)
        entries.append(
            MatrixSoT(
                path=rel,
                title=_extract_title(text),
                sot_type=str(frontmatter.get("sot-type", "unknown")),
                parent=str(frontmatter.get("parent", "")),
                domain=str(frontmatter.get("domain", "unknown")),
                status=str(frontmatter.get("status", "unknown")),
                area=area,
                is_cornerstone=Path(rel).name == "Cornerstone.Project-Vela-SoT.md",
            )
        )
    return entries


def discover_references() -> list[MatrixReference]:
    entries: list[MatrixReference] = []
    for payload in _reference_payloads():
        reference = payload.get("reference")
        if not reference:
            continue
        entries.append(
            MatrixReference(
                path=str(reference.get("path", "")),
                title=str(reference.get("title", "Untitled Reference")),
                ref_type=str(reference.get("ref_type", "reference")),
                parent=str(reference.get("parent", "")),
                domain=str(reference.get("domain", "unknown")),
                status=str(reference.get("status", "unknown")),
            )
        )
    return entries


def validate_matrix_rules(entries: list[MatrixSoT] | None = None) -> list[ValidationFinding]:
    sots = entries or discover_sots()
    findings: list[ValidationFinding] = []
    cornerstone_count = sum(item.is_cornerstone for item in sots)

    if cornerstone_count != 1:
        findings.append(
            annotate_finding(ValidationFinding(
                "MATRIX_SINGLE_CORNERSTONE_REQUIRED",
                f"Expected exactly one cornerstone, found {cornerstone_count}",
                "error",
            ))
        )

    for item in sots:
        if not item.is_cornerstone and not item.parent:
            findings.append(
                annotate_finding(ValidationFinding(
                    "MATRIX_PARENT_REQUIRED",
                    f"{item.path} is missing a parent link",
                    "error",
                ))
            )

    return findings


def validate_sot_structure(path: Path) -> list[ValidationFinding]:
    text = path.read_text(encoding="utf-8")
    payload = validate_sot_payload(str(path.relative_to(REPO_ROOT)), text)
    return annotate_findings(
        [ValidationFinding(item["code"], item["detail"], item["severity"], item.get("rule_refs", [])) for item in payload["findings"]]
    )


def validate_matrix_structure(entries: list[MatrixSoT] | None = None) -> list[ValidationFinding]:
    sots = entries or discover_sots()
    findings: list[ValidationFinding] = []
    for entry in sots:
        findings.extend(validate_sot_structure(REPO_ROOT / entry.path))
        findings.extend(validate_parent_consistency(REPO_ROOT / entry.path))
    return findings


def validate_reference_structure(entries: list[MatrixReference] | None = None) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for payload in _reference_payloads():
        findings.extend(
            annotate_findings(
                [
                    ValidationFinding(item["code"], item["detail"], item["severity"], item.get("rule_refs", []))
                    for item in payload.get("findings", [])
                ]
            )
        )
    return findings


def validate_parent_consistency(path: Path) -> list[ValidationFinding]:
    text = path.read_text(encoding="utf-8")
    payload = validate_parent_payload(str(path.relative_to(REPO_ROOT)), text)
    return annotate_findings(
        [ValidationFinding(item["code"], item["detail"], item["severity"], item.get("rule_refs", [])) for item in payload["findings"]]
    )


def classify_change_zone(before: str, after: str) -> str:
    if before == after:
        return "none"

    before_fm = _parse_frontmatter(before)
    after_fm = _parse_frontmatter(after)
    protected_frontmatter = {"sot-type", "created", "last-rewritten", "parent", "domain", "status", "tags"}
    for field in protected_frontmatter:
        if before_fm.get(field) != after_fm.get(field):
            return "protected"

    protected_markers = [
        "### Subject Declaration",
        "### Block Map",
        "## 100.",
        "## 200.",
        "## 300.",
        "## 400.",
        "## 500.",
        "## 600.",
        "## 700.",
    ]
    before_sections = _section_map(before)
    after_sections = _section_map(after)
    for marker in protected_markers:
        if before_sections.get(marker, "") != after_sections.get(marker, ""):
            return "protected"

    fluid_markers = ["### Inbox", "### Status", "### Open Questions", "### Next Actions", "### Decisions"]
    for marker in fluid_markers:
        if before_sections.get(marker, "") != after_sections.get(marker, ""):
            return "fluid"

    return "protected"


def _section_map(text: str) -> dict[str, str]:
    lines = text.splitlines()
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        if line.startswith("### ") or re.match(r"^## \d{3}\.", line):
            current = line.strip()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def render_matrix_index(entries: list[MatrixSoT], refs: list[MatrixReference]) -> str:
    grouped: dict[str, list[MatrixSoT]] = {}
    for entry in entries:
        grouped.setdefault(entry.area, []).append(entry)

    lines = [
        "---",
        "sot-type: reference",
        "created: 2026-04-08",
        "last-rewritten: 2026-04-08",
        'parent: "[[Cornerstone.Project-Vela-SoT#000.Index]]"',
        "domain: matrix",
        "status: active",
        'tags: ["matrix","index","reference","registry"]',
        "---",
        "",
        "# Project Vela Matrix Index",
        "",
        "## This Registry Gives a Top Level View of Every Source of Truth in the Matrix",
        "The index layer exists so the system can see the matrix as a whole, keep track of canonical homes, and verify that the tree still respects the root, parent, and indexing laws.",
        "",
        "## This Summary Shows the Current Shape of the Matrix at a Glance",
        f"- total SoTs: {len(entries)}",
        f"- total governed refs: {len(refs)}",
        f"- cornerstone count: {sum(item.is_cornerstone for item in entries)}",
        f"- indexed areas: {', '.join(sorted(grouped))}",
        "",
    ]

    for area in sorted(grouped):
        lines.extend(
            [
                f"## This Section Lists the {area.title()} SoTs Registered in the Matrix",
                "| Title | Path | Type | Parent | Status |",
                "|---|---|---|---|---|",
            ]
        )
        for item in grouped[area]:
            parent = item.parent or "Cornerstone"
            lines.append(f"| {item.title} | `{item.path}` | `{item.sot_type}` | `{parent}` | `{item.status}` |")
        lines.append("")

    if refs:
        lines.extend(
            [
                "## This Section Lists Governed References Registered in the Matrix",
                "| Title | Path | Type | Parent | Status |",
                "|---|---|---|---|---|",
            ]
        )
        for item in refs:
            lines.append(f"| {item.title} | `{item.path}` | `{item.ref_type}` | `{item.parent}` | `{item.status}` |")
        lines.append("")

    lines.extend(
        [
            "## This Registry Points Back to the Root and the Governing Laws",
            "- Root: [[Cornerstone.Project-Vela-SoT]]",
            "- Laws: `docs/directives/matrix-laws.md`",
            "",
        ]
    )
    return "\n".join(lines)


def write_matrix_index() -> dict[str, Any]:
    entries = discover_sots()
    refs = discover_references()
    findings = validate_matrix_rules(entries) + validate_matrix_structure(entries) + validate_reference_structure(refs)
    MATRIX_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    MATRIX_INDEX_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    MATRIX_INDEX_PATH.write_text(render_matrix_index(entries, refs), encoding="utf-8")
    MATRIX_INDEX_JSON_PATH.write_text(
        json.dumps(
            {
                "entries": [item.as_dict() for item in entries],
                "references": [item.as_dict() for item in refs],
                "findings": [item.as_dict() for item in findings],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "path": str(MATRIX_INDEX_PATH.relative_to(REPO_ROOT)),
        "json_path": str(MATRIX_INDEX_JSON_PATH.relative_to(REPO_ROOT)),
        "entries": len(entries),
        "references": len(refs),
        "findings": [item.as_dict() for item in findings],
    }
