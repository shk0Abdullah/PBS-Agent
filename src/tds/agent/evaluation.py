"""Small, reproducible evaluation suite with gold SQL and difficulty labels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tds.agent.service import UrduSQLAgent


@dataclass(frozen=True)
class EvaluationCase:
    question: str
    difficulty: str
    gold_sql: str | None
    expects_clarification: bool = False


CASES = (
    EvaluationCase("Punjab mein school se bahar bachay kitne hain?", "simple_filter",
        "SELECT geography, area_type, gender, out_of_school_pct AS value, source_row FROM school_participation WHERE geography = 'Punjab' AND area_type IS NULL AND gender IS NULL"),
    EvaluationCase("Punjab rural female primary completion", "multi_filter",
        "SELECT geography, area_type, gender, completed_primary_pct AS value, source_row FROM school_participation WHERE geography = 'Punjab' AND area_type = 'rural' AND gender = 'female'"),
    EvaluationCase("school se bahar bachon ka sab se zyada rate", "ranking",
        "SELECT s.geography, s.out_of_school_pct AS value, s.source_row FROM school_participation AS s JOIN geography_catalog AS g ON s.geography = g.name WHERE s.area_type IS NULL AND s.gender IS NULL ORDER BY value DESC, s.geography"),
    EvaluationCase("out of school children ka average", "aggregation",
        "SELECT ROUND(AVG(out_of_school_pct), 2) AS value FROM school_participation WHERE area_type IS NULL AND gender IS NULL"),
    EvaluationCase("Punjab ka rate kya hai?", "ambiguous", None, True),
)


def run_evaluation() -> dict[str, Any]:
    agent = UrduSQLAgent()
    buckets: dict[str, list[bool]] = {}
    clarification_ok = 0
    total_cost = 0.0
    execution_ok = 0
    sql_matches = 0
    for case in CASES:
        answer = agent.ask(case.question)
        total_cost += answer["cost_usd_estimate"]
        if case.expects_clarification:
            clarification_ok += answer["status"] == "clarification_needed"
            continue
        passed = answer["status"] == "answered" and answer["verification"]["valid"]
        execution_ok += passed
        sql_matches += answer.get("sql") == case.gold_sql
        buckets.setdefault(case.difficulty, []).append(passed)

    # Inject a deliberately mixed-grain statement to exercise the deterministic repair path.
    broken = "SELECT ROUND(AVG(out_of_school_pct), 2) AS value FROM school_participation WHERE geography = 'Punjab'"
    repaired = agent._repair(broken, {"valid": False})
    repair_success = bool(repaired and agent._verify(repaired)["valid"])
    non_clarifications = len(CASES) - sum(c.expects_clarification for c in CASES)
    return {
        "dataset": "PBS Education Table 1 (45 flattened source rows)",
        "cases": len(CASES),
        "execution_accuracy": execution_ok / non_clarifications,
        "gold_sql_accuracy": sql_matches / non_clarifications,
        "repair_success_rate": float(repair_success),
        "clarification_quality": clarification_ok / sum(c.expects_clarification for c in CASES),
        "cost_per_query_usd": total_cost / len(CASES),
        "by_difficulty": {level: sum(results) / len(results) for level, results in buckets.items()},
        "notes": "Deterministic prototype; cost is zero because it uses no hosted model. Replace the planner with an LLM and retain the verifier for production.",
    }
