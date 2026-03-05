"""
Configuration: model assignments, retry limits, and environment setup.

Model tier strategy:
  - HAIKU  → lightweight tasks (context synthesis in Node_1)
  - SONNET → quality language tasks (executive summary in Node_4)
  - OPUS   → complex reasoning (SQL generation + self-correction in Node_2)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Model IDs ---
HAIKU = "claude-haiku-4-5-20251001"   # Fast, cheap — retrieval synthesis
SONNET = "claude-sonnet-4-6"           # Balanced — executive summaries
OPUS = "claude-opus-4-6"               # Most capable — SQL generation & correction

# --- Agent settings ---
MAX_RETRIES = 3  # Max SQL correction attempts before graceful failure

# --- Database ---
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "telecom.db")

# --- LangSmith (set via .env) ---
# LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT
# are read automatically by LangChain/LangSmith from environment.

# --- Validation ---
def require_api_key() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill in your key."
        )
