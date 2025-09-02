# src/services/notifier.py
from __future__ import annotations
import os
import requests
from typing import Optional, Dict

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def _tg_api(method: str) -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"

def send_telegram_message(text: str, parse_mode: Optional[str] = None) -> bool:
    """
    Send a plain message to the configured chat. Returns True on success.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        # Soft fail (useful for demos without credentials)
        print("[notifier] Telegram disabled (missing token/chat_id).")
        return False

    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        r = requests.post(_tg_api("sendMessage"), data=payload, timeout=15)
        r.raise_for_status()
        ok = r.json().get("ok", False)
        if not ok:
            print("[notifier] Telegram API responded not OK:", r.text)
        return ok
    except Exception as e:
        print("[notifier] Telegram error:", e)
        return False


# --------- High-level helpers ---------

def format_ticket_alert(t: Dict) -> str:
    """
    Nicely formatted P1 alert.
    Expected keys: id, subject, topic, sentiment, created_at, owner_suggested, description
    """
    id_ = t.get("id", "—")
    subject = t.get("subject", "No subject")
    topic = t.get("topic", "other")
    sent = str(t.get("sentiment", "")).title() if t.get("sentiment") else "N/A"
    created = t.get("created_at", "N/A")
    owner = t.get("owner_suggested", "Unassigned")

    # Keep message short; description can be long.
    desc = str(t.get("description", "") or "")
    if len(desc) > 220:
        desc = desc[:220].rstrip() + "…"

    return (
        "🚨 *Critical ticket (P1)*\n"
        f"*ID*: `{id_}`\n"
        f"*Subject*: {subject}\n"
        f"*Topic*: {topic} | *Sentiment*: {sent}\n"
        f"*Owner (suggested)*: {owner}\n"
        f"*Created*: {created}\n"
        f"*Notes*: {desc}"
    )

def notify_p1_ticket(t: Dict) -> bool:
    text = format_ticket_alert(t)
    return send_telegram_message(text, parse_mode="Markdown")
