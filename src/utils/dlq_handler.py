import json
import os
import uuid
import time
from pathlib import Path
from datetime import datetime
from .logger import get_logger

logger = get_logger("dlq")

DLQ_DIR = os.getenv("DLQ_DIR", "dlq")

def write_to_dlq(ticket: dict, error_reason: str, stage: str) -> str:
    os.makedirs(DLQ_DIR, exist_ok=True)
    ticket_id = str(ticket.get("id") or ticket.get("ticket_id") or uuid.uuid4())
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    fname = f"{ts}_{ticket_id}_{stage}.json"
    path = os.path.join(DLQ_DIR, fname)

    payload = {
        "ticket": ticket,
        "error_reason": error_reason,
        "stage": stage,
        "ts": ts,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.error(
        f"Ticket derivado a DLQ: {fname}",
        extra={"ticket_id": ticket_id, "stage": stage}
    )
    return path

def prune_dlq_older_than(days: int = 7):
    cutoff = time.time() - days * 24 * 3600
    p = Path(DLQ_DIR)
    if not p.exists():
        return 0
    removed = 0
    for f in p.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except Exception:
            pass
    return removed