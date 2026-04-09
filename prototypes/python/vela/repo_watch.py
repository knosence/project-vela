from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agents import SequentialPipeline
from .config import load_config
from .governance import write_text
from .rust_bridge import analyze_release_payload


def local_context_markers() -> list[str]:
    cfg = load_config()
    markers: list[str] = ["runtime:python"]
    primary_provider = str(cfg.get("providers", {}).get("primary", "")).strip()
    if primary_provider and primary_provider != "<required>":
        markers.append(f"provider:{primary_provider}")
    deployment_target = str(cfg.get("deployment", {}).get("target", "")).strip()
    if deployment_target and deployment_target != "<required>":
        markers.append(f"deployment:{deployment_target}")

    integrations = cfg.get("integrations", {})
    for name, enabled in integrations.items():
        if enabled:
            markers.append(f"integration:{name}")

    if cfg.get("repo_watch", {}).get("watchlist_path"):
        markers.append("capability:repo-watch")
    markers.append("workflow:n8n")
    markers.append("capability:tooling")
    markers.append("capability:agent")
    return sorted(set(markers))


def analyze_release(packet: dict[str, Any], watchlist_text: str) -> dict[str, Any]:
    return analyze_release_payload(
        str(packet.get("repo", "unknown/repo")),
        str(packet.get("version", "unknown")),
        str(packet.get("notes", "No release notes provided.")),
        watchlist_text,
        local_context_markers(),
    )


def build_release_body(packet: dict[str, Any], watchlist_text: str) -> str:
    repo = packet.get("repo", "unknown/repo")
    version = packet.get("version", "unknown")
    notes = packet.get("notes", "No release notes provided.")
    assessment = analyze_release(packet, watchlist_text)
    watch_reason = assessment["relevance"].get("watch_reason") or "No canonical watch reason recorded."
    return (
        "## This Release Summary States the Upstream Change and Why It Matters Locally\n"
        f"Repository: `{repo}`\n\n"
        f"Version: `{version}`\n\n"
        f"Watched repo: `{'yes' if assessment['watched'] else 'no'}`\n\n"
        f"Breaking change risk: `{assessment['risk']['level']}`\n\n"
        f"Breaking change signals: `{', '.join(assessment['risk']['signals'])}`\n\n"
        f"Local relevance: `{assessment['relevance']['level']}`\n\n"
        f"Watchlist reason: `{watch_reason}`\n\n"
        f"Local relevance signals: `{', '.join(assessment['relevance']['signals'])}`\n\n"
        "## This Release Summary Records the Current Notes\n"
        f"{notes}\n"
    )


def build_release_intelligence_ref(
    packet: dict[str, Any],
    target: str,
    packet_target: str,
    assessment_target: str,
    reflection_target: str,
    validation_target: str,
    summary_target: str,
    assessment: dict[str, Any],
    critique: list[str],
    findings: list[dict[str, Any]],
) -> str:
    repo = packet.get("repo", "unknown/repo")
    version = packet.get("version", "unknown")
    notes = packet.get("notes", "No release notes provided.")
    risk_signals = ", ".join(assessment["risk"]["signals"]) or "none"
    relevance_signals = ", ".join(assessment["relevance"]["signals"]) or "none"
    impact_signals = ", ".join(assessment["local_impact"]["signals"]) or "none"
    critique_lines = "\n".join(f"- {item}" for item in critique) if critique else "- No critique recorded."
    finding_lines = (
        "\n".join(f"- `{item['code']}` {item['detail']}" for item in findings)
        if findings
        else "- No validation findings recorded."
    )
    return (
        "---\n"
        "sot-type: reference\n"
        "created: 2026-04-08\n"
        "last-rewritten: 2026-04-08\n"
        'parent: "[[WHAT.Repo-Watchlist-SoT#200.WHAT.Scope]]"\n'
        "domain: repo-watch\n"
        "status: active\n"
        'tags: ["repo-watch","release","intelligence","reference"]\n'
        "---\n\n"
        f"# Release Intelligence {repo} {version}\n\n"
        "## This Reference Declares the Release Packet and the Review Chain\n"
        f"The release packet for `{repo}` version `{version}` was ingested through the governed repo-watch flow and expanded into assessment, reflection, validation, and summary artifacts.\n\n"
        "## This Reference Links the Governing Inputs and Outputs\n"
        f"- Packet: `{packet_target}`\n"
        f"- Assessment: `{assessment_target}`\n"
        f"- Reflection: `{reflection_target}`\n"
        f"- Validation: `{validation_target}`\n"
        f"- Summary: `{summary_target}`\n"
        "- Parent watchlist: `knowledge/dimensions/WHAT.Repo-Watchlist-SoT.md`\n\n"
        "## This Reference States the Release Judgment Clearly\n"
        f"- Watched repo: `{'yes' if assessment['watched'] else 'no'}`\n"
        f"- Breaking change risk: `{assessment['risk']['level']}`\n"
        f"- Breaking change signals: `{risk_signals}`\n"
        f"- Local relevance: `{assessment['relevance']['level']}`\n"
        f"- Local relevance signals: `{relevance_signals}`\n"
        f"- Local impact: `{assessment['local_impact']['level']}`\n"
        f"- Local impact signals: `{impact_signals}`\n\n"
        "## This Reference Records Reflection Notes for Human Review\n"
        f"{critique_lines}\n\n"
        "## This Reference Records Validation Findings for Traceability\n"
        f"{finding_lines}\n\n"
        "## This Reference Preserves the Current Upstream Notes\n"
        f"{notes}\n"
    )


def ingest_release(packet: dict[str, Any], watchlist_text: str, target: str) -> dict[str, Any]:
    assessment = analyze_release(packet, watchlist_text)
    packet_target = _derived_target_for(target, "packet")
    normalized_packet = {
        "repo": packet.get("repo", "unknown/repo"),
        "version": packet.get("version", "unknown"),
        "notes": packet.get("notes", "No release notes provided."),
        "target": target,
        "watchlist_target": "knowledge/dimensions/WHAT.Repo-Watchlist-SoT.md",
        "context_markers": local_context_markers(),
    }
    packet_result = write_text(
        packet_target,
        json.dumps(normalized_packet, indent=2),
        actor="repo-watch",
        endpoint="repo-release-packet",
        reason="write normalized repo release packet",
    )
    assessment_target = _derived_target_for(target, "assessment")
    assessment_result = write_text(
        assessment_target,
        json.dumps(
            {
                "repo": normalized_packet["repo"],
                "version": normalized_packet["version"],
                "notes": normalized_packet["notes"],
                "watched": assessment["watched"],
                "risk": assessment["risk"],
                "relevance": assessment["relevance"],
                "local_impact": assessment["local_impact"],
            },
            indent=2,
        ),
        actor="repo-watch",
        endpoint="repo-release-assessment",
        reason="write structured repo release assessment",
    )
    pipeline = SequentialPipeline()
    result = pipeline.run(
        task_type="repo-release",
        title=f"Repo Release Summary for {packet.get('repo', 'unknown/repo')}",
        body=build_release_body(packet, watchlist_text),
        target=target,
    )
    reflection_target = _derived_target_for(target, "reflection")
    reflection_result = write_text(
        reflection_target,
        json.dumps(
            {
                "repo": normalized_packet["repo"],
                "version": normalized_packet["version"],
                "route": result.route,
                "critique": result.critique,
            },
            indent=2,
        ),
        actor="reflector",
        endpoint="repo-release-reflection",
        reason="write structured release reflection",
    )
    validation_target = _derived_target_for(target, "validation")
    validation_result = write_text(
        validation_target,
        json.dumps(
            {
                "repo": normalized_packet["repo"],
                "version": normalized_packet["version"],
                "route": result.route,
                "findings": result.findings,
                "committed": result.committed,
            },
            indent=2,
        ),
        actor="warden",
        endpoint="repo-release-validation",
        reason="write structured release validation",
    )
    intelligence_target = str(Path(target).with_name(f"Ref.{Path(target).stem}.Release-Intelligence.md"))
    intelligence_result = write_text(
        intelligence_target,
        build_release_intelligence_ref(
            packet=normalized_packet,
            target=target,
            packet_target=packet_target,
            assessment_target=assessment_target,
            reflection_target=reflection_target,
            validation_target=validation_target,
            summary_target=result.target,
            assessment=assessment,
            critique=result.critique,
            findings=result.findings,
        ),
        actor="scribe",
        endpoint="repo-release-intelligence",
        reason="write release intelligence reference",
    )
    return {
        "route": result.route,
        "plan": result.plan,
        "critique": result.critique,
        "findings": packet_result.get("findings", []) + assessment_result.get("findings", []) + reflection_result.get("findings", []) + validation_result.get("findings", []) + intelligence_result.get("findings", []) + result.findings,
        "committed": result.committed and packet_result["ok"] and assessment_result["ok"] and reflection_result["ok"] and validation_result["ok"] and intelligence_result["ok"],
        "target": result.target,
        "packet_target": packet_target,
        "assessment_target": assessment_target,
        "reflection_target": reflection_target,
        "validation_target": validation_target,
        "intelligence_target": intelligence_target,
        "artifacts": [
            packet_target,
            assessment_target,
            reflection_target,
            validation_target,
            intelligence_target,
            result.target,
        ],
        "risk": assessment["risk"],
        "relevance": assessment["relevance"],
        "watched": assessment["watched"],
        "local_impact": assessment["local_impact"],
    }


def _derived_target_for(target: str, suffix: str) -> str:
    path = Path(target)
    return str(path.with_name(f"{path.stem}.{suffix}.json"))
