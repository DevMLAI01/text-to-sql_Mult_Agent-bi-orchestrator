"""
Multi-Agent BI Orchestrator — Interactive CLI

Type any business question about the telecom data and the agent pipeline
will generate SQL, execute it, and return an executive summary.

Usage:
    python main.py

Commands at the prompt:
    <any question>   Run the full agent pipeline
    examples         Show 10 sample queries
    quit / exit      Exit the program

Prerequisites:
    1. pip install -r requirements.txt
    2. Copy .env.example to .env and fill in ANTHROPIC_API_KEY + LANGCHAIN_API_KEY
    3. python generate_data.py   (to populate telecom.db with 2,000 customers)
"""

import re
from typing import Tuple

import config
from database.setup import get_engine
from rag.chroma_store import build_data_dictionary
from agents import build_graph


# ---------------------------------------------------------------------------
# Guardrail #1 — Input sanitization (prompt injection detection)
# ---------------------------------------------------------------------------

# Patterns that indicate an attempt to hijack the LLM's instructions
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above|prior)\s+(instructions?|rules?|prompts?|context)",
    r"forget\s+(your|all|previous)\s+(instructions?|rules?|training)",
    r"you\s+are\s+now\s+a",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(if\s+you\s+are|a)\s+",
    r"disregard\s+(your|all|previous|the)\s+",
    r"new\s+(system\s+)?(instruction|prompt|rule|directive)",
    r"override\s+(your|the|all)\s+",
    r"jailbreak",
    r"system\s*prompt",
    r"<\s*system\s*>",
    r"\[\s*(system|inst|instruction)\s*\]",
    r"###\s*(system|instruction)",
    r"prompt\s+injection",
]

_MAX_QUESTION_LENGTH = 500


def _check_input(question: str) -> Tuple[bool, str]:
    """
    Returns (is_safe, rejection_reason).
    Blocks questions that exceed the length limit or match injection patterns.
    """
    if len(question) > _MAX_QUESTION_LENGTH:
        return False, (
            f"Question too long ({len(question)} chars). "
            f"Please keep it under {_MAX_QUESTION_LENGTH} characters."
        )
    lower = question.lower()
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, lower):
            return False, (
                "Question contains a pattern that looks like a prompt injection attempt. "
                "Please rephrase as a plain business question."
            )
    return True, ""


# ---------------------------------------------------------------------------
# Sample queries menu
# ---------------------------------------------------------------------------

SAMPLE_QUERIES = """
  Revenue & Billing
  -----------------
  1.  What is the total unpaid amount owed, broken down by plan type?
  2.  Which Enterprise customers have the largest outstanding unpaid balances in 2024?
  3.  Show me total paid revenue for each billing month in 2024, ordered chronologically.

  Churn Analysis
  --------------
  4.  What percentage of customers have churned for each plan type?
  5.  Show me churned customers who had both unpaid invoices and more than 15 dropped calls.
  6.  Which customers who signed up after 2022 have already churned and still have unpaid invoices?

  Network Quality
  ---------------
  7.  Which billing months had the highest average dropped calls count across all customers?
  8.  Which Enterprise customers had more than 15 dropped calls in any single month in 2024?

  Usage & Segmentation
  --------------------
  9.  Who are customers that consistently used more than 200 GB of data per month across 3+ months?
  10. Which Prepaid customers averaged more than 50 GB per month — upsell candidates for Postpaid_5G?
"""


# ---------------------------------------------------------------------------
# Query runner
# ---------------------------------------------------------------------------

def run_query(app, question: str) -> None:
    print(f"\n  Running... (Haiku → Opus → Executor → Sonnet)\n")

    initial_state = {
        "user_question": question,
        "business_context": "",
        "database_schema": "",
        "generated_sql": "",
        "execution_error": "",
        "raw_data_result": [],
        "final_summary": "",
        "retry_count": 0,
    }

    final_state = app.invoke(initial_state)

    retry = final_state.get("retry_count", 0)
    retry_note = f"  ({retry} retr{'y' if retry == 1 else 'ies'})" if retry > 0 else ""

    print(f"{'─'*70}")
    print(f"  SQL{retry_note}")
    print(f"{'─'*70}")
    print(f"  {final_state.get('generated_sql', 'N/A')}\n")
    print(f"{'─'*70}")
    print(f"  Executive Summary")
    print(f"{'─'*70}")
    print(f"  {final_state.get('final_summary', 'N/A')}")
    print(f"{'─'*70}\n")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    config.require_api_key()

    print("\nInitializing...")
    engine = get_engine()
    build_data_dictionary()
    app = build_graph(engine)

    print("\n" + "="*70)
    print("  Telecom BI Orchestrator  |  Text-to-SQL Agent")
    print("  Models: Haiku (retrieval) · Opus (SQL) · Sonnet (analysis)")
    print("  Type 'examples' to see sample queries, 'quit' to exit.")
    print("="*70)

    query_num = 0
    while True:
        try:
            question = input("\n  Your question: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n  Goodbye!\n")
            break

        if not question:
            continue

        if question.lower() in ("quit", "exit", "q"):
            print("\n  Goodbye!\n")
            break

        if question.lower() in ("examples", "example", "help"):
            print(SAMPLE_QUERIES)
            continue

        # --- Guardrail: reject injections before touching the LLM ---
        is_safe, reason = _check_input(question)
        if not is_safe:
            print(f"\n  [Blocked] {reason}\n")
            continue

        query_num += 1
        print(f"\n{'='*70}")
        print(f"  Q{query_num}: {question}")
        print(f"{'='*70}")

        try:
            run_query(app, question)
        except Exception as exc:
            print(f"\n  [Error] {exc}\n")


if __name__ == "__main__":
    main()
