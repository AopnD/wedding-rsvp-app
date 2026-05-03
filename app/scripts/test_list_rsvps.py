from __future__ import annotations

from app.core.database import SessionLocal
from app.models import Guest, Rsvp


def main() -> None:
    db = SessionLocal()

    try:
        rsvps = (
            db.query(Rsvp)
            .join(Guest)
            .order_by(Rsvp.submitted_at.desc())
            .all()
        )

        print(f"Total RSVP responses: {len(rsvps)}")
        print("-" * 50)

        for rsvp in rsvps:
            print(
                f"id={rsvp.id}, "
                f"guest={rsvp.guest.full_name}, "
                f"response={rsvp.response}, "
                f"attending_count={rsvp.attending_count}, "
                f"notes={rsvp.notes}, "
                f"submitted_at={rsvp.submitted_at}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()