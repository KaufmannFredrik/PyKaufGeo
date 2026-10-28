"""Milestone demos and the gallery: every finished milestone can be opened and looked at."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from gui_helpers import close, make_window
from pykaufgeo.core.document import Document
from pykaufgeo.demos import DEMOS, LATEST, load_demo
from pykaufgeo.gui.app import parse_args

ROOT = Path(__file__).resolve().parents[1]


def _gallery():
    spec = importlib.util.spec_from_file_location("gallery", ROOT / "tools" / "gallery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_finished_milestone_has_a_demo() -> None:
    done = [key for key, _scope, finished in _gallery().milestones() if finished and key != "m0"]
    assert done, "PLAN.md milestone table not found"
    missing = [key for key in done if key not in DEMOS]
    assert not missing, f"add a demo to pykaufgeo/demos.py for {missing}"
    assert LATEST == done[-1]


@pytest.mark.parametrize("key", list(DEMOS))
def test_demo_builds_cleanly(key) -> None:
    doc = Document(seed=1)
    demo = load_demo(doc, key)
    c = doc.construction
    assert len(c) + len(doc.cas_rows) >= 10 and demo.hint and demo.title.upper().startswith(key.upper())
    assert [el.label for el in c if not el.is_defined or el.error] == []
    assert [r["input"] for r in doc.cas_rows if r.get("error")] == []
    assert not doc.modified and not doc.undo.can_undo and doc.path is None


def test_parse_demo_arguments() -> None:
    assert parse_args(["app", "--demo"])[3] == LATEST
    assert parse_args(["app", "--demo=M2"])[3] == "m2"
    assert parse_args(["app", "--demo", "m1"]) == ([], None, None, "m1")
    assert parse_args(["app", "x.pkgeo"]) == (["x.pkgeo"], None, None, None)


def test_open_demo_in_the_window(qapp, light_theme, monkeypatch) -> None:
    win = make_window()
    help_menu = next(a.menu() for a in win.menuBar().actions() if "Help" in a.text())
    demos = next(a.menu() for a in help_menu.actions() if a.text() == "Milestone Demos")
    assert [a.text() for a in demos.actions()] == [d.title for d in DEMOS.values()]
    assert win.open_demo("m2")
    QApplication.processEvents()
    assert "Demo M2" in win.windowTitle() and win.message.property("kind") == "info"
    assert not win.panels["graphics2"].isHidden()
    win.document.execute("Z = (1, 1)")                      # a change: opening another demo asks first
    monkeypatch.setattr(win, "maybe_save", lambda: False)
    assert not win.open_demo("m3") and "Z" in win.document.construction
    monkeypatch.undo()
    win.document.modified = False
    assert not win.open_demo("m9") and win.message.property("kind") == "error"
    win.file_new()
    assert "Untitled" in win.windowTitle()
    close(win)


def test_gallery_is_up_to_date() -> None:
    gallery = _gallery()
    current = (ROOT / "docs" / "GALLERY.md").read_text(encoding="utf-8")
    assert current == gallery.gallery_markdown(), "run: python tools/gallery.py"
    for key in DEMOS:
        assert (ROOT / "docs" / "screenshots" / f"demo_{key}.png").exists(), "run: python tools/gallery.py"
        assert f"--demo {key}" in current
