"""Headless GUI smoke tests (QT_QPA_PLATFORM=offscreen). Screenshots land in build/."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QAbstractButton, QApplication, QPushButton

from pykaufgeo import theme
from pykaufgeo.gui.app import UI_EFFECTS
from pykaufgeo.gui.chrome import BrutalMenu, CloseButton
from pykaufgeo.gui.icons import ICONS, icon_pixmap
from pykaufgeo.gui.tools_catalog import TOOL_GROUPS, all_tools


def make_window():
    from pykaufgeo.gui.main_window import MainWindow

    win = MainWindow()
    win.resize(1200, 800)
    win.show()
    QApplication.processEvents()
    return win


def test_ui_effects_disabled(qapp) -> None:
    for effect in UI_EFFECTS:
        assert not QApplication.isEffectEnabled(effect)


def test_main_window_shell_and_screenshot(qapp, light_theme, screenshot_dir) -> None:
    win = make_window()
    path = screenshot_dir / "smoke_main.png"
    assert win.grab().save(str(path))
    img = QImage(str(path))
    assert img.width() >= 1000 and img.height() >= 700
    # The main frame border is solid black at the top-left inner corner.
    frame = win.centralWidget()
    corner = frame.mapTo(win, QPoint(1, 1))
    assert QColor(img.pixel(corner)).name().upper() == theme.BLACK
    win.close()


def test_all_panels_exist_and_toggle(qapp, light_theme) -> None:
    from pykaufgeo.gui.main_window import VIEWS

    win = make_window()
    assert set(win.panels) == {v.id for v in VIEWS}
    for spec in VIEWS:
        win.set_view_visible(spec.id, True)
        assert not win.panels[spec.id].isHidden()
        assert win.view_actions[spec.id].isChecked()
        assert win.panels[spec.id].title_label.text() == win.panels[spec.id].title_label.text().upper()
    win.panels["cas"].close_button.click()
    assert win.panels["cas"].isHidden()
    assert not win.view_actions["cas"].isChecked()
    win.close()


def test_menus_are_brutal(qapp, light_theme) -> None:
    win = make_window()
    for act in win.menuBar().actions():
        assert isinstance(act.menu(), BrutalMenu)
    win.close()


def test_hit_targets(qapp, light_theme) -> None:
    win = make_window()
    for btn in win.toolbar.buttons():
        r = btn.focus_rect()
        assert r.width() >= theme.MIN_HIT_TOOLBAR and r.height() >= theme.MIN_HIT_TOOLBAR
    for btn in win.findChildren(QAbstractButton):
        if not btn.isVisibleTo(win):
            continue
        hint = btn.sizeHint() if not isinstance(btn, CloseButton) else btn.size()
        assert hint.height() >= theme.MIN_HIT, f"{btn} {hint}"
    win.close()


def test_tool_selection_marks_unimplemented(qapp, light_theme) -> None:
    win = make_window()
    win.toolbar.select_tool("checkbox")
    assert win.toolbar.current_tool.id == "checkbox"
    assert win.toolbar.group_button("action").selected
    assert not win.toolbar.group_button("move").selected
    assert win.message.isVisibleTo(win)
    assert win.message.property("kind") == "warning"
    win.close()


def test_every_tool_has_an_icon(qapp) -> None:
    for tool in all_tools():
        assert tool.id in ICONS, tool.id
        pm = icon_pixmap(tool.id, theme.ICON_SIZE, QColor(theme.BLACK), QColor(theme.WHITE))
        img = pm.toImage()
        dark = sum(1 for x in range(0, img.width(), 2) for y in range(0, img.height(), 2)
                   if QColor(img.pixel(x, y)).lightness() < 128)
        assert dark > 10, f"icon {tool.id} looks empty"
    assert len({g.id for g in TOOL_GROUPS}) == len(TOOL_GROUPS)


def test_theme_switch_is_instant(qapp, light_theme, screenshot_dir) -> None:
    win = make_window()
    win.set_night(True)
    QApplication.processEvents()
    img = win.grab().toImage()
    win.grab().save(str(screenshot_dir / "smoke_night.png"))
    canvas = win.graphics.canvas
    corner = canvas.mapTo(win, QPoint(3, 3))
    assert QColor(img.pixel(corner)).lightness() < 64  # black canvas (or a dark grid line)
    assert QColor(img.pixel(win.panels["algebra"].mapTo(win, QPoint(20, 60)))).lightness() < 64
    win.set_night(False)
    win.set_high_contrast(True)
    assert light_theme.colors.high_contrast
    win.set_high_contrast(False)
    win.close()


def test_font_size_setting_applies(qapp, light_theme) -> None:
    win = make_window()
    small = win.panels["algebra"].title_label.sizeHint().height()
    win.set_font_size(24)
    QApplication.processEvents()
    big = win.panels["algebra"].title_label.sizeHint().height()
    assert big > small
    win.set_font_size(theme.FONT_SIZE_DEFAULT)
    win.close()


def test_focus_ring_follows_keyboard_focus(qapp, light_theme, screenshot_dir) -> None:
    win = make_window()
    win.activateWindow()
    field = win.input_bar.field
    field.setFocus(Qt.FocusReason.TabFocusReason)
    QApplication.processEvents()
    mgr = qapp._pykaufgeo_managers[1]
    if mgr.target is not None:  # offscreen focus delivery is platform dependent
        assert mgr.target is field
        win.grab().save(str(screenshot_dir / "smoke_focus.png"))
    win.close()


def test_dialogs_build(qapp, light_theme, screenshot_dir) -> None:
    from pykaufgeo.gui.dialogs import AboutDialog, PreferencesDialog
    from pykaufgeo.gui.preferences import Preferences

    win = make_window()
    for i, dlg in enumerate((AboutDialog(win), PreferencesDialog(Preferences(), win))):
        dlg.show()
        QApplication.processEvents()
        assert not dlg.mask().isEmpty()  # hard-shadow mask present
        assert dlg.mask().boundingRect() == dlg.rect()
        assert dlg.grab().save(str(screenshot_dir / f"smoke_dialog_{i}.png"))
        buttons = [b for b in dlg.findChildren(QPushButton)]
        assert buttons and all(b.sizeHint().height() >= theme.MIN_HIT for b in buttons)
        dlg.close()
        dlg.deleteLater()
    win.close()


def test_python_m_pykaufgeo_launches(tmp_path) -> None:
    """`python -m pykaufgeo <file>` starts, opens the file and exits cleanly."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    from pykaufgeo.core.document import Document

    doc = Document()
    doc.execute("A = (1, 2)")
    doc.execute("B = Midpoint(A, (3, 4))")
    path = doc.save(tmp_path / "launch.pkgeo")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYKAUFGEO_CONFIG_DIR=str(tmp_path / "cfg"))
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run([sys.executable, "-m", "pykaufgeo", str(path), "--quit-after=300"],
                          cwd=root, env=env, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert "smoke run OK: 2 objects, mathtext OK" in proc.stdout
