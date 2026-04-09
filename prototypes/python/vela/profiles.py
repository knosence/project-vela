from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_config, set_active_profile
from .paths import PROFILE_DIR
from .simple_yaml import dumps, loads


def profile_manifest_path(name: str) -> Path:
    return PROFILE_DIR / name / "profile.yaml"


def ensure_default_profile() -> None:
    manifest = profile_manifest_path("vela")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    if not manifest.exists():
        manifest.write_text(
            dumps(
                {
                    "name": "vela",
                    "label": "Vela",
                    "base_profile": "base",
                    "replaceable": True,
                    "system_owned": False,
                    "persona_path": "runtime/personas/vela",
                    "agent_sot_path": "knowledge",
                }
            ),
            encoding="utf-8",
        )
    (manifest.parent / "README.md").write_text(
        "# Vela Persona\n\n## This Persona Directory Holds the Default Bundled Profile Assets\nThe Vela profile is the default bundled assistant and remains replaceable under governed profile selection.\n",
        encoding="utf-8",
    )


def register_profile(name: str, label: str, base_profile: str = "vela") -> Path:
    manifest = profile_manifest_path(name)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        dumps(
            {
                "name": name,
                "label": label,
                "base_profile": base_profile,
                "replaceable": True,
                "system_owned": False,
                "persona_path": f"runtime/personas/{name}",
                "agent_sot_path": "knowledge",
            }
        ),
        encoding="utf-8",
    )
    (manifest.parent / "README.md").write_text(
        f"# {label} Persona\n\n## This Persona Directory Holds a Replaceable Profile\n`{name}` derives from `{base_profile}` and may become active without changing system-level Sources of Truth.\n",
        encoding="utf-8",
    )
    knowledge_dir = PROFILE_DIR.parents[1] / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    (knowledge_dir / f"100.WHO.{label.replace(' ', '-')}-Identity-SoT.md").write_text(
        "\n".join(
            [
                "---",
                "sot-type: system",
                "created: 2026-04-08",
                "last-rewritten: 2026-04-08",
                'parent: "[[100.WHO.Circle-SoT#100.WHO.Humans-and-Agents]]"',
                "domain: agents",
                "status: active",
                'tags: ["agent","identity","sot"]',
                "---",
                "",
                f"# {label} Identity Source of Truth",
                "",
                "## 000.Index",
                "",
                "### Subject Declaration",
                "",
                f"**Subject:** {label} is a replaceable assistant identity inside Knosence's shared knowledge matrix.",
                "**Type:** system",
                "**Created:** 2026-04-08",
                '**Parent:** [[100.WHO.Circle-SoT#100.WHO.Humans-and-Agents]]',
                "",
                "### Links",
                "",
                "- Parent: [[100.WHO.Circle-SoT#100.WHO.Humans-and-Agents]]",
                "- WHO hub: [[100.WHO.Circle-SoT]]",
                "- Cornerstone: [[Cornerstone.Knosence-SoT]]",
                "- WHAT hub: [[200.WHAT.Domain-SoT]]",
                "",
                "### Inbox",
                "",
                "No pending items.",
                "",
                "### Status",
                "",
                "Active replaceable profile identity.",
                "",
                "### Open Questions",
                "",
                f"- What meaningful specialization should `{name}` justify over time? (2026-04-08)",
                "  - A profile branch should earn its complexity instead of growing by default. [AGENT:gpt-5]",
                "",
                "### Next Actions",
                "",
                f"- Keep `{name}` aligned with the governed profile registry and matrix lineage. (2026-04-08)",
                "  - Branch identity should stay synchronized with the system root and activation path. [AGENT:gpt-5]",
                "",
                "### Decisions",
                "",
                "- [2026-04-08] Profile identity SoT created.",
                f"- [2026-04-08] {label} remains a branch identity rather than the matrix cornerstone.",
                "",
                "### Block Map — Single Source",
                "",
                "| ID | Question | Dimension | This SoT's Name |",
                "|----|----------|-----------|-----------------|",
                "| 000 | — | Index | Index |",
                "| 100 | Who | Circle | Identity |",
                "| 200 | What | Domain | Scope |",
                "| 300 | Where | Terrain | Placement |",
                "| 400 | When | Chronicle | Timeline |",
                "| 500 | How | Method | Operation |",
                "| 600 | Why/Not | Compass | Intent |",
                "| 700 | — | Archive | Archive |",
                "",
                "---",
                "",
                "## 100.WHO.Identity",
                "",
                "### Active",
                "",
                f"- {name} derives from `{base_profile}` and remains a shared-knowledge agent branch under Knosence. (2026-04-08)",
                "  - The active profile may change without changing the human-root cornerstone. [AGENT:gpt-5]",
                "",
                "### Inactive",
                "",
                "(No inactive entries.)",
                "",
                "---",
                "",
                "## 200.WHAT.Scope",
                "",
                "### Active",
                "",
                f"- {label} defines a replaceable assistant binding inside one of Knosence's governed domains. (2026-04-08)",
                "  - The profile exists as a branch identity in a shared matrix rather than as a separate knowledge tree. [AGENT:gpt-5]",
                "",
                "### Inactive",
                "",
                "(No inactive entries.)",
                "",
                "---",
                "",
                "## 300.WHERE.Placement",
                "",
                "### Active",
                "",
                f"- The persona manifest lives under `runtime/personas/{name}` and its identity SoT lives in the flat `knowledge/` root. (2026-04-08)",
                "  - Runtime assets stay separated from shared knowledge while the SoT root remains flat. [AGENT:gpt-5]",
                "",
                "### Inactive",
                "",
                "(No inactive entries.)",
                "",
                "---",
                "",
                "## 400.WHEN.Timeline",
                "",
                "### Active",
                "",
                f"- {label} was registered as a profile branch on 2026-04-08. (2026-04-08)",
                "  - The registration date anchors the branch entry in the matrix. [AGENT:gpt-5]",
                "",
                "### Inactive",
                "",
                "(No inactive entries.)",
                "",
                "---",
                "",
                "## 500.HOW.Method",
                "",
                "### Active",
                "",
                f"- {label} is selected through governed profile activation rather than raw file edits. (2026-04-08)",
                "  - Profile switching should happen through the registry and policy path. [AGENT:gpt-5]",
                "",
                "### Inactive",
                "",
                "(No inactive entries.)",
                "",
                "---",
                "",
                "## 600.WHY.Compass",
                "",
                "### Active",
                "",
                f"- {label} exists so the system can support replacement and customization without identity collapse. (2026-04-08)",
                "  - Profiles are branches of the matrix rather than rival roots. [AGENT:gpt-5]",
                "",
                "### Inactive",
                "",
                "(No inactive entries.)",
                "",
                "---",
                "",
                "## 700.Archive",
                "",
                "(No archived entries.)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return manifest


def list_profiles() -> dict[str, Any]:
    ensure_default_profile()
    active = load_config().get("assistant", {}).get("active_profile", "vela")
    profiles = []
    for manifest in sorted(PROFILE_DIR.glob("*/profile.yaml")):
        data = loads(manifest.read_text(encoding="utf-8"))
        profiles.append(
            {
                "name": data["name"],
                "label": data.get("label", data["name"]),
                "base_profile": data.get("base_profile"),
                "active": data["name"] == active,
            }
        )
    return {"active_profile": active, "profiles": profiles}


def activate_profile(name: str) -> dict[str, Any]:
    available = {item["name"] for item in list_profiles()["profiles"]}
    if name not in available:
        raise ValueError(f"Unknown profile: {name}")
    return set_active_profile(name)
