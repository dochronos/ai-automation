import os
import time
import requests
from src.utils.logger import get_logger

from dotenv import load_dotenv, find_dotenv
env_path = find_dotenv(usecwd=True)
load_dotenv(dotenv_path=env_path, override=True)

logger = get_logger("notifier")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

logger.info(
    "Telegram config snapshot",
    extra={"ticket_id": None, "stage": "startup", "extra": {
        "has_token": bool(BOT_TOKEN),
        "has_chat_id": bool(CHAT_ID)
    }}
)

def send_telegram_message(text: str, max_retries: int = 3, backoff_sec: float = 1.5) -> tuple[bool, int]:
    """
    Envía un mensaje a Telegram con reintentos exponenciales.
    Devuelve: (ok, retries_used)  -> retries_used = intentos adicionales al primero (0..max_retries-1)
    """
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram no configurado (BOT_TOKEN/CHAT_ID vacíos)")
        return False, 0

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                logger.info("Notificación Telegram enviada")
                return True, (attempt - 1)
            else:
                last_error = f"HTTP {r.status_code}: {r.text}"
                logger.warning(f"Telegram {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Error enviando Telegram: {e}")

        if attempt < max_retries:
            time.sleep(backoff_sec * attempt)

    logger.error(f"Fallaron los reintentos de Telegram. Último error: {last_error}")
    return False, (max_retries - 1)


def format_p1_alert(ticket: dict) -> str:
    """
    Formato más claro para Week 6 (ID + Título). Link opcional si existiera.
    """
    tid = ticket.get("id", "N/A")
    title = ticket.get("title") or ticket.get("subject") or "P1 Ticket"
    maybe_url = ticket.get("url")
    lines = [
        "🚨 P1 Ticket Alert",
        f"ID: {tid}",
        f"Title: {title}",
    ]
    if maybe_url:
        lines.append(str(maybe_url))
    return "\n".join(lines)
