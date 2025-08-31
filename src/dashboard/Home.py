# src/dashboard/Home.py
from __future__ import annotations
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Load .env so we can read LOCAL_OUTPUT_CSV if set
load_dotenv(override=True)

# Optional: use our LLM client for the weekly summary
try:
    from src.services.llm_client import LLMClient
except Exception:
    LLMClient = None  # graceful fallback if not available

st.set_page_config(page_title="AI Automation – Classified Tickets", layout="wide")

# ---------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------
OUT_CSV = os.getenv("LOCAL_OUTPUT_CSV", "data/outputs/classified.csv")
IN_CSV = os.getenv("LOCAL_INPUT_CSV", "data/sample_tickets.csv")

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

    # Normalize expected columns
    for col in [
        "id", "created_at", "channel", "subject", "description",
        "topic", "priority", "sentiment", "owner_suggested"
    ]:
        if col not in df.columns:
            df[col] = None
    return df

df = load_data()

st.title("📊 AI Automation – Classified Tickets")

if df.empty:
    st.stop()

# ---------------------------------------------------------------------
# AI Weekly Summary (Ollama / OpenAI via LLMClient)
# ---------------------------------------------------------------------
with st.container():
    st.subheader("🧠 AI Weekly Summary")
    if LLMClient is None:
        st.info("LLM client not available. Ensure src/services/llm_client.py exists.")
    else:
        try:
            llm = LLMClient()
            summary = llm.summarize_week(df.to_dict(orient="records"))

            # --- Ensure it ends cleanly (best-effort) ---
            if summary and summary[-1] not in ".!?":
                last_dot = summary.rfind(".")
                if last_dot != -1:
                    summary = summary[: last_dot + 1]

            st.write(summary)
        except Exception as e:
            st.warning(f"Could not generate summary: {e}")

# ---------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

tickets = len(df)
critical = int((df["priority"] == "P1").sum()) if "priority" in df.columns else 0
topics_count = df["topic"].nunique(dropna=True) if "topic" in df.columns else 0
pct_negative = (
    (df["sentiment"].str.lower() == "negative").mean() * 100
    if "sentiment" in df.columns and df["sentiment"].notna().any()
    else 0.0
)

col1.metric("Tickets", f"{tickets}")
col2.metric("Critical (P1)", f"{critical}")
col3.metric("Topics", f"{topics_count}")
col4.metric("% Negative", f"{pct_negative:.0f}%")

st.divider()

# ---------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Top Topics")
    if "topic" in df.columns and df["topic"].notna().any():
        top_topics = (
            df["topic"]
            .fillna("other")
            .value_counts()
            .head(10)
            .rename_axis("topic")
            .reset_index(name="count")
            .set_index("topic")
        )
        st.bar_chart(top_topics)
    else:
        st.info("No topic data available.")

with right:
    st.subheader("Priority Distribution")
    if "priority" in df.columns and df["priority"].notna().any():
        prio_counts = (
            df["priority"]
            .fillna("P3")
            .value_counts()
            .reindex(["P1", "P2", "P3"], fill_value=0)
            .rename_axis("priority")
            .reset_index(name="count")
            .set_index("priority")
        )
        st.bar_chart(prio_counts)
    else:
        st.info("No priority data available.")

st.divider()

# ---------------------------------------------------------------------
# Raw data
# ---------------------------------------------------------------------
with st.expander("View data"):
    st.dataframe(
        df[
            [
                "id", "created_at", "channel", "subject",
                "topic", "priority", "sentiment", "owner_suggested", "description"
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )
