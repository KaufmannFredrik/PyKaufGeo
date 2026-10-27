"""Generated documentation stays in sync with the code."""

from __future__ import annotations

from pathlib import Path

from pykaufgeo.commands.docs import commands_markdown, help_entries
from pykaufgeo.commands.registry import all_commands

ROOT = Path(__file__).resolve().parents[1]


def test_commands_md_is_up_to_date() -> None:
    current = (ROOT / "docs" / "COMMANDS.md").read_text(encoding="utf-8")
    assert current == commands_markdown(), "run: python tools/gen_commands_md.py"


def test_every_command_documented() -> None:
    text = commands_markdown()
    for c in all_commands():
        assert f"### {c.name}\n" in text
        for syntax in c.syntaxes():
            assert syntax in text


def test_help_entries_cover_commands_and_functions() -> None:
    names = {e.name for e in help_entries()}
    assert {"Circle", "Sequence", "sin", "ln", "floor"} <= names
