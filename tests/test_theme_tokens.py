"""Design-token guard rails.

* No colour, font family, or border-width literal may appear in the package outside
  ``pykaufgeo/theme.py``. The scanner is tested against known-bad snippets so it
  cannot pass vacuously.
* The chrome palette is restricted to the seven brand colours plus neutral greys.
* Every text/background role meets WCAG AA (3:1 for the large-text error block).
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import pytest

from pykaufgeo import theme

PACKAGE = Path(__file__).resolve().parents[1] / "pykaufgeo"
THEME_FILE = PACKAGE / "theme.py"

COLOR_NAMES = {
    "black", "white", "red", "blue", "yellow", "green", "magenta", "cyan", "gray", "grey",
    "orange", "purple", "pink", "brown", "darkgray", "lightgray", "darkgrey", "lightgrey",
    "navy", "lime", "maroon", "olive", "silver", "teal", "fuchsia", "aqua",
}
FONT_NAMES = (
    "arial", "helvetica", "segoe", "consolas", "courier", "monospace", "sans-serif", "serif",
    "times", "verdana", "tahoma", "calibri", "dejavu", "liberation", "menlo", "monaco",
    "roboto", "inter", "noto",
)

STRING_RULES = [
    ("hex colour", re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b|#[0-9A-Fa-f]{8}\b")),
    ("css colour function", re.compile(r"\brgba?\s*\(|\bhsla?\s*\(")),
    ("css px size", re.compile(r"\b\d+(\.\d+)?\s*px\b")),
    ("css property", re.compile(r"\b(color|background|border|font-family|font-size)\s*:", re.I)),
]
CODE_RULES = [
    ("QColor from numbers", re.compile(r"QColor\s*\(\s*\d")),
    ("QColor.fromRgb/fromHsv", re.compile(r"QColor\.from(Rgb|Rgba|Hsv|Hsl|Cmyk)")),
    ("Qt named colour", re.compile(
        r"Qt\.(GlobalColor\.)?(black|white|red|blue|yellow|green|magenta|cyan|gray|darkGray|lightGray|"
        r"darkRed|darkGreen|darkBlue|darkCyan|darkMagenta|darkYellow)\b")),
    ("pen/border width literal", re.compile(r"\b(setWidth|setWidthF|setLineWidth|setMidLineWidth)\s*\(\s*\d")),
    ("QPen width literal", re.compile(r"QPen\s*\([^()]*,\s*\d+(\.\d+)?\s*[,)]")),
    ("QFont family literal", re.compile(r"QFont\s*\(\s*['\"]")),
]


def scan_source(source: str) -> list[str]:
    """Return violations found in ``source`` (string-token and code rules)."""
    problems: list[str] = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError) as exc:  # pragma: no cover
        return [f"cannot tokenize: {exc}"]
    code_lines: dict[int, str] = {}
    significant = [t for t in tokens if t.type not in (tokenize.NL, tokenize.COMMENT)]
    docstrings = set()
    for i, tok in enumerate(significant):
        # A docstring is a string that forms a statement on its own (prose, not styling).
        prev = significant[i - 1].type if i > 0 else tokenize.NEWLINE
        nxt = significant[i + 1].type if i + 1 < len(significant) else tokenize.NEWLINE
        if tok.type == tokenize.STRING and prev in (
                tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING) and nxt in (
                tokenize.NEWLINE, tokenize.ENDMARKER):
            docstrings.add(tok.start)
    for tok in tokens:
        if tok.start in docstrings:
            continue
        if tok.type == tokenize.STRING or tok.type == getattr(tokenize, "FSTRING_MIDDLE", -1):
            text = tok.string
            body = re.sub(r"^[rbfuRBFU]*('''|\"\"\"|'|\")|('''|\"\"\"|'|\")$", "", text)
            stripped = body.strip().lower()
            if stripped in COLOR_NAMES:
                problems.append(f"line {tok.start[0]}: colour name string {text}")
            for name in FONT_NAMES:
                # a backslash before the name means a LaTeX macro such as \times
                if re.search(rf"(?<![a-z\\]){re.escape(name)}(?![a-z])", stripped):
                    problems.append(f"line {tok.start[0]}: font family string {text}")
                    break
            for label, rx in STRING_RULES:
                if rx.search(body):
                    problems.append(f"line {tok.start[0]}: {label} in {text}")
        elif tok.type not in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE):
            code_lines.setdefault(tok.start[0], "")
            code_lines[tok.start[0]] += " " + tok.string
    for lineno, line in code_lines.items():
        compact = re.sub(r"\s*([().,])\s*", r"\1", line)
        for label, rx in CODE_RULES:
            if rx.search(compact) or rx.search(line):
                problems.append(f"line {lineno}: {label}: {line.strip()}")
    return problems


def package_files() -> list[Path]:
    return [p for p in PACKAGE.rglob("*.py") if p != THEME_FILE]


@pytest.mark.parametrize("snippet", [
    'c = "#FF00AA"',
    'c = QColor(255, 0, 0)',
    'c = Qt.GlobalColor.red',
    'pen.setWidth(3)',
    'p = QPen(color, 2)',
    'f = QFont("Arial")',
    'css = "QLabel { border: 3px solid; }"',
    'name = "red"',
    'fam = "Consolas"',
    'x = QColor.fromRgb(1, 2, 3)',
    'style = "color: black"',
])
def test_scanner_catches_known_violations(snippet: str) -> None:
    assert scan_source(snippet + "\n"), f"scanner missed: {snippet}"


@pytest.mark.parametrize("snippet", [
    'pen.setWidthF(theme.LINE_WIDTH)',
    'c = QColor(theme.BLACK)',
    'msg = "Reflect about Line"',
    'pm.fill(QColor(Qt.GlobalColor.transparent))',
    'op = r"\times"',
    'x = QPen(color)',
])
def test_scanner_allows_token_usage(snippet: str) -> None:
    assert scan_source(snippet + "\n") == []


def test_no_design_literals_outside_theme() -> None:
    failures = []
    for path in package_files():
        for problem in scan_source(path.read_text(encoding="utf-8")):
            failures.append(f"{path.relative_to(PACKAGE.parent)}: {problem}")
    assert not failures, "Design literals outside theme.py:\n" + "\n".join(failures)


def _all_variants() -> list[theme.ThemeColors]:
    return [theme.theme_colors(n, h) for n in (False, True) for h in (False, True)]


def test_chrome_palette_is_restricted() -> None:
    allowed = set(theme.PALETTE.values()) | set(theme.NEUTRALS.values())
    for neutral in theme.NEUTRALS.values():
        h = neutral.lstrip("#")
        assert h[0:2] == h[2:4] == h[4:6], f"{neutral} is not a neutral grey"
    for colors in _all_variants():
        for field, value in vars(colors).items():
            if isinstance(value, str) and value.startswith("#"):
                assert value in allowed, f"{colors.name}.{field} = {value} not in palette"


@pytest.mark.parametrize("colors", _all_variants(), ids=lambda c: c.name)
def test_text_contrast_meets_wcag_aa(colors: theme.ThemeColors) -> None:
    for role, (fg, bg, large) in theme.text_role_pairs(colors).items():
        ratio = theme.contrast_ratio(fg, bg)
        need = 3.0 if large else 4.5
        assert ratio >= need, f"{colors.name}/{role}: {fg} on {bg} = {ratio:.2f} < {need}"


@pytest.mark.parametrize("colors", _all_variants(), ids=lambda c: c.name)
def test_no_yellow_or_green_text_on_white(colors: theme.ThemeColors) -> None:
    low = {theme.PALETTE[n] for n in theme.LOW_CONTRAST_ON_LIGHT}
    for role, (fg, bg, _) in theme.text_role_pairs(colors).items():
        assert not (fg in low and bg == theme.WHITE), role


def test_high_contrast_removes_magenta_and_green() -> None:
    hc = theme.theme_colors(False, True)
    assert theme.resolve_color("magenta", hc) != theme.MAGENTA
    assert theme.resolve_color("green", hc) != theme.GREEN
    assert theme.MAGENTA not in vars(hc).values()
    assert theme.GREEN not in vars(hc).values()


def test_border_tokens() -> None:
    assert (theme.BORDER_DENSE, theme.BORDER, theme.BORDER_HEAVY) == (2, 3, 4)
    assert theme.RADIUS == 0
    assert theme.SHADOW_OFFSET == 4
    assert theme.FOCUS_RING == 4
    assert theme.MIN_HIT_TOOLBAR >= 28 and theme.TOOLBAR_BUTTON >= theme.MIN_HIT_TOOLBAR
    assert theme.MIN_HIT >= 24


def test_stylesheet_generated_from_tokens() -> None:
    css = theme.build_stylesheet(theme.LIGHT, 11)
    assert f"border: {theme.BORDER}px solid {theme.BLACK}" in css
    assert f"border: {theme.BORDER_HEAVY}px solid" in css
    assert f"border: {theme.BORDER_DENSE}px solid" in css
    assert "border-radius: 0px" in css
    assert theme.UI_FONT_FAMILIES[0] in css and theme.MONO_FONT_FAMILIES[0] in css
    night = theme.build_stylesheet(theme.NIGHT, 11)
    assert f"background: {theme.BLACK}" in night


def test_font_size_clamp_and_system_scaling() -> None:
    assert theme.clamp_font_size(3) == theme.FONT_SIZE_MIN
    assert theme.clamp_font_size(99) == theme.FONT_SIZE_MAX
    assert theme.scaled_font_pt(12, theme.SYSTEM_BASELINE_PT) == 12
    assert theme.scaled_font_pt(12, theme.SYSTEM_BASELINE_PT * 1.5) == pytest.approx(18)
