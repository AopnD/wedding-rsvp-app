from __future__ import annotations

import logging
import subprocess
import sys
import time

from app.core.database import SessionLocal, create_database
from app.models import Event
from app.services.link_service import list_guest_rsvp_links
from app.services.tunnel_service import TunnelError, start_quick_tunnel, stop_tunnel


LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 8000
LOCAL_URL = f"http://{LOCAL_HOST}:{LOCAL_PORT}"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    create_database()

    server_process: subprocess.Popen[str] | None = None
    tunnel = None

    try:
        event_id = _get_latest_event_id()

        if event_id is None:
            print("No event found in the database.")
            print("Import guests from the UI first, then run this script again.")
            return

        server_process = _start_rsvp_server()
        _wait_for_server_startup()

        tunnel = start_quick_tunnel(local_url=LOCAL_URL)

        print()
        print("=" * 80)
        print("PUBLIC RSVP TUNNEL IS RUNNING")
        print("=" * 80)
        print(f"Public base URL: {tunnel.public_url}")
        print()
        print("Personalized RSVP links:")
        print("-" * 80)

        db = SessionLocal()

        try:
            links = list_guest_rsvp_links(
                db=db,
                event_id=event_id,
                public_base_url=tunnel.public_url,
            )

            if not links:
                print("No guests found for the latest event.")
            else:
                for link in links:
                    print(f"{link.guest_name} | {link.phone_number or ''}")
                    print(link.public_rsvp_url)
                    print()

        finally:
            db.close()

        print("-" * 80)
        print("Keep this PowerShell window open while guests are using the RSVP links.")
        print("Press CTRL+C to stop the public tunnel and local RSVP server.")
        print("=" * 80)
        print()

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print("Stopping public RSVP server...")

    except TunnelError as exc:
        logger.exception("Tunnel failed.")
        print(f"Tunnel failed: {exc}")

    except Exception:
        logger.exception("Unexpected error while running public RSVP.")
        print("Something went wrong while running the public RSVP tunnel.")

    finally:
        if tunnel is not None:
            stop_tunnel(tunnel)

        if server_process is not None and server_process.poll() is None:
            server_process.terminate()

            try:
                server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_process.kill()


def _start_rsvp_server() -> subprocess.Popen[str]:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.backend.api:app",
        "--host",
        LOCAL_HOST,
        "--port",
        str(LOCAL_PORT),
    ]

    logger.info("Starting RSVP server: %s", " ".join(command))

    return subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _wait_for_server_startup() -> None:
    """
    Simple alpha wait.

    Later we can replace this with an HTTP /health check.
    """

    time.sleep(2)


def _get_latest_event_id() -> int | None:
    db = SessionLocal()

    try:
        event = (
            db.query(Event)
            .order_by(Event.id.desc())
            .first()
        )

        if event is None:
            return None

        return event.id

    finally:
        db.close()


if __name__ == "__main__":
    main()