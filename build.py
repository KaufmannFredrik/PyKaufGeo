"""Build a single-file PyKaufGeo executable with PyInstaller.

Usage:
    python build.py            # one-file, windowed build into dist/
    python build.py --onedir   # faster to build and start; a folder instead of one file
    python build.py --console  # keep a console window (useful for debugging)

The script draws the application icon with Qt (no binary assets in the repository),
runs PyInstaller, and prints the path of the result.

Platform notes
--------------
Windows (primary target): produces ``dist/PyKaufGeo.exe``. Build on the oldest
Windows you want to support.

Linux: run the same command on Linux; the output is ``dist/PyKaufGeo`` (an ELF
binary). Build on the oldest glibc you target (e.g. in a manylinux container).
Qt needs the system's xcb libraries at runtime (``libxcb-cursor0`` on Debian/Ubuntu).

macOS: run on macOS; ``--onefile --windowed`` produces both ``dist/PyKaufGeo`` and
``dist/PyKaufGeo.app``. Prefer the .app. For distribution, sign it
(``codesign --deep --sign "Developer ID ..."``) and notarise it with ``notarytool``.
The icon is written as PNG there (PyInstaller converts it when Pillow is present;
otherwise the default icon is used).
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "PyKaufGeo"
ENTRY = ROOT / "pykaufgeo" / "__main__.py"
BUILD = ROOT / "build" / "pyinstaller"
DIST = ROOT / "dist"

# Modules PyInstaller would otherwise drag in through optional imports.
EXCLUDES = [
    "tkinter", "PyQt5", "PyQt6", "PySide2", "IPython", "jupyter", "notebook",
    "pytest", "_pytest", "pandas", "PIL.ImageQt",
]


def make_icon(target_dir: Path) -> Path | None:
    """Render the logo icon with Qt to .ico (Windows) or .png (elsewhere)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT))
    try:
        from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
        from PySide6.QtCore import QRectF

        from pykaufgeo import theme
        from pykaufgeo.gui.icons import draw_icon
    except ImportError as exc:  # pragma: no cover
        print(f"warning: could not draw icon ({exc}); using the default icon")
        return None
    app = QGuiApplication.instance() or QGuiApplication([])
    size = 256
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(QColor(theme.WHITE))
    p = QPainter(img)
    draw_icon(p, QRectF(0, 0, size, size), "logo", QColor(theme.BLACK))
    p.end()
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".ico" if platform.system() == "Windows" else ".png"
    path = target_dir / f"pykaufgeo{suffix}"
    if not img.save(str(path)):
        print(f"warning: Qt could not write {path}; using the default icon")
        return None
    del app
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--onedir", action="store_true", help="build a folder instead of one file")
    parser.add_argument("--console", action="store_true", help="keep a console window")
    parser.add_argument("--clean", action="store_true", help="remove previous build output first")
    args = parser.parse_args()

    if args.clean:
        shutil.rmtree(BUILD, ignore_errors=True)
    icon = make_icon(BUILD)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--name", NAME,
        "--onedir" if args.onedir else "--onefile",
        "--console" if args.console else "--windowed",
        "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
        "--distpath", str(DIST),
        "--paths", str(ROOT),
        "--collect-submodules", "pykaufgeo",
    ]
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    if icon is not None:
        cmd += ["--icon", str(icon)]
    cmd.append(str(ENTRY))
    print("running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"PyInstaller failed with exit code {result.returncode}")
        return result.returncode

    if args.onedir:
        out = DIST / NAME / (NAME + (".exe" if platform.system() == "Windows" else ""))
    elif platform.system() == "Windows":
        out = DIST / f"{NAME}.exe"
    elif platform.system() == "Darwin" and (DIST / f"{NAME}.app").exists():
        out = DIST / f"{NAME}.app"
    else:
        out = DIST / NAME
    if not out.exists():
        print(f"build finished but {out} is missing")
        return 1
    print(f"\nBuilt: {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
