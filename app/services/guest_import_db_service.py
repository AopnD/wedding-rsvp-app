from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.importers.guest_import_service import import_guest_file
from app.importers.guest_validator import ValidGuestRow
from app.models import Guest
from app.services.invite_code_service import generate_unique_invite_code


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GuestDatabaseImportResult:
    saved_count: int
    invalid_count: int
    duplicate_count: int


def import_valid_guest_rows_to_database(
    db: Session,
    valid_rows: list[ValidGuestRow],
    event_id: int,
    invalid_count: int = 0,
) -> GuestDatabaseImportResult:
    """
    Save already-validated guest rows to the database.

    Safety behavior:
    - Only saves valid rows.
    - Skips phone numbers that already exist for the same event.
    - Prevents duplicate imports if the same file is imported twice.
    - Creates one private invite code per saved guest.
    """

    existing_phone_numbers = {
        phone_number
        for (phone_number,) in db.query(Guest.phone_number)
        .filter(Guest.event_id == event_id)
        .all()
        if phone_number
    }

    saved_count = 0
    duplicate_count = 0

    for valid_row in valid_rows:
        if valid_row.normalized_phone in existing_phone_numbers:
            duplicate_count += 1
            continue

        guest = Guest(
            event_id=event_id,
            full_name=valid_row.name,
            phone_number=valid_row.normalized_phone,
            telegram_username=None,
            invite_code=generate_unique_invite_code(db),
            invited_count=valid_row.guests_count,
            is_matched_telegram_contact=False,
        )

        db.add(guest)
        existing_phone_numbers.add(valid_row.normalized_phone)
        saved_count += 1

    db.commit()

    logger.info(
        "Imported valid guests to database. event_id=%s saved=%s invalid=%s duplicates=%s",
        event_id,
        saved_count,
        invalid_count,
        duplicate_count,
    )

    return GuestDatabaseImportResult(
        saved_count=saved_count,
        invalid_count=invalid_count,
        duplicate_count=duplicate_count,
    )


def import_valid_guests_to_database(
    db: Session,
    file_path: str | Path,
    event_id: int,
    default_phone_region: str = "PT",
) -> GuestDatabaseImportResult:
    """
    Backwards-compatible helper for scripts.

    Reads, validates, and saves valid guests from a file.
    The UI should prefer import_valid_guest_rows_to_database()
    because it already has the validation result.
    """

    result = import_guest_file(
        file_path=file_path,
        default_phone_region=default_phone_region,
    )

    return import_valid_guest_rows_to_database(
        db=db,
        valid_rows=result.valid_rows,
        event_id=event_id,
        invalid_count=len(result.invalid_rows),
    )