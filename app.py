"""
Multi-Agent BI Orchestrator — Streamlit Web UI

Wraps the existing LangGraph pipeline with a browser-accessible interface.
The LangGraph app and DB engine are cached per session using @st.cache_resource.

Usage (local):
    streamlit run app.py

Usage (production — started by systemd):
    streamlit run app.py --server.port 8501 --server.headless true
"""

import os
import time

import streamlit as st

from main import _check_input, SAMPLE_QUERIES

# ---------------------------------------------------------------------------
# Page config — must be the first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Telecom BI Orchestrator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Cached pipeline initialisation (once per server session, not per query)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Initialising pipeline…")
def _init_pipeline():
    """Load DB engine + build LangGraph app once, reuse across all queries."""
    import config
    config.require_api_key()

    from database.setup import get_engine
    from rag.chroma_store import build_data_dictionary
    from agents import build_graph

    engine = get_engine()
    build_data_dictionary()
    app = build_graph(engine)
    return engine, app


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("📊 BI Orchestrator")
    st.caption("Multi-Agent Text-to-SQL · Telecom Dataset")

    st.divider()

    st.subheader("Model Tiers")
    st.markdown(
        """
| Step | Model | Role |
|------|-------|------|
| 1 | Haiku | Context retrieval |
| 2 | Opus | SQL generation |
| 3 | *(none)* | DB execution |
| 4 | Sonnet | Executive summary |
        """
    )

    st.divider()

    langsmith_url = os.getenv("LANGSMITH_PROJECT_URL", "")
    if langsmith_url:
        st.markdown(f"[🔍 LangSmith Traces]({langsmith_url})")
    else:
        st.caption("Set LANGSMITH_PROJECT_URL in .env for trace links.")

    st.divider()

    with st.expander("Sample Questions", expanded=False):
        st.markdown(SAMPLE_QUERIES)


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

st.title("Telecom BI Orchestrator")
st.markdown(
    "Ask any business question about the telecom dataset — "
    "the agent pipeline generates SQL, executes it, and returns an executive summary."
)

# Initialise pipeline (cached)
try:
    engine, app = _init_pipeline()
except Exception as exc:
    st.error(f"Pipeline initialisation failed: {exc}")
    st.stop()

# Question input
with st.form("query_form", clear_on_submit=False):
    question = st.text_input(
        "Your question",
        placeholder="e.g. What is the total unpaid amount owed, broken down by plan type?",
        max_chars=500,
    )
    submitted = st.form_submit_button("Run Query", type="primary")

if submitted and question.strip():
    # Guardrail #1 — injection check
    is_safe, reason = _check_input(question.strip())
    if not is_safe:
        st.error(f"Blocked: {reason}")
        st.stop()

    initial_state = {
        "user_question": question.strip(),
        "business_context": "",
        "database_schema": "",
        "generated_sql": "",
        "execution_error": "",
        "raw_data_result": [],
        "final_summary": "",
        "retry_count": 0,
    }

    with st.spinner("Running… Haiku → Opus → Executor → Sonnet"):
        t0 = time.perf_counter()
        try:
            final_state = app.invoke(initial_state)
        except Exception as exc:
            st.error(f"Pipeline error: {exc}")
            st.stop()
        elapsed = time.perf_counter() - t0

    # --- Metrics row ---
    rows_returned = len(final_state.get("raw_data_result", []))
    retry_count   = final_state.get("retry_count", 0)

    col1, col2, col3 = st.columns(3)
    col1.metric("Rows returned", rows_returned)
    col2.metric("Retries", retry_count)
    col3.metric("Elapsed (s)", f"{elapsed:.1f}")

    st.divider()

    # --- Generated SQL ---
    st.subheader("Generated SQL")
    sql = final_state.get("generated_sql", "")
    if sql:
        st.code(sql, language="sql")
    else:
        st.caption("No SQL generated.")

    st.divider()

    # --- Executive Summary ---
    st.subheader("Executive Summary")
    summary = final_state.get("final_summary", "")
    if summary:
        st.markdown(summary)
    else:
        st.caption("No summary available.")

elif submitted and not question.strip():
    st.warning("Please enter a question before submitting.")
