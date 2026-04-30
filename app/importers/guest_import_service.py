from __future__ import annotations

import logging
from pathlib import Path

from app.importers.guest_file_reader import GuestFileReadError, read_guest_file
from app.importers.guest_validator import ValidationResult, validate_guest_rows


logger = logging.getLogger(__name__)


class GuestImportError(Exception):
    """Raised when guest import fails."""


def import_guest_file(
    file_path: str | Path,
    default_phone_region: str = "PT",
) -> ValidationResult:
    """
    Import and validate a guest file.

    This function is the main entry point the UI will call later.
    """

    try:
        rows, columns = read_guest_file(file_path)
    except GuestFileReadError as exc:
        logger.exception("Failed to read guest file: %s", file_path)
        raise GuestImportError(str(exc)) from exc

    logger.info(
        "Guest file loaded. file=%s rows=%s columns=%s",
        file_path,
        len(rows),
        sorted(columns),
    )

    result = validate_guest_rows(
        rows=rows,
        columns=columns,
        default_region=default_phone_region,
    )

    logger.info(
        "Guest file validated. valid_rows=%s invalid_rows=%s missing_columns=%s",
        len(result.valid_rows),
        len(result.invalid_rows),
        result.missing_columns,
    )

    return result