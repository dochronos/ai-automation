from __future__ import annotations
import os


MODEL = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")


class LLMClient:
    def __init__(self):
        self.key = os.getenv("OPENAI_API_KEY")


def summarize_week(self, rows: list[dict]) -> str:
    # Week 1 stub: return a simple text without calling an API
    total = len(rows)
    p1 = sum(1 for r in rows if r.get("priority") == "P1")
    topics = {}
    for r in rows:
        topics[r.get("topic","other")] = topics.get(r.get("topic","other"), 0) + 1
    top = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:3]
    return (
        f"Auto summary: {total} tickets, {p1} critical. Top topics: "
    + ", ".join([f"{t} ({c})" for t, c in top])
    + ". Next actions: review login flow and tighten security alerts."
    )