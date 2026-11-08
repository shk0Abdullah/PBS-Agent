from decimal import Decimal
from pathlib import Path

from tds.ingestion.table_01 import parse_table_01


PROJECT_ROOT = Path(__file__).parents[2]
TABLE_01 = PROJECT_ROOT / (
    "edu/Table-1-Population-10-Year-and-older-that-has-Ever-Attended-School-"
    "completed-primary-and-out-of-school-by-Province-Region-and-Gender.xlsx"
)


def test_parse_table_01_flattens_the_observed_hierarchy() -> None:
    observations = parse_table_01(TABLE_01)

    assert len(observations) == 45

    pakistan_total = observations[0]
    assert pakistan_total.worksheet_row_number == 5
    assert pakistan_total.geography_name == "Pakistan"
    assert pakistan_total.area_type is None
    assert pakistan_total.gender is None
    assert pakistan_total.ever_attended_pct == Decimal("67")

    pakistan_urban_male = observations[4]
    assert pakistan_urban_male.worksheet_row_number == 9
    assert pakistan_urban_male.geography_name == "Pakistan"
    assert pakistan_urban_male.area_type == "urban"
    assert pakistan_urban_male.gender == "male"
    assert pakistan_urban_male.completed_primary_pct == Decimal("73")

    balochistan_rural_female = observations[-1]
    assert balochistan_rural_female.worksheet_row_number == 49
    assert balochistan_rural_female.geography_name == "Balochistan"
    assert balochistan_rural_female.area_type == "rural"
    assert balochistan_rural_female.gender == "female"
    assert balochistan_rural_female.out_of_school_pct == Decimal("57")
