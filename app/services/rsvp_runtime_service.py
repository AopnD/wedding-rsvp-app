from __future__ import annotations

import logging
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from app.core.config import DATA_DIR
from app.services.tunnel_service import TunnelProcess, start_quick_tunnel, stop_tunnel


logger = logging.getLogger(__name__)


LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 8000
LOCAL_BASE_URL = f"http://{LOCAL_HOST}:{LOCAL_PORT}"
HEALTH_URL = f"{LOCAL_BASE_URL}/health"


class RsvpRuntimeError(Exception):
    """Raised when the local RSVP runtime cannot start or stop cleanly."""


@dataclass(frozen=True)
class RsvpRuntimeStatus:
    server_running: bool
    tunnel_running: bool
    local_base_url: str
    public_base_url: str | None


class RsvpRuntimeManager:
    """
    Manages the local RSVP server and public Cloudflare tunnel.

    Alpha behavior:
    - The local FastAPI RSVP server runs as a subprocess.
    - The public tunnel is started only when the user clicks a button.
    - The public URL is kept in memory while the desktop app is open.
    """

    def __init__(self) -> None:
        self._server_process: subprocess.Popen[str] | None = None
        self._server_log_file: TextIO | None = None
        self._tunnel: TunnelProcess | None = None

    @property
    def public_base_url(self) -> str | None:
        if self._tunnel is None:
            return None

        if self._tunnel.process.poll() is not None:
            logger.warning("Tunnel process is no longer running.")
            self._tunnel = None
            return None

        return self._tunnel.public_url

    def get_status(self) -> RsvpRuntimeStatus:
        return RsvpRuntimeStatus(
            server_running=self.is_server_running(),
            tunnel_running=self.is_tunnel_running(),
            local_base_url=LOCAL_BASE_URL,
            public_base_url=self.public_base_url,
        )

    def is_server_running(self) -> bool:
        """
        Return True if the RSVP server responds to /health.

        This works even if the server was started earlier by this manager
        and is safer than checking only the subprocess state.
        """

        return _is_health_check_ok()

    def is_tunnel_running(self) -> bool:
        if self._tunnel is None:
            return False

        if self._tunnel.process.poll() is not None:
            logger.warning("Tunnel process stopped.")
            self._tunnel = None
            return False

        return True

    def start_server_if_needed(self) -> None:
        """
        Start uvicorn for the local FastAPI RSVP server if it is not already running.
        """

        if self.is_server_running():
            logger.info("RSVP server already running at %s", LOCAL_BASE_URL)
            return

        if self._server_process is not None and self._server_process.poll() is None:
            logger.info("RSVP server process exists; waiting for health check.")
            self._wait_for_server_health()
            return

        logs_dir = DATA_DIR / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        server_log_path = logs_dir / "rsvp_server.log"
        self._server_log_file = server_log_path.open("a", encoding="utf-8")

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
        logger.info("RSVP server logs: %s", server_log_path)

        creation_flags = 0

        if platform.system().lower() == "windows":
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            self._server_process = subprocess.Popen(
                command,
                stdout=self._server_log_file,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creation_flags,
            )
        except Exception as exc:
            self._close_server_log_file()
            raise RsvpRuntimeError("Could not start the local RSVP server.") from exc

        self._wait_for_server_health()

        logger.info("RSVP server started successfully at %s", LOCAL_BASE_URL)

    def start_public_tunnel_if_needed(self) -> str:
        """
        Start a public Cloudflare tunnel if needed and return the public base URL.
        """

        self.start_server_if_needed()

        existing_public_url = self.public_base_url

        if existing_public_url:
            logger.info("Public RSVP tunnel already running: %s", existing_public_url)
            return existing_public_url

        logger.info("Starting public RSVP tunnel for %s", LOCAL_BASE_URL)

        try:
            self._tunnel = start_quick_tunnel(local_url=LOCAL_BASE_URL)
        except Exception as exc:
            logger.exception("Failed to start public RSVP tunnel.")
            raise RsvpRuntimeError(f"Could not start public RSVP tunnel: {exc}") from exc

        logger.info("Public RSVP tunnel started: %s", self._tunnel.public_url)

        return self._tunnel.public_url

    def stop_all(self) -> None:
        """
        Stop the public tunnel and local RSVP server.

        This is called when the desktop app exits.
        """

        logger.info("Stopping RSVP runtime.")

        if self._tunnel is not None:
            try:
                stop_tunnel(self._tunnel)
            except Exception:
                logger.exception("Failed to stop public RSVP tunnel.")
            finally:
                self._tunnel = None

        if self._server_process is not None and self._server_process.poll() is None:
            logger.info("Stopping RSVP server process.")

            self._server_process.terminate()

            try:
                self._server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("RSVP server did not stop gracefully; killing process.")
                self._server_process.kill()

        self._server_process = None
        self._close_server_log_file()

    def _wait_for_server_health(self, timeout_seconds: int = 15) -> None:
        started_at = time.monotonic()

        while time.monotonic() - started_at < timeout_seconds:
            if self._server_process is not None and self._server_process.poll() is not None:
                raise RsvpRuntimeError(
                    "The RSVP server stopped while starting. "
                    "Check data/logs/rsvp_server.log for details."
                )

            if _is_health_check_ok():
                return

            time.sleep(0.5)

        raise RsvpRuntimeError(
            "Timed out while starting the RSVP server. "
            "Check data/logs/rsvp_server.log for details."
        )

    def _close_server_log_file(self) -> None:
        if self._server_log_file is None:
            return

        try:
            self._server_log_file.close()
        except Exception:
            logger.exception("Failed to close RSVP server log file.")
        finally:
            self._server_log_file = None


def _is_health_check_ok() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1) as response:
            return 200 <= response.status < 300

    except (urllib.error.URLError, TimeoutError, OSError):
        return False