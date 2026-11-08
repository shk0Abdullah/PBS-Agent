"""Parser for the inspected layout of education source Table 1."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

from openpyxl import load_workbook


DATA_START_ROW: Final = 5
DATA_END_ROW: Final = 49
EXPECTED_TITLE: Final = "Table 1"
GENDERS: Final = {"Male": "male", "Female": "female"}
AREA_TYPES: Final = {"Urban": "urban", "Rural": "rural"}


class Table01ParseError(ValueError):
    """Raised when the workbook does not match the inspected Table 1 layout."""


@dataclass(frozen=True)
class Table01Observation:
    worksheet_row_number: int
    geography_name: str
    area_type: str | None
    gender: str | None
    ever_attended_pct: Decimal
    completed_primary_pct: Decimal
    out_of_school_pct: Decimal


def parse_table_01(workbook_path: Path) -> list[Table01Observation]:
    """Read Table 1 without changing the workbook and flatten its row context."""
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        worksheet = workbook.active
        title = worksheet.cell(row=3, column=2).value
        if title != EXPECTED_TITLE:
            raise Table01ParseError(
                f"expected {EXPECTED_TITLE!r} in B3, found {title!r}"
            )

        observations: list[Table01Observation] = []
        geography_name: str | None = None
        area_type: str | None = None

        for row_number in range(DATA_START_ROW, DATA_END_ROW + 1):
            label, ever_attended, completed_primary, out_of_school = (
                worksheet.cell(row=row_number, column=column).value
                for column in range(2, 6)
            )
            if not isinstance(label, str) or not label.strip():
                raise Table01ParseError(f"row {row_number}: missing row label")
            label = label.strip()

            if label in GENDERS:
                if geography_name is None:
                    raise Table01ParseError(
                        f"row {row_number}: gender has no geography context"
                    )
                gender = GENDERS[label]
            elif label in AREA_TYPES:
                if geography_name is None:
                    raise Table01ParseError(
                        f"row {row_number}: area has no geography context"
                    )
                area_type = AREA_TYPES[label]
                gender = None
            else:
                geography_name = label
                area_type = None
                gender = None

            observations.append(
                Table01Observation(
                    worksheet_row_number=row_number,
                    geography_name=geography_name,
                    area_type=area_type,
                    gender=gender,
                    ever_attended_pct=_percentage(ever_attended, row_number, "ever attended"),
                    completed_primary_pct=_percentage(
                        completed_primary, row_number, "completed primary"
                    ),
                    out_of_school_pct=_percentage(
                        out_of_school, row_number, "out of school"
                    ),
                )
            )

        return observations
    finally:
        workbook.close()


def _percentage(value: object, row_number: int, field_name: str) -> Decimal:
    try:
        percentage = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise Table01ParseError(
            f"row {row_number}: invalid {field_name} percentage {value!r}"
        ) from error

    if not Decimal("0") <= percentage <= Decimal("100"):
        raise Table01ParseError(
            f"row {row_number}: {field_name} percentage outside 0–100: {percentage}"
        )
    return percentage
