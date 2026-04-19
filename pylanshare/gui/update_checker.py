"""Background check for new releases on GitHub."""

import json
import logging
import urllib.request
from typing import Callable

from PySide6.QtCore import QThread, Signal

from .. import __version__

log = logging.getLogger("pylanshare.update")

GITHUB_REPO = "ArcademMan/PyLanShare"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    """Turn 'v1.2.3' or '1.2.3' into (1, 2, 3)."""
    return tuple(int(x) for x in tag.lstrip("v").split("."))


class UpdateCheckThread(QThread):
    """Fetch latest release in a background thread, emit result."""

    result = Signal(bool, str, str)  # (update_available, latest_tag, download_url)

    def run(self):
        try:
            req = urllib.request.Request(
                API_URL,
                headers={"Accept": "application/vnd.github+json",
                         "User-Agent": "PyLanShare-UpdateCheck"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            latest_tag = data.get("tag_name", "")
            html_url = data.get("html_url", RELEASE_URL)

            if not latest_tag:
                self.result.emit(False, "", "")
                return

            if _parse_version(latest_tag) > _parse_version(__version__):
                log.info("New version available: %s (current: %s)", latest_tag, __version__)
                self.result.emit(True, latest_tag, html_url)
            else:
                log.debug("Up to date (%s)", __version__)
                self.result.emit(False, latest_tag, html_url)

        except Exception as e:
            log.debug("Update check failed: %s", e)
            self.result.emit(False, "", "")
