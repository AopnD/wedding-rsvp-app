from __future__ import annotations

import logging
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

import uvicorn

# IMPORTANT:
# Import the FastAPI app object directly.
# Do NOT pass "app.backend.api:app" as a string in the packaged app.
# PyInstaller can miss dynamic import strings, causing:
# ModuleNotFoundError: No module named 'app.backend'
from app.backend.api import app as fastapi_app
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
    - The local FastAPI RSVP server runs inside this desktop app process
      on a background thread.
    - The public Cloudflare tunnel runs as a separate cloudflared process.
    - The public URL is kept in memory while the desktop app is open.
    """

    def __init__(self) -> None:
        self._server: uvicorn.Server | None = None
        self._server_thread: threading.Thread | None = None
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
        Start the local FastAPI RSVP server if it is not already running.

        Packaging rules:
        - Do not start this with sys.executable -m uvicorn.
          In PyInstaller, sys.executable is LocalWeddingRSVP.exe,
          which opens another desktop app window.
        - Do not pass the app as "app.backend.api:app".
          PyInstaller may miss that dynamic import.
        """

        if self.is_server_running():
            logger.info("RSVP server already running at %s", LOCAL_BASE_URL)
            return

        if self._server_thread is not None and self._server_thread.is_alive():
            logger.info("RSVP server thread exists; waiting for health check.")
            self._wait_for_server_health()
            return

        logger.info("Starting RSVP server in background thread at %s", LOCAL_BASE_URL)

        try:
            config = uvicorn.Config(
                app=fastapi_app,
                host=LOCAL_HOST,
                port=LOCAL_PORT,
                log_level="warning",
                access_log=False,
                log_config=None,
                lifespan="on",
            )

            self._server = uvicorn.Server(config=config)

            self._server_thread = threading.Thread(
                target=self._run_server,
                name="rsvp-server",
                daemon=True,
            )

            self._server_thread.start()
            self._wait_for_server_health()

            logger.info("RSVP server started successfully at %s", LOCAL_BASE_URL)

        except RsvpRuntimeError:
            raise

        except Exception as exc:
            logger.exception("Failed to start RSVP server.")
            raise RsvpRuntimeError(
                "Could not start the local RSVP server. "
                "Check data/logs/app.log for details."
            ) from exc

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
        """

        logger.info("Stopping RSVP runtime.")

        if self._tunnel is not None:
            try:
                stop_tunnel(self._tunnel)
            except Exception:
                logger.exception("Failed to stop public RSVP tunnel.")
            finally:
                self._tunnel = None

        if self._server is not None:
            logger.info("Stopping RSVP server.")
            self._server.should_exit = True

        if self._server_thread is not None and self._server_thread.is_alive():
            self._server_thread.join(timeout=10)

            if self._server_thread.is_alive():
                logger.warning("RSVP server thread did not stop within timeout.")

        self._server = None
        self._server_thread = None

    def _run_server(self) -> None:
        if self._server is None:
            return

        try:
            self._server.run()
        except Exception:
            logger.exception("RSVP server crashed.")

    def _wait_for_server_health(self, timeout_seconds: int = 15) -> None:
        started_at = time.monotonic()

        while time.monotonic() - started_at < timeout_seconds:
            if _is_health_check_ok():
                return

            if self._server_thread is not None and not self._server_thread.is_alive():
                raise RsvpRuntimeError(
                    "The RSVP server stopped while starting. "
                    "Check data/logs/app.log for details."
                )

            time.sleep(0.5)

        raise RsvpRuntimeError(
            "Timed out while starting the RSVP server. "
            "Check data/logs/app.log for details."
        )


def _is_health_check_ok() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1) as response:
            return 200 <= response.status < 300

    except (urllib.error.URLError, TimeoutError, OSError):
        return False