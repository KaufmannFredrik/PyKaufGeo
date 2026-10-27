"""The .pkgeo format: round trips, versioning, migrations, damaged files."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from pykaufgeo.core.document import Document
from pykaufgeo.core.errors import FileFormatError
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import Point, Vector
from pykaufgeo.io import pkgeo

SAMPLE = [
    "A = (1, 2)", "B = (4, 6)", "M = Midpoint(A, B)", "d = Distance(A, B)", "f(x) = x^2 - 2x",
    "a = 3", "g(x) = a x^2 + 1", "c: x^2 + y^2 = 4", "y = 2x + 1", "u = (1, 2)", "s = Sequence(k^2, k, 1, 5)",
    "z_1 = 3 + 2i", "t = 30°", "text1 = \"Hello \\\"world\\\"\"", "l1 = {{1, 2}, {3, 4}}", "Intersect(c, Line(A, B))",
    "r = RandomBetween(1, 1000)", "q(x) = If(x < 0, -x, x^2)", "p = Polygon((0, 0), (4, 0), (0, 3))", "ok = a > 2",
    "b = 1/0", "h(t) = t^3", "e1 = ?",
]


def build() -> Document:
    doc = Document(seed=42)
    for line in SAMPLE:
        doc.execute(line)
    doc.set_style("A", color="#123456", point_size=7, label_mode="name_value", layer=3)
    doc.construction["M"].caption = "middle"
    doc.views["graphics"]["xmin"] = -3.5
    doc.spreadsheet["cells"]["A1"] = "1"
    doc.cas["rows"].append({"input": "Solve(x^2 = 4)"})
    return doc


def test_round_trip_preserves_everything(tmp_path: Path) -> None:
    doc = build()
    path = tmp_path / "sample.pkgeo"
    doc.save(path, thumbnail_png=b"\x89PNG fake")
    other = Document(seed=0)
    errors = other.open(path)
    assert errors == []
    assert other.snapshot() == doc.snapshot()
    assert other.thumbnail == b"\x89PNG fake"
    c = other.construction
    assert c["r"].value == doc.construction["r"].value  # random value kept
    assert c["u"].geo_type is GeoType.VECTOR and c["u"].value == Vector(1, 2)
    assert c["A"].style.color == "#123456" and c["A"].style.layer == 3
    assert c["M"].caption == "middle"
    assert other.views["graphics"]["xmin"] == -3.5
    assert not other.modified and other.path == path
    assert not other.undo.can_undo


def test_round_trip_after_edits(tmp_path: Path) -> None:
    doc = build()
    doc.set_value("A", Point(-1.25, 0.1))
    doc.rename("M", "Mid")
    doc.delete("y" if "y" in doc.construction else "p")
    path = tmp_path / "edited.pkgeo"
    doc.save(path)
    again = Document()
    assert again.open(path) == []
    assert again.snapshot() == doc.snapshot()
    assert again.construction["A"].value == Point(-1.25, 0.1)


def test_file_layout_and_version(tmp_path: Path) -> None:
    path = build().save(tmp_path / "x.pkgeo", b"png")
    with zipfile.ZipFile(path) as z:
        assert set(z.namelist()) == {"document.json", "thumbnail.png"}
        data = json.loads(z.read("document.json"))
    assert data["format"] == "pkgeo" and data["format_version"] == pkgeo.FORMAT_VERSION
    assert set(pkgeo.SECTIONS) <= set(data)
    assert data["construction"]["elements"][0] == {
        "label": "A", "type": "point", "definition": "(1, 2)", "params": None,
        "style": data["construction"]["elements"][0]["style"]}


def test_migration_hook(tmp_path: Path, monkeypatch) -> None:
    path = build().save(tmp_path / "old.pkgeo")
    with zipfile.ZipFile(path) as z:
        data = json.loads(z.read("document.json"))
    data["format_version"] = 0
    data["legacy_views"] = data.pop("views")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("document.json", json.dumps(data))

    def v0_to_v1(d: dict) -> dict:
        d["views"] = d.pop("legacy_views")
        return d

    monkeypatch.setitem(pkgeo.MIGRATIONS, 0, v0_to_v1)
    doc = Document()
    assert doc.open(path) == []
    assert doc.views["graphics"]["xmin"] == -3.5


def test_newer_and_unmigratable_versions(tmp_path: Path) -> None:
    for version, fragment in ((pkgeo.FORMAT_VERSION + 1, "newer"), (-3, "valid format version")):
        path = tmp_path / f"v{version}.pkgeo"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("document.json", json.dumps({"format": "pkgeo", "format_version": version}))
        with pytest.raises(FileFormatError, match=fragment):
            Document().open(path)


@pytest.mark.parametrize("content,fragment", [
    (b"not a zip at all", "not a zip"),
    (None, "no document.json"),
    ("{broken json", "not valid JSON"),
    (json.dumps({"format": "other", "format_version": 1}), "not a PyKaufGeo document"),
])
def test_damaged_files_give_friendly_errors(tmp_path: Path, content, fragment: str) -> None:
    path = tmp_path / "bad.pkgeo"
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        with zipfile.ZipFile(path, "w") as z:
            if content is None:
                z.writestr("other.txt", "x")
            else:
                z.writestr("document.json", content)
    with pytest.raises(FileFormatError, match=fragment):
        Document().open(path)


def test_missing_file() -> None:
    with pytest.raises(FileFormatError, match="not found"):
        Document().open("does/not/exist.pkgeo")


def test_bad_objects_are_skipped_with_messages(tmp_path: Path) -> None:
    doc = Document()
    doc.execute("A = (1, 2)")
    doc.execute("B = A + (1, 1)")
    snap = doc.snapshot()
    snap["construction"]["elements"].insert(1, {"label": "bad", "definition": "Foo(1)"})
    snap["construction"]["elements"].append({"label": "C", "definition": "bad + 1"})
    snap["construction"]["elements"].append("garbage")
    path = tmp_path / "partial.pkgeo"
    pkgeo.write_pkgeo(path, snap)
    other = Document()
    errors = other.open(path)
    assert len(errors) == 3
    assert any("Unknown command" in e for e in errors)
    assert other.construction["B"].value == Point(2, 3)
    assert "bad" not in other.construction and "C" not in other.construction


def test_save_is_atomic_on_failure(tmp_path: Path) -> None:
    target = tmp_path / "missing_dir" / "x.pkgeo"
    with pytest.raises(FileFormatError, match="Could not save"):
        build().save(target)
    assert not target.exists()
