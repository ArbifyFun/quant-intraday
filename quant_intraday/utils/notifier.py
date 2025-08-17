"""Notification helpers for external messaging services."""

import os
import json

import httpx

WEBHOOK = os.getenv("QI_WEBHOOK_URL", None)


def notify(event: str, payload: dict | None = None) -> bool:
    """Send a generic webhook notification."""

    if not WEBHOOK:
        return False
    try:
        body = {"event": event, "payload": payload or {}}
        httpx.post(WEBHOOK, json=body, timeout=5)
        return True
    except Exception:
        return False


def send_tg(text: str) -> None:
    """Send a Telegram message if credentials are configured."""

    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{tok}/sendMessage",
            data={"chat_id": chat, "text": text},
            timeout=5.0,
        )
    except Exception:
        pass


def send_feishu(text: str) -> None:
    """Send a Feishu notification if webhook URL is set."""

    url = os.getenv("FEISHU_WEBHOOK_URL")
    if not url:
        return
    try:
        httpx.post(
            url,
            json={"msg_type": "text", "content": {"text": text}},
            timeout=5.0,
        )
    except Exception:
        pass
