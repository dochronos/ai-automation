# src/dashboard/Home.py
from __future__ import annotations
import os
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Load .env (para variables como LOCAL_OUTPUT_CSV)
load_dotenv(override=True)

# Intentamos importar el cliente LLM (Ollama/OpenAI)
try:
    from src.services.llm_client import LLMClient
except Exception:
    LLMClient = None  # fallback si no está disponible


st.set_page_config(page_title="AI Automation – Classified Tickets", layout="wide")

# ---------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------
OUT_CSV = os.getenv("LOCAL_OUTPUT_CSV", "data/outputs/classified.csv")
IN_CSV = os.getenv("LOCAL_INPUT_CSV", "data/sample_tickets.csv")

EXPECTED_COLS: List[str] = [
    "id", "created_at", "channel", "subject", "description",
    "topic", "priority", "sentiment", "owner_suggested"
]

def load_data() -> pd.DataFrame:
    path_out = Path(OUT_CSV)
    path_in = Path(IN_CSV)

    if path_out.exists():
        df = pd.read_csv(path_out)
    elif path_in.exists():
        df = pd.read_csv(path_in)
    else:
        st.warning("No data found. Please run the processing job first.")
        return pd.DataFrame()

    for col in EXPECTED_COLS:
        if col not in df.columns:
            df[col] = None

    # Normaliza tipos
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    if "priority" in df.columns:
        df["priority"] = df["priority"].fillna("P3").astype(str)
    if "topic" in df.columns:
        df["topic"] = df["topic"].fillna("other").astype(str)
    if "sentiment" in df.columns:
        df["sentiment"] = df["sentiment"].fillna("").astype(str)

    return df

df = load_data()

st.title("📊 AI Automation – Classified Tickets")

if df.empty:
    st.stop()

# ---------------------------------------------------------------------
# Filtros (Week 3)
# ---------------------------------------------------------------------
with st.container():
    st.subheader("🔎 Filters")

    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])

    # Priority filter (multi)
    all_priorities = ["P1", "P2", "P3"]
    selected_priorities = col_f1.multiselect(
        "Priority",
        options=all_priorities,
        default=all_priorities,
        help="Filter by ticket priority"
    )

    # Topic filter (single select con 'All')
    topics_sorted = sorted(t for t in df["topic"].unique() if isinstance(t, str))
    topics_with_all = ["All topics"] + topics_sorted
    selected_topic = col_f2.selectbox(
        "Topic",
        options=topics_with_all,
        index=0,
        help="Focus on a single topic or view all"
    )

    # (Opcional) Date range filter si hay fechas válidas
    if df["created_at"].notna().any():
        min_date = pd.to_datetime(df["created_at"].min())
        max_date = pd.to_datetime(df["created_at"].max())
        date_range = col_f3.date_input(
            "Date range",
            value=(min_date.date(), max_date.date()),
            min_value=min_date.date(),
            max_value=max_date.date(),
            help="Limit analysis to a date window"
        )
    else:
        date_range = None

# Aplica filtros
fdf = df.copy()

# Priority
if selected_priorities:
    fdf = fdf[fdf["priority"].isin(selected_priorities)]
else:
    # Si deseleccionan todo, no mostramos nada
    fdf = fdf.iloc[0:0]

# Topic
if selected_topic != "All topics":
    fdf = fdf[fdf["topic"] == selected_topic]

# Date range
if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
    start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    # Incluir todo el end_day (hasta las 23:59:59)
    end_d = end_d + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    if fdf["created_at"].notna().any():
        fdf = fdf[(fdf["created_at"] >= start_d) & (fdf["created_at"] <= end_d)]

# ---------------------------------------------------------------------
# AI Weekly (Filtered) Summary
# ---------------------------------------------------------------------
with st.container():
    st.subheader("🧠 AI Summary")

    summarize_filtered = st.checkbox(
        "Summarize the current filtered view",
        value=True,
        help="If unchecked, summarizes the full dataset"
    )

    target_df = fdf if summarize_filtered else df

    if target_df.empty:
        st.info("No data in the selected view to summarize.")
    elif LLMClient is None:
        st.info("LLM client not available. Ensure src/services/llm_client.py exists.")
    else:
        try:
            llm = LLMClient()
            summary = llm.summarize_week(target_df.to_dict(orient="records"))

            # Best-effort: asegurar cierre de oración
            if summary and summary[-1] not in ".!?":
                last_dot = summary.rfind(".")
                if last_dot != -1:
                    summary = summary[: last_dot + 1]

            st.write(summary)
        except Exception as e:
            st.warning(f"Could not generate summary: {e}")

# ---------------------------------------------------------------------
# KPIs (responden a filtros)
# ---------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

tickets = len(fdf)
critical = int((fdf["priority"] == "P1").sum()) if "priority" in fdf.columns else 0
topics_count = fdf["topic"].nunique(dropna=True) if "topic" in fdf.columns else 0
pct_negative = (
    (fdf["sentiment"].str.lower() == "negative").mean() * 100
    if "sentiment" in fdf.columns and fdf["sentiment"].notna().any() and len(fdf) > 0
    else 0.0
)

col1.metric("Tickets", f"{tickets}")
col2.metric("Critical (P1)", f"{critical}")
col3.metric("Topics", f"{topics_count}")
col4.metric("% Negative", f"{pct_negative:.0f}%")

st.divider()

# ---------------------------------------------------------------------
# Charts (responden a filtros)
# ---------------------------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Top Topics")
    if "topic" in fdf.columns and fdf["topic"].notna().any() and len(fdf) > 0:
        top_topics = (
            fdf["topic"]
            .fillna("other")
            .value_counts()
            .head(10)
            .rename_axis("topic")
            .reset_index(name="count")
            .set_index("topic")
        )
        st.bar_chart(top_topics)
    else:
        st.info("No topic data available for the selected view.")

with right:
    st.subheader("Priority Distribution")
    if "priority" in fdf.columns and fdf["priority"].notna().any() and len(fdf) > 0:
        prio_counts = (
            fdf["priority"]
            .fillna("P3")
            .value_counts()
            .reindex(["P1", "P2", "P3"], fill_value=0)
            .rename_axis("priority")
            .reset_index(name="count")
            .set_index("priority")
        )
        st.bar_chart(prio_counts)
    else:
        st.info("No priority data available for the selected view.")

st.divider()

# ---------------------------------------------------------------------
# Drill-down por topic (si está seleccionado un topic específico)
# ---------------------------------------------------------------------
if selected_topic != "All topics":
    st.subheader(f"🔬 Drill-down — Topic: {selected_topic}")
    subset = fdf.sort_values(by="created_at", ascending=False) if "created_at" in fdf.columns else fdf.copy()
    show_cols = [c for c in [
        "id", "created_at", "channel", "subject", "priority", "sentiment", "owner_suggested", "description"
    ] if c in subset.columns]
    st.dataframe(subset[show_cols], use_container_width=True, hide_index=True)
else:
    # Raw data completa de la vista filtrada
    with st.expander("View data"):
        subset = fdf.sort_values(by="created_at", ascending=False) if "created_at" in fdf.columns else fdf.copy()
        show_cols = [c for c in [
            "id", "created_at", "channel", "subject", "topic", "priority", "sentiment", "owner_suggested", "description"
        ] if c in subset.columns]
        st.dataframe(subset[show_cols], use_container_width=True, hide_index=True)
