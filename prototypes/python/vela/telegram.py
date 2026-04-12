from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import load_config
from .models import ValidationFinding
from .traceability import annotate_findings


_urlopen = urlopen


def telegram_status() -> dict[str, Any]:
    cfg = load_config()
    integrations = cfg.get("integrations", {})
    telegram_cfg = cfg.get("telegram", {})
    enabled = bool(integrations.get("telegram"))
    findings = _telegram_config_findings(cfg)
    return {
        "enabled": enabled,
        "configured": enabled and not findings,
        "default_chat_id": telegram_cfg.get("default_chat_id"),
        "send_morning_report": bool(telegram_cfg.get("send_morning_report", True)),
        "send_blocked_summary": bool(telegram_cfg.get("send_blocked_summary", True)),
        "findings": [item.as_dict() for item in findings],
    }


def send_telegram_message(
    text: str,
    *,
    actor: str,
    reason: str,
    chat_id: str | None = None,
) -> dict[str, Any]:
    cfg = load_config()
    findings = _telegram_config_findings(cfg)
    if findings:
        return {"ok": False, "findings": [item.as_dict() for item in findings]}

    telegram_cfg = cfg.get("telegram", {})
    token = str(telegram_cfg.get("bot_token", "")).strip()
    resolved_chat_id = str(chat_id or telegram_cfg.get("default_chat_id", "")).strip()
    if not resolved_chat_id:
        finding = ValidationFinding(
            "TELEGRAM_CHAT_ID_REQUIRED",
            "Telegram send requested without a chat id and no default chat id is configured.",
        )
        return {"ok": False, "findings": [annotate_findings([finding])[0].as_dict()]}

    payload = urlencode(
        {
            "chat_id": resolved_chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with _urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        finding = ValidationFinding(
            "TELEGRAM_SEND_FAILED",
            f"Telegram send failed with HTTP {exc.code}.",
        )
        return {"ok": False, "findings": [annotate_findings([finding])[0].as_dict()]}
    except URLError as exc:
        finding = ValidationFinding(
            "TELEGRAM_SEND_FAILED",
            f"Telegram send failed: {exc.reason}.",
        )
        return {"ok": False, "findings": [annotate_findings([finding])[0].as_dict()]}

    try:
        response_data = json.loads(raw)
    except json.JSONDecodeError:
        finding = ValidationFinding(
            "TELEGRAM_SEND_FAILED",
            "Telegram send returned non-JSON output.",
        )
        return {"ok": False, "findings": [annotate_findings([finding])[0].as_dict()]}

    if not response_data.get("ok"):
        detail = response_data.get("description") or "Telegram API rejected the message."
        finding = ValidationFinding("TELEGRAM_SEND_FAILED", str(detail))
        return {"ok": False, "findings": [annotate_findings([finding])[0].as_dict()], "response": response_data}

    return {
        "ok": True,
        "chat_id": resolved_chat_id,
        "actor": actor,
        "reason": reason,
        "response": response_data,
    }


def build_blocked_summary_text(*, report_target: str, blocked_items: list[dict[str, Any]]) -> str:
    lines = [
        "Vela blocked summary",
        "",
        f"Report: {report_target}",
        f"Blocked items: {len(blocked_items)}",
        "",
    ]
    for item in blocked_items[:10]:
        target = str(item.get("target", ""))
        reason = str(item.get("reason", ""))
        lines.append(f"- {target} :: {reason}")
    return "\n".join(lines).strip()


def _telegram_config_findings(cfg: dict[str, Any]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    integrations = cfg.get("integrations", {})
    telegram_cfg = cfg.get("telegram", {})
    enabled = bool(integrations.get("telegram"))
    if not enabled:
        findings.append(ValidationFinding("TELEGRAM_DISABLED", "Telegram integration is disabled in config."))
        return annotate_findings(findings)
    token = str(telegram_cfg.get("bot_token", "")).strip()
    default_chat_id = str(telegram_cfg.get("default_chat_id", "")).strip()
    if not token or token == "<required-if-enabled>":
        findings.append(ValidationFinding("TELEGRAM_BOT_TOKEN_REQUIRED", "Telegram is enabled but bot_token is not configured."))
    if not default_chat_id or default_chat_id == "<required-if-enabled>":
        findings.append(ValidationFinding("TELEGRAM_CHAT_ID_REQUIRED", "Telegram is enabled but default_chat_id is not configured."))
    return annotate_findings(findings)
