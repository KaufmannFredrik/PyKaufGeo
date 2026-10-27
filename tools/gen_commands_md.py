"""Regenerate docs/COMMANDS.md from the command registry."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pykaufgeo.commands.docs import commands_markdown  # noqa: E402

TARGET = ROOT / "docs" / "COMMANDS.md"


def main() -> int:
    TARGET.write_text(commands_markdown(), encoding="utf-8", newline="\n")
    print(TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
