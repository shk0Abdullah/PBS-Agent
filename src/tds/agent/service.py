"""A deliberately constrained Urdu/Roman Urdu Text-to-SQL agent.

This is a prototype planner, not a general-purpose LLM SQL executor.  Its
small intent grammar makes every generated statement auditable; the verifier
still parses, schema-checks, dry-runs, evaluates result plausibility, and can
repair a common unsafe aggregate-grain error.
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

import sqlglot
from sqlglot import exp

from tds.agent.dataset import create_database


ALLOWED_COLUMNS = {
    "source_row", "geography", "area_type", "gender", "ever_attended_pct",
    "completed_primary_pct", "out_of_school_pct", "value", "name",
}
METRICS = {
    "out": ("out_of_school_pct", "school se bahar bachay", "اسکول سے باہر بچے"),
    "bahar": ("out_of_school_pct", "school se bahar bachay", "اسکول سے باہر بچے"),
    "باہر": ("out_of_school_pct", "school se bahar bachay", "اسکول سے باہر بچے"),
    "school": ("ever_attended_pct", "school jane walay", "اسکول جانے والے"),
    "ever": ("ever_attended_pct", "school jane walay", "اسکول جانے والے"),
    "primary": ("completed_primary_pct", "primary mukammal karne walay", "پرائمری مکمل کرنے والے"),
    "پرائمری": ("completed_primary_pct", "primary mukammal karne walay", "پرائمری مکمل کرنے والے"),
    "اسکول": ("ever_attended_pct", "school jane walay", "اسکول جانے والے"),
}
GEOGRAPHIES = {
    "pakistan": "Pakistan", "پاکستان": "Pakistan", "punjab": "Punjab", "پنجاب": "Punjab",
    "sindh": "Sindh", "سندھ": "Sindh", "kpk": "Khyber Pakhtunkhwa",
    "khyber": "Khyber Pakhtunkhwa", "خیبر": "Khyber Pakhtunkhwa",
    "balochistan": "Balochistan", "بلوچستان": "Balochistan",
}


@dataclass
class Plan:
    metric: str
    metric_label: str
    metric_urdu: str
    geography: str | None
    area: str | None
    gender: str | None
    ranking: bool
    average: bool


class UrduSQLAgent:
    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self.connection = connection or create_database()

    def ask(self, question: str, include_chart: bool = False) -> dict[str, Any]:
        started = time.perf_counter()
        normalized = question.lower().strip()
        ambiguity = self._ambiguity(normalized)
        if ambiguity:
            return self._clarification(question, ambiguity, started)
        plan = self._plan(normalized)
        sql = self._generate(plan)
        verification = self._verify(sql)
        repaired = False
        if not verification["valid"]:
            repaired_sql = self._repair(sql, verification)
            if repaired_sql is None:
                return self._failure(question, sql, verification, started)
            sql = repaired_sql
            verification = self._verify(sql)
            repaired = True
        rows = [dict(row) for row in self.connection.execute(sql).fetchall()]
        suspicious = self._suspicious(rows, plan)
        if suspicious:
            verification["warnings"].extend(suspicious)
        result: dict[str, Any] = {
            "status": "answered", "question": question, "plan": self._plan_text(plan),
            "sql": sql, "verification": verification, "repaired": repaired,
            "result": rows, "answer_ur": self._answer_urdu(rows, plan),
            "provenance": "Pakistan Bureau of Statistics education Table 1; worksheet rows shown as source_row.",
            "cost_usd_estimate": 0.0,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
        if include_chart and rows:
            result["chart"] = self._chart(rows, plan)
        return result

    def _ambiguity(self, q: str) -> str | None:
        if not any(key in q for key in METRICS):
            return "Aap kis indicator ke baray mein pooch rahe hain: school attendance, primary completion, ya out-of-school children?"
        if any(word in q for word in ("male", "female", "mard", "aurat", "لڑکے", "لڑکیاں")) and not any(
            word in q for word in ("urban", "rural", "shehri", "dehati", "شہری", "دیہی")
        ):
            return "Gender ke liye area wazeh karein: urban ya rural?"
        return None

    def _plan(self, q: str) -> Plan:
        metric_key = next(key for key in METRICS if key in q)
        metric, label, urdu = METRICS[metric_key]
        geography = next((value for key, value in GEOGRAPHIES.items() if key in q), None)
        area = "urban" if any(x in q for x in ("urban", "shehri", "شہری")) else "rural" if any(x in q for x in ("rural", "dehati", "دیہی")) else None
        gender = "female" if any(x in q for x in ("female", "aurat", "لڑکیاں")) else "male" if any(x in q for x in ("male", "mard", "لڑکے")) else None
        ranking = any(x in q for x in ("sab se", "highest", "lowest", "rank", "zya", "kam", "زیادہ", "کم"))
        average = any(x in q for x in ("average", "ausat", "اوسط"))
        return Plan(metric, label, urdu, geography, area, gender, ranking, average)

    def _generate(self, plan: Plan) -> str:
        filters = []
        if plan.geography: filters.append(f"geography = '{plan.geography}'")
        if plan.area: filters.append(f"area_type = '{plan.area}'")
        if plan.gender: filters.append(f"gender = '{plan.gender}'")
        # The provenance table contains parent/child display rows.  A no-filter question
        # must use only province totals, never average mixed aggregation levels.
        if not plan.area and not plan.gender:
            filters.extend(["area_type IS NULL", "gender IS NULL"])
        where = " AND ".join(filters)
        if plan.average:
            return f"SELECT ROUND(AVG({plan.metric}), 2) AS value FROM school_participation WHERE {where}"
        if plan.ranking and not plan.geography:
            joined_where = where.replace("area_type", "s.area_type").replace("gender", "s.gender")
            return f"SELECT s.geography, s.{plan.metric} AS value, s.source_row FROM school_participation AS s JOIN geography_catalog AS g ON s.geography = g.name WHERE {joined_where} ORDER BY value DESC, s.geography"
        return f"SELECT geography, area_type, gender, {plan.metric} AS value, source_row FROM school_participation WHERE {where}"

    def _verify(self, sql: str) -> dict[str, Any]:
        outcome = {"valid": False, "checks": [], "warnings": []}
        try:
            tree = sqlglot.parse_one(sql, read="sqlite")
            if not isinstance(tree, exp.Select): raise ValueError("Only SELECT statements are permitted")
            if tree.find(exp.Insert) or tree.find(exp.Update) or tree.find(exp.Delete) or tree.find(exp.Drop): raise ValueError("Mutating SQL is prohibited")
            tables = {t.name for t in tree.find_all(exp.Table)}
            if tables not in ({"school_participation"}, {"school_participation", "geography_catalog"}): raise ValueError("Unknown table")
            if "geography_catalog" in tables:
                joins = list(tree.find_all(exp.Join))
                if not joins or "geography" not in joins[0].sql(dialect="sqlite"):
                    raise ValueError("Geography table is not linked through its key")
            columns = {c.name for c in tree.find_all(exp.Column)}
            unknown = columns - ALLOWED_COLUMNS
            if unknown: raise ValueError(f"Unknown columns: {sorted(unknown)}")
            self.connection.execute("EXPLAIN QUERY PLAN " + sql).fetchall()
            self.connection.execute(sql).fetchall()
            outcome["valid"] = True
            outcome["checks"] = ["SELECT-only AST", "schema links valid", "dry-run passed"]
        except (ValueError, sqlite3.Error, sqlglot.errors.ParseError) as exc:
            outcome["error"] = str(exc)
        return outcome

    def _repair(self, sql: str, verification: dict[str, Any]) -> str | None:
        # Common generator bug: mixing total and subgroup rows. Repair by anchoring grain.
        if "school_participation" in sql and "WHERE" in sql:
            return sql.replace("WHERE ", "WHERE area_type IS NULL AND gender IS NULL AND ", 1)
        return None

    def _suspicious(self, rows: list[dict[str, Any]], plan: Plan) -> list[str]:
        warnings = []
        for row in rows:
            if "value" in row and isinstance(row["value"], (int, float)) and not 0 <= row["value"] <= 100:
                warnings.append("Result outside the source percentage range.")
        if not rows: warnings.append("No matching source row; check geography or filters.")
        if plan.average and not plan.geography: warnings.append("Average is restricted to province-level totals to avoid mixed-grain aggregation.")
        return warnings

    def _plan_text(self, plan: Plan) -> str:
        filters = [x for x in [plan.geography, plan.area, plan.gender] if x]
        return f"{plan.metric_label}; filters: {', '.join(filters) or 'province totals'}"

    def _answer_urdu(self, rows: list[dict[str, Any]], plan: Plan) -> str:
        if not rows: return "Is sawal ke liye data mein koi mutabiq record nahin mila۔"
        if len(rows) == 1 and "value" in rows[0]:
            return f"{plan.metric_urdu} ka rate {rows[0]['value']}٪ hai۔"
        return f"{plan.metric_urdu} ke natayij neeche diye gaye hain۔"

    def _clarification(self, question: str, prompt: str, started: float) -> dict[str, Any]:
        return {"status": "clarification_needed", "question": question, "clarification_ur": prompt,
                "cost_usd_estimate": 0.0, "latency_ms": round((time.perf_counter() - started)*1000, 1)}

    def _failure(self, question: str, sql: str, verification: dict[str, Any], started: float) -> dict[str, Any]:
        return {"status": "verification_failed", "question": question, "sql": sql, "verification": verification,
                "answer_ur": "Query tasdeeq se guzar nahin saki, is liye koi jawab nahin diya gaya۔",
                "cost_usd_estimate": 0.0, "latency_ms": round((time.perf_counter() - started)*1000, 1)}

    def _chart(self, rows: list[dict[str, Any]], plan: Plan) -> dict[str, Any]:
        points = [{"label": r.get("geography", "average"), "value": r["value"]} for r in rows if r.get("value") is not None]
        return {"type": "bar", "title_ur": plan.metric_urdu, "unit": "percent", "data": points}
