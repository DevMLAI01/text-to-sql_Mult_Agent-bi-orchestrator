"""
In-memory RAG store for the telecom Data Dictionary.

Replaces ChromaDB (incompatible with Python 3.14) with a lightweight
TF-IDF cosine similarity search using numpy — already installed as a
transitive dependency. Same public interface: build_data_dictionary()
and query_context().
"""

import math
import re
from collections import Counter

# ---------------------------------------------------------------------------
# Data Dictionary: business rules and metric definitions
# ---------------------------------------------------------------------------

_DATA_DICTIONARY: list[dict] = [
    {
        "id": "dd_001",
        "title": "High-Value Customer Definition",
        "content": (
            "A High-Value Customer is defined as any customer on the 'Enterprise' plan "
            "with total annual billing exceeding $40,000, OR any customer whose average "
            "monthly data usage exceeds 150 GB. These customers receive priority SLA treatment."
        ),
    },
    {
        "id": "dd_002",
        "title": "Churn Risk Definition",
        "content": (
            "A customer is flagged as Churn Risk when: (1) their churn_status is 'Churned', "
            "OR (2) they have 2+ consecutive unpaid invoices (is_paid = 0), "
            "OR (3) their dropped_calls_count exceeds 15 in any single month. "
            "Churned customers have already left; Churn Risk customers may still be retained."
        ),
    },
    {
        "id": "dd_003",
        "title": "Plan Type Descriptions",
        "content": (
            "Plan types in the system: "
            "'Prepaid' — pay-as-you-go, low ARPU (~$30-50/month), typically individual consumers. "
            "'Postpaid_5G' — monthly contract with 5G access, mid ARPU (~$100-150/month). "
            "'Enterprise' — corporate accounts with SLAs, high ARPU ($3,000-$10,000+/month), "
            "multiple lines bundled under a single customer_id."
        ),
    },
    {
        "id": "dd_004",
        "title": "Dropped Calls Threshold — Network Quality",
        "content": (
            "A dropped_calls_count of 0-5 per month is considered normal. "
            "6-15 is flagged as 'Degraded Service'. "
            "More than 15 dropped calls in a month constitutes a 'Critical Network Issue' "
            "and triggers an automatic SLA breach alert for Enterprise customers."
        ),
    },
    {
        "id": "dd_005",
        "title": "Billing Month Format and Fiscal Calendar",
        "content": (
            "billing_month and month columns use the format YYYY-MM (e.g., '2024-09'). "
            "The fiscal year runs January through December. "
            "When a query references 'this year', use the current calendar year. "
            "When referencing 'last quarter', compute the prior 3-month window from the current month."
        ),
    },
    {
        "id": "dd_006",
        "title": "Unpaid Invoice Definition",
        "content": (
            "An invoice is considered unpaid when is_paid = 0 (SQLite stores booleans as integers). "
            "Outstanding balance = SUM(amount_due) WHERE is_paid = 0 for a given customer. "
            "Overdue is defined as unpaid invoices from billing months prior to the current month."
        ),
    },
    {
        "id": "dd_007",
        "title": "ARPU — Average Revenue Per User",
        "content": (
            "ARPU is calculated as: total amount_due (all invoices, paid and unpaid) "
            "divided by the number of billing months with activity. "
            "When comparing ARPU across plan types, GROUP BY plan_type and JOIN customers to billing."
        ),
    },
    {
        "id": "dd_008",
        "title": "Data Usage Tiers",
        "content": (
            "Data usage tiers by monthly GB consumed: "
            "Light: < 20 GB. Moderate: 20-80 GB. Heavy: 80-200 GB. Ultra: > 200 GB. "
            "Enterprise customers are expected to be in the Heavy or Ultra tier. "
            "Prepaid customers exceeding 50 GB may be upsell candidates for Postpaid_5G."
        ),
    },
]

# ---------------------------------------------------------------------------
# Lightweight TF-IDF vector store (no external dependencies)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _tfidf_vectors(corpus: list[list[str]]) -> list[dict[str, float]]:
    """Build TF-IDF vectors for each document in the corpus."""
    n = len(corpus)
    # Document frequency
    df: dict[str, int] = {}
    for tokens in corpus:
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1

    vectors: list[dict[str, float]] = []
    for tokens in corpus:
        tf = Counter(tokens)
        total = len(tokens) or 1
        vec: dict[str, float] = {}
        for term, count in tf.items():
            tfidf = (count / total) * math.log((n + 1) / (df.get(term, 0) + 1))
            vec[term] = tfidf
        vectors.append(vec)
    return vectors


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    dot = sum(a.get(t, 0.0) * v for t, v in b.items())
    mag_a = math.sqrt(sum(v * v for v in a.values())) or 1e-9
    mag_b = math.sqrt(sum(v * v for v in b.values())) or 1e-9
    return dot / (mag_a * mag_b)


# Module-level index (built once on first call)
_index: list[dict[str, float]] | None = None
_corpus_tokens: list[list[str]] | None = None


def build_data_dictionary() -> None:
    """
    Builds the in-memory TF-IDF index from the Data Dictionary.
    Safe to call multiple times — only builds once.
    """
    global _index, _corpus_tokens
    if _index is not None:
        return
    _corpus_tokens = [_tokenize(doc["content"]) for doc in _DATA_DICTIONARY]
    _index = _tfidf_vectors(_corpus_tokens)


def query_context(question: str, n_results: int = 3) -> str:
    """
    Returns the top-k most relevant Data Dictionary entries for the question,
    ranked by TF-IDF cosine similarity.
    """
    if _index is None:
        build_data_dictionary()

    q_tokens = _tokenize(question)
    # Build query vector against the same IDF weights
    n = len(_DATA_DICTIONARY)
    df: dict[str, int] = {}
    for tokens in _corpus_tokens:  # type: ignore[union-attr]
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1

    tf = Counter(q_tokens)
    total = len(q_tokens) or 1
    q_vec: dict[str, float] = {
        term: (count / total) * math.log((n + 1) / (df.get(term, 0) + 1))
        for term, count in tf.items()
    }

    scores = [(_cosine(q_vec, doc_vec), i) for i, doc_vec in enumerate(_index)]  # type: ignore[union-attr]
    scores.sort(reverse=True)

    top = scores[:n_results]
    parts: list[str] = []
    for _, idx in top:
        doc = _DATA_DICTIONARY[idx]
        parts.append(f"[{doc['title']}]\n{doc['content']}")

    return "\n\n".join(parts) if parts else "No relevant business context found."
