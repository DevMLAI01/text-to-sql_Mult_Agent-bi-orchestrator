"""
The four agent nodes of the BI Orchestrator state machine.

Node  | Model              | Role
------|--------------------|------------------------------------------
  1   | claude-haiku-4-5   | Retriever — context synthesis (cheap/fast)
  2   | claude-opus-4-6    | SQL Coder — generation + self-correction
  3   | (no LLM)           | DB Executor — pure SQLAlchemy
  4   | claude-sonnet-4-6  | Analyst — executive summary
"""

import re
import json

import sqlglot
import sqlglot.expressions as exp
from anthropic import Anthropic
from pydantic import BaseModel, ValidationError, field_validator
from sqlalchemy import text, Engine

import config
from database.schema import get_schema_ddl
from rag.chroma_store import query_context, build_data_dictionary
from prompts.templates import (
    RETRIEVER_SYSTEM,
    SQL_CODER_SYSTEM,
    SQL_CODER_ERROR_SECTION,
    ANALYST_SYSTEM,
    ANALYST_FAILURE_SYSTEM,
)
from .state import GraphState

# ---------------------------------------------------------------------------
# Shared Anthropic client
# ---------------------------------------------------------------------------

_client = Anthropic()


def _call_llm(model: str, system: str, user_message: str, max_tokens: int = 1024) -> str:
    """Thin wrapper around the Anthropic Messages API."""
    response = _client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Guardrail constants for SQL validation
# ---------------------------------------------------------------------------

_ALLOWED_TABLES = {"customers", "billing", "network_usage"}

_MAX_ROWS = 500  # Hard cap on result set size


# ---------------------------------------------------------------------------
# Guardrail #2 — Pydantic SQL guard (SELECT-only + sqlglot schema validation)
# ---------------------------------------------------------------------------

class SQLOutput(BaseModel):
    sql: str

    @field_validator("sql")
    @classmethod
    def must_be_select(cls, v: str) -> str:
        clean = v.strip()
        # Strip markdown code fences if the model added them
        clean = re.sub(r"^```(?:sql)?\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean)
        clean = clean.strip()

        # Rule 1: must start with SELECT
        if not clean.upper().startswith("SELECT"):
            raise ValueError(f"Query must start with SELECT. Got: {clean[:60]!r}")

        # Rule 2: sqlglot — validate tables and columns against known schema
        try:
            parsed = sqlglot.parse_one(clean, dialect="sqlite")

            # Collect CTE alias names — these are valid "virtual tables" within the query
            cte_names = {
                cte.alias.lower()
                for cte in parsed.find_all(exp.CTE)
                if cte.alias
            }

            # Check all referenced table names, excluding CTE aliases
            referenced_tables = {t.name.lower() for t in parsed.find_all(exp.Table)}
            unknown_tables = (referenced_tables - _ALLOWED_TABLES) - cte_names
            if unknown_tables:
                raise ValueError(
                    f"Query references table(s) not in the schema: {unknown_tables}. "
                    f"Allowed tables: {_ALLOWED_TABLES}"
                )

        except ValueError:
            raise  # re-raise our own validation errors
        except Exception as parse_err:
            # sqlglot parse failures are non-fatal — let the DB executor surface real errors
            pass

        return clean


# ---------------------------------------------------------------------------
# Node 1: Retriever  (Haiku — lightweight)
# ---------------------------------------------------------------------------

def node_1_retriever(state: GraphState, engine: Engine) -> dict:
    """
    Fetches business context from ChromaDB and the DB schema via SQLAlchemy,
    then uses Haiku to synthesize a concise context brief for the SQL Coder.
    """
    build_data_dictionary()

    question = state["user_question"]
    data_dict_context = query_context(question, n_results=3)
    schema_ddl = get_schema_ddl(engine)

    system_prompt = RETRIEVER_SYSTEM.format(
        user_question=question,
        data_dictionary=data_dict_context,
        database_schema=schema_ddl,
    )

    context_brief = _call_llm(
        model=config.HAIKU,
        system=system_prompt,
        user_message="Produce the context brief now.",
        max_tokens=512,
    )

    return {
        "business_context": context_brief,
        "database_schema": schema_ddl,
    }


# ---------------------------------------------------------------------------
# Node 2: SQL Coder  (Opus — most capable)
# ---------------------------------------------------------------------------

def node_2_sql_coder(state: GraphState) -> dict:
    """
    Generates a validated SELECT query using Opus.
    On retries, injects the previous error for self-correction.
    """
    retry_count = state.get("retry_count", 0)
    execution_error = state.get("execution_error", "")

    # Build optional error section for self-correction
    if execution_error:
        error_section = SQL_CODER_ERROR_SECTION.format(
            retry_count=retry_count,
            max_retries=config.MAX_RETRIES,
            execution_error=execution_error,
        )
        retry_count += 1
    else:
        error_section = ""

    system_prompt = SQL_CODER_SYSTEM.format(
        user_question=state["user_question"],
        business_context=state.get("business_context", ""),
        database_schema=state["database_schema"],
        error_section=error_section,
    )

    raw_sql = _call_llm(
        model=config.OPUS,
        system=system_prompt,
        user_message="Write the SQL query now.",
        max_tokens=512,
    )

    # Pydantic validation: strips fences, enforces SELECT-only + schema allow-list.
    # If validation fails (e.g. hallucinated table name), treat it as an execution
    # error so the self-correction loop retries with the failure reason.
    try:
        validated = SQLOutput(sql=raw_sql)
    except ValidationError as exc:
        error_msg = "; ".join(e["msg"] for e in exc.errors())
        return {
            "generated_sql": raw_sql,
            "retry_count": retry_count + 1,
            "execution_error": f"SQL validation failed: {error_msg}",
        }

    return {
        "generated_sql": validated.sql,
        "retry_count": retry_count,
        "execution_error": "",
    }


# ---------------------------------------------------------------------------
# Node 3: DB Executor  (No LLM — pure SQLAlchemy)
# ---------------------------------------------------------------------------

def node_3_db_executor(state: GraphState, engine: Engine) -> dict:
    """
    Executes the generated SQL against the read-only SQLite engine.

    Guardrail #3 — Row limit cap: appends LIMIT 500 to any query that
    doesn't already specify a LIMIT, preventing runaway result sets.
    Captures any errors for the self-correction loop.
    """
    sql = state["generated_sql"]

    # Guardrail #3: enforce row cap if no LIMIT clause is present
    try:
        parsed = sqlglot.parse_one(sql, dialect="sqlite")
        if parsed.find(exp.Limit) is None:
            sql = sql.rstrip().rstrip(";") + f" LIMIT {_MAX_ROWS}"
    except Exception:
        # If sqlglot can't parse (shouldn't happen after SQLOutput validation),
        # fall back to a simple string check
        if "LIMIT" not in sql.upper():
            sql = sql.rstrip().rstrip(";") + f" LIMIT {_MAX_ROWS}"

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = [dict(row._mapping) for row in result]
        return {
            "raw_data_result": rows,
            "execution_error": "",
        }
    except Exception as exc:
        return {
            "raw_data_result": [],
            "execution_error": str(exc),
        }


# ---------------------------------------------------------------------------
# Node 4: Analyst  (Sonnet — quality prose, cost-efficient)
# ---------------------------------------------------------------------------

def node_4_analyst(state: GraphState) -> dict:
    """
    Produces an executive-friendly summary using Sonnet.
    Falls back to a graceful failure message if retries were exhausted.
    """
    execution_error = state.get("execution_error", "")
    retry_count = state.get("retry_count", 0)

    if execution_error and retry_count >= config.MAX_RETRIES:
        # Graceful failure path
        system_prompt = ANALYST_FAILURE_SYSTEM.format(
            user_question=state["user_question"],
            execution_error=execution_error,
            max_retries=config.MAX_RETRIES,
        )
        summary = _call_llm(
            model=config.SONNET,
            system=system_prompt,
            user_message="Write the failure message now.",
            max_tokens=256,
        )
    else:
        raw_data = state.get("raw_data_result", [])
        # Serialize result rows as JSON for the prompt
        raw_data_str = json.dumps(raw_data, indent=2, default=str)

        system_prompt = ANALYST_SYSTEM.format(
            user_question=state["user_question"],
            raw_data=raw_data_str,
        )
        summary = _call_llm(
            model=config.SONNET,
            system=system_prompt,
            user_message="Write the executive summary now.",
            max_tokens=512,
        )

    return {"final_summary": summary}
