from __future__ import annotations

from typing import Any

from .agents import SequentialPipeline


def build_release_body(packet: dict[str, Any], watchlist_text: str) -> str:
    repo = packet.get("repo", "unknown/repo")
    version = packet.get("version", "unknown")
    notes = packet.get("notes", "No release notes provided.")
    relevant = repo in watchlist_text
    risk = "high" if any(word in notes.lower() for word in ["breaking", "migration", "removed"]) else "low"
    return (
        "## This Release Summary States the Change Clearly\n"
        f"Repository: `{repo}`\n\n"
        f"Version: `{version}`\n\n"
        f"Breaking change risk: `{risk}`\n\n"
        f"Local relevance: `{'high' if relevant else 'unknown'}`\n\n"
        "## This Release Summary Records the Current Notes\n"
        f"{notes}\n"
    )


def ingest_release(packet: dict[str, Any], watchlist_text: str, target: str) -> dict[str, Any]:
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
    }

