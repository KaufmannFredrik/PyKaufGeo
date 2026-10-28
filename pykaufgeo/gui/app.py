"""QApplication bootstrap: Fusion style, no UI effects, fonts, theme, chrome managers."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from pykaufgeo import APP_NAME, __version__, theme
from pykaufgeo.gui.chrome import FocusRingManager, ToolTipManager
from pykaufgeo.gui.preferences import Preferences, load_preferences
from pykaufgeo.gui.qt_theme import ThemeManager, install_font_substitutions, install_theme_manager
from pykaufgeo.i18n import set_language

log = logging.getLogger(__name__)

# Every Qt UI effect: chrome must never animate.
UI_EFFECTS = (
    Qt.UIEffect.UI_AnimateMenu,
    Qt.UIEffect.UI_FadeMenu,
    Qt.UIEffect.UI_AnimateCombo,
    Qt.UIEffect.UI_AnimateTooltip,
    Qt.UIEffect.UI_FadeTooltip,
    Qt.UIEffect.UI_AnimateToolBox,
)


def ensure_offscreen_fonts() -> None:
    """The offscreen platform plugin finds no fonts on Windows unless told where."""
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen" and "QT_QPA_FONTDIR" not in os.environ:
        windir = os.environ.get("WINDIR")
        if windir and (Path(windir) / "Fonts").is_dir():
            os.environ["QT_QPA_FONTDIR"] = str(Path(windir) / "Fonts")


def create_app(argv: list[str] | None = None, prefs: Preferences | None = None) -> QApplication:
    """Create (or reuse) the QApplication and install theme, tooltip and focus managers."""
    ensure_offscreen_fonts()
    app = QApplication.instance()
    if app is None:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    for effect in UI_EFFECTS:
        QApplication.setEffectEnabled(effect, False)
    app.setProperty("pykaufgeo_system_pt", app.property("pykaufgeo_system_pt") or app.font().pointSizeF())
    system_pt = float(app.property("pykaufgeo_system_pt"))
    install_font_substitutions()
    prefs = prefs if prefs is not None else load_preferences()
    set_language(prefs.language)
    mgr = ThemeManager(app, prefs, system_pt)
    install_theme_manager(mgr)
    mgr.apply()
    if not getattr(app, "_pykaufgeo_managers", None):
        app._pykaufgeo_managers = (ToolTipManager(app), FocusRingManager(app))  # type: ignore[attr-defined]
    return app


def parse_args(argv: list[str]) -> tuple[list[str], int | None, str | None, str | None]:
    """Files to open, ``--demo[=m2]``, ``--quit-after=MS`` and ``--smoke-report=FILE``.

    ``--demo`` alone opens the latest milestone demo; ``--demo m2`` and ``--demo=m2`` a given one.
    """
    from pykaufgeo.demos import DEMOS, LATEST

    files: list[str] = []
    quit_after: int | None = None
    report: str | None = None
    demo: str | None = None
    args = argv[1:]
    for i, arg in enumerate(args):
        if arg == "--demo":
            demo = LATEST
        elif arg.startswith("--demo="):
            demo = arg.split("=", 1)[1].lower()
        elif i and args[i - 1] == "--demo" and arg.lower() in DEMOS:
            demo = arg.lower()
        elif arg.startswith("--smoke-report="):
            report = arg.split("=", 1)[1]
        elif arg.startswith("--quit-after="):
            try:
                quit_after = max(0, int(arg.split("=", 1)[1]))
            except ValueError:
                pass
        elif not arg.startswith("-"):
            files.append(arg)
    return files, quit_after, report, demo


def run(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    argv = list(argv if argv is not None else sys.argv)
    files, quit_after, report, demo = parse_args(argv)
    app = create_app(argv[:1])
    from PySide6.QtCore import QTimer

    from pykaufgeo.gui.main_window import MainWindow

    win = MainWindow()
    win.show()
    from pykaufgeo.engine.sym_bridge import preload

    preload()  # sympy takes seconds to import; the first derivative should not wait for it
    if files:
        win.file_open(files[0])
    elif demo is not None:
        win.open_demo(demo)
    if quit_after is not None:
        def finish() -> None:
            from pykaufgeo.gui.mathtext import math_renderer

            mathtext = math_renderer().image(r"\frac{x^{2}}{2}", theme.FONT_SIZE_DEFAULT, theme.BLACK) is not None
            count = len(win.document.construction)
            win.document.modified = False  # smoke runs never prompt
            win.close()
            line = f"PyKaufGeo {__version__} smoke run OK: {count} objects, mathtext {'OK' if mathtext else 'FAILED'}"
            print(line)
            if report:
                Path(report).write_text(line + "\n", encoding="utf-8")
            app.quit()

        QTimer.singleShot(quit_after, finish)
    return app.exec()
