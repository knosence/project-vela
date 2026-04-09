from __future__ import annotations

import argparse
import json
import sys

from .config import ensure_bootstrap_files, load_config, missing_required_fields, save_config, setup_complete
from .governance import apply_growth_proposal, create_cross_reference
from .inbox import triage_inbox
from .matrix import write_matrix_index
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
        actor="scribe",
        endpoint="cross-reference",
        reason=args.reason,
        approval_id=args.approval_id,
    )
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
