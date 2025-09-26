import os
import time
import requests
from src.utils.logger import get_logger
from dotenv import load_dotenv
load_dotenv(override=True)

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

def send_telegram_message(text: str, max_retries: int = 3, backoff_sec: float = 1.5) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram no configurado (BOT_TOKEN/CHAT_ID vacíos)")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                logger.info("Notificación Telegram enviada")
                return True
            else:
                logger.warning(f"Telegram HTTP {r.status_code}: {r.text}")
        except Exception as e:
            logger.warning(f"Error enviando Telegram: {e}")

        if attempt < max_retries:
            time.sleep(backoff_sec * attempt)

    logger.error("Fallaron los reintentos de Telegram")
    return False