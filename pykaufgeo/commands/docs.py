"""Generate docs/COMMANDS.md and help/autocomplete data from the command registry."""

from __future__ import annotations

from dataclasses import dataclass

from pykaufgeo.commands.registry import all_commands
from pykaufgeo.engine.builtins import ALIASES, BUILTINS

HEADER = """# Command reference

Generated from the command registry by `python tools/gen_commands_md.py`; do not
edit by hand (`tests/test_docs.py` fails when this file is out of date).

Command names are case-insensitive and accept `()` or `[]`. Arguments written
`<Expression>` or `<Condition>` are evaluated by the command itself (they may use
the command's `<Variable>`); all other arguments are evaluated first and checked
against the type in brackets.
"""


@dataclass(frozen=True)
class HelpEntry:
    name: str
    category: str
    description: str
    syntaxes: tuple[str, ...]
    examples: tuple[str, ...]


def help_entries() -> list[HelpEntry]:
    """Commands and predefined functions, for autocomplete and the help dialog."""
    out = [HelpEntry(c.name, c.category, c.description, tuple(c.syntaxes()), c.examples) for c in all_commands()]
    for b in sorted(BUILTINS.values(), key=lambda b: b.name):
        args = ", ".join(["<x>"] if b.max_args == 1 else ["<a>", "<b>"][: b.max_args])
        out.append(HelpEntry(b.name, "Predefined functions", b.help, (f"{b.name}( {args} )",), ()))
    return out


def commands_markdown() -> str:
    lines = [HEADER]
    by_cat: dict[str, list] = {}
    for c in all_commands():
        by_cat.setdefault(c.category, []).append(c)
    lines.append("## Contents\n")
    for cat in sorted(by_cat):
        names = ", ".join(f"[{c.name}](#{c.name.lower()})" for c in by_cat[cat])
        lines.append(f"* **{cat}**: {names}")
    lines.append("* **Predefined functions**: [list](#predefined-functions)\n")
    for cat in sorted(by_cat):
        lines.append(f"## {cat}\n")
        for c in by_cat[cat]:
            lines.append(f"### {c.name}\n")
            lines.append(c.description + "\n")
            if c.aliases:
                lines.append("Also available as: " + ", ".join(f"`{a}`" for a in c.aliases) + "\n")
            for s in c.signatures:
                lines.append(f"* `{s.syntax(c.name)}`" + (f": {s.help}" if s.help else ""))
            if c.examples:
                lines.append("\nExamples:\n")
                for e in c.examples:
                    lines.append(f"* `{e}`")
            lines.append("")
    lines.append("## Predefined functions\n")
    lines.append("| Function | Arguments | Meaning |")
    lines.append("|---|---|---|")
    inv_alias: dict[str, list[str]] = {}
    for a, target in ALIASES.items():
        inv_alias.setdefault(target, []).append(a)
    for b in sorted(BUILTINS.values(), key=lambda b: b.name):
        names = ", ".join(f"`{n}`" for n in [b.name, *sorted(inv_alias.get(b.name, []))])
        argc = str(b.min_args) if b.min_args == b.max_args else f"{b.min_args}-{b.max_args}"
        lines.append(f"| {names} | {argc} | {b.help} |")
    lines.append("")
    lines.append("Constants: `pi` (`π`), `e` (`ℯ`), `i` (`ί`), `∞` (`infinity`), `deg` (one degree, "
                 "as in `30deg`). Postfix operators: `!` factorial, `°` degrees, `%` percent.\n")
    return "\n".join(lines)
