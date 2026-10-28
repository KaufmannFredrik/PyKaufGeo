"""Design tokens for PyKaufGeo: the single source of truth for the brutalist look.

Every colour, font family and border width used anywhere in the application is
defined here. Other modules refer to these names; ``tests/test_theme_tokens.py``
fails if a literal colour, font family or border width appears outside this file.

The module is pure Python (no Qt import) so the core model can read default
object colour tokens without pulling in the GUI. ``build_stylesheet`` produces the
complete Qt stylesheet for the application from the tokens.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# --------------------------------------------------------------------------------
# Palette. No other colours may appear in the UI chrome.
# --------------------------------------------------------------------------------

BLACK = "#000000"
WHITE = "#FFFFFF"
RED = "#FF0000"
BLUE = "#0000FF"
YELLOW = "#FFFF00"
GREEN = "#00FF00"
MAGENTA = "#FF00FF"

PALETTE: dict[str, str] = {
    "black": BLACK,
    "white": WHITE,
    "red": RED,
    "blue": BLUE,
    "yellow": YELLOW,
    "green": GREEN,
    "magenta": MAGENTA,
}

# Neutral greys: only for grid lines and disabled states.
NEUTRALS: dict[str, str] = {
    "grid_major_light": "#9E9E9E",
    "grid_minor_light": "#D6D6D6",
    "grid_major_night": "#6B6B6B",
    "grid_minor_night": "#2E2E2E",
    "disabled_fg_light": "#6B6B6B",
    "disabled_bg_light": "#D6D6D6",
    "disabled_fg_night": "#9E9E9E",
    "disabled_bg_night": "#2E2E2E",
}

# Named colours accepted by commands such as SetColor(A, "red"). Values are tokens
# ("ink" follows the theme: black on the light canvas, white on the Night canvas).
COLOR_NAMES: dict[str, str] = {
    "black": "black",
    "white": "white",
    "red": "red",
    "blue": "blue",
    "yellow": "yellow",
    "green": "green",
    "magenta": "magenta",
    "ink": "ink",
}

# Colour choices offered by the style bar and Properties, in this order.
SWATCH_TOKENS: tuple[str, ...] = ("ink", "blue", "red", "magenta", "green", "yellow", "black", "white")

# Colours that must never be used for text on a light background.
LOW_CONTRAST_ON_LIGHT: frozenset[str] = frozenset({"yellow", "green"})

# --------------------------------------------------------------------------------
# Shape and borders.
# --------------------------------------------------------------------------------

RADIUS = 0
BORDER_DENSE = 2      # spreadsheet cells, tables, list rows
BORDER = 3            # panels, buttons, inputs, menus, tooltips, scrollbars, handles
BORDER_HEAVY = 4      # dialogs and the main window frame
SPLITTER = 8          # thick black splitter bars between views
FOCUS_RING = 4        # yellow focus ring width
FOCUS_EDGE = 2        # black lines either side of the yellow ring
SHADOW_OFFSET = 4     # hard offset shadow: solid block 4 px right and 4 px down
ICON_STROKE = 3       # stroke width of self-drawn icons
ICON_HATCH_STROKE = 1.5  # hatching inside icons (area tool)

# --------------------------------------------------------------------------------
# Type.
# --------------------------------------------------------------------------------

UI_FONT_FAMILIES: tuple[str, ...] = ("Arial", "Helvetica", "Segoe UI", "sans-serif")
MONO_FONT_FAMILIES: tuple[str, ...] = ("Consolas", "Courier New", "monospace")
FONT_WEIGHT = 700
FONT_WEIGHT_HEAVY = 900
FONT_SIZE_DEFAULT = 11
FONT_SIZE_MIN = 10
FONT_SIZE_MAX = 24
# Message blocks with white text on red are rendered as WCAG "large text"
# (14 pt bold) so that their 4.0:1 contrast meets AA. See docs/DECISIONS.md D-007.
LARGE_TEXT_PT = 14
# Windows' default UI font size at 100 % text scaling; used to derive the system
# font scaling factor (system pt / baseline pt).
SYSTEM_BASELINE_PT = 9.0

# --------------------------------------------------------------------------------
# Sizes and spacing (pixels).
# --------------------------------------------------------------------------------

TOOLBAR_BUTTON = 44   # square tool buttons
MIN_HIT_TOOLBAR = 28
MIN_HIT = 24
ICON_SIZE = 32
ICON_MENU = 28
SPACING = 6
PADDING = 6
PADDING_WIDE = 12
SCROLLBAR = 22

# --------------------------------------------------------------------------------
# Motion. Chrome never animates; only mathematical content may.
# --------------------------------------------------------------------------------

CHROME_ANIMATION_MS = 0
TOOLTIP_DELAY_MS = 500
TOOLTIP_HIDE_MS = 10000
ANIMATION_FPS = 60

# --------------------------------------------------------------------------------
# Graphics view tokens (mathematical content).
# --------------------------------------------------------------------------------

AXIS_WIDTH = 3
GRID_WIDTH = 1
POINT_OUTLINE = 3
POINT_SIZE = 5             # default point size (radius in px is POINT_SIZE + 1)
LINE_WIDTH = 3             # default stroke for lines, conics, functions
SELECTION_EXTRA = 3        # extra stroke width for selected objects
HALO_WIDTH = 8             # yellow halo behind selected objects
HALO_EDGE = 2              # black outline of the halo
FILL_EDGE = 2              # dark edge around filled areas
CASING_WIDTH = 1           # ink casing each side of strokes with < 3:1 contrast to the canvas
GRAPHIC_CONTRAST = 3.0     # WCAG 1.4.11 minimum for non-text graphics
FILL_OPACITY = 0.25        # default fill opacity for polygons and regions
ANGLE_FILL_OPACITY = 0.4

TICK_LENGTH = 6            # axis tick marks
AXIS_ARROW = 10            # arrow heads at the positive ends of the axes
VECTOR_HEAD = 14           # vector arrow heads
LABEL_GAP = 6              # distance between an object and its label
SNAP_PX = 10               # snapping radius to grid intersections
HIT_TOLERANCE = 8          # pick distance around curves; points use max(radius, MIN_HIT / 2)
PREVIEW_WIDTH = 2          # rubber-band previews of tools
ZOOM_RECT_WIDTH = 2        # rectangle zoom outline and selection rectangle
ANGLE_RADIUS = 30          # radius of drawn angle sectors
RIGHT_ANGLE_SIZE = 16      # side of the square marking a right angle
SLIDER_WIDTH = 200         # default slider track length
SLIDER_KNOB = 9            # slider knob radius
SLIDER_TRACK = 3           # slider track stroke
SLIDER_MARGIN = 24         # default slider position from the top-left corner
SLIDER_SPACING = 48        # vertical distance between default slider positions
TEXT_PAD = 4               # padding around texts in the Graphics view (hit area)
GHOST_OPACITY = 0.35       # hidden objects while the Show / Hide Object tool is active
PEN_WIDTH = 3              # Pen tool strokes
TRACE_LIMIT = 4000         # traced drawables kept per view before the oldest are dropped
# Dash patterns in multiples of the line width (Qt convention).
DASH_PATTERNS: dict[str, tuple[float, ...]] = {"dash": (4.0, 3.0), "dot": (1.0, 2.0), "dashdot": (4.0, 2.0, 1.0, 2.0)}
PREVIEW_DASH: tuple[float, ...] = (3.0, 3.0)

# Formula rendering (matplotlib mathtext). DejaVu Sans ships with matplotlib under the
# Bitstream Vera / public-domain licence, so nothing is bundled by us (docs/DESIGN.md).
MATH_FONTSET = "custom"
MATH_FONT_RM = "DejaVu Sans:bold"
MATH_FONT_IT = "DejaVu Sans:italic:bold"
MATH_FONT_BF = "DejaVu Sans:bold"
MATH_FONT_WEIGHT = "bold"

# Algebra view rows.
ALGEBRA_ROW_MIN = 40
ALGEBRA_BOX = 16           # visibility toggle and colour square

# Default colour token per object kind. "ink" means black on the light canvas and
# white on the Night canvas.
OBJECT_COLORS: dict[str, str] = {
    "point_free": "blue",
    "point_dependent": "ink",
    "point_on_path": "yellow",
    "vector": "ink",
    "line": "ink",
    "segment": "ink",
    "ray": "ink",
    "polyline": "ink",
    "function": "blue",
    "curve": "blue",
    "circle": "red",
    "conic": "red",
    "implicit": "magenta",
    "polygon": "yellow",
    "angle": "green",
    "locus": "magenta",
    "inequality": "blue",
    "integral": "blue",
    "text": "ink",
    "number": "ink",
    "boolean": "ink",
    "list": "ink",
    "complex": "blue",
    "default": "ink",
}

# High-contrast mode removes the magenta and green accents.
HIGH_CONTRAST_SUBSTITUTES: dict[str, str] = {"magenta": "blue", "green": "ink"}


# --------------------------------------------------------------------------------
# Role colours per theme.
# --------------------------------------------------------------------------------

@dataclass(frozen=True)
class ThemeColors:
    """Concrete colour roles for one theme variant."""

    name: str
    bg: str
    fg: str
    border: str
    title_bg: str
    title_fg: str
    hover_bg: str
    hover_fg: str
    pressed_bg: str
    pressed_fg: str
    selection_bg: str
    selection_fg: str
    tool_selected_bg: str
    tool_selected_fg: str
    focus: str
    focus_edge: str
    shadow: str
    error_bg: str
    error_fg: str
    success_bg: str
    success_fg: str
    warning_bg: str
    warning_fg: str
    disabled_bg: str
    disabled_fg: str
    canvas_bg: str
    axes: str
    grid_major: str
    grid_minor: str
    ink: str
    high_contrast: bool = False


LIGHT = ThemeColors(
    name="light",
    bg=WHITE, fg=BLACK, border=BLACK,
    title_bg=BLACK, title_fg=WHITE,
    hover_bg=BLACK, hover_fg=WHITE,
    pressed_bg=YELLOW, pressed_fg=BLACK,
    selection_bg=YELLOW, selection_fg=BLACK,
    tool_selected_bg=BLACK, tool_selected_fg=YELLOW,
    focus=YELLOW, focus_edge=BLACK,
    shadow=BLACK,
    error_bg=RED, error_fg=WHITE,
    success_bg=GREEN, success_fg=BLACK,
    warning_bg=YELLOW, warning_fg=BLACK,
    disabled_bg=NEUTRALS["disabled_bg_light"], disabled_fg=NEUTRALS["disabled_fg_light"],
    canvas_bg=WHITE, axes=BLACK,
    grid_major=NEUTRALS["grid_major_light"], grid_minor=NEUTRALS["grid_minor_light"],
    ink=BLACK,
)

NIGHT = ThemeColors(
    name="night",
    bg=BLACK, fg=WHITE, border=WHITE,
    title_bg=WHITE, title_fg=BLACK,
    hover_bg=WHITE, hover_fg=BLACK,
    pressed_bg=YELLOW, pressed_fg=BLACK,
    selection_bg=YELLOW, selection_fg=BLACK,
    tool_selected_bg=WHITE, tool_selected_fg=BLACK,
    focus=YELLOW, focus_edge=WHITE,
    shadow=WHITE,
    error_bg=RED, error_fg=WHITE,
    success_bg=GREEN, success_fg=BLACK,
    warning_bg=YELLOW, warning_fg=BLACK,
    disabled_bg=NEUTRALS["disabled_bg_night"], disabled_fg=NEUTRALS["disabled_fg_night"],
    canvas_bg=BLACK, axes=WHITE,
    grid_major=NEUTRALS["grid_major_night"], grid_minor=NEUTRALS["grid_minor_night"],
    ink=WHITE,
)


def theme_colors(night: bool = False, high_contrast: bool = False) -> ThemeColors:
    """Return the role colours for the requested theme variant.

    High contrast swaps the green success block for an ink block and keeps every
    other role on black/white/yellow/red/blue, which all reach at least AA.
    """
    base = NIGHT if night else LIGHT
    if not high_contrast:
        return base
    return replace(
        base,
        name=base.name + "-hc",
        success_bg=base.fg,
        success_fg=base.bg,
        # Night's selected tool already inverts; light keeps black + yellow.
        high_contrast=True,
    )


def resolve_color(token: str, colors: ThemeColors) -> str:
    """Turn a colour token (``ink``, ``red``, ...) or ``#RRGGBB`` into a hex string."""
    if token.startswith("#"):
        return token
    key = token.lower()
    if colors.high_contrast and key in HIGH_CONTRAST_SUBSTITUTES:
        key = HIGH_CONTRAST_SUBSTITUTES[key]
    if key == "ink":
        return colors.ink
    if key in PALETTE:
        return PALETTE[key]
    return colors.ink


def object_color_token(kind: str) -> str:
    """Default colour token for an object kind (see ``OBJECT_COLORS``)."""
    return OBJECT_COLORS.get(kind, OBJECT_COLORS["default"])


# --------------------------------------------------------------------------------
# Contrast helpers (WCAG 2.x).
# --------------------------------------------------------------------------------

def _channel(c: int) -> float:
    s = c / 255.0
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    la, lb = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def text_role_pairs(colors: ThemeColors) -> dict[str, tuple[str, str, bool]]:
    """Text/background pairs used in the chrome: name -> (fg, bg, is_large_text)."""
    return {
        "body": (colors.fg, colors.bg, False),
        "title": (colors.title_fg, colors.title_bg, False),
        "hover": (colors.hover_fg, colors.hover_bg, False),
        "pressed": (colors.pressed_fg, colors.pressed_bg, False),
        "selection": (colors.selection_fg, colors.selection_bg, False),
        "tool_selected": (colors.tool_selected_fg, colors.tool_selected_bg, False),
        "error": (colors.error_fg, colors.error_bg, True),
        "success": (colors.success_fg, colors.success_bg, False),
        "warning": (colors.warning_fg, colors.warning_bg, False),
    }


# --------------------------------------------------------------------------------
# Font helpers.
# --------------------------------------------------------------------------------

def clamp_font_size(pt: float) -> int:
    return int(max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, round(pt))))


def scaled_font_pt(user_pt: int, system_pt: float) -> float:
    """Apply the operating system's text scaling to the user's chosen size."""
    factor = system_pt / SYSTEM_BASELINE_PT if system_pt > 0 else 1.0
    factor = max(0.75, min(3.0, factor))
    return clamp_font_size(user_pt) * factor


def _families(fams: tuple[str, ...]) -> str:
    generic = {"sans-serif", "monospace", "serif"}
    return ", ".join(f if f in generic else f'"{f}"' for f in fams)


# --------------------------------------------------------------------------------
# Qt stylesheet.
# --------------------------------------------------------------------------------

def build_stylesheet(colors: ThemeColors, font_pt: float) -> str:
    """Generate the complete application stylesheet from the tokens."""
    c = colors
    ui = _families(UI_FONT_FAMILIES)
    mono = _families(MONO_FONT_FAMILIES)
    pt = f"{font_pt:.1f}pt"
    large_pt = f"{max(font_pt, LARGE_TEXT_PT):.1f}pt"
    title_pt = f"{font_pt:.1f}pt"
    b, bd, bh = BORDER, BORDER_DENSE, BORDER_HEAVY
    pad, padw, hit, sb = PADDING, PADDING_WIDE, MIN_HIT, SCROLLBAR
    return f"""
* {{ outline: none; }}
QWidget {{
    background: {c.bg}; color: {c.fg};
    font-family: {ui}; font-size: {pt}; font-weight: {FONT_WEIGHT};
    selection-background-color: {c.selection_bg}; selection-color: {c.selection_fg};
}}
QWidget:disabled {{ color: {c.disabled_fg}; }}
QMainWindow, QDialog {{ background: {c.bg}; }}
QFrame#MainFrame {{ border: {bh}px solid {c.border}; background: {c.bg}; }}

/* ---------- menus ---------- */
QMenuBar {{ background: {c.bg}; border: none; padding: 0; }}
QMenuBar::item {{ background: transparent; color: {c.fg}; padding: {pad}px {padw}px; margin: 0; }}
QMenuBar::item:selected {{ background: {c.hover_bg}; color: {c.hover_fg}; }}
QMenuBar::item:pressed {{ background: {c.pressed_bg}; color: {c.pressed_fg}; }}
/* BrutalMenu paints its own 3 px border and hard shadow (QMenu ignores per-edge
   borders); the stylesheet only styles the items. */
QMenu {{ background: {c.bg}; color: {c.fg}; border: none; padding: 0; margin: 0; icon-size: {ICON_MENU}px; }}
QMenu::item {{ padding: {pad}px {padw * 3}px {pad}px {padw}px; min-height: {hit}px; background: {c.bg}; }}
QMenu::item:selected {{ background: {c.hover_bg}; color: {c.hover_fg}; }}
QMenu::item:disabled {{ color: {c.disabled_fg}; background: {c.bg}; }}
QMenu::separator {{ height: {b}px; background: {c.border}; margin: 0; }}
QMenu::indicator {{ width: {hit - 2 * pad}px; height: {hit - 2 * pad}px; margin-left: {pad}px;
                    border: {bd}px solid {c.border}; background: {c.bg}; }}
QMenu::indicator:checked {{ background: {c.fg}; }}
QMenu::indicator:selected {{ border-color: {c.hover_fg}; }}
QMenu::indicator:checked:selected {{ background: {c.hover_fg}; }}
QMenu::right-arrow {{ width: {pad}px; height: {pad}px; background: {c.fg}; margin-right: {padw}px; }}
QMenu::right-arrow:selected {{ background: {c.hover_fg}; }}

/* ---------- buttons ---------- */
QPushButton, QToolButton {{
    background: {c.bg}; color: {c.fg}; border: {b}px solid {c.border}; border-radius: {RADIUS}px;
    padding: {pad // 2}px {padw}px; min-height: {hit - 2 * b}px; min-width: {hit - 2 * b}px;
}}
QPushButton:hover, QToolButton:hover {{ background: {c.hover_bg}; color: {c.hover_fg}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {c.pressed_bg}; color: {c.pressed_fg}; }}
QPushButton:checked, QToolButton:checked {{ background: {c.tool_selected_bg}; color: {c.tool_selected_fg}; }}
QPushButton:disabled, QToolButton:disabled {{
    background: {c.disabled_bg}; color: {c.disabled_fg}; border-color: {c.disabled_fg}; }}
QPushButton[role="primary"] {{ background: {c.fg}; color: {c.bg}; }}
QPushButton[role="primary"]:hover {{ background: {c.bg}; color: {c.fg}; }}
QPushButton[role="primary"]:pressed {{ background: {c.pressed_bg}; color: {c.pressed_fg}; }}

/* ---------- text inputs (monospace: anything containing math) ---------- */
QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox {{
    background: {c.bg}; color: {c.fg}; border: {b}px solid {c.border}; border-radius: {RADIUS}px;
    padding: {pad // 2}px {pad}px; min-height: {hit - 2 * b}px;
    font-family: {mono}; font-weight: {FONT_WEIGHT};
}}
QLineEdit:disabled, QAbstractSpinBox:disabled {{ background: {c.disabled_bg}; border-color: {c.disabled_fg}; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    width: {hit - 2 * b}px; border-left: {b}px solid {c.border}; background: {c.bg}; }}
QAbstractSpinBox::up-button {{ border-bottom: {bd}px solid {c.border}; }}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{ background: {c.hover_bg}; }}
QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {{ width: {pad}px; height: {pad}px; background: {c.fg}; }}
QAbstractSpinBox::up-arrow:hover, QAbstractSpinBox::down-arrow:hover {{ background: {c.hover_fg}; }}
*[mono="true"] {{ font-family: {mono}; }}

QComboBox {{
    background: {c.bg}; color: {c.fg}; border: {b}px solid {c.border}; border-radius: {RADIUS}px;
    padding: {pad // 2}px {pad}px; min-height: {hit - 2 * b}px;
}}
QComboBox:hover {{ background: {c.hover_bg}; color: {c.hover_fg}; }}
QComboBox::drop-down {{ width: {hit}px; border: none; border-left: {b}px solid {c.border}; }}
QComboBox::down-arrow {{ width: {pad + 2}px; height: {pad + 2}px; background: {c.fg}; }}
QComboBox::down-arrow:hover {{ background: {c.hover_fg}; }}
QComboBox QAbstractItemView {{
    background: {c.bg}; color: {c.fg}; border: {b}px solid {c.border};
    selection-background-color: {c.selection_bg}; selection-color: {c.selection_fg};
}}

/* ---------- check boxes and radio buttons: square, filled when on ---------- */
QCheckBox, QRadioButton {{ spacing: {pad}px; background: transparent; min-height: {hit}px; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: {hit - 2 * pad}px; height: {hit - 2 * pad}px; border: {b}px solid {c.border}; background: {c.bg}; }}
QCheckBox::indicator:checked {{ background: {c.fg}; }}
QRadioButton::indicator:checked {{ background: {c.fg}; border-color: {c.border}; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {c.fg}; background: {c.pressed_bg}; }}
QCheckBox::indicator:checked:hover, QRadioButton::indicator:checked:hover {{ background: {c.fg}; }}

/* ---------- sliders ---------- */
QSlider {{ min-height: {hit}px; background: transparent; }}
QSlider::groove:horizontal {{ height: {b * 2}px; background: {c.fg}; margin: 0 {pad}px; }}
QSlider::handle:horizontal {{
    width: {hit - 2 * b - 4}px; height: {hit - 2 * b}px; margin: -{hit // 2 - b}px -{pad}px;
    background: {c.bg}; border: {b}px solid {c.border}; }}
QSlider::handle:horizontal:hover {{ background: {c.hover_bg}; }}
QSlider::handle:horizontal:pressed {{ background: {c.pressed_bg}; }}

/* ---------- tabs: square boxes sharing borders; the current tab is inverted ---------- */
QTabWidget::pane {{ border: {b}px solid {c.border}; top: -{b}px; background: {c.bg}; }}
QTabBar::tab {{
    background: {c.bg}; color: {c.fg}; border: {b}px solid {c.border}; margin-right: -{b}px;
    padding: {pad // 2}px {pad}px; min-height: {hit - 2 * b}px; font-weight: {FONT_WEIGHT_HEAVY}; }}
QTabBar::tab:selected {{ background: {c.fg}; color: {c.bg}; }}
QTabBar::tab:hover:!selected {{ background: {c.hover_bg}; color: {c.hover_fg}; }}

/* ---------- scroll bars ---------- */
QScrollBar:vertical {{ width: {sb}px; background: {c.bg}; border: {b}px solid {c.border}; margin: 0; }}
QScrollBar:horizontal {{ height: {sb}px; background: {c.bg}; border: {b}px solid {c.border}; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c.fg}; min-height: {hit}px; margin: {bd}px; }}
QScrollBar::handle:horizontal {{ background: {c.fg}; min-width: {hit}px; margin: {bd}px; }}
QScrollBar::handle:hover {{ background: {c.pressed_bg}; border: {bd}px solid {c.border}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; background: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: {c.bg}; }}
QAbstractScrollArea::corner {{ background: {c.border}; }}

/* ---------- splitters ---------- */
QSplitter {{ background: {c.border}; }}
QSplitter::handle {{ background: {c.border}; }}
QSplitter::handle:horizontal {{ width: {SPLITTER}px; }}
QSplitter::handle:vertical {{ height: {SPLITTER}px; }}
QSplitter::handle:hover {{ background: {c.pressed_bg}; }}

/* ---------- panels ---------- */
QFrame#Panel {{ background: {c.bg}; border: {b}px solid {c.border}; }}
QWidget#PanelTitleBar {{ background: {c.title_bg}; }}
QLabel#PanelTitle {{
    background: {c.title_bg}; color: {c.title_fg}; padding: {pad // 2}px {pad}px;
    font-weight: {FONT_WEIGHT_HEAVY}; font-size: {title_pt};
}}
QPushButton#PanelClose {{
    background: {c.title_bg}; color: {c.title_fg}; border: {bd}px solid {c.title_fg};
    min-width: {hit - 2 * bd}px; min-height: {hit - 2 * bd}px; padding: 0; }}
QPushButton#PanelClose:hover {{ background: {c.title_fg}; color: {c.title_bg}; }}
QPushButton#PanelClose:pressed {{ background: {c.pressed_bg}; color: {c.pressed_fg}; }}
QLabel#PanelPlaceholder {{ color: {c.fg}; background: transparent; padding: {padw}px; }}
QLabel#PanelPlaceholderMilestone {{
    color: {c.warning_fg}; background: {c.warning_bg}; border: {b}px solid {c.border}; padding: {pad}px {padw}px; }}

/* ---------- toolbar ---------- */
QWidget#ToolBar {{ background: {c.bg}; border-bottom: {b}px solid {c.border}; }}
QLabel#ToolHelp {{ background: {c.bg}; color: {c.fg}; padding: 0 {padw}px; font-family: {mono}; }}

/* ---------- message blocks ---------- */
QLabel[kind="error"] {{
    background: {c.error_bg}; color: {c.error_fg}; border: {b}px solid {c.border};
    padding: {pad}px {padw}px; font-size: {large_pt}; font-weight: {FONT_WEIGHT_HEAVY}; }}
QLabel[kind="success"] {{
    background: {c.success_bg}; color: {c.success_fg}; border: {b}px solid {c.border};
    padding: {pad}px {padw}px; font-weight: {FONT_WEIGHT_HEAVY}; }}
QLabel[kind="warning"] {{
    background: {c.warning_bg}; color: {c.warning_fg}; border: {b}px solid {c.border};
    padding: {pad}px {padw}px; font-weight: {FONT_WEIGHT_HEAVY}; }}
QLabel[kind="info"] {{
    background: {c.bg}; color: {c.fg}; border: {b}px solid {c.border}; padding: {pad}px {padw}px; }}

/* ---------- input bar ---------- */
QWidget#InputBar {{ background: {c.bg}; border-top: {b}px solid {c.border}; }}
QLabel#InputLabel {{ background: {c.title_bg}; color: {c.title_fg}; padding: {pad}px {padw}px;
                     font-family: {mono}; font-weight: {FONT_WEIGHT_HEAVY}; }}
QLineEdit#InputField {{ font-family: {mono}; font-size: {pt}; }}

/* ---------- item views ---------- */
QListView, QTreeView, QTableView, QListWidget, QTreeWidget, QTableWidget {{
    background: {c.bg}; color: {c.fg}; border: {bd}px solid {c.border};
    selection-background-color: {c.selection_bg}; selection-color: {c.selection_fg};
    gridline-color: {c.border}; alternate-background-color: {c.bg};
}}
QListView::item, QTreeView::item {{ min-height: {hit}px; border-bottom: {bd}px solid {c.border}; padding: 0 {pad}px; }}
QListView::item:hover, QTreeView::item:hover {{ background: {c.hover_bg}; color: {c.hover_fg}; }}
QListView::item:selected, QTreeView::item:selected, QTableView::item:selected {{
    background: {c.selection_bg}; color: {c.selection_fg}; }}
QListView#AlgebraList {{ font-family: {mono}; border: none; }}
QHeaderView::section {{
    background: {c.title_bg}; color: {c.title_fg}; border: {bd}px solid {c.border};
    padding: {pad // 2}px {pad}px; font-weight: {FONT_WEIGHT_HEAVY}; }}
QTableView {{ font-family: {mono}; }}
QTableCornerButton::section {{ background: {c.title_bg}; border: {bd}px solid {c.border}; }}

/* ---------- tabs ---------- */
QTabWidget::pane {{ border: {b}px solid {c.border}; top: -{b}px; }}
QTabBar::tab {{
    background: {c.bg}; color: {c.fg}; border: {b}px solid {c.border}; padding: {pad}px {padw}px;
    min-height: {hit - 2 * b}px; margin-right: -{b}px; }}
QTabBar::tab:hover {{ background: {c.hover_bg}; color: {c.hover_fg}; }}
QTabBar::tab:selected {{ background: {c.fg}; color: {c.bg}; }}

QGroupBox {{ border: {b}px solid {c.border}; margin-top: {padw * 2}px; padding: {padw}px {pad}px {pad}px {pad}px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 0; top: 0; padding: {pad // 2}px {pad}px;
                    background: {c.title_bg}; color: {c.title_fg}; }}

QProgressBar {{ border: {b}px solid {c.border}; background: {c.bg}; text-align: center; min-height: {hit - 2 * b}px; }}
QProgressBar::chunk {{ background: {c.fg}; }}

QStatusBar {{ background: {c.bg}; border-top: {b}px solid {c.border}; }}
QStatusBar::item {{ border: none; }}
QToolTip {{ background: {c.bg}; color: {c.fg}; border: {b}px solid {c.border}; padding: {pad}px; }}

/* ---------- view bars, hints, completion, inline editor ---------- */
QWidget#ViewBar {{ background: {c.bg}; border-bottom: {bd}px solid {c.border}; }}
QWidget#ViewBar QPushButton {{ padding: 0 {pad}px; }}
QWidget#ViewBar QCheckBox {{ min-height: {hit}px; }}
QListWidget#CompletionList {{ border: none; font-family: {mono}; }}
QLineEdit#AlgebraEditor {{ border: {b}px solid {c.border}; font-family: {mono}; }}
QLineEdit#AlgebraEditor[kind="error"] {{ border: {b}px solid {c.error_bg}; }}

/* ---------- CAS view: numbered rows, the current row marked yellow ---------- */
QWidget#CasRows {{ background: {c.bg}; }}
QFrame#CasRow {{ background: {c.bg}; border-bottom: {bd}px solid {c.border}; }}
QFrame#CasRow[current="true"] {{ background: {c.selection_bg}; }}
QLabel#CasRowNumber {{
    background: {c.title_bg}; color: {c.title_fg}; font-family: {mono}; font-weight: {FONT_WEIGHT_HEAVY};
    min-width: {hit + pad}px; padding: {pad}px {pad // 2}px; }}
QFrame#CasRow[current="true"] QLabel#CasRowNumber {{ background: {c.selection_bg}; color: {c.selection_fg};
    border-right: {b}px solid {c.border}; }}
QLineEdit#CasInput {{ border: {bd}px solid {c.border}; font-family: {mono}; background: {c.bg}; color: {c.fg}; }}
QLabel#CasMark {{ color: {c.fg}; font-weight: {FONT_WEIGHT_HEAVY}; font-size: {large_pt}; background: transparent; }}
QLabel#CasOutput {{ color: {c.fg}; background: transparent; padding: {pad // 2}px 0; }}
QLabel#CasOutput[kind="error"] {{ background: {c.error_bg}; color: {c.error_fg}; font-weight: {FONT_WEIGHT_HEAVY};
    padding: {pad // 2}px {pad}px; }}
QLabel#CasNote {{ color: {c.fg}; background: transparent; font-family: {mono}; }}
QFrame#CasRow[current="true"] QLabel#CasMark, QFrame#CasRow[current="true"] QLabel#CasNote,
QFrame#CasRow[current="true"] QLabel#CasOutput {{ color: {c.selection_fg}; }}

/* ---------- frameless brutalist dialogs ---------- */
QWidget#DialogBody {{ background: {c.bg}; }}
QWidget#DialogTitleBar {{ background: {c.title_bg}; }}
QLabel#DialogTitle {{ background: {c.title_bg}; color: {c.title_fg}; padding: {pad}px {padw}px;
                      font-weight: {FONT_WEIGHT_HEAVY}; }}
QLabel#TooltipText {{ background: {c.bg}; color: {c.fg}; padding: {pad}px {padw}px; }}
QLabel#TooltipShortcut {{ background: {c.title_bg}; color: {c.title_fg}; padding: {pad}px {pad}px;
                          font-family: {mono}; }}
QLabel#Heading {{ font-size: {max(font_pt * 1.6, LARGE_TEXT_PT):.1f}pt; font-weight: {FONT_WEIGHT_HEAVY}; background: transparent; }}
QLabel#Mono, QLabel[mono="true"] {{ font-family: {mono}; background: transparent; }}
"""
