from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.importers.guest_import_service import import_guest_file
from app.models import Guest


logger = logging.getLogger(__name__)


def import_valid_guests_to_database(
    db: Session,
    file_path: str | Path,
    event_id: int,
    default_phone_region: str = "PT",
) -> tuple[int, int]:
    """
    Import a guest file, validate it, and save only valid rows to the database.

    Only valid rows are saved.
    Invalid rows are skipped.

    Returns:
        tuple[int, int]:
        - number of saved guests
        - number of invalid rows
    """

    result = import_guest_file(
        file_path=file_path,
        default_phone_region=default_phone_region,
    )

    saved_count = 0

    for valid_row in result.valid_rows:
        guest = Guest(
            event_id=event_id,
            full_name=valid_row.name,
            phone_number=valid_row.normalized_phone,
            telegram_username=None,
            invited_count=valid_row.guests_count,
            is_matched_telegram_contact=False,
        )

        db.add(guest)
        saved_count += 1

    db.commit()

    logger.info(
        "Imported valid guests to database. saved=%s invalid=%s file=%s",
        saved_count,
        len(result.invalid_rows),
        file_path,
    )

    return saved_count, len(result.invalid_rows)