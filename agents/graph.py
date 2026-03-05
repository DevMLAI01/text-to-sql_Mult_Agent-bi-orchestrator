"""
LangGraph state machine assembly.

Graph topology:
  START
    └─> retriever
          └─> sql_coder
                └─> db_executor ─┬─(success)──────────────> analyst ─> END
                                  └─(error, retry < 3)──> sql_coder
                                  └─(error, retry >= 3)──> analyst ─> END
"""

from functools import partial

from langgraph.graph import StateGraph, END
from sqlalchemy import Engine

import config
from .state import GraphState
from .nodes import node_1_retriever, node_2_sql_coder, node_3_db_executor, node_4_analyst


def _route_after_execution(state: GraphState) -> str:
    """Conditional edge: decide whether to retry SQL generation or proceed to analyst."""
    if not state.get("execution_error"):
        return "analyst"
    elif state.get("retry_count", 0) < config.MAX_RETRIES:
        return "sql_coder"
    else:
        return "analyst"


def build_graph(engine: Engine) -> StateGraph:
    """
    Constructs and compiles the LangGraph state machine.

    The engine is injected via functools.partial so nodes receive it
    without polluting the state schema.
    """
    workflow = StateGraph(GraphState)

    # Bind engine to nodes that need DB access
    retriever_node = partial(node_1_retriever, engine=engine)
    executor_node = partial(node_3_db_executor, engine=engine)

    # Register nodes
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("sql_coder", node_2_sql_coder)
    workflow.add_node("db_executor", executor_node)
    workflow.add_node("analyst", node_4_analyst)

    # Linear edges
    workflow.set_entry_point("retriever")
    workflow.add_edge("retriever", "sql_coder")
    workflow.add_edge("sql_coder", "db_executor")

    # Conditional edge from db_executor
    workflow.add_conditional_edges(
        "db_executor",
        _route_after_execution,
        {
            "sql_coder": "sql_coder",
            "analyst": "analyst",
        },
    )

    # Terminal edge
    workflow.add_edge("analyst", END)

    return workflow.compile()
