from __future__ import annotations

import json
import unittest
from pathlib import Path

from prototypes.python.vela.agents import SequentialPipeline
from prototypes.python.vela.config import DEFAULT_CONFIG, ensure_bootstrap_files, load_config, missing_required_fields, save_config
from prototypes.python.vela.governance import (
    apply_growth_proposal,
    archive_dimension_entry,
    build_pointer_entry,
    create_cross_reference,
    record_approval,
    route_inbox_entry,
    write_text,
)
from prototypes.python.vela.inbox import triage_inbox
from prototypes.python.vela.growth import assess_growth
from prototypes.python.vela.matrix import classify_change_zone
from prototypes.python.vela.matrix import validate_canonical_graph_targets
from prototypes.python.vela.matrix import write_matrix_index
from prototypes.python.vela.matrix import validate_parent_consistency
from prototypes.python.vela.operations_runtime import list_dreamer_queue, review_dreamer_proposal, run_night_cycle, run_warden_patrol
from prototypes.python.vela.paths import EVENT_LOG_PATH, PATCH_LOG_PATH, REPO_ROOT, STARTER_PATH
from prototypes.python.vela.profiles import activate_profile, list_profiles, register_profile
from prototypes.python.vela.repo_watch import analyze_release
from prototypes.python.vela.rust_bridge import (
    inspect_reference_payload,
    matrix_inventory_payload,
    route_for_target,
    route_inbox_payload,
    validate_archive_postconditions_payload,
    validate_config_payload,
    validate_growth_stage_payload,
    validate_subject_declaration_payload,
    validate_target as validate_target_payload,
)
from prototypes.python.vela.server import VelaService
from prototypes.python.vela.verification import run_scenario

TEST_SOVEREIGN_TARGET = "knowledge/ARTIFACTS/proposals/TEST.Sovereign-Guardrail-Fixture.md"


class VelaSystemTest(unittest.TestCase):
    def setUp(self) -> None:
        ensure_bootstrap_files()
        save_config(json.loads(json.dumps(DEFAULT_CONFIG)))
        EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVENT_LOG_PATH.write_text("", encoding="utf-8")
        self._cleanup_generated_artifacts()

    def tearDown(self) -> None:
        self._cleanup_generated_artifacts()

    def _cleanup_generated_artifacts(self) -> None:
        for target in [
            "knowledge/Cornerstone.Knosence-SoT.Spawned-Child-SoT.md",
            "knowledge/Cornerstone.Project-Vela.Spawned-Child-SoT.md",
            "knowledge/ARTIFACTS/refs/Ref.WHAT.Vela-Capabilities.md",
            "knowledge/ARTIFACTS/refs/Ref.210.WHAT.Vela-Capabilities-SoT.md",
            "knowledge/ARTIFACTS/refs/Ref.reference-source.md",
            "knowledge/ARTIFACTS/refs/Ref.service-source.md",
            "knowledge/ARTIFACTS/proposals/growth-apply-reference-test.md",
            "knowledge/ARTIFACTS/proposals/growth-apply-service-test.md",
            "knowledge/ARTIFACTS/proposals/growth-apply-sovereign-test.md",
            "knowledge/ARTIFACTS/proposals/reference-source-SoT.md",
            "knowledge/ARTIFACTS/proposals/service-source-SoT.md",
            "knowledge/ARTIFACTS/proposals/spawn-source-SoT.md",
            "knowledge/ARTIFACTS/proposals/spawn-source.Spawned-Child-SoT.md",
            "knowledge/ARTIFACTS/proposals/fractal-source-SoT.md",
            "knowledge/ARTIFACTS/proposals/growth-apply-fractal-test.md",
            "knowledge/ARTIFACTS/proposals/growth-apply-spawn-test.md",
            "knowledge/ARTIFACTS/proposals/Synthetic-Identity-SoT.md",
            "knowledge/ARTIFACTS/proposals/Synthetic-Identity.Spawned-Child-SoT.md",
            "knowledge/ARTIFACTS/proposals/direct-root-agent-branch-test.md",
            "knowledge/ARTIFACTS/proposals/direct-root-dimension-branch-test.md",
            "knowledge/ARTIFACTS/proposals/repo-watch-test.md",
            "knowledge/ARTIFACTS/proposals/Ref.repo-watch-test.Release-Intelligence.md",
            "knowledge/ARTIFACTS/proposals/repo-watch-test.packet.json",
            "knowledge/ARTIFACTS/proposals/repo-watch-test.assessment.json",
            "knowledge/ARTIFACTS/proposals/repo-watch-test.reflection.json",
            "knowledge/ARTIFACTS/proposals/repo-watch-test.validation.json",
            "knowledge/ARTIFACTS/refs/indexed-release-summary.md",
            "knowledge/ARTIFACTS/refs/Ref.indexed-release-summary.Release-Intelligence.md",
            "knowledge/ARTIFACTS/refs/indexed-release-summary.packet.json",
            "knowledge/ARTIFACTS/refs/indexed-release-summary.assessment.json",
            "knowledge/ARTIFACTS/refs/indexed-release-summary.reflection.json",
            "knowledge/ARTIFACTS/refs/indexed-release-summary.validation.json",
            "knowledge/ARTIFACTS/proposals/inbox-triage-target.md",
            "knowledge/ARTIFACTS/proposals/cross-reference-target.md",
        ]:
            path = REPO_ROOT / target
            if path.exists():
                path.unlink()
        for target in [
            "knowledge/INBOX/test-inbox-item.md",
            "knowledge/INBOX/test-inbox-missing-target.md",
            "knowledge/INBOX/test-inbox-item.txt",
            "knowledge/INBOX/test-inbox-item.csv",
            "knowledge/INBOX/test-inbox-ambiguous.csv",
            "knowledge/INBOX/test-inbox-binary.png",
        ]:
            path = REPO_ROOT / target
            if path.exists():
                path.unlink()
        for target in [
            "knowledge/ARTIFACTS/proposals/inbox-triage-target.txt",
            "knowledge/ARTIFACTS/proposals/inbox-triage-target-20260409.txt",
            "knowledge/ARTIFACTS/proposals/inbox-triage-target.csv",
            "knowledge/ARTIFACTS/proposals/inbox-triage-target-20260409.csv",
        ]:
            path = REPO_ROOT / target
            if path.exists():
                path.unlink()
        for path in (REPO_ROOT / "knowledge/ARTIFACTS/refs").glob("Warden-Patrol-*.md"):
            path.unlink()
        for path in (REPO_ROOT / "knowledge/ARTIFACTS/refs").glob("DC-Night-Report-*.md"):
            path.unlink()
        for path in (REPO_ROOT / "knowledge/ARTIFACTS/refs").glob("Dreamer-Pattern-Report-*.md"):
            path.unlink()
        for path in (REPO_ROOT / "knowledge/ARTIFACTS/proposals").glob("Dreamer-Proposal.*.md"):
            path.unlink()
        if PATCH_LOG_PATH.exists():
            PATCH_LOG_PATH.unlink()

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
        self.assertTrue((REPO_ROOT / "knowledge/Cornerstone.Knosence-SoT.md").exists())
        self.assertTrue((REPO_ROOT / "knowledge").exists())

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
        self.assertEqual(route_for_target("repo-release", "knowledge/ARTIFACTS/refs/release.md"), "repo-watch")

    def test_sequential_agent_pipeline(self) -> None:
        pipeline = SequentialPipeline()
        result = pipeline.run(
            task_type="write",
            title="Safe Note",
            body="## This Draft Demonstrates Sequential Flow\nThe worker drafts, reflector critiques, warden validates, and scribe commits.",
            target="knowledge/ARTIFACTS/refs/safe-note.md",
        )
        self.assertTrue(result.committed)
        self.assertTrue((REPO_ROOT / "knowledge/ARTIFACTS/refs/safe-note.md").exists())
        self.assertTrue(result.growth_proposal["ok"])
        self.assertTrue((REPO_ROOT / result.growth_proposal["target"]).exists())
        proposal_text = (REPO_ROOT / result.growth_proposal["target"]).read_text(encoding="utf-8")
        self.assertIn("Recommended stage:", proposal_text)
        self.assertIn("target: `knowledge/ARTIFACTS/refs/safe-note.md`", proposal_text)
        self.assertIn("inventory role:", proposal_text)

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
                "target": "knowledge/ARTIFACTS/proposals/repo-watch-test.md",
            }
        )
        self.assertTrue(result["ok"])
        self.assertTrue((REPO_ROOT / "knowledge/ARTIFACTS/proposals/repo-watch-test.md").exists())
        self.assertTrue((REPO_ROOT / result["data"]["packet_target"]).exists())
        self.assertTrue((REPO_ROOT / result["data"]["assessment_target"]).exists())
        self.assertTrue((REPO_ROOT / result["data"]["reflection_target"]).exists())
        self.assertTrue((REPO_ROOT / result["data"]["validation_target"]).exists())
        self.assertTrue((REPO_ROOT / result["data"]["intelligence_target"]).exists())
        self.assertEqual(result["data"]["risk"]["level"], "high")
        self.assertEqual(result["data"]["relevance"]["level"], "high")
        self.assertEqual(result["data"]["local_impact"]["level"], "high")
        packet_record = json.loads((REPO_ROOT / result["data"]["packet_target"]).read_text(encoding="utf-8"))
        assessment_record = json.loads((REPO_ROOT / result["data"]["assessment_target"]).read_text(encoding="utf-8"))
        reflection_record = json.loads((REPO_ROOT / result["data"]["reflection_target"]).read_text(encoding="utf-8"))
        validation_record = json.loads((REPO_ROOT / result["data"]["validation_target"]).read_text(encoding="utf-8"))
        intelligence_ref = (REPO_ROOT / result["data"]["intelligence_target"]).read_text(encoding="utf-8")
        self.assertEqual(packet_record["repo"], "openai/openai-python")
        self.assertEqual(assessment_record["risk"]["level"], "high")
        self.assertTrue(reflection_record["critique"])
        self.assertIn("findings", validation_record)
        self.assertIn("Release Intelligence openai/openai-python 1.2.3", intelligence_ref)
        self.assertIn(result["data"]["assessment_target"], intelligence_ref)

    def test_repo_watch_analysis_uses_watchlist_reasoning(self) -> None:
        watchlist = (REPO_ROOT / "knowledge/220.WHAT.Repo-Watchlist-SoT.md").read_text(encoding="utf-8")
        assessment = analyze_release(
            {
                "repo": "openai/openai-python",
                "version": "1.2.3",
                "notes": "Breaking migration removes the old client construction path for the python sdk responses api.",
            },
            watchlist,
        )
        self.assertEqual(assessment["risk"]["level"], "high")
        self.assertIn("migration", assessment["risk"]["signals"])
        self.assertEqual(assessment["relevance"]["level"], "high")
        self.assertIn("client", assessment["relevance"]["signals"])
        self.assertIn("Python SDK changes are relevant", assessment["relevance"]["watch_reason"])
        self.assertEqual(assessment["local_impact"]["level"], "high")
        self.assertIn("runtime:python", assessment["local_impact"]["context_markers"])
        self.assertIn("integration:github", assessment["local_impact"]["context_markers"])

    def test_narrative_structure(self) -> None:
        result = VelaService().validate({"scope": "repo", "checks": ["narrative"], "mode": "report"})
        self.assertTrue(result["ok"])
        self.assertTrue(any(item["code"] == "NARRATIVE_VALIDATOR_ACTIVE" for item in result["data"]["findings"]))

    def test_validation_findings_include_rule_refs(self) -> None:
        result = VelaService().validate({"scope": "repo", "checks": ["policy"], "mode": "report"})
        config_finding = next(item for item in result["data"]["findings"] if item["code"] == "CONFIG_REQUIRED")
        self.assertIn("Vela Setup Rule: Setup Mode Honesty", config_finding["rule_refs"])

    def test_rust_bridge_findings_include_rule_refs(self) -> None:
        payload = validate_target_payload(
            "knowledge/Cornerstone.Knosence-SoT.md",
            "# Proposed Change\n\n## This Draft Tries to Touch the Cornerstone\nThis should require approval.\n",
            "missing",
        )
        finding = next(item for item in payload["findings"] if item["code"] == "SOVEREIGN_APPROVAL_REQUIRED")
        self.assertIn("Pattern 18 Human Gate", finding["rule_refs"])

    def test_event_log(self) -> None:
        pipeline = SequentialPipeline()
        pipeline.run(
            task_type="write",
            title="Event Log Exercise",
            body="## This Draft Forces a Meaningful Mutation\nA committed write should emit an event record.",
            target="knowledge/ARTIFACTS/refs/event-log.md",
        )
        self.assertIn("event_id", EVENT_LOG_PATH.read_text(encoding="utf-8"))

    def test_protected_zone_write_creates_backup(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/protected-zone-test.md"
        original = (REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8")
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
        target = "knowledge/ARTIFACTS/proposals/archive-transaction-test.md"
        content = (REPO_ROOT / "knowledge/110.WHO.Vela-Identity-SoT.md").read_text(encoding="utf-8").replace(
            "- Vela is the default installed assistant profile under Knosence. (2026-04-08)\n  - The profile is close to the human root without replacing it. [HUMAN]",
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

    def test_vela_cannot_archive_directly(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/archive-transaction-test.md"
        content = (REPO_ROOT / "knowledge/110.WHO.Vela-Identity-SoT.md").read_text(encoding="utf-8").replace(
            "- Vela is the default installed assistant profile under Knosence. (2026-04-08)\n  - The profile is close to the human root without replacing it. [HUMAN]",
            "- Sample archived value. (2026-04-08)\n  - Exists to verify archive movement. [AGENT:gpt-5]",
        )
        path = REPO_ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        result = archive_dimension_entry(
            target=target,
            dimension_heading="## 100.WHO.Identity",
            entry_value="Sample archived value. (2026-04-08)",
            archived_reason="Replaced by newer fact",
            actor="vela",
            endpoint="test-archive",
            reason="archive entry",
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "ROLE_ACTION_NOT_ALLOWED" for item in result["findings"]))

    def test_subject_declaration_change_requires_approval(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/subject-declaration-test.md"
        original = (REPO_ROOT / "knowledge/110.WHO.Vela-Identity-SoT.md").read_text(encoding="utf-8")
        path = REPO_ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(original, encoding="utf-8")
        changed = original.replace(
            "**Subject:** Vela is the default bundled assistant identity inside Knosence's Knosence domain.",
            "**Subject:** Vela is the fully sovereign root of the matrix.",
        )
        denied = write_text(target, changed, actor="scribe", endpoint="test", reason="subject declaration change")
        self.assertFalse(denied["ok"])
        self.assertTrue(any(item["code"] == "SUBJECT_DECLARATION_APPROVAL_REQUIRED" for item in denied["findings"]))
        record_approval("approve_subject_declaration", "approved", "human", "allow protected declaration test", target)
        allowed = write_text(
            target,
            changed,
            actor="scribe",
            endpoint="test",
            reason="subject declaration change",
            approval_id="approve_subject_declaration",
        )
        self.assertTrue(allowed["ok"])

    def test_warden_cannot_write_canonical_sot(self) -> None:
        target = "knowledge/210.WHAT.Vela-Capabilities-SoT.md"
        original = (REPO_ROOT / target).read_text(encoding="utf-8")
        changed = original.replace(
            "Vela routes, plans, drafts, critiques, validates, documents, and proposes growth under governed workflows.",
            "Vela routes, plans, drafts, critiques, validates, documents, proposes growth, and patrols canonical writes.",
        )
        result = write_text(target, changed, actor="warden", endpoint="test", reason="warden canonical write")
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "ROLE_ACTION_NOT_ALLOWED" for item in result["findings"]))

    def test_change_zone_classifier_distinguishes_fluid_and_protected(self) -> None:
        before = "### Status\n\nOld\n\n### Decisions\n\n- old"
        after = "### Status\n\nNew\n\n### Decisions\n\n- old"
        self.assertEqual(classify_change_zone(before, after), "fluid")
        self.assertEqual(classify_change_zone("## 100.WHO.Identity", "## 100.WHO.Scope"), "protected")

    def test_dimension_router_routes_and_leaves_ambiguous_in_inbox(self) -> None:
        self.assertEqual(route_inbox_entry("Alex joined the project team this week."), "100")
        self.assertEqual(route_inbox_entry("We chose Fidelity because of NAV DRIP."), "600")
        self.assertIsNone(route_inbox_entry("Unsorted note needing review."))

    def test_cross_reference_pointer_format(self) -> None:
        pointer = build_pointer_entry(
            "Repo watch summary recorded",
            "220.WHAT.Repo-Watchlist-SoT",
            "200.WHAT.Domain",
            "2026-04-08",
        )
        self.assertEqual(
            pointer,
            "- Repo watch summary recorded. See: [[220.WHAT.Repo-Watchlist-SoT#200.WHAT.Domain]] (2026-04-08)",
        )

    def test_cross_reference_operation_creates_pointer_entry(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/cross-reference-target.md"
        target_path = REPO_ROOT / target
        target_path.write_text((REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8"), encoding="utf-8")
        result = create_cross_reference(
            claimant_target=target,
            claimant_dimension_heading="## 200.WHAT.Capabilities",
            description="Repo watch summary recorded",
            primary_target="knowledge/220.WHAT.Repo-Watchlist-SoT.md",
            primary_dimension_heading="200.WHAT.Watch Scope",
            actor="scribe",
            endpoint="test-cross-reference",
            reason="pointer operation test",
        )
        self.assertTrue(result["ok"])
        updated = target_path.read_text(encoding="utf-8")
        self.assertIn(
            "- Repo watch summary recorded. See: [[220.WHAT.Repo-Watchlist-SoT#200.WHAT.Watch Scope]] (",
            updated,
        )

    def test_cross_reference_service_endpoint(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/cross-reference-target.md"
        target_path = REPO_ROOT / target
        target_path.write_text((REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8"), encoding="utf-8")
        result = VelaService().cross_reference(
            {
                "claimant_target": target,
                "claimant_dimension_heading": "## 200.WHAT.Capabilities",
                "description": "Repo watch summary recorded",
                "primary_target": "knowledge/220.WHAT.Repo-Watchlist-SoT.md",
                "primary_dimension_heading": "200.WHAT.Watch Scope",
                "actor": "n8n",
            }
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["endpoint"], "cross-reference")

    def test_growth_assessment_stays_flat_for_small_sot(self) -> None:
        assessment = assess_growth("knowledge/110.WHO.Vela-Identity-SoT.md")
        self.assertEqual(assessment.stage, "flat")
        self.assertEqual(assessment.inventory_role, "agent-identity")

    def test_growth_assessment_prefers_spawn_for_dense_dimension_hub(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/200.WHAT.Domain-SoT.md"
        path = REPO_ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        base = (REPO_ROOT / "knowledge/200.WHAT.Domain-SoT.md").read_text(encoding="utf-8")
        repeated_entries = "\n".join(
            f"- Dense hub entry {idx}. (2026-04-08)\n  - Context {idx}. [AGENT:gpt-5]"
            for idx in range(1, 12)
        )
        path.write_text(
            base + "\n\n## 210.Domain-Pressure\n\n### Active\n\n" + repeated_entries + "\n\n### Inactive\n\n(No inactive entries.)\n",
            encoding="utf-8",
        )
        assessment = assess_growth(target)
        self.assertEqual(assessment.inventory_role, "dimension-hub")
        self.assertEqual(assessment.stage, "spawn")

    def test_growth_assessment_prefers_reference_for_dense_identity_branch(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/Synthetic-Identity-SoT.md"
        path = REPO_ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        base = (REPO_ROOT / "knowledge/110.WHO.Vela-Identity-SoT.md").read_text(encoding="utf-8")
        repeated_entries = "\n".join(
            f"- Identity entry {idx}. (2026-04-08)\n  - Context {idx}. [AGENT:gpt-5]"
            for idx in range(1, 12)
        )
        path.write_text(
            base.replace(
                "- Vela is the default installed assistant profile. (2026-04-08)\n  - The system ships with Vela while still allowing replacement and customization. [AGENT:gpt-5]",
                repeated_entries,
            ) + ("\nInterpretive note.\n" * 260),
            encoding="utf-8",
        )
        assessment = assess_growth(target)
        self.assertEqual(assessment.inventory_role, "agent-identity")
        self.assertEqual(assessment.stage, "reference-note")

    def test_growth_assessment_detects_fractal_signal(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/growth-fractal-test.md"
        path = REPO_ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        entries = "\n".join(
            f"- Entry {idx}. (2026-04-08)\n  - Context {idx}. [AGENT:gpt-5]"
            for idx in range(1, 10)
        )
        path.write_text(
            (REPO_ROOT / "knowledge/110.WHO.Vela-Identity-SoT.md")
            .read_text(encoding="utf-8")
            .replace("- Vela is the default installed assistant profile under Knosence. (2026-04-08)\n  - The profile is close to the human root without replacing it. [HUMAN]", entries),
            encoding="utf-8",
        )
        assessment = assess_growth(target)
        self.assertEqual(assessment.stage, "fractal")

    def test_growth_assessment_detects_reference_note_signal(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/growth-reference-test.md"
        path = REPO_ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        repeated = "\n".join(f"## 210.Group{idx}\n\n### Active\n\n- Group entry {idx}. (2026-04-08)\n  - Context. [AGENT:gpt-5]\n" for idx in range(1, 6))
        base = (REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8")
        path.write_text(base + "\n" + repeated + ("\nExtra line.\n" * 220), encoding="utf-8")
        assessment = assess_growth(target)
        self.assertEqual(assessment.stage, "reference-note")

    def test_growth_assessment_detects_spawn_signal(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/growth-spawn-test.md"
        path = REPO_ROOT / target
        path.parent.mkdir(parents=True, exist_ok=True)
        repeated_entries = "\n".join(
            f"- Heavy entry {idx}. (2026-04-08)\n  - Context {idx}. [AGENT:gpt-5]"
            for idx in range(1, 15)
        )
        base = (REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8")
        path.write_text(base.replace("- Vela routes, plans, drafts, critiques, validates, documents, and proposes growth under governed workflows. (2026-04-08)\n  - The profile is oriented toward structured assistance rather than unbounded autonomy. [AGENT:gpt-5]", repeated_entries) + ("\nOperational note.\n" * 340), encoding="utf-8")
        assessment = assess_growth(target)
        self.assertEqual(assessment.stage, "spawn")

    def test_apply_growth_proposal_creates_execution_artifact(self) -> None:
        proposal_target = "knowledge/ARTIFACTS/proposals/growth-apply-reference-test.md"
        source_target = "knowledge/ARTIFACTS/proposals/reference-source-SoT.md"
        (REPO_ROOT / source_target).write_text(
            (REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        proposal_path = REPO_ROOT / proposal_target
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(
            "---\n"
            "sot-type: proposal\n"
            "created: 2026-04-09\n"
            "last-rewritten: 2026-04-09\n"
            'parent: "[[reference-source-SoT]]"\n'
            "domain: governance\n"
            "status: proposed\n"
            f'target: "{source_target}"\n'
            'route: "standard"\n'
            'recommended-stage: "reference-note"\n'
            'tags: ["growth","proposal"]\n'
            "---\n\n"
            "# Growth Proposal\n\n"
            "## This Proposal Records the Matrix Growth Assessment After the Main Task\n"
            "Reference note extraction should happen.\n\n"
            "## This Proposal States the Recommended Growth Path and the Reason for It\n"
            "Recommended stage: `reference-note`.\n\n"
            "Reason: The parent artifact needs a companion reference note.\n\n"
            "## This Proposal Records the Signals That Triggered the Recommendation\n"
            "- signals: `{'line_count': 280}`\n\n"
            "## This Proposal Identifies the Artifact That Would Be Affected If Approved\n"
            "- target: `knowledge/210.WHAT.Vela-Capabilities-SoT.md`\n",
            encoding="utf-8",
        )
        result = apply_growth_proposal(proposal_target, actor="scribe")
        self.assertTrue(result["ok"])
        self.assertEqual(result["execution_kind"], "reference-note")
        self.assertTrue((REPO_ROOT / result["execution_target"]).exists())
        ref_text = (REPO_ROOT / result["execution_target"]).read_text(encoding="utf-8")
        self.assertIn("This Reference Note Preserves the Extracted Active Entries", ref_text)
        self.assertIn("Vela routes, plans, drafts, critiques, validates, documents, and proposes growth under governed workflows.", ref_text)
        updated_source = (REPO_ROOT / source_target).read_text(encoding="utf-8")
        self.assertIn("Reference Note: [[Ref.reference-source]]", updated_source)
        self.assertIn("created a reference note `[[Ref.reference-source]]`", updated_source)
        self.assertIn("Detailed entries moved to `[[Ref.reference-source]]`", updated_source)

    def test_apply_growth_proposal_blocks_sovereign_without_approval(self) -> None:
        proposal_target = "knowledge/ARTIFACTS/proposals/growth-apply-sovereign-test.md"
        source_target = "knowledge/ARTIFACTS/proposals/Synthetic-Identity-SoT.md"
        (REPO_ROOT / source_target).write_text(
            (REPO_ROOT / "knowledge/110.WHO.Vela-Identity-SoT.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        proposal_path = REPO_ROOT / proposal_target
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(
            "---\n"
            "sot-type: proposal\n"
            "created: 2026-04-09\n"
            "last-rewritten: 2026-04-09\n"
            'parent: "[[Synthetic-Identity-SoT]]"\n'
            "domain: governance\n"
            "status: proposed\n"
            f'target: "{source_target}"\n'
            'route: "sovereign-change"\n'
            'recommended-stage: "spawn"\n'
            'tags: ["growth","proposal"]\n'
            "---\n\n"
            "# Growth Proposal\n\n"
            "## This Proposal Records the Matrix Growth Assessment After the Main Task\n"
            "Spawn should not execute without approval.\n\n"
            "## This Proposal States the Recommended Growth Path and the Reason for It\n"
            "Recommended stage: `spawn`.\n\n"
            "Reason: The cornerstone branch needs protected review.\n",
            encoding="utf-8",
        )
        denied = apply_growth_proposal(proposal_target, actor="scribe")
        self.assertFalse(denied["ok"])
        self.assertTrue(denied["approval_required"])
        finding = denied["findings"][0]
        self.assertTrue(
            "Pattern 18 Human Gate" in finding["rule_refs"] or "Pattern 12 Sovereign Spawn" in finding["rule_refs"]
        )
        record_approval("approve_growth_sovereign", "approved", "human", "allow growth test", source_target)
        allowed = apply_growth_proposal(proposal_target, actor="scribe", approval_id="approve_growth_sovereign")
        self.assertTrue(allowed["ok"])

    def test_apply_growth_proposal_updates_source_for_spawn(self) -> None:
        proposal_target = "knowledge/ARTIFACTS/proposals/growth-apply-spawn-test.md"
        source_target = "knowledge/ARTIFACTS/proposals/spawn-source-SoT.md"
        source_path = REPO_ROOT / source_target
        source_path.write_text(
            (REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        proposal_path = REPO_ROOT / proposal_target
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(
            "---\n"
            "sot-type: proposal\n"
            "created: 2026-04-09\n"
            "last-rewritten: 2026-04-09\n"
            'parent: "[[spawn-source-SoT]]"\n'
            "domain: governance\n"
            "status: proposed\n"
            f'target: "{source_target}"\n'
            'route: "standard"\n'
            'recommended-stage: "spawn"\n'
            'tags: ["growth","proposal"]\n'
            "---\n\n"
            "# Growth Proposal\n\n"
            "## This Proposal Records the Matrix Growth Assessment After the Main Task\n"
            "Spawn should create a child SoT and update the source.\n",
            encoding="utf-8",
        )
        denied = apply_growth_proposal(proposal_target, actor="scribe")
        self.assertFalse(denied["ok"])
        self.assertTrue(any(item["code"] == "SPAWN_APPROVAL_REQUIRED" for item in denied["findings"]))
        record_approval("approve_spawn_execution", "approved", "human", "allow spawn execution", source_target)
        result = apply_growth_proposal(proposal_target, actor="scribe", approval_id="approve_spawn_execution")
        self.assertTrue(result["ok"])
        self.assertEqual(result["execution_kind"], "spawned-sot")
        child_text = (REPO_ROOT / result["execution_target"]).read_text(encoding="utf-8")
        self.assertIn("- Source Branch: [[spawn-source-SoT]]", child_text)
        self.assertIn("- Source Target: `knowledge/ARTIFACTS/proposals/spawn-source-SoT.md`", child_text)
        updated_source = source_path.read_text(encoding="utf-8")
        self.assertIn("Spawned Child: [[spawn-source.Spawned-Child-SoT]]", updated_source)
        self.assertIn("created a spawned child SoT `[[spawn-source.Spawned-Child-SoT]]`", updated_source)
        self.assertIn("Branch-specific detail now continues in `[[spawn-source.Spawned-Child-SoT]]`", updated_source)

    def test_grower_cannot_execute_spawn_stage(self) -> None:
        proposal_target = "knowledge/ARTIFACTS/proposals/growth-apply-spawn-test.md"
        source_target = "knowledge/ARTIFACTS/proposals/spawn-source-SoT.md"
        (REPO_ROOT / source_target).write_text(
            (REPO_ROOT / "knowledge/110.WHO.Vela-Identity-SoT.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        proposal_path = REPO_ROOT / proposal_target
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(
            "---\n"
            "sot-type: proposal\n"
            "created: 2026-04-09\n"
            "last-rewritten: 2026-04-09\n"
            'parent: "[[spawn-source-SoT]]"\n'
            "domain: governance\n"
            "status: proposed\n"
            f'target: "{source_target}"\n'
            'route: "standard"\n'
            'recommended-stage: "spawn"\n'
            'tags: ["growth","proposal"]\n'
            "---\n\n"
            "# Growth Proposal\n\n"
            "## This Proposal Records the Matrix Growth Assessment After the Main Task\n"
            "Spawn should not execute under Grower.\n",
            encoding="utf-8",
        )
        record_approval("approve_spawn_for_role_test", "approved", "human", "allow spawn test", source_target)
        result = apply_growth_proposal(proposal_target, actor="grower", approval_id="approve_spawn_for_role_test")
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "ROLE_ACTION_NOT_ALLOWED" for item in result["findings"]))

    def test_apply_growth_proposal_fractalizes_source(self) -> None:
        proposal_target = "knowledge/ARTIFACTS/proposals/growth-apply-fractal-test.md"
        source_target = "knowledge/ARTIFACTS/proposals/fractal-source-SoT.md"
        source_path = REPO_ROOT / source_target
        entries = "\n".join(
            f"- Entry {idx}. (2026-04-08)\n  - Context {idx}. [AGENT:gpt-5]"
            for idx in range(1, 10)
        )
        source_path.write_text(
            (REPO_ROOT / "knowledge/110.WHO.Vela-Identity-SoT.md")
            .read_text(encoding="utf-8")
            .replace(
                "- Vela is the default installed assistant profile. (2026-04-08)\n  - The system ships with Vela while still allowing replacement and customization. [AGENT:gpt-5]",
                entries,
            ),
            encoding="utf-8",
        )
        proposal_path = REPO_ROOT / proposal_target
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(
            "---\n"
            "sot-type: proposal\n"
            "created: 2026-04-09\n"
            "last-rewritten: 2026-04-09\n"
            'parent: "[[fractal-source-SoT]]"\n'
            "domain: governance\n"
            "status: proposed\n"
            f'target: "{source_target}"\n'
            'route: "standard"\n'
            'recommended-stage: "fractal"\n'
            'tags: ["growth","proposal"]\n'
            "---\n\n"
            "# Growth Proposal\n\n"
            "## This Proposal Records the Matrix Growth Assessment After the Main Task\n"
            "Fractalization should scaffold a subgroup.\n",
            encoding="utf-8",
        )
        result = apply_growth_proposal(proposal_target, actor="scribe")
        self.assertTrue(result["ok"])
        self.assertEqual(result["execution_kind"], "fractalized-source")
        updated_source = source_path.read_text(encoding="utf-8")
        self.assertIn("## 110.Identity-Subgroup", updated_source)

    def test_growth_apply_service_endpoint(self) -> None:
        proposal_target = "knowledge/ARTIFACTS/proposals/growth-apply-service-test.md"
        source_target = "knowledge/ARTIFACTS/proposals/service-source-SoT.md"
        (REPO_ROOT / source_target).write_text(
            (REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        proposal_path = REPO_ROOT / proposal_target
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(
            "---\n"
            "sot-type: proposal\n"
            "created: 2026-04-09\n"
            "last-rewritten: 2026-04-09\n"
            'parent: "[[service-source-SoT]]"\n'
            "domain: governance\n"
            "status: proposed\n"
            f'target: "{source_target}"\n'
            'route: "standard"\n'
            'recommended-stage: "reference-note"\n'
            'tags: ["growth","proposal"]\n'
            "---\n\n"
            "# Growth Proposal\n\n"
            "## This Proposal Records the Matrix Growth Assessment After the Main Task\n"
            "Service apply path should create a reference note.\n",
            encoding="utf-8",
        )
        result = VelaService().growth_apply({"proposal": proposal_target, "actor": "n8n"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["endpoint"], "growth-apply")
        self.assertEqual(result["status"], "accepted")
        self.assertTrue((REPO_ROOT / result["data"]["execution_target"]).exists())

    def test_inbox_triage_extracts_markdown_into_declared_target(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/inbox-triage-target.md"
        target_path = REPO_ROOT / target
        target_path.write_text((REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8"), encoding="utf-8")
        inbox_path = REPO_ROOT / "knowledge/INBOX/test-inbox-item.md"
        inbox_path.write_text(
            "# Inbox Item\n\n"
            f"Target: [[{Path(target).name}]]\n\n"
            "Capability update\n\n"
            "The inbox item captures a component-level change that belongs in WHAT.\n",
            encoding="utf-8",
        )
        result = triage_inbox(file_name="test-inbox-item.md", actor="vela")
        self.assertTrue(result["ok"])
        self.assertFalse(inbox_path.exists())
        updated = target_path.read_text(encoding="utf-8")
        self.assertIn("- Capability update. (", updated)
        self.assertIn("The inbox item captures a component-level change", updated)
        self.assertTrue(PATCH_LOG_PATH.exists())
        self.assertIn("STATUS: applied", PATCH_LOG_PATH.read_text(encoding="utf-8"))

    def test_inbox_triage_flags_missing_target_for_review(self) -> None:
        inbox_path = REPO_ROOT / "knowledge/INBOX/test-inbox-missing-target.md"
        inbox_path.write_text(
            "# Inbox Item\n\n"
            "Capability update\n\n"
            "The inbox item captures a component-level change that belongs in WHAT.\n",
            encoding="utf-8",
        )
        result = triage_inbox(file_name="test-inbox-missing-target.md", actor="vela")
        self.assertFalse(result["ok"])
        self.assertTrue(inbox_path.exists())
        self.assertEqual(result["results"][0]["reason"], "missing-target")

    def test_inbox_triage_service_endpoint(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/inbox-triage-target.md"
        target_path = REPO_ROOT / target
        target_path.write_text((REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8"), encoding="utf-8")
        inbox_path = REPO_ROOT / "knowledge/INBOX/test-inbox-item.md"
        inbox_path.write_text(
            "# Inbox Item\n\n"
            f"Target: [[{Path(target).name}]]\n\n"
            "Capability update\n\n"
            "The inbox item captures a component-level change that belongs in WHAT.\n",
            encoding="utf-8",
        )
        result = VelaService().inbox_triage({"file": "test-inbox-item.md", "actor": "n8n"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["endpoint"], "inbox-triage")

    def test_warden_patrol_writes_report(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/inbox-triage-target.md"
        target_path = REPO_ROOT / target
        target_path.write_text((REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8"), encoding="utf-8")
        inbox_path = REPO_ROOT / "knowledge/INBOX/test-inbox-item.md"
        inbox_path.write_text(
            "# Inbox Item\n\n"
            f"Target: [[{Path(target).name}]]\n\n"
            "Capability update\n\n"
            "The inbox item captures a component-level change that belongs in WHAT.\n",
            encoding="utf-8",
        )
        triage_inbox(file_name="test-inbox-item.md", actor="vela")
        result = run_warden_patrol(requested_by="human")
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["files_checked"], 1)
        report_text = (REPO_ROOT / result["report_target"]).read_text(encoding="utf-8")
        self.assertIn("## Checked Targets", report_text)
        self.assertIn("inbox-triage-target.md", report_text)

    def test_night_cycle_writes_dc_report(self) -> None:
        for _ in range(3):
            write_text(
                "knowledge/210.WHAT.Vela-Capabilities-SoT.md",
                (REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8").replace(
                    "Vela routes, plans, drafts, critiques, validates, documents, and proposes growth under governed workflows.",
                    "Vela routes, plans, drafts, critiques, validates, documents, proposes growth, and patrols canonical writes.",
                ),
                actor="warden",
                endpoint="test",
                reason="force blocked pattern for night report",
            )
        result = run_night_cycle(requested_by="human")
        self.assertTrue(result["ok"])
        report_text = (REPO_ROOT / result["report_target"]).read_text(encoding="utf-8")
        dreamer_text = (REPO_ROOT / result["dreamer_report_target"]).read_text(encoding="utf-8")
        self.assertTrue(result["dreamer_proposals"])
        proposal_text = (REPO_ROOT / result["dreamer_proposals"][0]["target"]).read_text(encoding="utf-8")
        self.assertIn("## Warden Patrol Summary", report_text)
        self.assertIn("## Grower Activity", report_text)
        self.assertIn("## Dreamer Activity", report_text)
        self.assertIn("## Dreamer Proposals", report_text)
        self.assertIn("## Blocked (Needs Dario)", report_text)
        self.assertIn("Dreamer-Pattern-Report-", report_text)
        self.assertIn("## Three Strike Patterns", dreamer_text)
        self.assertIn("## Proposed Responses", dreamer_text)
        self.assertIn("## Recent Blocked Items", dreamer_text)
        self.assertIn("Dreamer-Proposal.", report_text)
        self.assertIn("Dreamer-Proposal.", dreamer_text)
        self.assertIn("# Dreamer Proposal", proposal_text)

    def test_patrol_and_night_cycle_service_endpoints(self) -> None:
        patrol = VelaService().patrol_run({"actor": "n8n"})
        self.assertTrue(patrol["ok"])
        self.assertEqual(patrol["endpoint"], "patrol-run")
        night_cycle = VelaService().night_cycle_run({"actor": "n8n"})
        self.assertTrue(night_cycle["ok"])
        self.assertEqual(night_cycle["endpoint"], "night-cycle-run")

    def test_dreamer_queue_and_review(self) -> None:
        for _ in range(3):
            write_text(
                "knowledge/210.WHAT.Vela-Capabilities-SoT.md",
                (REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8").replace(
                    "Vela routes, plans, drafts, critiques, validates, documents, and proposes growth under governed workflows.",
                    "Vela routes, plans, drafts, critiques, validates, documents, proposes growth, and patrols canonical writes.",
                ),
                actor="warden",
                endpoint="test",
                reason="force blocked pattern for dreamer queue",
            )
        cycle = run_night_cycle(requested_by="human")
        self.assertTrue(cycle["dreamer_proposals"])
        queue = list_dreamer_queue()
        self.assertTrue(queue["items"])
        target = queue["items"][0]["target"]
        review = review_dreamer_proposal(target=target, decision="approved", actor="human", reason="accept dreamer follow up")
        self.assertTrue(review["ok"])
        updated = (REPO_ROOT / target).read_text(encoding="utf-8")
        self.assertIn("status: approved", updated)
        self.assertIn("## Review Outcome", updated)

    def test_dreamer_queue_service_and_review_endpoint(self) -> None:
        for _ in range(3):
            write_text(
                "knowledge/210.WHAT.Vela-Capabilities-SoT.md",
                (REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8").replace(
                    "Vela routes, plans, drafts, critiques, validates, documents, and proposes growth under governed workflows.",
                    "Vela routes, plans, drafts, critiques, validates, documents, proposes growth, and patrols canonical writes.",
                ),
                actor="warden",
                endpoint="test",
                reason="force blocked pattern for dreamer service queue",
            )
        VelaService().night_cycle_run({"actor": "n8n"})
        queue = VelaService().dreamer_queue()
        self.assertTrue(queue["ok"])
        target = queue["data"]["items"][0]["target"]
        review = VelaService().dreamer_review(
            {"target": target, "decision": "denied", "actor": "human", "reason": "not worth pursuing"}
        )
        self.assertTrue(review["ok"])
        self.assertEqual(review["endpoint"], "dreamer-review")

    def test_inbox_triage_moves_text_file_to_companion_and_links_it(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/inbox-triage-target.md"
        target_path = REPO_ROOT / target
        target_path.write_text((REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8"), encoding="utf-8")
        existing_companion = REPO_ROOT / "knowledge/ARTIFACTS/proposals/inbox-triage-target.txt"
        existing_companion.write_text("existing companion", encoding="utf-8")
        inbox_path = REPO_ROOT / "knowledge/INBOX/test-inbox-item.txt"
        inbox_path.write_text(
            "Target: [[inbox-triage-target.md]]\n\n"
            "Capability update\n\n"
            "The text intake should be preserved as a companion file while its contents are extracted.\n",
            encoding="utf-8",
        )
        result = triage_inbox(file_name="test-inbox-item.txt", actor="vela")
        self.assertTrue(result["ok"])
        self.assertFalse(inbox_path.exists())
        companion = REPO_ROOT / "knowledge/ARTIFACTS/proposals/inbox-triage-target-20260409.txt"
        self.assertTrue(companion.exists())
        updated = target_path.read_text(encoding="utf-8")
        self.assertIn("See: [[inbox-triage-target-20260409.txt]]", updated)

    def test_inbox_triage_flags_unsupported_binary_file(self) -> None:
        inbox_path = REPO_ROOT / "knowledge/INBOX/test-inbox-binary.png"
        inbox_path.write_bytes(b"png")
        result = triage_inbox(file_name="test-inbox-binary.png", actor="vela")
        self.assertFalse(result["ok"])
        self.assertEqual(result["results"][0]["reason"], "unsupported-non-markdown")
        self.assertTrue(inbox_path.exists())

    def test_inbox_triage_moves_csv_file_to_companion_and_routes_rows(self) -> None:
        target = "knowledge/ARTIFACTS/proposals/inbox-triage-target.md"
        target_path = REPO_ROOT / target
        target_path.write_text((REPO_ROOT / "knowledge/210.WHAT.Vela-Capabilities-SoT.md").read_text(encoding="utf-8"), encoding="utf-8")
        existing_companion = REPO_ROOT / "knowledge/ARTIFACTS/proposals/inbox-triage-target.csv"
        existing_companion.write_text("existing,data\n", encoding="utf-8")
        inbox_path = REPO_ROOT / "knowledge/INBOX/test-inbox-item.csv"
        inbox_path.write_text(
            "# target: [[inbox-triage-target.md]]\n"
            "value,context,dimension\n"
            "Component watch update,Tracks a component-level update,200\n"
            "Release rationale,Explains why the change matters,600\n",
            encoding="utf-8",
        )

        result = triage_inbox(file_name="test-inbox-item.csv", actor="vela")

        self.assertTrue(result["ok"])
        self.assertFalse(inbox_path.exists())
        companion = REPO_ROOT / "knowledge/ARTIFACTS/proposals/inbox-triage-target-20260409.csv"
        self.assertTrue(companion.exists())
        updated = target_path.read_text(encoding="utf-8")
        self.assertIn("Component watch update. (", updated)
        self.assertIn("Tracks a component-level update See: [[inbox-triage-target-20260409.csv]]", updated)
        self.assertIn("Release rationale. (", updated)
        self.assertIn("Explains why the change matters See: [[inbox-triage-target-20260409.csv]]", updated)

    def test_inbox_triage_flags_ambiguous_csv_row(self) -> None:
        inbox_path = REPO_ROOT / "knowledge/INBOX/test-inbox-ambiguous.csv"
        inbox_path.write_text(
            "# target: [[210.WHAT.Vela-Capabilities-SoT.md]]\n"
            "value,context\n"
            "Ambiguous note,Unsorted note needing review.\n",
            encoding="utf-8",
        )

        result = triage_inbox(file_name="test-inbox-ambiguous.csv", actor="vela")

        self.assertFalse(result["ok"])
        self.assertEqual(result["results"][0]["reason"], "unsorted-needs-review")
        self.assertTrue(inbox_path.exists())

    def test_dry_boot_prompt(self) -> None:
        health = VelaService().health()
        self.assertEqual(health["status"], "setup-required")
        self.assertIn("active_profile", health["data"])

    def test_rust_config_bridge(self) -> None:
        payload = validate_config_payload(load_config())
        self.assertTrue(payload["setup_required"])
        self.assertTrue(any(item["code"] == "CONFIG_REQUIRED" for item in payload["findings"]))

    def test_rust_reference_bridge(self) -> None:
        payload = inspect_reference_payload(
            "knowledge/ARTIFACTS/refs/Ref.example.Release-Intelligence.md",
            "---\n"
            "sot-type: reference\n"
            "created: 2026-04-08\n"
            "last-rewritten: 2026-04-08\n"
            "parent: \"[[220.WHAT.Repo-Watchlist-SoT#200.WHAT.Scope]]\"\n"
            "domain: repo-watch\n"
            "status: active\n"
            "tags: [\"repo-watch\",\"release\",\"reference\"]\n"
            "---\n\n"
            "# Release Intelligence openai/openai-python 1.2.3\n\n"
            "## This Reference Declares the Release Packet and the Review Chain\n"
            "The packet exists.\n\n"
            "## This Reference Links the Governing Inputs and Outputs\n"
            "- Packet: `knowledge/ARTIFACTS/refs/example.packet.json`\n\n"
            "## This Reference States the Release Judgment Clearly\n"
            "- Breaking change risk: `high`\n",
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["reference"]["domain"], "repo-watch")

    def test_rust_inventory_bridge(self) -> None:
        payload = matrix_inventory_payload()
        self.assertTrue(payload["ok"])
        self.assertTrue(any(item["is_cornerstone"] for item in payload["entries"]))
        self.assertTrue(any(item["inventory_role"] == "cornerstone" for item in payload["entries"]))
        self.assertTrue(any(item["inventory_role"] == "dimension-hub" for item in payload["entries"]))
        self.assertTrue(any(item["inventory_role"] == "agent-identity" for item in payload["entries"]))
        self.assertTrue(any(item["inventory_role"] == "branch-sot" for item in payload["entries"]))
        self.assertTrue(all(item["inventory_role"] == "governed-reference" for item in payload["references"]))
        self.assertTrue(all("path" in item for item in payload["references"]))

    def test_rust_operations_bridge(self) -> None:
        route_payload = route_inbox_payload("Alex joined the project team this week.")
        self.assertEqual(route_payload["dimension"], "100")

        growth_payload = validate_growth_stage_payload("spawn", "missing")
        self.assertTrue(any(item["code"] == "SPAWN_APPROVAL_REQUIRED" for item in growth_payload["findings"]))

        subject_payload = validate_subject_declaration_payload(
            "## 000.Index\n\n### Subject Declaration\n\n**Subject:** Before\n\n### Links\n",
            "## 000.Index\n\n### Subject Declaration\n\n**Subject:** After\n\n### Links\n",
            "missing",
        )
        self.assertTrue(any(item["code"] == "SUBJECT_DECLARATION_APPROVAL_REQUIRED" for item in subject_payload["findings"]))

        archive_payload = validate_archive_postconditions_payload(
            "## 100.WHO.Identity\n\n### Active\n\n(No active entries.)\n\n### Inactive\n\n- Sample archived value. (2026-04-08)\n  - Exists to verify archive movement. [AGENT:gpt-5]\n  - Archived: 2026-04-09\n  - Archived Reason: Replaced by newer fact\n\n## 700.Archive\n\n[202604090352] FROM: ## 100.WHO.Identity\n- Sample archived value. (2026-04-08)\n  - Exists to verify archive movement. [AGENT:gpt-5]\n  - Archived: 2026-04-09\n  - Archived Reason: Replaced by newer fact\n",
            "Sample archived value. (2026-04-08)",
            "Replaced by newer fact",
            "## 100.WHO.Identity",
        )
        self.assertTrue(archive_payload["ok"])

    def test_matrix_parent_rule_rejects_direct_root_attachment_for_agent_branch(self) -> None:
        target = REPO_ROOT / "knowledge/ARTIFACTS/proposals/direct-root-agent-branch-test.md"
        target.write_text(
            (
                (REPO_ROOT / "knowledge/110.WHO.Vela-Identity-SoT.md")
                .read_text(encoding="utf-8")
                .replace('parent: "[[100.WHO.Circle-SoT#100.WHO.Humans-and-Agents]]"', 'parent: "[[Cornerstone.Knosence-SoT#100.WHO.Circle]]"')
                .replace("**Parent:** [[100.WHO.Circle-SoT#100.WHO.Humans-and-Agents]]", "**Parent:** [[Cornerstone.Knosence-SoT#100.WHO.Circle]]")
                .replace("- Parent: [[100.WHO.Circle-SoT#100.WHO.Humans-and-Agents]]", "- Parent: [[Cornerstone.Knosence-SoT#100.WHO.Circle]]")
                .replace("- WHO hub: [[100.WHO.Circle-SoT]]\n", "")
            ),
            encoding="utf-8",
        )
        findings = validate_parent_consistency(target)
        self.assertTrue(any(item.code == "MATRIX_HUB_PARENT_REQUIRED" for item in findings))

    def test_matrix_parent_rule_rejects_direct_root_attachment_for_dimension_branch(self) -> None:
        target = REPO_ROOT / "knowledge/ARTIFACTS/proposals/direct-root-dimension-branch-test.md"
        target.write_text(
            (
                (REPO_ROOT / "knowledge/220.WHAT.Repo-Watchlist-SoT.md")
                .read_text(encoding="utf-8")
                .replace('parent: "[[200.WHAT.Domain-SoT#200.WHAT.Domains]]"', 'parent: "[[Cornerstone.Knosence-SoT#200.WHAT.Domain]]"')
                .replace("**Parent:** [[200.WHAT.Domain-SoT#200.WHAT.Domains]]", "**Parent:** [[Cornerstone.Knosence-SoT#200.WHAT.Domain]]")
                .replace("- Parent: [[200.WHAT.Domain-SoT#200.WHAT.Domains]]", "- Parent: [[Cornerstone.Knosence-SoT#200.WHAT.Domain]]")
                .replace("- Dimension hub: [[200.WHAT.Domain-SoT]]\n", "")
            ),
            encoding="utf-8",
        )
        findings = validate_parent_consistency(target)
        self.assertTrue(any(item.code == "MATRIX_HUB_PARENT_REQUIRED" for item in findings))

    def test_matrix_index_layer(self) -> None:
        result = write_matrix_index()
        self.assertTrue((REPO_ROOT / result["path"]).exists())
        contents = (REPO_ROOT / result["path"]).read_text(encoding="utf-8")
        self.assertIn("Cornerstone.Knosence-SoT", contents)
        self.assertIn("references", json.loads((REPO_ROOT / result["json_path"]).read_text(encoding="utf-8")))
        self.assertFalse(result["findings"])

    def test_canonical_graph_targets_are_resolved(self) -> None:
        findings = validate_canonical_graph_targets()
        self.assertFalse(findings, [item.as_dict() for item in findings])

    def test_matrix_index_registers_governed_release_reference(self) -> None:
        try:
            result = VelaService().repo_release(
                {
                    "repo": "openai/openai-python",
                    "version": "1.2.3",
                    "notes": "Breaking API migration required.",
                    "target": "knowledge/ARTIFACTS/refs/indexed-release-summary.md",
                }
            )
            self.assertTrue(result["ok"])
            index_result = write_matrix_index()
            matrix_index = (REPO_ROOT / index_result["path"]).read_text(encoding="utf-8")
            self.assertIn("Governed References Registered in the Matrix", matrix_index)
            self.assertIn(result["data"]["intelligence_target"], matrix_index)
            self.assertGreaterEqual(index_result["references"], 1)
        finally:
            self._cleanup_generated_artifacts()
            write_matrix_index()

    def test_scenario_runner(self) -> None:
        results = run_scenario("routing")
        self.assertTrue(all("name" in item for item in results))


if __name__ == "__main__":
    unittest.main()
