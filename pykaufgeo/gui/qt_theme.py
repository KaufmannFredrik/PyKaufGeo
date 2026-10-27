"""Qt adapters for the design tokens in :mod:`pykaufgeo.theme`.

This module turns tokens into ``QColor``/``QFont``/``QPen`` objects and owns the
:class:`ThemeManager`, which applies the generated stylesheet and palette to the
application and notifies custom-painted widgets when the theme changes.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette, QPen
from PySide6.QtWidgets import QApplication

from pykaufgeo import theme
from pykaufgeo.gui.preferences import Preferences


def qcolor(hex_or_token: str, colors: theme.ThemeColors | None = None) -> QColor:
    """QColor from ``#RRGGBB`` or a colour token (resolved against ``colors``)."""
    if not hex_or_token.startswith("#"):
        hex_or_token = theme.resolve_color(hex_or_token, colors or theme.LIGHT)
    return QColor(hex_or_token)


def ui_font(pt: float, heavy: bool = False) -> QFont:
    font = QFont()
    font.setFamilies(list(theme.UI_FONT_FAMILIES))
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setPointSizeF(pt)
    font.setWeight(QFont.Weight(theme.FONT_WEIGHT_HEAVY if heavy else theme.FONT_WEIGHT))
    return font


def mono_font(pt: float, heavy: bool = False) -> QFont:
    font = QFont()
    font.setFamilies(list(theme.MONO_FONT_FAMILIES))
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    font.setPointSizeF(pt)
    font.setWeight(QFont.Weight(theme.FONT_WEIGHT_HEAVY if heavy else theme.FONT_WEIGHT))
    return font


def pen(color: QColor, width: float) -> QPen:
    p = QPen(color)
    p.setWidthF(width)
    p.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    p.setCapStyle(Qt.PenCapStyle.SquareCap)
    return p


def install_font_substitutions() -> None:
    """Make the first family of each stack fall back to the rest on any OS."""
    for stack in (theme.UI_FONT_FAMILIES, theme.MONO_FONT_FAMILIES):
        first, rest = stack[0], list(stack[1:])
        QFont.insertSubstitutions(first, rest)


class ThemeManager(QObject):
    """Applies the current theme (stylesheet, palette, font) to the application."""

    changed = Signal()

    def __init__(self, app: QApplication, prefs: Preferences, system_pt: float) -> None:
        super().__init__(app)
        self._app = app
        self.prefs = prefs
        self.system_pt = system_pt
        self.colors = theme.theme_colors(prefs.night, prefs.high_contrast)
        self.font_pt = theme.scaled_font_pt(prefs.font_size, system_pt)

    # -- state -----------------------------------------------------------------
    def set_night(self, on: bool) -> None:
        self.prefs.night = on
        self.apply()

    def set_high_contrast(self, on: bool) -> None:
        self.prefs.high_contrast = on
        self.apply()

    def set_font_size(self, pt: int) -> None:
        self.prefs.font_size = theme.clamp_font_size(pt)
        self.apply()

    def color(self, token: str) -> QColor:
        return qcolor(theme.resolve_color(token, self.colors))

    def ui_font(self, scale: float = 1.0, heavy: bool = False) -> QFont:
        return ui_font(self.font_pt * scale, heavy)

    def mono_font(self, scale: float = 1.0, heavy: bool = False) -> QFont:
        return mono_font(self.font_pt * scale, heavy)

    # -- application -----------------------------------------------------------
    def apply(self) -> None:
        self.colors = theme.theme_colors(self.prefs.night, self.prefs.high_contrast)
        self.font_pt = theme.scaled_font_pt(self.prefs.font_size, self.system_pt)
        c = self.colors
        pal = QPalette()
        roles = {
            QPalette.ColorRole.Window: c.bg,
            QPalette.ColorRole.WindowText: c.fg,
            QPalette.ColorRole.Base: c.bg,
            QPalette.ColorRole.AlternateBase: c.bg,
            QPalette.ColorRole.Text: c.fg,
            QPalette.ColorRole.Button: c.bg,
            QPalette.ColorRole.ButtonText: c.fg,
            QPalette.ColorRole.Highlight: c.selection_bg,
            QPalette.ColorRole.HighlightedText: c.selection_fg,
            QPalette.ColorRole.ToolTipBase: c.bg,
            QPalette.ColorRole.ToolTipText: c.fg,
            QPalette.ColorRole.PlaceholderText: c.disabled_fg,
            QPalette.ColorRole.BrightText: c.error_bg,
            QPalette.ColorRole.Link: c.fg,
        }
        for role, value in roles.items():
            pal.setColor(role, QColor(value))
        for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
            pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(c.disabled_fg))
        self._app.setPalette(pal)
        self._app.setFont(ui_font(self.font_pt))
        self._app.setStyleSheet(theme.build_stylesheet(c, self.font_pt))
        self.changed.emit()


_MANAGER: ThemeManager | None = None


def install_theme_manager(mgr: ThemeManager) -> None:
    global _MANAGER
    _MANAGER = mgr


def theme_manager() -> ThemeManager:
    """The application's ThemeManager (created by :func:`pykaufgeo.gui.app.create_app`)."""
    if _MANAGER is None:
        raise RuntimeError("ThemeManager not installed; call create_app() first")
    return _MANAGER
