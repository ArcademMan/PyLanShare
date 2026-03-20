"""Configurazione persistente per ammstools.

Salva le preferenze in un file JSON nella cartella utente.
"""

import json
import os

_CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AmMstools")
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "config.json")


def _ensure_dir():
    os.makedirs(_CONFIG_DIR, exist_ok=True)


def load() -> dict:
    """Carica la configurazione."""
    if not os.path.exists(_CONFIG_FILE):
        return {}
    try:
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save(config: dict):
    """Salva la configurazione."""
    _ensure_dir()
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get(key: str, default=None):
    """Ottiene un valore dalla configurazione."""
    return load().get(key, default)


def set(key: str, value):
    """Imposta un valore nella configurazione."""
    config = load()
    config[key] = value
    save(config)
