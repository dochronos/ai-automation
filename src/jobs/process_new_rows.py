from __future__ import annotations
from dotenv import load_dotenv
load_dotenv(override=True)
import os
import pandas as pd
from pathlib import Path
from src.services.rules import simple_topic, simple_priority, simple_sentiment, owner_for_topic
from src.services.llm_client import LLMClient
from src.services.notifier import send_telegram_message
from src.utils.io import read_csv, write_csv

IN_CSV = os.getenv("LOCAL_INPUT_CSV", "data/sample_tickets.csv")
OUT_CSV = os.getenv("LOCAL_OUTPUT_CSV", "data/outputs/classified.csv")

def _get_text(row: pd.Series) -> str:
    subject = row.get('subject') or row.get('asunto') or ''
    description = row.get('description') or row.get('descripcion') or ''
    return f"{subject} {description}".strip()

def classify_row(row: pd.Series) -> dict:
    text = _get_text(row)
    topic = simple_topic(text)
    priority = simple_priority(text)
    sentiment = simple_sentiment(text)
    owner = owner_for_topic(topic)
    return {
        **row.to_dict(),
        "topic": topic,
        "priority": priority,
        "sentiment": sentiment,
        "owner_suggested": owner,
    }

def _read_previous_ids(path: str | Path) -> set:
    p = Path(path)
    if not p.exists():
        return set()
    try:
        prev = pd.read_csv(p)
        return set(prev.get("id", pd.Series(dtype="int")).astype(str).tolist())
    except Exception:
        return set()

def _alert_p1_new_rows(new_df: pd.DataFrame, previous_ids: set) -> int:
    count = 0
    for _, r in new_df.iterrows():
        row_id = str(r.get("id"))
        if r.get("priority") == "P1" and row_id not in previous_ids:
            ok = send_telegram_message(
                text=(
                    f"🚨 *Critical ticket (P1)*\n"
                    f"ID: {row_id}\n"
                    f"Topic: {r.get('topic')}\n"
                    f"Subject: {r.get('subject', '')}\n"
                    f"Owner suggestion: {r.get('owner_suggested')}"
                ),
                parse_mode="Markdown"
            )
            count += 1 if ok else 0
    return count

def main() -> None:
    df = read_csv(IN_CSV)
    enriched = df.apply(classify_row, axis=1, result_type="expand")

    previous_ids = _read_previous_ids(OUT_CSV)
    write_csv(enriched, OUT_CSV)

    alerted = _alert_p1_new_rows(enriched, previous_ids)
    print(f"[notify] Telegram alerts sent: {alerted}")

    llm = LLMClient()
    summary = llm.summarize_week(enriched.to_dict(orient="records"))
    print("[summary]\n" + summary)

if __name__ == "__main__":
    main()
