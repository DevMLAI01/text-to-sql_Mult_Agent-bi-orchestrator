# Sample Queries — Multi-Agent BI Orchestrator

Natural language questions you can ask the system. Copy any into `main.py`'s
`SAMPLE_QUESTIONS` list or pass directly to `app.invoke({"user_question": "..."})`.

---

## Revenue & Billing

**1. Total outstanding revenue by plan type**
> What is the total unpaid amount owed, broken down by plan type?

**2. Highest-value unpaid Enterprise accounts**
> Which Enterprise customers have the largest outstanding unpaid balances in 2024, and how much do they owe?

**3. Monthly revenue trend**
> Show me total paid revenue for each billing month in 2024, ordered chronologically.

---

## Churn Analysis

**4. Churn rate by plan type**
> What percentage of customers have churned for each plan type?

**5. High-risk churned customers**
> Show me churned customers who had both unpaid invoices and more than 15 dropped calls in any month.

**6. Recent churners with large balances**
> Which customers who signed up after 2022 have already churned and still have unpaid invoices?

---

## Network Quality

**7. Worst network quality months**
> Which billing months had the highest average dropped calls count across all customers?

**8. Enterprise SLA breaches**
> Which Enterprise customers had more than 15 dropped calls in any single month in 2024?

---

## Customer Segmentation & Usage

**9. Ultra-tier data consumers**
> Who are the customers that consistently used more than 200 GB of data per month across at least 3 months?

**10. Prepaid upsell candidates**
> Which Prepaid customers averaged more than 50 GB of data usage per month — potential candidates for an upgrade to Postpaid_5G?

---

## How to run a custom query

```python
from database.setup import get_engine
from rag.chroma_store import build_data_dictionary
from agents import build_graph

engine = get_engine()
build_data_dictionary()
app = build_graph(engine)

result = app.invoke({
    "user_question": "YOUR QUESTION HERE",
    "business_context": "",
    "database_schema": "",
    "generated_sql": "",
    "execution_error": "",
    "raw_data_result": [],
    "final_summary": "",
    "retry_count": 0,
})

print(result["generated_sql"])
print(result["final_summary"])
```
