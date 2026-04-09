from __future__ import annotations

import re
from typing import Any

from .agents import SequentialPipeline


RISK_KEYWORDS = {
    "high": ["breaking", "migration", "removed", "deprecat", "rename", "drop support", "incompatib"],
    "medium": ["changed", "updated", "refactor", "new default", "new auth", "retry", "timeout"],
}

LOCAL_SIGNALS = {
    "openai/openai-python": ["python", "sdk", "client", "responses", "chat", "embedding", "api key"],
    "openai/openai-agents-python": ["agent", "tool", "handoff", "workflow", "runner"],
    "n8n-io/n8n": ["workflow", "webhook", "node", "trigger", "credential", "dashboard"],
    "modelcontextprotocol/servers": ["mcp", "server", "tool", "connector", "transport"],
}


def parse_watchlist_entries(watchlist_text: str) -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    current_repo = ""
    for line in watchlist_text.splitlines():
        repo_match = re.match(r"^- ([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\. \(\d{4}-\d{2}-\d{2}\)$", line.strip())
        if repo_match:
            current_repo = repo_match.group(1)
            entries[current_repo] = {"reason": ""}
            continue
        if current_repo and line.strip().startswith("- "):
            entries[current_repo]["reason"] = line.strip()[2:]
            current_repo = ""
    return entries


def assess_breaking_change_risk(notes: str) -> dict[str, Any]:
    lowered = notes.lower()
    matched_high = [word for word in RISK_KEYWORDS["high"] if word in lowered]
    matched_medium = [word for word in RISK_KEYWORDS["medium"] if word in lowered]
    level = "high" if matched_high else "medium" if matched_medium else "low"
    reasons = matched_high or matched_medium or ["no obvious breaking-change markers detected"]
    return {"level": level, "signals": reasons}


def assess_local_relevance(repo: str, notes: str, watchlist_entries: dict[str, dict[str, str]]) -> dict[str, Any]:
    lowered = notes.lower()
    entry = watchlist_entries.get(repo)
    repo_keywords = LOCAL_SIGNALS.get(repo, [])
    matched = [word for word in repo_keywords if word in lowered]
    high_risk = assess_breaking_change_risk(notes)["level"] == "high"
    if entry and matched:
        return {"level": "high", "signals": matched, "watch_reason": entry.get("reason", "")}
    if entry and high_risk:
        return {
            "level": "high",
            "signals": ["high breakage risk on a canonically watched repo"],
            "watch_reason": entry.get("reason", ""),
        }
    if entry:
        return {
            "level": "medium",
            "signals": ["repo is explicitly watched even though release notes did not hit local keywords"],
            "watch_reason": entry.get("reason", ""),
        }
    return {"level": "low", "signals": ["repo is not on the canonical watchlist"], "watch_reason": ""}


def build_release_body(packet: dict[str, Any], watchlist_text: str) -> str:
    repo = packet.get("repo", "unknown/repo")
    version = packet.get("version", "unknown")
    notes = packet.get("notes", "No release notes provided.")
    watchlist_entries = parse_watchlist_entries(watchlist_text)
    risk = assess_breaking_change_risk(notes)
    relevance = assess_local_relevance(repo, notes, watchlist_entries)
    watched = repo in watchlist_entries
    watch_reason = relevance["watch_reason"] or "No canonical watch reason recorded."
    return (
        "## This Release Summary States the Upstream Change and Why It Matters Locally\n"
        f"Repository: `{repo}`\n\n"
        f"Version: `{version}`\n\n"
        f"Watched repo: `{'yes' if watched else 'no'}`\n\n"
        f"Breaking change risk: `{risk['level']}`\n\n"
        f"Breaking change signals: `{', '.join(risk['signals'])}`\n\n"
        f"Local relevance: `{relevance['level']}`\n\n"
        f"Watchlist reason: `{watch_reason}`\n\n"
        f"Local relevance signals: `{', '.join(relevance['signals'])}`\n\n"
        "## This Release Summary Records the Current Notes\n"
        f"{notes}\n"
    )
def ingest_release(packet: dict[str, Any], watchlist_text: str, target: str) -> dict[str, Any]:
    watchlist_entries = parse_watchlist_entries(watchlist_text)
    risk = assess_breaking_change_risk(packet.get("notes", ""))
    relevance = assess_local_relevance(packet.get("repo", "unknown/repo"), packet.get("notes", ""), watchlist_entries)
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
        "risk": risk,
        "relevance": relevance,
    }
