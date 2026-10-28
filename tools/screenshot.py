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


M3_INPUT = (
    "A = (-7, 1)", "B = (-4, 1)", "C = (-5, 4)", "t1 = Polygon(A, B, C)", "α = Angle(B, A, C)",
    "g: x = -2.5", "t1' = Reflect(t1, g)", "el = Ellipse((1, 3), (5, 3), 3)", "P = Point(el)",
    "Tangent(P, el)", "c = Circle((1, -3), 1.5)", "M = Point(c)", "Q = Midpoint(M, (5, -3))", "loc = Locus(Q, M)",
    "a = Slider(0, 5, 0.1)", "k = CircularSector((-7, -4), (-5, -4), (-7, -2))", "r = Rotate(Segment(M, Q), 90°, Q)",
)


def m3_document():
    from pykaufgeo.core.document import Document

    doc = Document(seed=1)
    for line in M3_INPUT:
        doc.execute(line)
    c = doc.construction
    c.place_on_path("P", 3, 6)
    c.place_on_path("M", 2, -2)
    text = c.add_text('"Drag M: Q traces the locus"', extras={"pos": [-1.5, -5.6]})[0]
    c.set_style(text, visible_in=["g1"])
    c.set_style("α", color="green")
    doc.undo.reset()
    return doc


def m3_main(out: Path, name: str, prefs: Preferences | None = None, setup: Callable | None = None) -> Path:
    def full_setup(app, win):
        win.selection.set(["el"])
        settle(app)
        win.graphics.canvas.grab()
        win.graphics.canvas.show_all()
        settle(app)
        if setup is not None:
            setup(app, win)
            settle(app)
    return shot_main(out, name, prefs, (), full_setup, m3_document())


def m3_overlay(out: Path, name: str, setup: Callable, prefs: Preferences | None = None) -> Path:
    app, win = make_window(prefs, m3_document())
    settle(app)
    win.graphics.canvas.grab()
    popup = setup(app, win)
    popup.ensurePolished()
    popup.resize(popup.sizeHint())
    settle(app)
    pos = win.mapFromGlobal(popup.pos())
    path = out / f"{name}.png"
    compose(win.grab(), [(popup, pos)]).save(str(path))
    win.document.modified = False
    win.close()
    return path


def m3_dialog(out: Path, name: str, factory: Callable, prefs: Preferences | None = None, tab: int = 0) -> Path:
    app, win = make_window(prefs, m3_document())
    dlg = factory(win)
    dlg.show()  # tab pages are laid out only when shown
    settle(app)
    if hasattr(dlg, "tabs"):
        dlg.tabs.setCurrentIndex(tab)
    dlg.ensurePolished()
    dlg.adjustSize()
    dlg.resize(dlg.sizeHint())
    settle(app)
    pos = QPoint((win.width() - dlg.width()) // 2, (win.height() - dlg.height()) // 3)
    path = out / f"{name}.png"
    compose(win.grab(), [(dlg, pos)]).save(str(path))
    win.document.modified = False
    win.close()
    return path


def m3_jobs(out: Path) -> dict:
    from pykaufgeo.gui.dialogs import SliderDialog, TextPromptDialog
    from pykaufgeo.gui.properties import PropertiesDialog

    def object_menu(app, win):
        canvas = win.graphics.canvas
        win.selection.set(["M"])
        menu = canvas.object_menu("M")
        p = canvas.mapToGlobal(canvas.rect().center())
        menu.move(p)
        win._shot_menu = menu
        return menu

    def style_menu(app, win):
        win.selection.set(["el"])
        settle(app)
        bar = win.graphics.style_bar
        menu = bar.build_menu("color")
        b = bar.buttons["color"]
        menu.move(b.mapToGlobal(b.rect().bottomLeft()))
        win._shot_menu = menu
        return menu

    def show_hide(app, win):
        win.document.set_style("t1'", visible_in=[])
        win.toolbar.select_tool("show_hide_object")

    def polygon_preview(app, win):
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent

        win.toolbar.select_tool("polygon")
        canvas = win.graphics.canvas
        for x, y in ((1, -6), (3, -5.5)):
            pt = QPointF(canvas.vp.sx(x), canvas.vp.sy(y))
            for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
                ev = QMouseEvent(kind, pt, QPointF(canvas.mapToGlobal(pt.toPoint())), Qt.MouseButton.LeftButton,
                                 Qt.MouseButton.LeftButton if kind == QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton,
                                 Qt.KeyboardModifier.NoModifier)
                QApplication.sendEvent(canvas, ev)
        cur = QPointF(canvas.vp.sx(2), canvas.vp.sy(-4))
        QApplication.sendEvent(canvas, QMouseEvent(QEvent.Type.MouseMove, cur, QPointF(canvas.mapToGlobal(cur.toPoint())),
                                                   Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                                                   Qt.KeyboardModifier.NoModifier))

    def props(label: str):
        return lambda w: PropertiesDialog(w.document, [label], w)

    return {
        "m3_main": lambda: m3_main(out, "m3_main"),
        "m3_night": lambda: m3_main(out, "m3_night", Preferences(night=True)),
        "m3_contrast": lambda: m3_main(out, "m3_high_contrast", Preferences(high_contrast=True)),
        "m3_font": lambda: m3_main(out, "m3_font_20pt", Preferences(font_size=20)),
        "m3_show_hide": lambda: m3_main(out, "m3_show_hide_tool", setup=show_hide),
        "m3_polygon_preview": lambda: m3_main(out, "m3_polygon_preview", setup=polygon_preview),
        "m3_object_menu": lambda: m3_overlay(out, "m3_object_menu", object_menu),
        "m3_style_menu": lambda: m3_overlay(out, "m3_style_menu", style_menu),
        "m3_props": lambda: m3_dialog(out, "m3_dialog_properties", props("el")),
        "m3_props_style": lambda: m3_dialog(out, "m3_dialog_properties_style", props("el"), tab=2),
        "m3_props_slider": lambda: m3_dialog(out, "m3_dialog_properties_slider", props("a"), tab=4),
        "m3_props_font": lambda: m3_dialog(out, "m3_dialog_properties_20pt", props("el"), Preferences(font_size=20)),
        "m3_props_night": lambda: m3_dialog(out, "m3_dialog_properties_night", props("el"), Preferences(night=True), 1),
        "m3_slider_dialog": lambda: m3_dialog(out, "m3_dialog_slider", lambda w: SliderDialog("b", w)),
        "m3_text_dialog": lambda: m3_dialog(out, "m3_dialog_text", lambda w: TextPromptDialog(
            "Text", "Text", "Area of the triangle", w, multiline=True)),
    }


M4_INPUT = (
    "f(x) = x^3 / 4 - x", "f'", "Root(f)", "Extremum(f)", "I = Integral(f, -2, 0)", "T = TaylorPolynomial(cos(x), 0, 4)",
    "ic = ImplicitCurve(x^3 + y^3 - 6x y)", "k = Curve(2cos(t) + 6, 2sin(3t) - 4, t, 0, 2π)",
    "l = Asymptote((x^2 + 1) / (x - 4))", "d = Limit(sin(x) / x, 0)", "n = NSolve(cos(x) = x)",
)
REGION_INPUT = ("r_1: x^2 + y^2 < 16", "r_2: y > x^2 - 3", "r_3: y < sin(2x) - 1 || x > 5", "s: x + y >= 1 && x - y <= 2")


def m4_document(lines=M4_INPUT):
    from pykaufgeo.core.document import Document

    doc = Document(seed=1)
    for line in lines:
        doc.execute(line)
    if "r_1" in doc.construction:
        doc.construction.set_style("r_2", color="red")
        doc.construction.set_style("r_3", color="magenta")
        doc.construction.set_style("s", color="green")
    doc.undo.reset()
    return doc


def m4_main(out: Path, name: str, prefs: Preferences | None = None, lines=M4_INPUT,
            window=(-8.0, -6.0, 9.0, 6.0), setup: Callable | None = None) -> Path:
    def full_setup(app, win):
        win.selection.set(["f"] if "f" in win.document.construction else [])
        settle(app)
        canvas = win.graphics.canvas
        canvas.grab()
        canvas.set_viewport(canvas.vp.zoomed_to(*window, keep_ratio=True))
        settle(app)
        if setup is not None:
            setup(app, win)
            settle(app)
    return shot_main(out, name, prefs, (), full_setup, m4_document(lines))


def m4_jobs(out: Path) -> dict:
    def sketch(app, win):
        from PySide6.QtCore import QPointF

        win.toolbar.select_tool("freehand")
        canvas = win.graphics.canvas
        canvas.tool.stroke = [QPointF(canvas.vp.sx(x / 10), canvas.vp.sy(-4 + 0.15 * (x / 10) ** 2))
                              for x in range(-60, 61, 3)]
        canvas.update()

    return {
        "m4_main": lambda: m4_main(out, "m4_main"),
        "m4_night": lambda: m4_main(out, "m4_night", Preferences(night=True)),
        "m4_contrast": lambda: m4_main(out, "m4_high_contrast", Preferences(high_contrast=True)),
        "m4_font": lambda: m4_main(out, "m4_font_20pt", Preferences(font_size=20)),
        "m4_regions": lambda: m4_main(out, "m4_regions", lines=REGION_INPUT, window=(-7.0, -6.0, 7.0, 6.0)),
        "m4_regions_night": lambda: m4_main(out, "m4_regions_night", Preferences(night=True), lines=REGION_INPUT,
                                            window=(-7.0, -6.0, 7.0, 6.0)),
        "m4_sketch": lambda: m4_main(out, "m4_freehand_sketch", setup=sketch),
        "m4_inspector": lambda: m4_dialog(out, "m4_dialog_function_inspector", 0),
        "m4_inspector_points": lambda: m4_dialog(out, "m4_dialog_function_inspector_points", 1),
    }


def m4_dialog(out: Path, name: str, tab: int) -> Path:
    from pykaufgeo.gui.function_inspector import FunctionInspector

    app, win = make_window(None, m4_document())
    dlg = FunctionInspector(win.document, "f", -2, 2, win)
    dlg.show()
    settle(app)
    dlg.tabs.setCurrentIndex(tab)
    settle(app)
    pos = QPoint((win.width() - dlg.width()) // 2, (win.height() - dlg.height()) // 4)
    path = out / f"{name}.png"
    compose(win.grab(), [(dlg, pos)]).save(str(path))
    win.document.modified = False
    dlg.close()
    win.close()
    return path


def m5_main(out: Path, name: str, prefs: Preferences | None = None, focus: int = 3) -> Path:
    def setup(app, win):
        win.open_demo("m5")
        settle(app, 6)
        win.message.clear_message()
        win.cas_view.focus_row(focus)
        settle(app)
    return shot_main(out, name, prefs, (), setup)


def m5_jobs(out: Path) -> dict:
    return {
        "m5_main": lambda: m5_main(out, "m5_main"),
        "m5_night": lambda: m5_main(out, "m5_night", Preferences(night=True)),
        "m5_contrast": lambda: m5_main(out, "m5_high_contrast", Preferences(high_contrast=True)),
        "m5_font": lambda: m5_main(out, "m5_font_20pt", Preferences(font_size=20)),
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
    jobs.update(m3_jobs(out))
    jobs.update(m4_jobs(out))
    jobs.update(m5_jobs(out))
    names = args.only or list(jobs)
    for n in names:
        path = jobs[n]()
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
