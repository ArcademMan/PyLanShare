"""Sistema di localizzazione per ammstools.

Uso:
    from shared.i18n import t, set_locale, register_locale_dir

    register_locale_dir("sysdel", "/path/to/sysdel/locale")  # Registra stringhe tool
    set_locale("it")                                          # Cambia lingua
    print(t("btn_scan"))                                      # -> chiave in common
    print(t("sysdel.btn_scan"))                               # -> chiave del tool
    print(t("sysdel.scanning", path="/tmp"))                  # -> con interpolazione

Le stringhe comuni (common) vivono in shared/locale/.
Ogni tool registra la propria cartella locale con register_locale_dir().
"""

import json
import locale
import os
import sys


def _find_dir(*candidates):
    """Restituisce la prima directory esistente tra i candidati."""
    for d in candidates:
        if os.path.isdir(d):
            return d
    return candidates[0]


# In compilato sys.executable e' il .exe, __file__ potrebbe non essere valido
_EXE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
_SHARED_LOCALE_DIR = _find_dir(
    os.path.join(os.path.dirname(__file__), "locale"),       # dev: shared/locale
    os.path.join(_EXE_DIR, "shared", "locale"),              # compilato
)
_DEFAULT_LANG = "en"

_current_lang: str = ""
_common_strings: dict = {}
_tool_dirs: dict[str, str] = {}
_tool_strings: dict[str, dict] = {}


def _detect_system_lang() -> str:
    """Rileva la lingua: prima da config salvata, poi dal sistema."""
    try:
        from shared.config import get as config_get
        saved = config_get("language")
        if saved and os.path.exists(os.path.join(_SHARED_LOCALE_DIR, f"{saved}.json")):
            return saved
    except Exception:
        pass
    try:
        lang = locale.getdefaultlocale()[0] or ""
        code = lang[:2].lower()
        if os.path.exists(os.path.join(_SHARED_LOCALE_DIR, f"{code}.json")):
            return code
    except Exception:
        pass
    return _DEFAULT_LANG


def _load_json(directory: str, lang: str) -> dict:
    path = os.path.join(directory, f"{lang}.json")
    if not os.path.exists(path):
        path = os.path.join(directory, f"{_DEFAULT_LANG}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _reload_all():
    """Ricarica tutte le stringhe per la lingua corrente."""
    global _common_strings, _tool_strings
    _common_strings = _load_json(_SHARED_LOCALE_DIR, _current_lang)
    _tool_strings = {
        name: _load_json(directory, _current_lang)
        for name, directory in _tool_dirs.items()
    }


def set_locale(lang: str):
    """Imposta la lingua corrente e ricarica tutte le stringhe."""
    global _current_lang
    _current_lang = lang
    _reload_all()


def get_locale() -> str:
    """Restituisce la lingua corrente."""
    if not _current_lang:
        set_locale(_detect_system_lang())
    return _current_lang


def register_locale_dir(name: str, directory: str):
    """Registra la cartella locale di un tool.

    Args:
        name: Nome del tool (es. "sysdel"), usato come prefisso nelle chiavi.
        directory: Percorso assoluto alla cartella locale del tool.
    """
    _tool_dirs[name] = directory
    if _current_lang:
        _tool_strings[name] = _load_json(directory, _current_lang)


def available_locales() -> list[str]:
    """Restituisce le lingue disponibili (basato su shared/locale/)."""
    return [
        f.removesuffix(".json")
        for f in os.listdir(_SHARED_LOCALE_DIR)
        if f.endswith(".json")
    ]


def t(key: str, **kwargs) -> str:
    """Ottieni una stringa tradotta.

    Formato chiave:
        "tool.chiave"   -> cerca in tool_strings["tool"]["chiave"]
        "chiave"        -> cerca in common_strings["chiave"]

    Fallback: lingua corrente -> inglese -> restituisce la chiave grezza.
    """
    if not _current_lang:
        set_locale(_detect_system_lang())

    val = _lookup(key)
    if val is None and _current_lang != _DEFAULT_LANG:
        val = _lookup_fallback(key)
    if val is None:
        return key

    if kwargs:
        val = val.format(**kwargs)
    return val


def _lookup(key: str) -> str | None:
    """Cerca una chiave nelle stringhe della lingua corrente."""
    parts = key.split(".", 1)

    if len(parts) == 2 and parts[0] in _tool_strings:
        return _resolve(parts[1], _tool_strings[parts[0]])

    return _resolve(key, _common_strings)


def _lookup_fallback(key: str) -> str | None:
    """Cerca una chiave nelle stringhe inglesi (fallback)."""
    parts = key.split(".", 1)

    if len(parts) == 2 and parts[0] in _tool_dirs:
        fallback = _load_json(_tool_dirs[parts[0]], _DEFAULT_LANG)
        return _resolve(parts[1], fallback)

    fallback = _load_json(_SHARED_LOCALE_DIR, _DEFAULT_LANG)
    return _resolve(key, fallback)


def _resolve(key: str, data: dict) -> str | None:
    parts = key.split(".")
    node = data
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node if isinstance(node, str) else None
