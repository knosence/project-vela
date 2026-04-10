from __future__ import annotations

import argparse
import json
import sys

from .config import ensure_bootstrap_files, load_config, missing_required_fields, save_config, setup_complete
from .dreamer_actions import filtered_dreamer_actions, load_dreamer_actions, register_dreamer_action, update_dreamer_action_status
from .governance import apply_growth_proposal, create_cross_reference
from .inbox import triage_inbox
from .matrix import write_matrix_index
from .operations_runtime import (
    apply_dreamer_follow_up,
    list_dreamer_follow_ups,
    list_dreamer_queue,
    review_dreamer_proposal,
    run_night_cycle,
    run_warden_patrol,
)
from .profiles import activate_profile, list_profiles
from .server import VelaService, serve
from .verification import run_scenario, write_verification_report


def cmd_init(_: argparse.Namespace) -> int:
    ensure_bootstrap_files()
    print("initialized")
    return 0


def cmd_setup(_: argparse.Namespace) -> int:
    ensure_bootstrap_files()
    cfg = load_config()
    missing = missing_required_fields(cfg)
    if missing:
        cfg["project"]["setup_complete"] = False
        save_config(cfg)
        print(json.dumps({"setup_mode": True, "missing_required_fields": missing}, indent=2))
        return 1
    cfg["project"]["setup_complete"] = True
    save_config(cfg)
    print(json.dumps({"setup_mode": False, "active_profile": cfg["assistant"]["active_profile"]}, indent=2))
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    service = VelaService()
    print(json.dumps(service.validate({"scope": "repo", "checks": ["narrative", "policy"], "mode": "report"}), indent=2))
    return 0


def cmd_dry_boot(_: argparse.Namespace) -> int:
    service = VelaService()
    print(json.dumps(service.health(), indent=2))
    return 0 if setup_complete(load_config()) else 1


def cmd_verify(args: argparse.Namespace) -> int:
    results = run_scenario(args.scenario)
    report = write_verification_report(results, args.scenario)
    passed = all(item["passed"] for item in results)
    print(json.dumps({"scenario": args.scenario, "passed": passed, "report_path": str(report)}, indent=2))
    return 0 if passed else 1


def cmd_index(_: argparse.Namespace) -> int:
    print(json.dumps(write_matrix_index(), indent=2))
    return 0


def cmd_profiles_list(_: argparse.Namespace) -> int:
    print(json.dumps(list_profiles(), indent=2))
    return 0


def cmd_profiles_use(args: argparse.Namespace) -> int:
    cfg = activate_profile(args.name)
    print(json.dumps({"active_profile": cfg["assistant"]["active_profile"]}, indent=2))
    return 0


def cmd_growth_apply(args: argparse.Namespace) -> int:
    result = apply_growth_proposal(args.proposal, actor="scribe", approval_id=args.approval_id)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def cmd_inbox_triage(args: argparse.Namespace) -> int:
    result = triage_inbox(file_name=args.file, actor="vela")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def cmd_cross_reference(args: argparse.Namespace) -> int:
    result = create_cross_reference(
        claimant_target=args.claimant_target,
        claimant_dimension_heading=args.claimant_dimension_heading,
        description=args.description,
        primary_target=args.primary_target,
        primary_dimension_heading=args.primary_dimension_heading,
        actor="vela",
        endpoint="cross-reference",
        reason=args.reason,
        approval_id=args.approval_id,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def cmd_patrol_run(_: argparse.Namespace) -> int:
    result = run_warden_patrol(requested_by="human")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def cmd_night_cycle_run(_: argparse.Namespace) -> int:
    result = run_night_cycle(requested_by="human")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def cmd_dreamer_queue(_: argparse.Namespace) -> int:
    print(json.dumps(list_dreamer_queue(), indent=2))
    return 0


def cmd_dreamer_actions(_: argparse.Namespace) -> int:
    print(json.dumps(load_dreamer_actions(), indent=2))
    return 0


def cmd_dreamer_actions_filtered(args: argparse.Namespace) -> int:
    print(json.dumps(filtered_dreamer_actions(kind=args.kind, status=args.status), indent=2))
    return 0


def cmd_dreamer_register_action(args: argparse.Namespace) -> int:
    result = register_dreamer_action(
        kind=args.kind,
        follow_up_target=args.follow_up_target,
        execution_target=args.execution_target,
        pattern_reason=args.pattern_reason,
        actor="human",
        execution_reason=args.execution_reason,
        status=args.status,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def cmd_dreamer_set_action_status(args: argparse.Namespace) -> int:
    result = update_dreamer_action_status(
        follow_up_target=args.follow_up_target,
        status=args.status,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def cmd_dreamer_review(args: argparse.Namespace) -> int:
    result = review_dreamer_proposal(target=args.target, decision=args.decision, actor="human", reason=args.reason)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def cmd_dreamer_follow_ups(_: argparse.Namespace) -> int:
    print(json.dumps(list_dreamer_follow_ups(), indent=2))
    return 0


def cmd_dreamer_apply_follow_up(args: argparse.Namespace) -> int:
    result = apply_dreamer_follow_up(target=args.target, actor="human", reason=args.reason)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def cmd_serve(args: argparse.Namespace) -> int:
    serve(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vela")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init")
    init_parser.set_defaults(func=cmd_init)

    setup_parser = sub.add_parser("setup")
    setup_parser.set_defaults(func=cmd_setup)

    validate_parser = sub.add_parser("validate")
    validate_parser.set_defaults(func=cmd_validate)

    boot_parser = sub.add_parser("dry-boot")
    boot_parser.set_defaults(func=cmd_dry_boot)

    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--scenario", default="full")
    verify_parser.set_defaults(func=cmd_verify)

    index_parser = sub.add_parser("index")
    index_parser.set_defaults(func=cmd_index)

    profiles_parser = sub.add_parser("profiles")
    profiles_sub = profiles_parser.add_subparsers(dest="profiles_command", required=True)

    profiles_list_parser = profiles_sub.add_parser("list")
    profiles_list_parser.set_defaults(func=cmd_profiles_list)

    profiles_use_parser = profiles_sub.add_parser("use")
    profiles_use_parser.add_argument("name")
    profiles_use_parser.set_defaults(func=cmd_profiles_use)

    growth_parser = sub.add_parser("growth")
    growth_sub = growth_parser.add_subparsers(dest="growth_command", required=True)

    growth_apply_parser = growth_sub.add_parser("apply")
    growth_apply_parser.add_argument("proposal")
    growth_apply_parser.add_argument("--approval-id")
    growth_apply_parser.set_defaults(func=cmd_growth_apply)

    inbox_parser = sub.add_parser("inbox")
    inbox_sub = inbox_parser.add_subparsers(dest="inbox_command", required=True)

    inbox_triage_parser = inbox_sub.add_parser("triage")
    inbox_triage_parser.add_argument("--file")
    inbox_triage_parser.set_defaults(func=cmd_inbox_triage)

    cross_reference_parser = sub.add_parser("cross-reference")
    cross_reference_parser.add_argument("claimant_target")
    cross_reference_parser.add_argument("claimant_dimension_heading")
    cross_reference_parser.add_argument("description")
    cross_reference_parser.add_argument("primary_target")
    cross_reference_parser.add_argument("primary_dimension_heading")
    cross_reference_parser.add_argument("--reason", default="create governed pointer entry")
    cross_reference_parser.add_argument("--approval-id")
    cross_reference_parser.set_defaults(func=cmd_cross_reference)

    patrol_parser = sub.add_parser("patrol")
    patrol_sub = patrol_parser.add_subparsers(dest="patrol_command", required=True)
    patrol_run_parser = patrol_sub.add_parser("run")
    patrol_run_parser.set_defaults(func=cmd_patrol_run)

    night_cycle_parser = sub.add_parser("night-cycle")
    night_cycle_sub = night_cycle_parser.add_subparsers(dest="night_cycle_command", required=True)
    night_cycle_run_parser = night_cycle_sub.add_parser("run")
    night_cycle_run_parser.set_defaults(func=cmd_night_cycle_run)

    dreamer_parser = sub.add_parser("dreamer")
    dreamer_sub = dreamer_parser.add_subparsers(dest="dreamer_command", required=True)
    dreamer_queue_parser = dreamer_sub.add_parser("queue")
    dreamer_queue_parser.set_defaults(func=cmd_dreamer_queue)
    dreamer_actions_parser = dreamer_sub.add_parser("actions")
    dreamer_actions_parser.set_defaults(func=cmd_dreamer_actions)
    dreamer_actions_filter_parser = dreamer_sub.add_parser("actions-filter")
    dreamer_actions_filter_parser.add_argument("--kind")
    dreamer_actions_filter_parser.add_argument("--status")
    dreamer_actions_filter_parser.set_defaults(func=cmd_dreamer_actions_filtered)
    dreamer_register_action_parser = dreamer_sub.add_parser("register-action")
    dreamer_register_action_parser.add_argument("kind")
    dreamer_register_action_parser.add_argument("follow_up_target")
    dreamer_register_action_parser.add_argument("execution_target")
    dreamer_register_action_parser.add_argument("pattern_reason")
    dreamer_register_action_parser.add_argument("--execution-reason", default="")
    dreamer_register_action_parser.add_argument("--status", default="active")
    dreamer_register_action_parser.set_defaults(func=cmd_dreamer_register_action)
    dreamer_set_action_status_parser = dreamer_sub.add_parser("set-action-status")
    dreamer_set_action_status_parser.add_argument("follow_up_target")
    dreamer_set_action_status_parser.add_argument("status")
    dreamer_set_action_status_parser.set_defaults(func=cmd_dreamer_set_action_status)
    dreamer_review_parser = dreamer_sub.add_parser("review")
    dreamer_review_parser.add_argument("target")
    dreamer_review_parser.add_argument("decision")
    dreamer_review_parser.add_argument("--reason", default="")
    dreamer_review_parser.set_defaults(func=cmd_dreamer_review)
    dreamer_follow_ups_parser = dreamer_sub.add_parser("follow-ups")
    dreamer_follow_ups_parser.set_defaults(func=cmd_dreamer_follow_ups)
    dreamer_apply_follow_up_parser = dreamer_sub.add_parser("apply-follow-up")
    dreamer_apply_follow_up_parser.add_argument("target")
    dreamer_apply_follow_up_parser.add_argument("--reason", default="")
    dreamer_apply_follow_up_parser.set_defaults(func=cmd_dreamer_apply_follow_up)

    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8787)
    serve_parser.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
