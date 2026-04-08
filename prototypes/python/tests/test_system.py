from __future__ import annotations

import json
import unittest
from pathlib import Path

from prototypes.python.vela.agents import SequentialPipeline
from prototypes.python.vela.config import DEFAULT_CONFIG, ensure_bootstrap_files, load_config, missing_required_fields, save_config
from prototypes.python.vela.governance import record_approval
from prototypes.python.vela.paths import EVENT_LOG_PATH, REPO_ROOT, STARTER_PATH
from prototypes.python.vela.profiles import activate_profile, list_profiles, register_profile
from prototypes.python.vela.server import VelaService
from prototypes.python.vela.verification import run_scenario


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
        self.assertTrue((REPO_ROOT / "knowledge/cornerstone/100.WHO.System-Identity-SoT.md").exists())
        self.assertTrue((REPO_ROOT / "knowledge/agents/test-custom").exists())

    def test_router_and_planner_paths(self) -> None:
        pipeline = SequentialPipeline()
        result = pipeline.run(
            task_type="write",
            title="Unsafe Change",
            body="## This Draft Tests Guardrails\nThis draft should not commit without approval.",
            target="knowledge/cornerstone/100.WHO.System-Identity-SoT.md",
        )
        self.assertEqual(result.route, "sovereign-change")
        self.assertFalse(result.committed)

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

    def test_sovereign_guardrail(self) -> None:
        service = VelaService()
        denied = service.repo_release({"repo": "openai/example", "version": "1.0.0", "notes": "feature release", "target": "knowledge/cornerstone/100.WHO.System-Identity-SoT.md"})
        self.assertFalse(denied["ok"])
        record_approval("approve_identity", "approved", "human", "allow test", "knowledge/cornerstone/100.WHO.System-Identity-SoT.md")
        pipeline = SequentialPipeline()
        allowed = pipeline.run(
            task_type="write",
            title="Approved Identity Revision",
            body="## This Approved Revision Passes the Guardrail\nThe test now includes a human approval path.",
            target="knowledge/cornerstone/100.WHO.System-Identity-SoT.md",
            approval_id="approve_identity",
        )
        self.assertTrue(allowed.committed)

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

    def test_dry_boot_prompt(self) -> None:
        health = VelaService().health()
        self.assertEqual(health["status"], "setup-required")
        self.assertIn("active_profile", health["data"])

    def test_scenario_runner(self) -> None:
        results = run_scenario("routing")
        self.assertTrue(all("name" in item for item in results))


if __name__ == "__main__":
    unittest.main()
