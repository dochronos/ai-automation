from __future__ import annotations

# --- Bootstrap opcional para que 'from src...' funcione al correr desde la raíz ---
import sys
from pathlib import Path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))
# -------------------------------------------------------------------------------

import os
import time
from typing import List, Optional
import json
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Cargar variables de entorno (.env)
load_dotenv(override=True)

# Intento de importar cliente LLM (opcional)
try:
    from src.services.llm_client import LLMClient  # opcional
except Exception:
    LLMClient = None

# Config
API_URL = os.getenv("API_URL", "http://localhost:8001")
OUT_CSV = os.getenv("LOCAL_OUTPUT_CSV", "data/outputs/classified.csv")
IN_CSV = os.getenv("LOCAL_INPUT_CSV", "data/sample_tickets.csv")
DLQ_DIR = Path(os.getenv("DLQ_DIR", "dlq"))

# Retención visual del DLQ en días (solo afecta a la UI)
def _parse_int(value: Optional[str], default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default

DLQ_RETENTION_DAYS_UI = _parse_int(os.getenv("DLQ_RETENTION_DAYS", "7"), 7)

EXPECTED_COLS: List[str] = [
    "id", "created_at", "channel", "subject", "description",
    "topic", "priority", "sentiment", "owner_suggested"
]

st.set_page_config(page_title="AI Automation – Dashboard", layout="wide")
st.title("AI Automation – Dashboard")

# ------------------------------- Helpers --------------------------------
@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    path_out = Path(OUT_CSV)
    path_in = Path(IN_CSV)
    df = pd.DataFrame()
    if path_out.exists():
        df = pd.read_csv(path_out)
    elif path_in.exists():
        df = pd.read_csv(path_in)
    else:
        st.warning("No data found. Please run the processing job first.")
        return df

    EXPECTED_COLS = [
        "id", "created_at", "channel", "subject", "description",
        "topic", "priority", "sentiment", "owner_suggested"
    ]
    for col in EXPECTED_COLS:
        if col not in df.columns:
            df[col] = None

    # Normalización
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    return df

def fetch_metrics() -> dict | None:
    try:
        r = requests.get(f"{API_URL}/metrics", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"No se pudo leer /metrics: {e}")
        return None

def list_dlq_files(n: int = 20, max_age_days: Optional[int] = None):
    """
    Lista archivos del DLQ limitados por 'n'.
    Si max_age_days está seteado, filtra por antigüedad (mtime).
    Devuelve (lista_filtrada, total_sin_filtrar)
    """
    if not DLQ_DIR.exists():
        return [], 0
    all_files = sorted(DLQ_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    total = len(all_files)

    if max_age_days is not None and max_age_days >= 0:
        cutoff = time.time() - max_age_days * 24 * 3600
        all_files = [f for f in all_files if f.stat().st_mtime >= cutoff]

    return all_files[:n], total

# ------------------------------- Tabs -----------------------------------
tab_explorer, tab_health, tab_dlq = st.tabs(["📊 KPIs & Explorer", "🛠️ System Health", "🧩 DLQ"])

# ========================= TAB: KPIs & EXPLORER =========================
with tab_explorer:
    st.subheader("🔎 Filters")
    df = load_data()
    if df.empty:
        st.info("No data available.")
    else:
        col_f1, col_f2, col_f3 = st.columns([1, 1, 2])

        # Priority filter (multi)
        all_priorities = ["P1", "P2", "P3"]
        selected_priorities = col_f1.multiselect(
            "Priority",
            options=all_priorities,
            default=all_priorities,
            help="Filter by ticket priority"
        )

        # Topic filter (single with 'All')
        topics_sorted = sorted(t for t in df["topic"].unique() if isinstance(t, str))
        topics_with_all = ["All topics"] + topics_sorted
        selected_topic = col_f2.selectbox(
            "Topic",
            options=topics_with_all,
            index=0,
            help="Focus on a single topic or view all"
        )

        # Date range (si hay fechas)
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

        # Aplicar filtros
        fdf = df.copy()

        if selected_priorities:
            fdf = fdf[fdf["priority"].isin(selected_priorities)]
        else:
            fdf = fdf.iloc[0:0]

        if selected_topic != "All topics":
            fdf = fdf[fdf["topic"] == selected_topic]

        if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
            start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
            end_d = end_d + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            if fdf["created_at"].notna().any():
                fdf = fdf[(fdf["created_at"] >= start_d) & (fdf["created_at"] <= end_d)]

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
                # cierre de oración best-effort
                if summary and summary[-1] not in ".!?":
                    last_dot = summary.rfind(".")
                    if last_dot != -1:
                        summary = summary[: last_dot + 1]
                st.write(summary)
            except Exception as e:
                st.warning(f"Could not generate summary: {e}")

        # KPIs
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

        # Charts
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

        # Drill-down
        if selected_topic != "All topics":
            st.subheader(f"🔬 Drill-down — Topic: {selected_topic}")
            subset = fdf.sort_values(by="created_at", ascending=False) if "created_at" in fdf.columns else fdf.copy()
            show_cols = [c for c in [
                "id", "created_at", "channel", "subject", "priority", "sentiment", "owner_suggested", "description"
            ] if c in subset.columns]
            st.dataframe(subset[show_cols], use_container_width=True, hide_index=True)
        else:
            with st.expander("View data"):
                subset = fdf.sort_values(by="created_at", ascending=False) if "created_at" in fdf.columns else fdf.copy()
                show_cols = [c for c in [
                    "id", "created_at", "channel", "subject", "topic", "priority", "sentiment", "owner_suggested", "description"
                ] if c in subset.columns]
                st.dataframe(subset[show_cols], use_container_width=True, hide_index=True)

# ============================ TAB: SYSTEM HEALTH ============================
with tab_health:
    st.subheader("System Health")
    m = fetch_metrics()

    if not m:
        st.stop()

    # Fila 1: éxito / error
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Processed", m.get("tickets_processed", 0))
    c2.metric("Failed", m.get("tickets_failed", 0))
    c3.metric("Success rate", f"{m.get('success_rate', 0.0) * 100:.1f}%")
    c4.metric("Error rate", f"{m.get('error_rate', 0.0) * 100:.1f}%")

    # Fila 2: notificaciones y reintentos
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Notify OK", m.get("notify_success", 0))
    d2.metric("Notify failed", m.get("notify_failed", 0))
    d3.metric("Retries (total)", m.get("retries", 0))
    d4.metric("Retry failed (cases)", m.get("retry_failed", 0))

    # Nota
    st.caption(
        f"DLQ escritos: {m.get('dlq_written', 0)} · "
        f"API_URL: {API_URL}"
    )

# ================================ TAB: DLQ =================================
with tab_dlq:
    st.subheader("Dead Letter Queue (últimos errores)")

    st.caption(f"Mostrando archivos de los últimos **{DLQ_RETENTION_DAYS_UI}** días (ajustable con `DLQ_RETENTION_DAYS` en .env).")

    files, total_raw = list_dlq_files(n=100, max_age_days=DLQ_RETENTION_DAYS_UI)
    if not files:
        if total_raw > 0:
            st.success("No hay errores dentro de la ventana de retención. ✅")
            st.caption(f"(Hay {total_raw} archivo(s) antiguos en disco fuera de la ventana de {DLQ_RETENTION_DAYS_UI} días.)")
        else:
            st.success("DLQ vacío ✅")
    else:
        st.caption(f"Archivos recientes mostrados: {len(files)} / Total en disco: {total_raw}")
        for f in files[:20]:
            try:
                with f.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                with st.expander(f.name):
                    st.json(data)
            except Exception as e:
                st.warning(f"No se pudo leer {f.name}: {e}")
