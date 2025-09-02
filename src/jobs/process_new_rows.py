# src/jobs/process_new_rows.py
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict

import pandas as pd
from dotenv import load_dotenv

# Cargar .env antes de leer cualquier var
load_dotenv(override=True)

from src.services.rules import (
    simple_topic,
    simple_priority,
    simple_sentiment,
    owner_for_topic,
)
from src.services.notifier import notify_p1_ticket
from src.services.llm_client import LLMClient

# Permite override por .env si querés apuntar a otros paths
INPUT_CSV = os.getenv("LOCAL_INPUT_CSV", "data/sample_tickets.csv")
OUTPUT_CSV = os.getenv("LOCAL_OUTPUT_CSV", "data/outputs/classified.csv")

# Asegurar carpetas
Path(OUTPUT_CSV).parent.mkdir(parents=True, exist_ok=True)


def _load_existing(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.exists():
        try:
            df = pd.read_csv(p)
            # normalizar tipos básicos
            if "created_at" in df.columns:
                df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
            return df
        except Exception:
            pass
    return pd.DataFrame()


def _load_input(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")
    df = pd.read_csv(p)
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    return df


def _text_of(r: Dict) -> str:
    """Concat minimal text context for rules."""
    subj = str(r.get("subject", "") or "")
    desc = str(r.get("description", "") or "")
    return (subj + " " + desc).strip()


def _classify_rows(rows: List[Dict]) -> List[Dict]:
    """Apply simple rules to compute topic, priority, sentiment, and owner."""
    out: List[Dict] = []
    for r in rows:
        text = _text_of(r)

        # topic/sentiment esperan TEXTO
        topic = simple_topic(text)
        sentiment = simple_sentiment(text)

        # priority: intentar (row, topic); si tu firma es distinta, caer a (text)
        try:
            priority = simple_priority(r, topic)  # firma 1: (row, topic)
        except TypeError:
            priority = simple_priority(text)      # firma 2: (text)

        owner = owner_for_topic(topic)

        rr = dict(r)
        rr.update(
            {
                "topic": topic,
                "priority": priority,
                "sentiment": sentiment,
                "owner_suggested": owner,
            }
        )
        out.append(rr)
    return out


def main() -> None:
    # 1) Cargar insumo y salidas previas
    df_in = _load_input(INPUT_CSV)
    df_prev = _load_existing(OUTPUT_CSV)

    # 2) Definir columnas esperadas
    expected_cols = [
        "id",
        "created_at",
        "channel",
        "subject",
        "description",
        "topic",
        "priority",
        "sentiment",
        "owner_suggested",
    ]
    for c in expected_cols:
        if c not in df_in.columns:
            df_in[c] = None
    for c in expected_cols:
        if c not in df_prev.columns:
            df_prev[c] = None

    # 3) Detectar nuevas filas por 'id'
    prev_ids = (
        set(df_prev["id"].astype(str))
        if not df_prev.empty and "id" in df_prev.columns
        else set()
    )
    df_in["id"] = df_in["id"].astype(str)
    df_new = df_in[~df_in["id"].isin(prev_ids)].copy()

    # 4) Clasificar nuevas (reglas)
    new_rows = df_new.to_dict(orient="records")
    classified_new = _classify_rows(new_rows)

    # 5) Marcar 'is_new' y armar DF final de nuevas
    for r in classified_new:
        r["is_new"] = True
    df_new_cls = (
        pd.DataFrame(classified_new)
        if classified_new
        else pd.DataFrame(columns=expected_cols + ["is_new"])
    )

    # 6) Conciliar: unir previas + nuevas clasificadas (solo si hay nuevas)
    cols_all = expected_cols + ["is_new"]

    if df_prev.empty and df_new_cls.empty:
        merged = pd.DataFrame(columns=cols_all)
    elif df_prev.empty and not df_new_cls.empty:
        merged = df_new_cls[cols_all].copy()
    elif not df_prev.empty and df_new_cls.empty:
        # nada nuevo: mantener previas tal cual
        if "is_new" not in df_prev.columns:
            df_prev["is_new"] = False
        merged = df_prev[cols_all].copy()
    else:
        # hay previas y nuevas
        if "is_new" not in df_prev.columns:
            df_prev["is_new"] = False
        merged = pd.concat(
            [df_prev[cols_all], df_new_cls[cols_all]],
            ignore_index=True,
        )

    # 7) Guardar outputs
    merged.sort_values(
        by="created_at", ascending=False, inplace=True, na_position="last"
    )
    merged.to_csv(OUTPUT_CSV, index=False)

    # 8) Notificación: SOLO para nuevos P1
    p1_sent = 0
    for row in classified_new:
        try:
            if row.get("priority") == "P1":  # solo P1
                ok = notify_p1_ticket(row)
                if ok:
                    p1_sent += 1
        except Exception as e:
            print("[notify] error sending telegram:", e)
    print(f"[notify] Telegram alerts sent: {p1_sent}")

    # 9) (Opcional) Resumen IA en consola (sobre todo el dataset o solo nuevas)
    try:
        llm = LLMClient()
        # Elegí qué resumir: todo (merged) suele ser más útil semana a semana
        rows_for_summary = merged.to_dict(orient="records")
        print("[summary]")
        summary = llm.summarize_week(rows_for_summary)
        # Acabado limpio
        if summary and summary[-1] not in ".!?":
            last_dot = summary.rfind(".")
            if last_dot != -1:
                summary = summary[: last_dot + 1]
        print(summary)
    except Exception as e:
        print("[summary] AI summary unavailable:", e)

    # 10) Métricas rápidas
    total_now = len(merged)
    new_count = len(df_new_cls)
    p1_now = (
        int((merged["priority"] == "P1").sum()) if "priority" in merged.columns else 0
    )
    print(f"[metrics] total={total_now} (+{new_count} new), P1_total={p1_now}")


if __name__ == "__main__":
    main()
