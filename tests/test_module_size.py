"""Keep modules small: no module in the package over about 800 lines."""

from __future__ import annotations

from pathlib import Path

LIMIT = 800
PACKAGE = Path(__file__).resolve().parents[1] / "pykaufgeo"


def test_modules_under_limit() -> None:
    too_big = []
    for path in PACKAGE.rglob("*.py"):
        n = sum(1 for _ in path.open(encoding="utf-8"))
        if n > LIMIT:
            too_big.append(f"{path.relative_to(PACKAGE.parent)}: {n} lines")
    assert not too_big, "Modules over the size limit:\n" + "\n".join(too_big)


def test_core_does_not_import_qt() -> None:
    gui_free = ("core", "parser", "engine", "commands", "io", "render")
    offenders = []
    for sub in gui_free:
        for path in (PACKAGE / sub).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "PySide6" in text or "pykaufgeo.gui" in text:
                offenders.append(str(path.relative_to(PACKAGE.parent)))
    assert not offenders, offenders
