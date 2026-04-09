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
                    "agent_sot_path": "knowledge/agents/vela",
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
                "agent_sot_path": f"knowledge/agents/{name}",
            }
        ),
        encoding="utf-8",
    )
    (manifest.parent / "README.md").write_text(
        f"# {label} Persona\n\n## This Persona Directory Holds a Replaceable Profile\n`{name}` derives from `{base_profile}` and may become active without changing system-level Sources of Truth.\n",
        encoding="utf-8",
    )
    agent_sot_dir = PROFILE_DIR.parents[1] / "knowledge" / "agents" / name
    agent_sot_dir.mkdir(parents=True, exist_ok=True)
    (agent_sot_dir / f"WHO.{label.replace(' ', '-')}-Identity-SoT.md").write_text(
        "\n".join(
            [
                "---",
                "sot-type: system",
                "created: 2026-04-08",
                "last-rewritten: 2026-04-08",
                'parent: "[[Cornerstone.Project-Vela-SoT#100.WHO.Circle]]"',
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
                f"**Subject:** {label} is a replaceable assistant identity bound to the Project Vela system.",
                "**Type:** system",
                "**Created:** 2026-04-08",
                '**Parent:** [[Cornerstone.Project-Vela-SoT#100.WHO.Circle]]',
                "",
                "### Links",
                "",
                "- Parent: [[Cornerstone.Project-Vela-SoT#100.WHO.Circle]]",
                "- Cornerstone: [[Cornerstone.Project-Vela-SoT]]",
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
                f"- {name} derives from `{base_profile}` and remains subordinate to system governance. (2026-04-08)",
                "  - This profile can become active without replacing the system root. [AGENT:gpt-5]",
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
                f"- {label} defines a replaceable assistant binding. (2026-04-08)",
                "  - The profile exists as a branch identity in the matrix rather than as a second cornerstone. [AGENT:gpt-5]",
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
                f"- The persona manifest lives under `runtime/personas/{name}` and its identity SoT lives here. (2026-04-08)",
                "  - The profile has one home in runtime and one SoT home in knowledge. [AGENT:gpt-5]",
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
