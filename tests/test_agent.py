from tds.agent.service import UrduSQLAgent
from tds.agent.evaluation import run_evaluation


def test_urdu_question_returns_verified_gold_sql() -> None:
    response = UrduSQLAgent().ask("Punjab mein school se bahar bachay kitne hain?")
    assert response["status"] == "answered"
    assert response["sql"] == (
        "SELECT geography, area_type, gender, out_of_school_pct AS value, source_row "
        "FROM school_participation WHERE geography = 'Punjab' AND area_type IS NULL AND gender IS NULL"
    )
    assert response["verification"]["valid"] is True
    assert response["result"][0]["value"] == 21.0


def test_subgroup_query_has_gold_filter() -> None:
    response = UrduSQLAgent().ask("Punjab rural female primary completion")
    assert "geography = 'Punjab' AND area_type = 'rural' AND gender = 'female'" in response["sql"]
    assert response["verification"]["valid"]


def test_ranking_uses_only_province_totals_and_chart() -> None:
    response = UrduSQLAgent().ask("school se bahar bachon ka sab se zyada rate", include_chart=True)
    assert "s.area_type IS NULL AND s.gender IS NULL" in response["sql"]
    assert "JOIN geography_catalog" in response["sql"]
    assert len(response["result"]) == 5
    assert response["chart"]["type"] == "bar"


def test_missing_indicator_requests_clarification() -> None:
    response = UrduSQLAgent().ask("Punjab ka rate kya hai?")
    assert response["status"] == "clarification_needed"


def test_verifier_rejects_unknown_column() -> None:
    verdict = UrduSQLAgent()._verify("SELECT secret FROM school_participation")
    assert verdict["valid"] is False


def test_evaluation_reports_required_metrics() -> None:
    report = run_evaluation()
    assert report["execution_accuracy"] == 1.0
    assert report["repair_success_rate"] == 1.0
    assert report["clarification_quality"] == 1.0
