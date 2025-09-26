from src.utils.logger import get_logger
from src.utils.dlq_handler import write_to_dlq
from src.metrics import METRICS
from src.notifier import send_telegram_message

logger = get_logger("processor")

# Stubs: pluggea tu clasificador real / LLM si ya lo tenés
def classify(ticket: dict) -> dict:
    # TODO: reemplazar por tu pipeline real (tema, prioridad, sentimiento, owner sugerido)
    enriched = ticket.copy()
    enriched.setdefault("priority", "P2")
    enriched.setdefault("owner", "auto-assigned")
    enriched["sentiment"] = "neutral"
    enriched["topic"] = "general"
    return enriched

def should_notify(ticket: dict) -> bool:
    return str(ticket.get("priority", "")).upper() == "P1"

def process_ticket(ticket: dict) -> dict:
    METRICS["processed"] += 1
    ticket_id = ticket.get("id")

    logger.info("Procesando ticket", extra={"ticket_id": ticket_id, "stage": "start"})

    # 1) Clasificación
    try:
        enriched = classify(ticket)
        logger.info("Clasificación OK", extra={"ticket_id": ticket_id, "stage": "classify"})
    except Exception as e:
        METRICS["failed"] += 1
        METRICS["dlq"] += 1
        path = write_to_dlq(ticket, f"classify_error: {e}", stage="classify")
        return {"ticket_id": ticket_id, "status": "DLQ", "dlq_path": path}

    # 2) Notificación si P1
    if should_notify(enriched):
        ok = False
        try:
            ok = send_telegram_message(f"[P1] {enriched.get('title')} — #{enriched.get('id')}")
        except Exception as e:
            logger.warning(f"Notifier throw: {e}", extra={"ticket_id": ticket_id, "stage": "notify"})

        if not ok:
            METRICS["notify_failed"] += 1
            METRICS["failed"] += 1
            METRICS["dlq"] += 1
            path = write_to_dlq(enriched, "notify_failed", stage="notify")
            return {"ticket_id": ticket_id, "status": "DLQ", "dlq_path": path}
        else:
            METRICS["notify_success"] += 1
            logger.info("Notificación P1 OK", extra={"ticket_id": ticket_id, "stage": "notify"})

    logger.info("Procesamiento OK", extra={"ticket_id": ticket_id, "stage": "end"})
    return {"ticket_id": ticket_id, "status": "OK"}
