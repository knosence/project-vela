from __future__ import annotations

from .models import ValidationFinding


RULE_MAP: dict[str, list[str]] = {
    "SOVEREIGN_APPROVAL_REQUIRED": [
        "Pattern 18 Human Gate",
        "Law 5 Sovereign Changes Shall Touch Roots and Rules Only Through Governed Paths",
    ],
    "SPAWN_APPROVAL_REQUIRED": [
        "Pattern 12 Sovereign Spawn",
        "Pattern 18 Human Gate",
    ],
    "SUBJECT_DECLARATION_APPROVAL_REQUIRED": [
        "Pattern 6 Protected/Fluid Zones",
        "Pattern 9 Declaration Anchor",
        "Pattern 18 Human Gate",
    ],
    "MATRIX_SINGLE_CORNERSTONE_REQUIRED": [
        "Pattern 3 Single Parent",
        "Law 1 The Matrix Shall Have Exactly One Cornerstone",
    ],
    "MATRIX_PARENT_REQUIRED": [
        "Pattern 3 Single Parent",
        "Law 2 Every Non Cornerstone Source of Truth Shall Declare One Parent",
    ],
    "MATRIX_PARENT_DECLARATION_MISMATCH": [
        "Pattern 3 Single Parent",
        "Pattern 9 Declaration Anchor",
        "Law 2 Every Non Cornerstone Source of Truth Shall Declare One Parent",
    ],
    "MATRIX_CORNERSTONE_PARENT_MUST_BE_EMPTY": [
        "Pattern 3 Single Parent",
        "Law 1 The Matrix Shall Have Exactly One Cornerstone",
    ],
    "MATRIX_CORNERSTONE_DECLARATION_PARENT_INVALID": [
        "Pattern 9 Declaration Anchor",
        "Law 1 The Matrix Shall Have Exactly One Cornerstone",
    ],
    "MATRIX_FRONTMATTER_REQUIRED": [
        "Pattern 16 Frontmatter Contract",
    ],
    "MATRIX_HEADING_REQUIRED": [
        "Pattern 2 Demand-Driven Dimensions",
        "Pattern 9 Declaration Anchor",
    ],
    "MATRIX_ACTIVE_SECTION_REQUIRED": [
        "Pattern 2 Demand-Driven Dimensions",
    ],
    "MATRIX_INACTIVE_SECTION_REQUIRED": [
        "Pattern 2 Demand-Driven Dimensions",
        "Pattern 10 Dual Archive",
    ],
    "ARCHIVE_ENTRY_NOT_FOUND": [
        "Pattern 10 Dual Archive",
        "Pattern 13 Extraction Before Deletion",
    ],
    "ARCHIVE_DIMENSION_NOT_FOUND": [
        "Pattern 2 Demand-Driven Dimensions",
        "Pattern 10 Dual Archive",
    ],
    "ARCHIVE_STRUCTURE_INVALID": [
        "Pattern 10 Dual Archive",
    ],
    "ARCHIVE_ACTIVE_ENTRY_NOT_FOUND": [
        "Pattern 10 Dual Archive",
        "Pattern 13 Extraction Before Deletion",
    ],
    "ARCHIVE_BLOCK_MISSING": [
        "Pattern 10 Dual Archive",
    ],
    "ARCHIVE_POSTCONDITION_FAILED": [
        "Pattern 10 Dual Archive",
        "Pattern 13 Extraction Before Deletion",
    ],
    "GROWTH_PROPOSAL_NOT_FOUND": [
        "Pattern 11 Lightest Intervention",
        "Pattern 17 SoT-Native Output",
    ],
    "GROWTH_PROPOSAL_METADATA_INVALID": [
        "Pattern 11 Lightest Intervention",
        "Pattern 16 Frontmatter Contract",
        "Pattern 17 SoT-Native Output",
    ],
    "CONFIG_REQUIRED": [
        "Vela Setup Rule: Setup Mode Honesty",
    ],
    "CONFIG_INCONSISTENT_SETUP_STATE": [
        "Vela Setup Rule: Setup Mode Honesty",
    ],
    "ROLE_ACTION_NOT_ALLOWED": [
        "Role Purity",
        "SoT Operations Reference: Agent Boundary Table",
    ],
}


def annotate_finding(finding: ValidationFinding) -> ValidationFinding:
    if not finding.rule_refs:
        finding.rule_refs = RULE_MAP.get(finding.code, [])
    return finding


def annotate_findings(findings: list[ValidationFinding]) -> list[ValidationFinding]:
    return [annotate_finding(item) for item in findings]
