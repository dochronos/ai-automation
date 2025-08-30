import os
import pandas as pd
import streamlit as st
from pathlib import Path


OUT_CSV = os.getenv("LOCAL_OUTPUT_CSV", "data/outputs/classified.csv")


st.set_page_config(page_title="AI Automation – Classified Tickets", layout="wide")
st.title("📊 AI Automation – Classified Tickets")


path = Path(OUT_CSV)
if not path.exists():
    st.info("First run the job: `python -m src.jobs.process_new_rows`.")
else:
    df = pd.read_csv(path)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tickets", len(df))
    c2.metric("Critical (P1)", int((df["priority"] == "P1").sum()))
    c3.metric("Topics", df["topic"].nunique())
    c4.metric("% Negative", round((df["sentiment"] == "neg").mean() * 100, 1))


    st.bar_chart(df["topic"].value_counts())
    st.bar_chart(df["priority"].value_counts())


    with st.expander("View data"):
        st.dataframe(df, use_container_width=True)