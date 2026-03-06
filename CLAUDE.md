# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
# Run the Streamlit web UI (primary interface)
python -m streamlit run app.py

# Run the interactive CLI (alternative)
python main.py

# Generate / regenerate the mock SQLite database (2,000 customers)
python generate_data.py

# Install dependencies
pip install -r requirements.txt
```

## Environment Setup

Copy `.env.example` to `.env` and fill in:
- `ANTHROPIC_API_KEY` — required
- `LANGCHAIN_API_KEY` + `LANGCHAIN_TRACING_V2=true` — required for LangSmith tracing
- `SQLITE_DB_PATH` — defaults to `telecom.db`

## Architecture

This is a **LangGraph state machine** that translates natural language questions into SQL queries against a telecom SQLite database, with a self-correction loop on failure.

### Graph Flow

```
START → retriever → sql_coder → db_executor ──(success)──→ analyst → END
                         ↑            │
                         └──(error, retry < 3)─┘
                                      │
                              (error, retry >= 3) → analyst → END
```

### Node → Model mapping (defined in `config.py`)

| Node | Model | Reason |
|------|-------|--------|
| `node_1_retriever` | `claude-haiku-4-5-20251001` | Lightweight context synthesis |
| `node_2_sql_coder` | `claude-opus-4-6` | Complex SQL generation + self-correction |
| `node_3_db_executor` | No LLM | Pure SQLAlchemy execution |
| `node_4_analyst` | `claude-sonnet-4-6` | Executive summary prose |

### Key design decisions

- **Engine injection**: The SQLAlchemy engine is passed to nodes that need DB access via `functools.partial` in `agents/graph.py` — it never appears in `GraphState`.
- **Self-correction**: When `node_3_db_executor` fails, it writes the error to `state["execution_error"]`. `node_2_sql_coder` detects this and injects `SQL_CODER_ERROR_SECTION` into its prompt on the retry. Pydantic `ValidationError`s from `SQLOutput` are also routed through this same loop.
- **RAG without ChromaDB**: `rag/chroma_store.py` implements TF-IDF cosine similarity in pure Python (no external vector DB) due to ChromaDB incompatibility with Python 3.14.
- **Multi-statement DDL**: SQLAlchemy on Python 3.14 rejects multi-statement `text()` calls — all DDL is split into individual `conn.execute()` calls.
- **Read-only engine**: `database/setup.py` uses a separate write engine only for seeding, then disposes it. All agent queries run against a SQLite `file:...?mode=ro` connection created via a `creator` function with an absolute path (required for `inspect()` to work correctly).

### Security guardrails (layered defence)

| Layer | Location | What it does |
|-------|----------|-------------|
| Input sanitization | `main.py:_check_input()` | 14 regex patterns block prompt injection phrases (`ignore previous instructions`, `you are now a`, `new system prompt`, etc.) and enforce a 500-char input limit — checked before any LLM call |
| SELECT-only guard | `agents/nodes.py:SQLOutput` | Pydantic validator strips markdown fences and rejects any query not starting with `SELECT` |
| Table allow-list | `agents/nodes.py:SQLOutput` | `sqlglot` parses the SQL and blocks references to any table outside `{customers, billing, network_usage}`; CTE aliases are excluded to avoid false positives |
| Row cap | `agents/nodes.py:node_3_db_executor` | Appends `LIMIT 500` to any query without an explicit LIMIT clause using `sqlglot` AST inspection |
| Read-only DB | `database/setup.py:get_engine()` | OS-level read-only SQLite connection — writes raise `attempt to write a readonly database` regardless of SQL content |

> **Important**: Column-level validation was intentionally omitted. SQL functions, aggregation aliases, and subquery aliases all surface as `exp.Column` nodes in sqlglot, causing too many false positives. The DB executor's error messages handle invalid column names cleanly through the self-correction loop.

### State schema (`agents/state.py`)

```python
user_question      # original NL question
business_context   # Haiku-synthesized brief from RAG + schema
database_schema    # DDL string from SQLAlchemy inspect()
generated_sql      # SELECT query from Opus
execution_error    # error string if db_executor fails; "" on success
raw_data_result    # list of row dicts from SQLAlchemy
final_summary      # executive prose from Sonnet
retry_count        # increments on each sql_coder retry
```

### Database (`telecom.db`)

Three tables: `customers`, `billing`, `network_usage`. Run `generate_data.py` to populate with 2,000 realistic customers + ~16K billing and usage rows. If the DB is missing, `database/setup.py:get_engine()` falls back to a 20-row seed.

### Prompt templates (`prompts/templates.py`)

All system prompts live here. To change agent behaviour, edit the relevant template constant — `RETRIEVER_SYSTEM`, `SQL_CODER_SYSTEM`, `SQL_CODER_ERROR_SECTION`, `ANALYST_SYSTEM`, or `ANALYST_FAILURE_SYSTEM`.

### Data Dictionary (`rag/chroma_store.py`)

Eight business rule documents (churn definitions, plan types, billing semantics, etc.) are indexed in memory on first call to `build_data_dictionary()`. `query_context(question, n_results=3)` returns the top-k entries by TF-IDF cosine similarity.

## Deployment

- **Live URL**: http://3.132.29.156
- **GitHub**: https://github.com/DevMLAI01/text-to-sql_Mult_Agent-bi-orchestrator
- **EC2**: t3.micro, Amazon Linux 2023, us-east-2, user=`ec2-user`, app at `~/app/`
- **Services**: `sudo systemctl status bi-orchestrator` / `sudo systemctl status nginx`
- **Logs**: `journalctl -u bi-orchestrator -f`
- **Update**: `cd ~/app && git pull && sudo systemctl restart bi-orchestrator`

### Python Compatibility Notes
- Use `Optional[X]` from `typing` instead of `X | None` (server runs Python 3.9)
- Use `Tuple[X, Y]` from `typing` instead of `tuple[X, Y]`
- `python -m streamlit run app.py` works even if `streamlit` is not on PATH (Windows)
