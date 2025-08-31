# src/services/llm_client.py
from __future__ import annotations
import os
import json
import requests
from typing import List, Dict
from dotenv import load_dotenv

# Cargar .env siempre que se importe este módulo
load_dotenv(override=True)

SYSTEM_PROMPT = (
    "You are an operations analyst. Summarize weekly support tickets with clear, "
    "concise insights for non-technical stakeholders. Include 3–5 findings and "
    "actionable next steps. Keep it under 130 words. Finish your answer completely "
    "with a full sentence (do not cut off)."
)

def _build_summary_prompt(rows: List[Dict]) -> str:
    total = len(rows)
    p1 = sum(1 for r in rows if r.get("priority") == "P1")
    topics = {}
    for r in rows:
        topics[r.get("topic","other")] = topics.get(r.get("topic","other"), 0) + 1
    top_sorted = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:5]
    top_str = ", ".join(f"{t}({c})" for t, c in top_sorted)
    return (
        f"Weekly tickets: {total}. Critical (P1): {p1}. Top topics: {top_str}.\n"
        "Write a short executive summary and 2–3 next actions."
    )

class LLMClient:
    def __init__(self):
        # Leer SIEMPRE al instanciar (por si cambiaste .env)
        self.provider = (os.getenv("LLM_PROVIDER", "openai") or "openai").strip().lower()
        self.model = (os.getenv("LLM_MODEL_NAME", "gpt-4o-mini") or "gpt-4o-mini").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.ollama_host = (os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434") or "http://127.0.0.1:11434").strip()
        print(f"[llm_client] provider={self.provider} model={self.model} host={self.ollama_host}")

    # ---------- OpenAI (no lo usarás ahora, pero queda operativo) ----------
    def _openai_chat(self, prompt: str) -> str:
        if not self.openai_api_key:
            return "AI summary unavailable (missing OPENAI_API_KEY)."
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.openai_api_key}", "Content-Type": "application/json"}
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 220,
        }
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(data), timeout=25)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return "AI summary unavailable (OpenAI error)."

    # ---------- Ollama (ajustado para Windows/CPU) ----------
    def _ollama_generate(self, prompt: str) -> str:
        url = f"{self.ollama_host.rstrip('/')}/api/generate"
        data = {
            "model": self.model,  # ej: llama3.2:3b
            "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
            "stream": False,           # 1 sola respuesta JSON
            "keep_alive": "30m",       # mantiene el modelo cargado en RAM
            "options": {
                "temperature": 0.3,
                "num_predict": 280     # resumen corto → acelera la respuesta
            }
        }
        try:
            # (connect_timeout=10s, read_timeout=600s) → evita cortes por warm-up
            r = requests.post(url, json=data, timeout=(10, 600))
            r.raise_for_status()
            obj = r.json()
            return (obj.get("response") or "").strip() or "AI summary (Ollama) unavailable."
        except Exception as e:
            return f"AI summary unavailable (Ollama error: {e})"

    # ---------- Público ----------
    def summarize_week(self, rows: List[Dict]) -> str:
        prompt = _build_summary_prompt(rows)
        if self.provider == "ollama":
            return self._ollama_generate(prompt)
        return self._openai_chat(prompt)
