"""
LangGraph state definition for the BI Orchestrator.

All nodes read from and write to this shared state dict.
LangGraph merges node return dicts into the state automatically.
"""

from typing import TypedDict


class GraphState(TypedDict):
    user_question: str       # The original natural language question
    business_context: str    # Synthesized context brief from Node_1 (Haiku)
    database_schema: str     # DDL pulled from SQLAlchemy in Node_1
    generated_sql: str       # SELECT query produced by Node_2 (Opus)
    execution_error: str     # Stack trace if Node_3 fails; empty string on success
    raw_data_result: list    # List of row dicts returned by Node_3
    final_summary: str       # Executive summary produced by Node_4 (Sonnet)
    retry_count: int         # Number of SQL generation retries attempted
