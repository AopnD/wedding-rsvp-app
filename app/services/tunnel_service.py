from __future__ import annotations

import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path


logger = logging.getLogger(__name__)


PUBLIC_URL_PATTERN = re.compile(r"https://[-a-zA-Z0-9.]+\.trycloudflare\.com")


class TunnelError(Exception):
    """Raised when the public tunnel cannot be started."""


@dataclass
class TunnelProcess:
    public_url: str
    process: subprocess.Popen[str]
    cloudflared_path: Path


def get_cloudflared_path() -> Path:
    """
    Find cloudflared.

    Priority:
    1. Existing cloudflared installed on the system PATH.
    2. Local app-managed cloudflared binary under data/bin.
    3. Download cloudflared for the current OS.
    """

    existing_path = shutil.which("cloudflared")

    if existing_path:
        logger.info("Using system cloudflared: %s", existing_path)
        return Path(existing_path)

    local_path = _get_local_cloudflared_path()

    if local_path.exists():
        logger.info("Using local cloudflared: %s", local_path)
        return local_path

    return download_cloudflared(local_path)


def download_cloudflared(destination_path: Path) -> Path:
    """
    Download cloudflared into the local data/bin folder.

    Alpha support:
    - Windows 64-bit
    - Linux 64-bit

    Later, we can add macOS and ARM builds if needed.
    """

    system_name = platform.system().lower()
    machine = platform.machine().lower()

    if machine not in {"amd64", "x86_64"}:
        raise TunnelError(
            f"Unsupported CPU architecture for automatic cloudflared download: {machine}"
        )

    if system_name == "windows":
        download_url = (
            "https://github.com/cloudflare/cloudflared/releases/latest/download/"
            "cloudflared-windows-amd64.exe"
        )
    elif system_name == "linux":
        download_url = (
            "https://github.com/cloudflare/cloudflared/releases/latest/download/"
            "cloudflared-linux-amd64"
        )
    else:
        raise TunnelError(
            f"Unsupported operating system for automatic cloudflared download: {system_name}"
        )

    destination_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading cloudflared from %s", download_url)
    logger.info("Saving cloudflared to %s", destination_path)

    try:
        urllib.request.urlretrieve(download_url, destination_path)
    except Exception as exc:
        raise TunnelError(
            "Could not download cloudflared. "
            "Please check your internet connection or install cloudflared manually."
        ) from exc

    if system_name == "linux":
        current_mode = destination_path.stat().st_mode
        destination_path.chmod(current_mode | stat.S_IEXEC)

    return destination_path


def start_quick_tunnel(
    local_url: str = "http://127.0.0.1:8000",
    timeout_seconds: int = 45,
) -> TunnelProcess:
    """
    Start a Cloudflare Quick Tunnel and return the public URL.

    This keeps the cloudflared process running.
    When the process stops, the public URL stops working.
    """

    cloudflared_path = get_cloudflared_path()

    command = [
        str(cloudflared_path),
        "tunnel",
        "--url",
        local_url,
    ]

    logger.info("Starting cloudflared tunnel for %s", local_url)

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        raise TunnelError("Could not start cloudflared.") from exc

    public_url = _wait_for_public_url(
        process=process,
        timeout_seconds=timeout_seconds,
    )

    logger.info("Cloudflare tunnel started. public_url=%s", public_url)

    return TunnelProcess(
        public_url=public_url,
        process=process,
        cloudflared_path=cloudflared_path,
    )


def stop_tunnel(tunnel_process: TunnelProcess) -> None:
    """
    Stop a running cloudflared process.
    """

    process = tunnel_process.process

    if process.poll() is not None:
        return

    logger.info("Stopping cloudflared tunnel.")

    process.terminate()

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        logger.warning("cloudflared did not stop gracefully; killing process.")
        process.kill()


def _wait_for_public_url(
    process: subprocess.Popen[str],
    timeout_seconds: int,
) -> str:
    assert process.stdout is not None

    started_at = time.monotonic()
    collected_output: list[str] = []

    while time.monotonic() - started_at < timeout_seconds:
        if process.poll() is not None:
            output = "".join(collected_output)
            raise TunnelError(
                "cloudflared stopped before creating a public URL.\n"
                f"Output:\n{output}"
            )

        line = process.stdout.readline()

        if not line:
            time.sleep(0.2)
            continue

        collected_output.append(line)
        logger.info("cloudflared: %s", line.strip())

        match = PUBLIC_URL_PATTERN.search(line)

        if match:
            return match.group(0)

    output = "".join(collected_output)

    raise TunnelError(
        "Timed out while waiting for cloudflared public URL.\n"
        f"Output:\n{output}"
    )


def _get_local_cloudflared_path() -> Path:
    from app.core.config import DATA_DIR

    bin_dir = DATA_DIR / "bin"

    if platform.system().lower() == "windows":
        return bin_dir / "cloudflared.exe"

    return bin_dir / "cloudflared"