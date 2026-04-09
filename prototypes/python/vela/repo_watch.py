from __future__ import annotations

from typing import Any

from .agents import SequentialPipeline
from .rust_bridge import analyze_release_payload


def analyze_release(packet: dict[str, Any], watchlist_text: str) -> dict[str, Any]:
    return analyze_release_payload(
        str(packet.get("repo", "unknown/repo")),
        str(packet.get("version", "unknown")),
        str(packet.get("notes", "No release notes provided.")),
        watchlist_text,
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


def ingest_release(packet: dict[str, Any], watchlist_text: str, target: str) -> dict[str, Any]:
    assessment = analyze_release(packet, watchlist_text)
    pipeline = SequentialPipeline()
    result = pipeline.run(
        task_type="repo-release",
        title=f"Repo Release Summary for {packet.get('repo', 'unknown/repo')}",
        body=build_release_body(packet, watchlist_text),
        target=target,
    )
    return {
        "route": result.route,
        "plan": result.plan,
        "critique": result.critique,
        "findings": result.findings,
        "committed": result.committed,
        "target": result.target,
        "risk": assessment["risk"],
        "relevance": assessment["relevance"],
        "watched": assessment["watched"],
    }
