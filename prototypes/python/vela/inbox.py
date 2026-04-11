from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dreamer_actions import matching_workflow_actions
from .governance import append_event, build_pointer_entry, route_inbox_entry, write_text
from .models import EventRecord
from .paths import INBOX_DIR, PATCH_LOG_PATH, REPO_ROOT
from .rust_bridge import plan_csv_inbox_payload
from .rust_bridge import plan_companion_path_payload
from .rust_bridge import plan_inbox_entry_payload


def triage_inbox(file_name: str | None = None, actor: str = "vela") -> dict[str, Any]:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    candidates = [INBOX_DIR / file_name] if file_name else sorted(path for path in INBOX_DIR.iterdir() if path.is_file() and path.name != "000.Project-Vela-Starter.md")
    results: list[dict[str, Any]] = []
    for path in candidates:
        if not path.exists():
            results.append({"ok": False, "file": str(path.relative_to(REPO_ROOT)), "status": "missing"})
            continue
        if path.suffix.lower() == ".md":
            results.append(_triage_markdown_file(path, actor=actor))
        elif path.suffix.lower() == ".txt":
            results.append(_triage_text_companion_file(path, actor=actor))
        elif path.suffix.lower() == ".csv":
            results.append(_triage_csv_companion_file(path, actor=actor))
        elif path.suffix.lower() == ".pdf":
            results.append(_triage_pdf_companion_file(path, actor=actor))
        elif path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
            results.append(_triage_image_companion_file(path, actor=actor))
        else:
            results.append(_flag_unsupported_inbox_file(path, actor=actor))
    return {
        "ok": all(item.get("ok", False) for item in results) if results else True,
        "processed": len(results),
        "results": results,
    }


def _triage_markdown_file(path: Path, actor: str) -> dict[str, Any]:
    relative_path = str(path.relative_to(REPO_ROOT))
    text = path.read_text(encoding="utf-8")
    plan_payload = plan_inbox_entry_payload(text, path.name)
    plan = plan_payload.get("plan") or {}
    target = str(plan.get("target", ""))
    dimension = str(plan.get("dimension", ""))
    findings = plan_payload.get("findings", [])
    workflow_actions = matching_workflow_actions(text)

    if findings and any(item.get("code") == "INBOX_TARGET_MISSING" for item in findings):
        _append_patch_log("flagged", relative_path, f"Missing target SoT for dimension {dimension or 'unknown'}.", actor)
        append_event(
            EventRecord(
                source="vela",
                endpoint="inbox-triage",
                actor=actor,
                target=relative_path,
                status="flagged",
                reason="target SoT not declared for inbox item",
                artifacts=[relative_path],
                validation_summary={"dimension": dimension, "reason": "missing-target"},
            )
        )
        return {"ok": False, "file": relative_path, "status": "flagged", "reason": "missing-target", "dimension": dimension}

    if not plan_payload.get("ok") or not dimension:
        _append_patch_log("flagged", relative_path, "Unsorted — needs review.", actor)
        append_event(
            EventRecord(
                source="vela",
                endpoint="inbox-triage",
                actor=actor,
                target=relative_path,
                status="flagged",
                reason="dimension router could not classify inbox item",
                artifacts=[relative_path],
                validation_summary={"reason": "unsorted-needs-review"},
            )
        )
        return {
            "ok": False,
            "file": relative_path,
            "status": "flagged",
            "reason": "unsorted-needs-review",
            "workflow_actions": [item["pattern_reason"] for item in workflow_actions],
        }

    if not target:
        _append_patch_log("flagged", relative_path, f"Missing target SoT for dimension {dimension}.", actor)
        append_event(
            EventRecord(
                source="vela",
                endpoint="inbox-triage",
                actor=actor,
                target=relative_path,
                status="flagged",
                reason="target SoT not declared for inbox item",
                artifacts=[relative_path],
                validation_summary={"dimension": dimension, "reason": "missing-target"},
            )
        )
        return {"ok": False, "file": relative_path, "status": "flagged", "reason": "missing-target", "dimension": dimension}

    target_path = REPO_ROOT / target
    if not target_path.exists():
        _append_patch_log("blocked", relative_path, f"Declared target does not exist: {target}.", actor)
        append_event(
            EventRecord(
                source="vela",
                endpoint="inbox-triage",
                actor=actor,
                target=relative_path,
                status="blocked",
                reason="declared target SoT does not exist",
                artifacts=[relative_path],
                validation_summary={"dimension": dimension, "target": target},
            )
        )
        return {"ok": False, "file": relative_path, "status": "blocked", "reason": "target-missing", "dimension": dimension, "target": target}

    entry = {"value": str(plan["value"]), "context": str(plan["context"])}
    updated = _append_entry_to_dimension(target_path.read_text(encoding="utf-8"), dimension, entry)
    write_result = write_text(target, updated, actor=actor, endpoint="inbox-triage", reason=f"triage inbox item {relative_path}")
    if not write_result["ok"]:
        _append_patch_log("blocked", relative_path, f"Target write blocked for {target}.", actor)
        return {
            "ok": False,
            "file": relative_path,
            "status": "blocked",
            "dimension": dimension,
            "target": target,
            "findings": write_result["findings"],
        }

    pointer = build_pointer_entry(entry["value"], Path(target).stem, _dimension_anchor(updated, dimension), _today())
    if path.exists():
        path.unlink()
    _append_patch_log("applied", relative_path, f"Extracted into {target} {pointer}", actor)
    append_event(
        EventRecord(
            source="vela",
            endpoint="inbox-triage",
            actor=actor,
            target=target,
            status="committed",
            reason=f"inbox item {relative_path} extracted into {target}",
            artifacts=[target],
            validation_summary={"dimension": dimension, "source_file": relative_path, "pointer": pointer},
        )
    )
    return {
        "ok": True,
        "file": relative_path,
        "status": "applied",
        "dimension": dimension,
        "target": target,
        "pointer": pointer,
        "workflow_actions": [item["pattern_reason"] for item in workflow_actions],
    }


def _triage_text_companion_file(path: Path, actor: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return _triage_extracted_companion_file(path, actor, text, extraction_kind="text")


def _triage_pdf_companion_file(path: Path, actor: str) -> dict[str, Any]:
    extracted = _extract_pdf_text(path)
    if not extracted["ok"]:
        return _flag_for_review(path, actor, "pdf-extraction-failed", extracted["detail"])
    return _triage_extracted_companion_file(path, actor, extracted["text"], extraction_kind="pdf")


def _triage_image_companion_file(path: Path, actor: str) -> dict[str, Any]:
    extracted = _extract_image_text(path)
    if not extracted["ok"]:
        return _flag_for_review(path, actor, "image-ocr-failed", extracted["detail"])
    return _triage_extracted_companion_file(path, actor, extracted["text"], extraction_kind="image")


def _triage_extracted_companion_file(path: Path, actor: str, text: str, *, extraction_kind: str) -> dict[str, Any]:
    relative_path = str(path.relative_to(REPO_ROOT))
    plan_payload = plan_inbox_entry_payload(text, path.name)
    plan = plan_payload.get("plan") or {}
    target = str(plan.get("target", ""))
    dimension = str(plan.get("dimension", ""))
    findings = plan_payload.get("findings", [])
    workflow_actions = matching_workflow_actions(text)

    if findings and any(item.get("code") == "INBOX_TARGET_MISSING" for item in findings):
        return _flag_for_review(path, actor, "missing-target", f"Missing target SoT for dimension {dimension}.", dimension=dimension)
    if not plan_payload.get("ok") or not dimension:
        return _flag_for_review(path, actor, "unsorted-needs-review", "dimension router could not classify inbox item")
    if not target:
        return _flag_for_review(path, actor, "missing-target", f"Missing target SoT for dimension {dimension}.", dimension=dimension)

    target_path = REPO_ROOT / target
    if not target_path.exists():
        return _block_missing_target(path, actor, target, dimension)

    companion_path = _move_to_companion_path(path, target_path)
    entry = {"value": str(plan["value"]), "context": str(plan["context"])}
    entry["context"] = f"{entry['context']} See: [[{companion_path.name}]]".strip()
    updated = _append_entry_to_dimension(target_path.read_text(encoding="utf-8"), dimension, entry)
    write_result = write_text(target, updated, actor=actor, endpoint="inbox-triage", reason=f"triage inbox item {relative_path}")
    if not write_result["ok"]:
        _append_patch_log("blocked", relative_path, f"Target write blocked for {target}.", actor)
        return {
            "ok": False,
            "file": relative_path,
            "status": "blocked",
            "dimension": dimension,
            "target": target,
            "findings": write_result["findings"],
        }

    pointer = build_pointer_entry(entry["value"], Path(target).stem, _dimension_anchor(updated, dimension), _today())
    _append_patch_log("applied", relative_path, f"Extracted into {target} with companion {companion_path.relative_to(REPO_ROOT)} {pointer}", actor)
    append_event(
        EventRecord(
            source="vela",
            endpoint="inbox-triage",
            actor=actor,
            target=target,
            status="committed",
            reason=f"inbox {extraction_kind} item {relative_path} extracted into {target}",
            artifacts=[target, str(companion_path.relative_to(REPO_ROOT))],
            validation_summary={"dimension": dimension, "source_file": relative_path, "pointer": pointer},
        )
    )
    return {
        "ok": True,
        "file": relative_path,
        "status": "applied",
        "dimension": dimension,
        "target": target,
        "companion": str(companion_path.relative_to(REPO_ROOT)),
        "pointer": pointer,
        "workflow_actions": [item["pattern_reason"] for item in workflow_actions],
    }


def _triage_csv_companion_file(path: Path, actor: str) -> dict[str, Any]:
    relative_path = str(path.relative_to(REPO_ROOT))
    text = path.read_text(encoding="utf-8")
    plan_payload = plan_csv_inbox_payload(text, path.name)
    plan = plan_payload.get("plan") or {}
    target = str(plan.get("target", ""))
    findings = plan_payload.get("findings", [])
    if findings and any(item.get("code") == "INBOX_TARGET_MISSING" for item in findings):
        return _flag_for_review(path, actor, "missing-target", "Missing target SoT for csv inbox item.")
    if findings and any(item.get("code") == "INBOX_CSV_EMPTY" for item in findings):
        return _flag_for_review(path, actor, "empty-csv", "CSV inbox item had no extractable rows.")
    if not plan_payload.get("ok") or not target:
        return _flag_for_review(path, actor, "unsorted-needs-review", "CSV inbox row could not be classified.")
    target_path = REPO_ROOT / target
    if not target_path.exists():
        return _block_missing_target(path, actor, target, "")

    workflow_actions = matching_workflow_actions(text)
    extracted_entries = [
        {
            "dimension": str(item["dimension"]),
            "value": str(item["value"]),
            "context": str(item["context"]),
        }
        for item in plan.get("entries", [])
    ]

    companion_path = _move_to_companion_path(path, target_path)
    updated = target_path.read_text(encoding="utf-8")
    for extracted in extracted_entries:
        entry_payload = {
            "value": extracted["value"],
            "context": f"{extracted['context']} See: [[{companion_path.name}]]".strip(),
        }
        updated = _append_entry_to_dimension(updated, extracted["dimension"], entry_payload)

    write_result = write_text(target, updated, actor=actor, endpoint="inbox-triage", reason=f"triage inbox item {relative_path}")
    if not write_result["ok"]:
        _append_patch_log("blocked", relative_path, f"Target write blocked for {target}.", actor)
        return {
            "ok": False,
            "file": relative_path,
            "status": "blocked",
            "target": target,
            "findings": write_result["findings"],
        }

    pointers = [
        build_pointer_entry(extracted["value"], Path(target).stem, _dimension_anchor(updated, extracted["dimension"]), _today())
        for extracted in extracted_entries
    ]
    _append_patch_log(
        "applied",
        relative_path,
        f"Extracted {len(extracted_entries)} csv rows into {target} with companion {companion_path.relative_to(REPO_ROOT)}.",
        actor,
    )
    append_event(
        EventRecord(
            source="vela",
            endpoint="inbox-triage",
            actor=actor,
            target=target,
            status="committed",
            reason=f"inbox csv item {relative_path} extracted into {target}",
            artifacts=[target, str(companion_path.relative_to(REPO_ROOT))],
            validation_summary={"rows": len(extracted_entries), "source_file": relative_path, "pointers": pointers},
        )
    )
    return {
        "ok": True,
        "file": relative_path,
        "status": "applied",
        "target": target,
        "companion": str(companion_path.relative_to(REPO_ROOT)),
        "rows": len(extracted_entries),
        "pointers": pointers,
        "workflow_actions": [item["pattern_reason"] for item in workflow_actions],
    }


def _flag_unsupported_inbox_file(path: Path, actor: str) -> dict[str, Any]:
    return _flag_for_review(path, actor, "unsupported-non-markdown", f"Unsupported inbox file type `{path.suffix}` requires richer extraction.")


def _extract_pdf_text(path: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["pdftotext", str(path), "-"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {"ok": False, "detail": f"PDF extraction tool unavailable: {exc}"}
    text = result.stdout.strip()
    if result.returncode != 0 or not text:
        detail = result.stderr.strip() or "PDF extraction produced no text."
        return {"ok": False, "detail": detail}
    return {"ok": True, "text": text}


def _extract_image_text(path: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["tesseract", str(path), "stdout"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {"ok": False, "detail": f"Image OCR tool unavailable: {exc}"}
    text = result.stdout.strip()
    if result.returncode != 0 or not text:
        detail = result.stderr.strip() or "Image OCR produced no text."
        return {"ok": False, "detail": detail}
    return {"ok": True, "text": text}


def _flag_for_review(path: Path, actor: str, reason: str, detail: str, dimension: str | None = None) -> dict[str, Any]:
    relative_path = str(path.relative_to(REPO_ROOT))
    _append_patch_log("flagged", relative_path, detail, actor)
    append_event(
        EventRecord(
            source="vela",
            endpoint="inbox-triage",
            actor=actor,
            target=relative_path,
            status="flagged",
            reason=detail,
            artifacts=[relative_path],
            validation_summary={"reason": reason, "dimension": dimension or ""},
        )
    )
    payload = {"ok": False, "file": relative_path, "status": "flagged", "reason": reason}
    if dimension:
        payload["dimension"] = dimension
    return payload


def _block_missing_target(path: Path, actor: str, target: str, dimension: str) -> dict[str, Any]:
    relative_path = str(path.relative_to(REPO_ROOT))
    _append_patch_log("blocked", relative_path, f"Declared target does not exist: {target}.", actor)
    append_event(
        EventRecord(
            source="vela",
            endpoint="inbox-triage",
            actor=actor,
            target=relative_path,
            status="blocked",
            reason="declared target SoT does not exist",
            artifacts=[relative_path],
            validation_summary={"dimension": dimension, "target": target},
        )
    )
    return {"ok": False, "file": relative_path, "status": "blocked", "reason": "target-missing", "dimension": dimension, "target": target}


def _move_to_companion_path(source: Path, target_path: Path) -> Path:
    source_rel = str(source.relative_to(REPO_ROOT))
    target_rel = str(target_path.relative_to(REPO_ROOT))
    plan = plan_companion_path_payload(source_rel, target_rel, _today().replace("-", ""))
    destination_rel = str(plan["plan"]["destination"])
    destination = REPO_ROOT / destination_rel
    source.rename(destination)
    return destination


def _append_entry_to_dimension(content: str, dimension: str, entry: dict[str, str]) -> str:
    heading = _dimension_heading(content, dimension)
    if not heading:
        raise ValueError(f"Dimension heading not found for {dimension}")
    section_start = content.find(heading)
    next_section = content.find("\n## ", section_start + 1)
    section = content[section_start: next_section if next_section != -1 else len(content)]
    active_marker = "### Active"
    inactive_marker = "### Inactive"
    active_start = section.find(active_marker)
    inactive_start = section.find(inactive_marker)
    if active_start == -1 or inactive_start == -1:
        raise ValueError(f"Dimension structure invalid for {heading}")
    active_section = section[active_start:inactive_start]
    new_entry = f"- {entry['value']}\n  - {entry['context']}"
    if "(No active entries.)" in active_section:
        active_section = active_section.replace("(No active entries.)", new_entry)
    else:
        active_section = active_section.rstrip() + f"\n\n{new_entry}\n"
    new_section = heading + "\n\n" + active_section.lstrip("\n") + "\n\n" + section[inactive_start:].lstrip("\n")
    return content[:section_start] + new_section + content[next_section if next_section != -1 else len(content):]


def _dimension_heading(content: str, dimension: str) -> str:
    match = re.search(rf"^##\s{dimension}\.[^\n]+$", content, re.MULTILINE)
    return match.group(0) if match else ""


def _dimension_anchor(content: str, dimension: str) -> str:
    return _dimension_heading(content, dimension).replace("## ", "", 1)


def _append_patch_log(status: str, target: str, detail: str, actor: str) -> None:
    PATCH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d@%H%M")
    with PATCH_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(
            f"[{stamp}] ACTION: inbox triage\n"
            f"  TARGET: {target}\n"
            f"  DETAIL: {detail}\n"
            f"  STATUS: {status}\n"
            f"  ACTOR: {actor}\n"
        )


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()
