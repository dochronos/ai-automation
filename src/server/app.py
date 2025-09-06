from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from datetime import datetime
from src.jobs.process_new_rows import main as run_job

app = FastAPI(title="AI Automation Workflow API")

@app.get("/health")
def health():
    return {"ok": True, "ts": datetime.utcnow().isoformat()}

@app.post("/run")
def run():
    try:
        run_job()
        return {"ok": True, "ts": datetime.utcnow().isoformat()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
