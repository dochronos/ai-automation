from __future__ import annotations
import os
import pandas as pd
from pathlib import Path
from src.services.rules import simple_topic, simple_priority, simple_sentiment, owner_for_topic
from src.services.llm_client import LLMClient
from src.utils.io import read_csv, write_csv


IN_CSV = os.getenv("LOCAL_INPUT_CSV", "data/sample_tickets.csv")
OUT_CSV = os.getenv("LOCAL_OUTPUT_CSV", "data/outputs/classified.csv")

def _get_text(row: pd.Series) -> str:
    # Support EN/ES headers gracefully
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


def main() -> None:
    df = read_csv(IN_CSV)
    enriched = df.apply(classify_row, axis=1, result_type="expand")
    write_csv(enriched, OUT_CSV)

    llm = LLMClient()
    summary = llm.summarize_week(enriched.to_dict(orient="records"))
    print(summary)


if __name__ == "__main__":
    main()
