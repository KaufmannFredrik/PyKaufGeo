"""Shared pytest setup: headless Qt, isolated config dir, one QApplication."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("PYKAUFGEO_CONFIG_DIR", str(ROOT / "build" / "test-config"))
if "QT_QPA_FONTDIR" not in os.environ and os.environ.get("WINDIR"):
    fonts = Path(os.environ["WINDIR"]) / "Fonts"
    if fonts.is_dir():
        os.environ["QT_QPA_FONTDIR"] = str(fonts)

SCREENSHOT_DIR = ROOT / "build" / "test-screenshots"


@pytest.fixture(scope="session")
def qapp():
    from pykaufgeo.gui.app import create_app
    from pykaufgeo.gui.preferences import Preferences

    app = create_app([], Preferences())
    yield app


@pytest.fixture()
def light_theme(qapp):
    """Reset to the default light theme before a GUI test."""
    from pykaufgeo.gui.qt_theme import theme_manager

    mgr = theme_manager()
    mgr.prefs.night = False
    mgr.prefs.high_contrast = False
    mgr.prefs.font_size = 11
    mgr.apply()
    yield mgr


@pytest.fixture(autouse=True)
def _delete_test_windows():
    """Delete windows a test leaves behind; restyling dozens of dead windows is slow."""
    yield
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    from PySide6.QtCore import QCoreApplication, QEvent

    from pykaufgeo.gui.chrome import BrutalToolTip

    for w in app.topLevelWidgets():
        if isinstance(w, BrutalToolTip):
            continue  # shared by the ToolTipManager for the whole session
        doc = getattr(w, "document", None)
        if doc is not None:
            doc.modified = False
        w.close()
        w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


@pytest.fixture()
def screenshot_dir() -> Path:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return SCREENSHOT_DIR
