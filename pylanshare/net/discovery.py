"""Discover hosts on the local network via the system ARP table."""

import re
import subprocess


def get_lan_hosts() -> list[str]:
    """Return a list of IP addresses from the local ARP cache."""
    try:
        result = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return re.findall(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", result.stdout)
    except (OSError, subprocess.TimeoutExpired):
        return []
