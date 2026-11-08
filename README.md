## Verified Urdu Text-to-SQL Agent

An auditable prototype for Urdu and Roman Urdu questions over Pakistan Bureau
of Statistics education Table 1. It never runs model-authored unrestricted SQL:
the planner creates a constrained `SELECT`, then the verifier parses its AST,
checks table/column links, dry-runs it, and flags empty/out-of-range/mixed-grain
results. Ambiguous indicators trigger an Urdu clarification instead of a guess.

### Run

```powershell
uv run uvicorn tds.main:app --reload
```

Then send:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/ask -Method Post -ContentType application/json -Body '{"question":"Punjab mein school se bahar bachay kitne hain?", "include_chart":true}'
```

The response includes the plan, generated SQL, verification evidence, source
row, Urdu explanation, zero model-cost estimate, and optional chart data.

### Evaluation set

`tests/test_agent.py` contains gold SQL for simple filters, subgroup filters,
a verified geography join, ranking, aggregation, clarification, and SQL repair. Run `uv run pytest`.
`GET /evaluation` produces execution accuracy, exact gold-SQL accuracy, repair
success, clarification quality, cost/query, and a difficulty breakdown.

### Data caveat

Rows are aggregates from the PBS workbook, not individual records. The agent
prevents mixed-grain averages by default; it does not join unrelated PBS tables.
