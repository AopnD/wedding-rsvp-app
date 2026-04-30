from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import phonenumbers


REQUIRED_COLUMNS = {"name", "phone_number", "guests_count"}


@dataclass(frozen=True)
class ValidGuestRow:
    row_number: int
    name: str
    phone_number: str
    normalized_phone: str
    guests_count: int


@dataclass(frozen=True)
class InvalidGuestRow:
    row_number: int
    raw_data: dict[str, Any]
    errors: list[str]


@dataclass(frozen=True)
class ValidationResult:
    valid_rows: list[ValidGuestRow]
    invalid_rows: list[InvalidGuestRow]
    missing_columns: list[str]


def validate_guest_rows(
    rows: list[dict[str, Any]],
    columns: set[str],
    default_region: str = "PT",
) -> ValidationResult:
    """
    Validate imported guest rows.

    Required columns:
    - name
    - phone_number
    - guests_count

    Validation rules:
    - missing columns
    - invalid phone
    - duplicate phone
    - empty name
    - invalid guest count
    """

    missing_columns = sorted(REQUIRED_COLUMNS - columns)

    if missing_columns:
        return ValidationResult(
            valid_rows=[],
            invalid_rows=[
                InvalidGuestRow(
                    row_number=0,
                    raw_data={},
                    errors=[f"Missing required columns: {', '.join(missing_columns)}"],
                )
            ],
            missing_columns=missing_columns,
        )

    valid_rows: list[ValidGuestRow] = []
    invalid_rows: list[InvalidGuestRow] = []

    seen_phone_numbers: set[str] = set()

    for row in rows:
        row_number = int(row.get("_row_number", 0))
        errors: list[str] = []

        name = _clean_string(row.get("name"))
        phone_number = _clean_string(row.get("phone_number"))
        guests_count_raw = row.get("guests_count")

        if not name:
            errors.append("Name is empty")

        normalized_phone = _normalize_phone_number(
            phone_number=phone_number,
            default_region=default_region,
        )

        if not normalized_phone:
            errors.append("Phone number is invalid")
        elif normalized_phone in seen_phone_numbers:
            errors.append("Duplicate phone number")

        guests_count = _parse_guests_count(guests_count_raw)

        if guests_count is None:
            errors.append("Guest count is invalid")
        elif guests_count < 1:
            errors.append("Guest count must be at least 1")
        elif guests_count > 20:
            errors.append("Guest count is unusually high; max allowed is 20")

        if errors:
            invalid_rows.append(
                InvalidGuestRow(
                    row_number=row_number,
                    raw_data=row,
                    errors=errors,
                )
            )
            continue

        assert guests_count is not None
        assert normalized_phone is not None

        seen_phone_numbers.add(normalized_phone)

        valid_rows.append(
            ValidGuestRow(
                row_number=row_number,
                name=name,
                phone_number=phone_number,
                normalized_phone=normalized_phone,
                guests_count=guests_count,
            )
        )

    return ValidationResult(
        valid_rows=valid_rows,
        invalid_rows=invalid_rows,
        missing_columns=[],
    )


def _clean_string(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _parse_guests_count(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None

    value_as_text = str(value).strip()

    if not value_as_text:
        return None

    if not value_as_text.isdigit():
        return None

    return int(value_as_text)


def _normalize_phone_number(
    phone_number: str,
    default_region: str,
) -> str | None:
    """
    Normalize phone numbers into E.164 format.

    Example:
    +351912345678 stays +351912345678.
    A local Portuguese number like 912345678 becomes +351912345678
    when default_region='PT'.
    """

    if not phone_number:
        return None

    try:
        parsed_number = phonenumbers.parse(phone_number, default_region)
    except phonenumbers.NumberParseException:
        return None

    if not phonenumbers.is_valid_number(parsed_number):
        return None

    return phonenumbers.format_number(
        parsed_number,
        phonenumbers.PhoneNumberFormat.E164,
    )