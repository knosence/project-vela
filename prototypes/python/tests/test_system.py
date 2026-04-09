from __future__ import annotations

import json
import unittest
from pathlib import Path

from prototypes.python.vela.agents import SequentialPipeline
from prototypes.python.vela.config import DEFAULT_CONFIG, ensure_bootstrap_files, load_config, missing_required_fields, save_config
from prototypes.python.vela.governance import archive_dimension_entry, record_approval, write_text
from prototypes.python.vela.growth import assess_growth
from prototypes.python.vela.matrix import classify_change_zone
from prototypes.python.vela.matrix import write_matrix_index
from prototypes.python.vela.paths import EVENT_LOG_PATH, REPO_ROOT, STARTER_PATH
from prototypes.python.vela.profiles import activate_profile, list_profiles, register_profile
from prototypes.python.vela.rust_bridge import route_for_target, validate_config_payload
from prototypes.python.vela.server import VelaService
from prototypes.python.vela.verification import run_scenario

TEST_SOVEREIGN_TARGET = "knowledge/proposals/TEST.Sovereign-Guardrail-Fixture.md"


class VelaSystemTest(unittest.TestCase):
    def setUp(self) -> None:
        ensure_bootstrap_files()
        save_config(json.loads(json.dumps(DEFAULT_CONFIG)))
        EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVENT_LOG_PATH.write_text("", encoding="utf-8")

    def test_config_boot(self) -> None:
        cfg = load_config()
        self.assertTrue(STARTER_PATH.exists())
        self.assertTrue((REPO_ROOT / "runtime/config/project-vela.yaml").exists())
        self.assertTrue(missing_required_fields(cfg))

    def test_profile_default_and_replacement(self) -> None:
        profiles = list_profiles()
        self.assertTrue(any(item["name"] == "vela" for item in profiles["profiles"]))
        register_profile("test-custom", "Test Custom")
        activate_profile("test-custom")
        updated = list_profiles()
        self.assertEqual(updated["active_profile"], "test-custom")
        self.assertTrue((REPO_ROOT / "knowledge/cornerstone/Cornerstone.Project-Vela-SoT.md").exists())
        self.assertTrue((REPO_ROOT / "knowledge/agents/test-custom").exists())

    def test_router_and_planner_paths(self) -> None:
        pipeline = SequentialPipeline()
        result = pipeline.run(
            task_type="write",
            title="Unsafe Change",
            body="## This Draft Tests Guardrails\nThis draft should not commit without approval.",
            target=TEST_SOVEREIGN_TARGET,
        )
        self.assertEqual(result.route, "sovereign-change")
        self.assertFalse(result.committed)
        self.assertEqual(route_for_target("repo-release", "knowledge/refs/release.md"), "repo-watch")

    def test_sequential_agent_pipeline(self) -> None:
        pipeline = SequentialPipeline()
        result = pipeline.run(
            task_type="write",
            title="Safe Note",
            body="## This Draft Demonstrates Sequential Flow\nThe worker drafts, reflector critiques, warden validates, and scribe commits.",
            target="knowledge/refs/safe-note.md",
        )
        self.assertTrue(result.committed)
        self.assertTrue((REPO_ROOT / "knowledge/refs/safe-note.md").exists())
        self.assertTrue(result.growth_proposal["ok"])
        self.assertTrue((REPO_ROOT / result.growth_proposal["target"]).exists())
        proposal_text = (REPO_ROOT / result.growth_proposal["target"]).read_text(encoding="utf-8")
        self.assertIn("Recommended stage:", proposal_text)
        self.assertIn("target: `knowledge/refs/safe-note.md`", proposal_text)

    def test_sovereign_guardrail(self) -> None:
        service = VelaService()
        denied = service.repo_release({"repo": "openai/example", "version": "1.0.0", "notes": "feature release", "target": TEST_SOVEREIGN_TARGET})
        self.assertFalse(denied["ok"])
        record_approval("approve_identity", "approved", "human", "allow test", TEST_SOVEREIGN_TARGET)
        pipeline = SequentialPipeline()
        allowed = pipeline.run(
            task_type="write",
            title="Approved Identity Revision",
            body="## This Approved Revision Passes the Guardrail\nThe test now includes a human approval path.",
            target=TEST_SOVEREIGN_TARGET,
            approval_id="approve_identity",
        )
        self.assertTrue(allowed.committed)
        self.assertTrue(allowed.growth_proposal["approval_required"])

    def test_repo_watch(self) -> None:
        result = VelaService().repo_release(
            {
                "repo": "openai/openai-python",
                "version": "1.2.3",
                "notes": "Breaking API migration required.",
                "target": "knowledge/refs/repo-watch-test.md",
            }
        )
        self.assertTrue(result["ok"])
        self.assertTrue((REPO_ROOT / "knowledge/refs/repo-watch-test.md").exists())

    def test_narrative_structure(self) -> None:
        result = VelaService().validate({"scope": "repo", "checks": ["narrative"], "mode": "report"})
        self.assertTrue(result["ok"])
        self.assertTrue(any(item["code"] == "NARRATIVE_VALIDATOR_ACTIVE" for item in result["data"]["findings"]))

    def test_event_log(self) -> None:
        pipeline = SequentialPipeline()
        pipeline.run(
            task_type="write",
            title="Event Log Exercise",
            body="## This Draft Forces a Meaningful Mutation\nA committed write should emit an event record.",
            target="knowledge/refs/event-log.md",
        )
        self.assertIn("event_id", EVENT_LOG_PATH.read_text(encoding="utf-8"))

    def test_protected_zone_write_creates_backup(self) -> None:
        target = "knowledge/proposals/protected-zone-test.md"
        original = (REPO_ROOT / "knowledge/agents/vela/WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8")
        seed_path = REPO_ROOT / target
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        seed_path.write_text(original, encoding="utf-8")
        updated = original.replace(
            "Vela routes, plans, drafts, critiques, validates, documents, and proposes growth under governed workflows.",
            "Vela routes, plans, drafts, critiques, validates, documents, proposes growth, and archives through governed workflows.",
        )
        result = write_text(target, updated, actor="scribe", endpoint="test", reason="protected change")
        self.assertTrue(result["ok"])
        self.assertEqual(result["change_zone"], "protected")
        self.assertTrue(any("Backup.md" in artifact for artifact in result["artifacts"]))

    def test_archive_transaction_moves_entry_and_appends_archive(self) -> None:
        target = "knowledge/proposals/archive-transaction-test.md"
        content = (REPO_ROOT / "knowledge/agents/vela/WHO.Vela-Identity-SoT.md").read_text(encoding="utf-8").replace(
            "- Vela is the default installed assistant profile. (2026-04-08)\n  - The system ships with Vela while still allowing replacement and customization. [AGENT:gpt-5]",
            "- Sample archived value. (2026-04-08)\n  - Exists to verify archive movement. [AGENT:gpt-5]",
        )
        seed_path = REPO_ROOT / target
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        seed_path.write_text(content, encoding="utf-8")
        result = archive_dimension_entry(
            target=target,
            dimension_heading="## 100.WHO.Identity",
            entry_value="Sample archived value. (2026-04-08)",
            archived_reason="Replaced by newer fact",
            actor="scribe",
            endpoint="test-archive",
            reason="archive entry",
        )
        self.assertTrue(result["ok"])
        updated = (REPO_ROOT / target).read_text(encoding="utf-8")
        self.assertIn("Archived Reason: Replaced by newer fact", updated)
        self.assertIn("FROM: ## 100.WHO.Identity", updated)

    def test_change_zone_classifier_distinguishes_fluid_and_protected(self) -> None:
        before = "### Status\n\nOld\n\n### Decisions\n\n- old"
        after = "### Status\n\nNew\n\n### Decisions\n\n- old"
        self.assertEqual(classify_change_zone(before, after), "fluid")
        self.assertEqual(classify_change_zone("## 100.WHO.Identity", "## 100.WHO.Scope"), "protected")

    def test_growth_assessment_stays_flat_for_small_sot(self) -> None:
        assessment = assess_growth("knowledge/agents/vela/WHO.Vela-Identity-SoT.md")
        self.assertEqual(assessment.stage, "flat")

    def test_growth_assessment_detects_fractal_signal(self) -> None:
        target = "knowledge/proposals/growth-fractal-test.md"
        path = REPO_ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        entries = "\n".join(
            f"- Entry {idx}. (2026-04-08)\n  - Context {idx}. [AGENT:gpt-5]"
            for idx in range(1, 10)
        )
        path.write_text(
            (REPO_ROOT / "knowledge/agents/vela/WHO.Vela-Identity-SoT.md")
            .read_text(encoding="utf-8")
            .replace("- Vela is the default installed assistant profile. (2026-04-08)\n  - The system ships with Vela while still allowing replacement and customization. [AGENT:gpt-5]", entries),
            encoding="utf-8",
        )
        assessment = assess_growth(target)
        self.assertEqual(assessment.stage, "fractal")

    def test_growth_assessment_detects_reference_note_signal(self) -> None:
        target = "knowledge/proposals/growth-reference-test.md"
        path = REPO_ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        repeated = "\n".join(f"## 210.Group{idx}\n\n### Active\n\n- Group entry {idx}. (2026-04-08)\n  - Context. [AGENT:gpt-5]\n" for idx in range(1, 6))
        base = (REPO_ROOT / "knowledge/agents/vela/WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8")
        path.write_text(base + "\n" + repeated + ("\nExtra line.\n" * 220), encoding="utf-8")
        assessment = assess_growth(target)
        self.assertEqual(assessment.stage, "reference-note")

    def test_growth_assessment_detects_spawn_signal(self) -> None:
        target = "knowledge/proposals/growth-spawn-test.md"
        path = REPO_ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        repeated_entries = "\n".join(
            f"- Heavy entry {idx}. (2026-04-08)\n  - Context {idx}. [AGENT:gpt-5]"
            for idx in range(1, 15)
        )
        base = (REPO_ROOT / "knowledge/agents/vela/WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8")
        path.write_text(base.replace("- Vela routes, plans, drafts, critiques, validates, documents, and proposes growth under governed workflows. (2026-04-08)\n  - The profile is oriented toward structured assistance rather than unbounded autonomy. [AGENT:gpt-5]", repeated_entries) + ("\nOperational note.\n" * 340), encoding="utf-8")
        assessment = assess_growth(target)
        self.assertEqual(assessment.stage, "spawn")

    def test_dry_boot_prompt(self) -> None:
        health = VelaService().health()
        self.assertEqual(health["status"], "setup-required")
        self.assertIn("active_profile", health["data"])

    def test_rust_config_bridge(self) -> None:
        payload = validate_config_payload(load_config())
        self.assertTrue(payload["setup_required"])
        self.assertTrue(any(item["code"] == "CONFIG_REQUIRED" for item in payload["findings"]))

    def test_matrix_index_layer(self) -> None:
        result = write_matrix_index()
        self.assertTrue((REPO_ROOT / result["path"]).exists())
        contents = (REPO_ROOT / result["path"]).read_text(encoding="utf-8")
        self.assertIn("Cornerstone.Project-Vela-SoT", contents)
        self.assertFalse(result["findings"])

    def test_scenario_runner(self) -> None:
        results = run_scenario("routing")
        self.assertTrue(all("name" in item for item in results))


if __name__ == "__main__":
    unittest.main()
