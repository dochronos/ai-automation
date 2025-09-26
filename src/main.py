from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List

from src.utils.logger import get_logger, set_request_id
from src.processor import process_ticket
from src.metrics import METRICS
from src.utils.dlq_handler import prune_dlq_older_than

logger = get_logger("api")

app = FastAPI(title="AI Automation Workflow API", version="0.2.0")

pruned = prune_dlq_older_than(days=7)
logger.info(f"DLQ pruned on startup: {pruned} files")

# --------- Middleware para request_id en cada request ----------
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id")
    set_request_id(rid)  # genera uno si viene None
    response = await call_next(request)
    response.headers["x-request-id"] = set_request_id(rid)  # devuelve el que quedó
    return response

# --------------------- Modelos ---------------------
class Ticket(BaseModel):
    id: str
    title: str
    description: str
    priority: str | None = None
    owner: str | None = None

class BatchIn(BaseModel):
    tickets: List[Ticket]

# --------------------- Endpoints ---------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/process")
def process(batch: BatchIn):
    results = []
    for t in batch.tickets:
        res = process_ticket(t.model_dump())
        results.append(res)
    return {"processed": len(results), "results": results}

@app.get("/metrics")
def metrics():
    return {
        "tickets_processed": METRICS["processed"],
        "tickets_failed": METRICS["failed"],
        "dlq_written": METRICS["dlq"],
        "notify_success": METRICS["notify_success"],
        "notify_failed": METRICS["notify_failed"],
        "success_rate": (
            0.0 if METRICS["processed"] == 0
            else round((METRICS["processed"] - METRICS["failed"]) / METRICS["processed"], 4)
        ),
    }

# ----------------- Global exception hook -----------------
@app.exception_handler(Exception)
async def unhandled_exc(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

# Ejecutar local:
# uvicorn src.main:app --reload --port 8001