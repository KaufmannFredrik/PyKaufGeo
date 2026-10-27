"""The native ``.pkgeo`` file format.

A zip archive containing:

* ``document.json``: format marker, ``format_version``, app version, save time, and
  the document sections ``construction`` (objects, definitions, styles, state),
  ``views`` (view settings), ``spreadsheet`` (cells) and ``cas`` (rows).
* ``thumbnail.png`` (optional): a picture of the Graphics view.
* ``assets/<name>`` (optional): pictures used by Image objects.

Older files are upgraded by the migration chain in ``MIGRATIONS``: a function
registered for version *n* turns a version-*n* dictionary into version *n + 1*.
"""

from __future__ import annotations

import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pykaufgeo import __version__
from pykaufgeo.core.errors import FileFormatError

FORMAT = "pkgeo"
FORMAT_VERSION = 1
DOCUMENT = "document.json"
THUMBNAIL = "thumbnail.png"
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_THUMBNAIL_BYTES = 16 * 1024 * 1024
ASSETS = "assets/"
MAX_ASSET_BYTES = 32 * 1024 * 1024
ASSET_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}\.(png|jpg|jpeg|gif|bmp)", re.I)
SECTIONS = ("construction", "views", "spreadsheet", "cas")

Migration = Callable[[dict], dict]
MIGRATIONS: dict[int, Migration] = {}


def migration(from_version: int) -> Callable[[Migration], Migration]:
    """Register a function upgrading a format-``from_version`` document by one version."""
    def deco(fn: Migration) -> Migration:
        MIGRATIONS[from_version] = fn
        return fn
    return deco


def migrate(data: dict, target: int | None = None) -> dict:
    target = FORMAT_VERSION if target is None else target
    version = data.get("format_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise FileFormatError("The file has no valid format version.")
    if version > target:
        raise FileFormatError(f"This file was saved by a newer PyKaufGeo (format {version}); "
                              f"this version reads format {target} and older.")
    while version < target:
        step = MIGRATIONS.get(version)
        if step is None:
            raise FileFormatError(f"Cannot upgrade a format {version} file: no migration available.")
        data = step(dict(data))
        version += 1
        data["format_version"] = version
    return data


def write_pkgeo(path: str | os.PathLike, sections: dict[str, Any], thumbnail_png: bytes | None = None,
                assets: dict[str, bytes] | None = None) -> Path:
    """Write a document atomically (temporary file, then rename)."""
    path = Path(path)
    payload = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "app_version": __version__,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    for key in SECTIONS:
        payload[key] = sections.get(key, {})
    text = json.dumps(payload, ensure_ascii=False, indent=1, allow_nan=False)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(DOCUMENT, text)
            if thumbnail_png:
                z.writestr(THUMBNAIL, thumbnail_png, compress_type=zipfile.ZIP_STORED)
            for name, data in (assets or {}).items():
                if ASSET_NAME.fullmatch(name):
                    z.writestr(ASSETS + name, data, compress_type=zipfile.ZIP_STORED)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise FileFormatError(f"Could not save {path.name}: {exc.strerror or exc}") from exc
    return path


def read_pkgeo(path: str | os.PathLike) -> tuple[dict, bytes | None]:
    """Read, validate and migrate a document. Returns (document dict, thumbnail PNG bytes)."""
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as z:
            try:
                info = z.getinfo(DOCUMENT)
            except KeyError:
                raise FileFormatError(f"{path.name} is not a PyKaufGeo document (no {DOCUMENT}).") from None
            if info.file_size > MAX_JSON_BYTES:
                raise FileFormatError(f"{path.name} is too large to open.")
            raw = z.read(DOCUMENT)
            thumb = None
            if THUMBNAIL in z.namelist() and z.getinfo(THUMBNAIL).file_size <= MAX_THUMBNAIL_BYTES:
                thumb = z.read(THUMBNAIL)
    except FileNotFoundError:
        raise FileFormatError(f"File not found: {path}") from None
    except zipfile.BadZipFile:
        raise FileFormatError(f"{path.name} is not a PyKaufGeo document (not a zip archive).") from None
    except OSError as exc:
        raise FileFormatError(f"Could not open {path.name}: {exc.strerror or exc}") from None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise FileFormatError(f"{path.name} is damaged: {DOCUMENT} is not valid JSON ({exc}).") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise FileFormatError(f"{path.name} is not a PyKaufGeo document.")
    data = migrate(data)
    for key in SECTIONS:
        if not isinstance(data.get(key), dict):
            data[key] = {}
    return data, thumb


def read_pkgeo_assets(path: str | os.PathLike) -> dict[str, bytes]:
    """Pictures stored in a document (names are checked; oversized entries are skipped)."""
    out: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(Path(path)) as z:
            for info in z.infolist():
                name = info.filename[len(ASSETS):]
                if info.filename.startswith(ASSETS) and ASSET_NAME.fullmatch(name) \
                        and info.file_size <= MAX_ASSET_BYTES:
                    out[name] = z.read(info)
    except (OSError, zipfile.BadZipFile) as exc:
        raise FileFormatError(f"Could not read the pictures in {Path(path).name}: {exc}") from None
    return out
