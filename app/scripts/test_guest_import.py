from __future__ import annotations

from pathlib import Path

from app.importers.guest_import_service import GuestImportError, import_guest_file


def main() -> None:
    file_path = Path("sample_guests.csv")

    try:
        result = import_guest_file(file_path)
    except GuestImportError as exc:
        print(f"Import failed: {exc}")
        return

    print("\nVALID ROWS")
    print("-" * 50)

    for row in result.valid_rows:
        print(
            f"Row {row.row_number}: "
            f"name={row.name}, "
            f"phone={row.normalized_phone}, "
            f"guests={row.guests_count}"
        )

    print("\nINVALID ROWS")
    print("-" * 50)

    for row in result.invalid_rows:
        print(f"Row {row.row_number}: {', '.join(row.errors)}")
        print(f"Raw data: {row.raw_data}")
        print()


if __name__ == "__main__":
    main()