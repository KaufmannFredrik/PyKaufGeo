"""Translation lookup.

UI strings are written in English and passed through :func:`tr`. Catalogues for
English and Norwegian Bokmål are JSON files in ``pykaufgeo/translations`` (M8);
until a catalogue is loaded, ``tr`` returns the English source text.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_CATALOG: dict[str, str] = {}
_LANGUAGE = "en"
SUPPORTED = {"en": "English", "nb": "Norsk bokmål"}


def set_language(code: str) -> None:
    """Load the catalogue for ``code`` (falls back to English source strings)."""
    global _CATALOG, _LANGUAGE
    _LANGUAGE = code if code in SUPPORTED else "en"
    _CATALOG = {}
    if _LANGUAGE == "en":
        return
    path = Path(__file__).parent / "translations" / f"{_LANGUAGE}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            _CATALOG = {str(k): str(v) for k, v in data.items()}
    except (OSError, ValueError) as exc:
        log.warning("No translation catalogue for %s: %s", _LANGUAGE, exc)


def language() -> str:
    return _LANGUAGE


def tr(text: str) -> str:
    """Translate ``text`` into the current language."""
    return _CATALOG.get(text, text)
