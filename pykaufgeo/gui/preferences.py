"""User preferences (font size, theme, contrast, point style, language), stored as JSON."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from pykaufgeo import theme

log = logging.getLogger(__name__)

CONFIG_ENV = "PYKAUFGEO_CONFIG_DIR"


@dataclass
class Preferences:
    font_size: int = theme.FONT_SIZE_DEFAULT
    night: bool = False
    high_contrast: bool = False
    square_points: bool = False
    language: str = "en"

    @classmethod
    def from_dict(cls, data: dict) -> "Preferences":
        prefs = cls()
        known = {f.name: f.type for f in fields(cls)}
        for key, value in data.items():
            if key not in known:
                continue
            default = getattr(prefs, key)
            if isinstance(default, bool) and isinstance(value, bool):
                setattr(prefs, key, value)
            elif isinstance(default, int) and not isinstance(default, bool) and isinstance(value, int):
                setattr(prefs, key, value)
            elif isinstance(default, str) and isinstance(value, str):
                setattr(prefs, key, value)
        prefs.font_size = theme.clamp_font_size(prefs.font_size)
        if prefs.language not in ("en", "nb"):
            prefs.language = "en"
        return prefs


def config_dir() -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override)
    try:
        from PySide6.QtCore import QStandardPaths

        loc = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        if loc:
            return Path(loc)
    except Exception:  # pragma: no cover - Qt missing or broken
        pass
    return Path.home() / ".pykaufgeo"


def load_preferences() -> Preferences:
    path = config_dir() / "preferences.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return Preferences.from_dict(data)
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        log.warning("Could not read preferences %s: %s", path, exc)
    return Preferences()


def save_preferences(prefs: Preferences) -> None:
    path = config_dir() / "preferences.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(prefs), indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("Could not save preferences %s: %s", path, exc)
