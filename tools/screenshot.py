"""Render the UI headless and save screenshots for design review.

Usage:  python tools/screenshot.py [--out docs/screenshots] [--only NAME ...]

Runs on the offscreen Qt platform. Popups (menus, tooltips, dialogs) are separate
top-level windows, so they are grabbed individually and composited onto the main
window grab at the position they would appear.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYKAUFGEO_CONFIG_DIR", str(ROOT / "build" / "screenshot-config"))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from pykaufgeo.gui.app import create_app  # noqa: E402
from pykaufgeo.gui.preferences import Preferences  # noqa: E402

WIDTH, HEIGHT = 1440, 900


def compose(base: QPixmap, overlays: list[tuple[QWidget, QPoint]]) -> QPixmap:
    """Paint popup widgets over ``base``, clipped by their window masks."""
    out = QPixmap(base.size())
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.drawPixmap(0, 0, base)
    for widget, pos in overlays:
        pm = widget.grab()
        mask = widget.mask()
        p.save()
        if not mask.isEmpty():
            p.setClipRegion(mask.translated(pos))
        p.drawPixmap(pos, pm)
        p.restore()
    p.end()
    return out


def settle(app: QApplication, rounds: int = 3) -> None:
    for _ in range(rounds):
        app.processEvents()


SAMPLE_INPUT = (
    "A = (1, 2)", "B = (4, 6)", "M = Midpoint(A, B)", "d = Distance(A, B)", "a = 3",
    "f(x) = a x^2 - 2x", "c: x^2 + y^2 = 4", "g = Line(A, B)", "Intersect(c, g)",
    "u = (1, 2)", "s = Sequence(k^2, k, 1, 5)", "z_1 = 3 + 2i", "\"Distance: \" + d",
    "q(x) = If(x < 0, -x, x^2)", "y > x^2", "H = Intersect(g, y = 10)",
)


def sample_document():
    from pykaufgeo.core.document import Document

    doc = Document(seed=1)
    for line in SAMPLE_INPUT:
        doc.execute(line)
    return doc


def make_window(prefs: Preferences | None = None, document=None):
    app = create_app([], prefs or Preferences())
    from pykaufgeo.gui.main_window import MainWindow

    win = MainWindow(document)
    win.resize(WIDTH, HEIGHT)
    win.show()
    settle(app)
    return app, win


def shot_main(out: Path, name: str, prefs: Preferences | None = None,
              views: tuple[str, ...] = (), setup: Callable | None = None, document=None) -> Path:
    app, win = make_window(prefs, document)
    for v in views:
        win.set_view_visible(v, True)
    if setup is not None:
        setup(app, win)
    settle(app)
    path = out / f"{name}.png"
    win.grab().save(str(path))
    win.document.modified = False
    win.close()
    return path


def shot_error(out: Path, name: str) -> Path:
    def setup(app, win):
        win.input_bar.field.setText("Circle(A, 2, 3, 4)")
        win.submit_input("Circle(A, 2, 3, 4)")
        settle(app)
    return shot_main(out, name, setup=setup, document=sample_document())


def shot_menu(out: Path, name: str, menu_index: int, prefs: Preferences | None = None) -> Path:
    app, win = make_window(prefs)
    bar = win.menuBar()
    menu = bar.actions()[menu_index].menu()
    geo = bar.actionGeometry(bar.actions()[menu_index])
    menu.ensurePolished()
    menu.adjustSize()
    menu.resize(menu.sizeHint())
    pos = bar.mapTo(win, geo.bottomLeft())
    path = out / f"{name}.png"
    compose(win.grab(), [(menu, pos)]).save(str(path))
    win.close()
    return path


def shot_group_menu(out: Path, name: str, group_id: str) -> Path:
    app, win = make_window()
    tb = win.toolbar
    from pykaufgeo.gui.tools_catalog import TOOL_GROUPS

    group = next(g for g in TOOL_GROUPS if g.id == group_id)
    tb.select_tool(group.tools[0].id)
    btn = tb.group_button(group_id)
    menu = tb.group_menu(group)
    menu.ensurePolished()
    menu.adjustSize()
    menu.resize(menu.sizeHint())
    settle(app)
    pos = btn.mapTo(win, QPoint(0, btn.height()))
    path = out / f"{name}.png"
    compose(win.grab(), [(menu, pos)]).save(str(path))
    win.close()
    return path


def shot_tooltip(out: Path, name: str) -> Path:
    app, win = make_window()
    mgr = app._pykaufgeo_managers[0]
    btn = win.toolbar.group_button("circle")
    mgr.popup.set_content(btn.toolTip())
    mgr.popup.ensurePolished()
    mgr.popup.adjustSize()
    pos = btn.mapTo(win, QPoint(btn.width() // 2, btn.height() + 4))
    path = out / f"{name}.png"
    mgr.popup.resize(mgr.popup.sizeHint())
    compose(win.grab(), [(mgr.popup, pos)]).save(str(path))
    win.close()
    return path


def shot_dialog(out: Path, name: str, factory: Callable[[QWidget], QWidget],
                prefs: Preferences | None = None) -> Path:
    app, win = make_window(prefs)
    dlg = factory(win)
    dlg.ensurePolished()
    dlg.adjustSize()
    dlg.resize(dlg.sizeHint())
    settle(app)
    pos = QPoint((win.width() - dlg.width()) // 2, (win.height() - dlg.height()) // 3)
    path = out / f"{name}.png"
    compose(win.grab(), [(dlg, pos)]).save(str(path))
    win.close()
    return path


def shot_focus(out: Path, name: str) -> Path:
    def setup(app, win):
        btn = win.toolbar.group_button("line")
        btn.setFocus(Qt.FocusReason.TabFocusReason)
        settle(app)
    return shot_main(out, name, setup=setup)


def shot_input_focus(out: Path, name: str) -> Path:
    def setup(app, win):
        win.input_bar.field.setFocus(Qt.FocusReason.TabFocusReason)
        win.input_bar.field.setText("Circle((0, 0), 3")
        settle(app)
    return shot_main(out, name, setup=setup)



GRAPHICS_INPUT = (
    "A = (1, 2)", "B = (4, -1)", "g = Line(A, B)", "c = Circle(A, B)", "M = Midpoint(A, B)",
    "a = 0.25", "f(x) = a x^2 - 3", "h(x) = tan(x)", "k(x) = floor(x) - 5",
    "u = Vector((-6, 3), (-4, 5))", "p = Polygon((-8, 1), (-6, 1), (-7, 3))",
    "s = Segment((-7, -4), (-3, -5))", "r = Ray((2, 5), (5, 6))", "q(x) = sqrt(x + 6) / 2 - 6",
)


def graphics_document():
    from pykaufgeo.core.document import Document

    doc = Document(seed=1)
    for line in GRAPHICS_INPUT:
        doc.execute(line)
    return doc


def m2_main(out: Path, name: str, prefs: Preferences | None = None, views: tuple[str, ...] = (),
            setup: Callable | None = None) -> Path:
    def full_setup(app, win):
        win.selection.set(["c"])
        settle(app)
        win.graphics.canvas.grab()
        if setup is not None:
            setup(app, win)
            settle(app)
    return shot_main(out, name, prefs, views, full_setup, graphics_document())


def m2_overlay(out: Path, name: str, setup: Callable, popup_of: Callable, prefs: Preferences | None = None) -> Path:
    """Main window with a popup (autocomplete, context menu) composited at its position."""
    app, win = make_window(prefs, graphics_document())
    setup(app, win)
    settle(app)
    popup = popup_of(win)
    pos = win.mapFromGlobal(popup.pos())
    path = out / f"{name}.png"
    compose(win.grab(), [(popup, pos)]).save(str(path))
    win.document.modified = False
    win.close()
    return path


def m2_jobs(out: Path) -> dict:
    from pykaufgeo.gui.command_help import CommandHelpDialog

    def edit(app, win):
        win.algebra.start_edit("f")

    def by_type(app, win):
        win.algebra.set_mode("type")

    def both(app, win):
        win.graphics2.canvas.set_setting(grid="isometric")
        win.graphics2.canvas.zoom_at(win.graphics2.canvas.rect().center(), 0.7)

    def polar(app, win):
        win.graphics.canvas.set_setting(grid="polar")

    def typing(app, win):
        f = win.input_bar.field
        f.setFocus()
        from PySide6.QtTest import QTest
        QTest.keyClicks(f, "Cir")

    def hint(app, win):
        f = win.input_bar.field
        f.setFocus()
        f.setText("Circle(A, ")
        f.setCursorPosition(len(f.text()))
        f._update_context()

    def context(app, win):
        canvas = win.graphics.canvas
        menu = canvas.build_context_menu()
        menu.ensurePolished()
        menu.resize(menu.sizeHint())
        menu.move(canvas.mapToGlobal(canvas.rect().center()))
        win._shot_menu = menu

    return {
        "m2_main": lambda: m2_main(out, "m2_main"),
        "m2_night": lambda: m2_main(out, "m2_night", Preferences(night=True)),
        "m2_contrast": lambda: m2_main(out, "m2_high_contrast", Preferences(high_contrast=True)),
        "m2_font": lambda: m2_main(out, "m2_font_20pt", Preferences(font_size=20)),
        "m2_square": lambda: m2_main(out, "m2_square_points", Preferences(square_points=True)),
        "m2_two_views": lambda: m2_main(out, "m2_two_graphics_views", views=("graphics2",), setup=both),
        "m2_type": lambda: m2_main(out, "m2_algebra_by_type", setup=by_type),
        "m2_edit": lambda: m2_main(out, "m2_algebra_inline_edit", setup=edit),
        "m2_polar": lambda: m2_main(out, "m2_polar_grid", setup=polar),
        "m2_hint": lambda: m2_main(out, "m2_argument_hint", setup=hint),
        "m2_complete": lambda: m2_overlay(out, "m2_autocomplete", typing, lambda w: w.input_bar.field.popup),
        "m2_context": lambda: m2_overlay(out, "m2_graphics_context_menu", context, lambda w: w._shot_menu),
        "m2_help": lambda: shot_dialog(out, "m2_dialog_command_help", lambda w: CommandHelpDialog(w, "circ")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "docs" / "screenshots"))
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--prefix", default="m0")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    from pykaufgeo.gui.dialogs import AboutDialog, ConfirmDialog, PreferencesDialog

    p = args.prefix
    jobs: dict[str, Callable[[], Path]] = {
        "main": lambda: shot_main(out, f"{p}_main"),
        "all_views": lambda: shot_main(out, f"{p}_all_views", views=(
            "cas", "graphics2", "graphics3d", "spreadsheet", "probability", "protocol")),
        "night": lambda: shot_main(out, f"{p}_night", Preferences(night=True)),
        "contrast": lambda: shot_main(out, f"{p}_high_contrast", Preferences(high_contrast=True)),
        "large_font": lambda: shot_main(out, f"{p}_font_20pt", Preferences(font_size=20)),
        "menu": lambda: shot_menu(out, f"{p}_menu_view", 2),
        "menu_night": lambda: shot_menu(out, f"{p}_menu_view_night", 2, Preferences(night=True)),
        "group_menu": lambda: shot_group_menu(out, f"{p}_tool_group_menu", "circle"),
        "tooltip": lambda: shot_tooltip(out, f"{p}_tooltip"),
        "about": lambda: shot_dialog(out, f"{p}_dialog_about", AboutDialog),
        "prefs": lambda: shot_dialog(out, f"{p}_dialog_preferences",
                                     lambda w: PreferencesDialog(Preferences(), w)),
        "confirm": lambda: shot_dialog(out, f"{p}_dialog_confirm", lambda w: ConfirmDialog(
            "Unsaved changes", "The construction has unsaved changes. Save them first?",
            [("cancel", "Cancel"), ("discard", "Discard"), ("save", "Save")], w)),
        "focus": lambda: shot_focus(out, f"{p}_focus_ring_toolbar"),
        "input_focus": lambda: shot_input_focus(out, f"{p}_focus_ring_input"),
        "m1_algebra": lambda: shot_main(out, "m1_algebra_list", document=sample_document()),
        "m1_error": lambda: shot_error(out, "m1_input_error"),
        "m1_night": lambda: shot_main(out, "m1_algebra_night", Preferences(night=True), document=sample_document()),
    }
    jobs.update(m2_jobs(out))
    names = args.only or list(jobs)
    for n in names:
        path = jobs[n]()
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
