from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

import requests

from .config import APP_VERSION, GITHUB_REPO, UPDATE_CHECK_INTERVAL_SECONDS


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse version strings like 'v1.2.0', '1.2.0-rc1' into a tuple of ints (1, 2, 0)."""
    cleaned = str(version_str).strip().lstrip("vV")
    match = re.match(r"^(\d+(?:\.\d+)*)", cleaned)
    if not match:
        return (0,)
    parts: list[int] = []
    for num in match.group(1).split("."):
        try:
            parts.append(int(num))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


def is_newer_version(remote_ver: str, local_ver: str) -> bool:
    """Return True if remote_ver is strictly greater than local_ver."""
    r_parts = parse_version(remote_ver)
    l_parts = parse_version(local_ver)
    max_len = max(len(r_parts), len(l_parts))
    r_padded = r_parts + (0,) * (max_len - len(r_parts))
    l_padded = l_parts + (0,) * (max_len - len(l_parts))
    return r_padded > l_padded


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    name: str
    html_url: str
    body: str
    published_at: str
    is_newer: bool
    download_url: str = ""


def fetch_latest_release(
    repo: str = GITHUB_REPO,
    current_version: str = APP_VERSION,
    timeout: int = 6,
) -> ReleaseInfo | None:
    """Check GitHub releases API for the latest release."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {
        "User-Agent": f"Bisik-Desktop/{current_version}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            tag = str(data.get("tag_name", "")).strip()
            name = str(data.get("name", tag)).strip()
            html_url = str(data.get("html_url", f"https://github.com/{repo}/releases/latest")).strip()
            body = str(data.get("body", "")).strip()
            published_at = str(data.get("published_at", "")).strip()

            download_url = html_url
            assets = data.get("assets", [])
            for asset in assets:
                asset_name = str(asset.get("name", "")).lower()
                if asset_name.endswith(".exe") or asset_name.endswith(".zip"):
                    download_url = str(asset.get("browser_download_url", download_url))
                    break

            is_newer = is_newer_version(tag, current_version)
            return ReleaseInfo(
                version=tag.lstrip("vV"),
                name=name,
                html_url=html_url,
                body=body,
                published_at=published_at,
                is_newer=is_newer,
                download_url=download_url,
            )
        elif response.status_code == 404:
            logging.info("updater_no_release_found repo=%s", repo)
            return None
        else:
            logging.warning("updater_github_api_status status=%s body=%s", response.status_code, response.text[:120])
            return None
    except requests.RequestException as exc:
        logging.warning("updater_network_error error=%s", type(exc).__name__)
        return None
    except Exception as exc:
        logging.error("updater_unexpected_error error=%s", type(exc).__name__)
        return None


class UpdateChecker:
    """Background worker that periodically checks for new GitHub releases every 3 hours."""

    def __init__(
        self,
        repo: str = GITHUB_REPO,
        current_version: str = APP_VERSION,
        interval_seconds: int = UPDATE_CHECK_INTERVAL_SECONDS,
        on_update_found: Callable[[ReleaseInfo], None] | None = None,
    ) -> None:
        self.repo = repo
        self.current_version = current_version
        self.interval_seconds = max(60, interval_seconds)
        self.on_update_found = on_update_found
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_checked: float = 0.0
        self.latest_release: ReleaseInfo | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="BisikUpdateChecker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def check_now(self) -> ReleaseInfo | None:
        """Synchronously check for updates."""
        info = fetch_latest_release(self.repo, self.current_version)
        self.last_checked = time.time()
        if info:
            self.latest_release = info
        return info

    def _run(self) -> None:
        # Initial delay to keep app launch snappy
        if self._stop_event.wait(15.0):
            return

        while not self._stop_event.is_set():
            try:
                info = self.check_now()
                if info and info.is_newer:
                    logging.info("updater_new_version_available latest=%s current=%s", info.version, self.current_version)
                    if self.on_update_found:
                        self.on_update_found(info)
            except Exception as exc:
                logging.warning("updater_check_cycle_failed error=%s", type(exc).__name__)

            # Sleep for interval (3 hours) or exit immediately if stopped
            if self._stop_event.wait(self.interval_seconds):
                break
