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
    (agent_sot_dir / f"100.WHO.{label.replace(' ', '-')}-Identity-SoT.md").write_text(
        f"# {label} Identity Source of Truth\n\n## This Profile Defines a Replaceable Assistant Binding\n{name} derives from `{base_profile}` and remains subordinate to system governance.\n",
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
