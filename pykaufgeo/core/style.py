"""Visual style of an element. Colours are theme tokens (``ink``, ``blue``) or ``#RRGGBB``."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields

from pykaufgeo import theme
from pykaufgeo.core.types import GRAPHICAL_2D, GeoType

LINE_STYLES = ("solid", "dash", "dot", "dashdot")
POINT_SHAPES = ("circle", "square", "cross", "plus", "diamond", "triangle", "ring")
LABEL_MODES = ("name", "name_value", "value", "caption", "caption_value")
ANIMATION_MODES = ("oscillate", "increasing", "decreasing", "once")
EQUATION_FORMS = ("input", "implicit", "explicit")
VIEW_IDS = ("g1", "g2", "g3d")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

KIND_FOR_TYPE: dict[GeoType, str] = {
    GeoType.POINT: "point_free", GeoType.VECTOR: "vector", GeoType.LINE: "line",
    GeoType.SEGMENT: "segment", GeoType.RAY: "ray", GeoType.POLYLINE: "polyline",
    GeoType.FUNCTION: "function", GeoType.CURVE: "curve", GeoType.CIRCLE: "circle",
    GeoType.CONIC: "conic", GeoType.IMPLICIT: "implicit", GeoType.POLYGON: "polygon",
    GeoType.ANGLE: "angle", GeoType.LOCUS: "locus", GeoType.INEQUALITY: "inequality",
    GeoType.TEXT: "text", GeoType.NUMBER: "number", GeoType.BOOLEAN: "boolean",
    GeoType.LIST: "list", GeoType.COMPLEX: "complex",
}


@dataclass
class Style:
    color: str = "ink"
    opacity: float = theme.FILL_OPACITY
    line_thickness: int = theme.LINE_WIDTH
    line_style: str = "solid"
    point_size: int = theme.POINT_SIZE
    point_shape: str = "circle"
    label_mode: str = "name"
    label_visible: bool = True
    caption: str = ""
    visible_in: frozenset[str] = field(default_factory=lambda: frozenset({"g1"}))
    layer: int = 0
    fixed: bool = False
    trace: bool = False
    animating: bool = False
    animation_speed: float = 1.0
    animation_mode: str = "oscillate"
    selection_allowed: bool = True
    auxiliary: bool = False
    equation_form: str = "input"
    label_offset: tuple[int, int] = (0, 0)
    decimals: int | None = None

    @classmethod
    def default_for(cls, kind: GeoType, free: bool) -> "Style":
        token_kind = KIND_FOR_TYPE.get(kind, "default")
        if kind is GeoType.POINT and not free:
            token_kind = "point_dependent"
        s = cls(color=theme.object_color_token(token_kind))
        # Like GeoGebra's "automatic" labelling: new points show their name, other objects do not.
        s.label_visible = kind in (GeoType.POINT, GeoType.POINT3D, GeoType.COMPLEX)
        if kind is GeoType.ANGLE:
            s.opacity = theme.ANGLE_FILL_OPACITY
        if kind not in GRAPHICAL_2D or kind is GeoType.ANGLE:
            s.visible_in = frozenset()
        if kind in (GeoType.POINT3D, GeoType.VECTOR3D):
            s.visible_in = frozenset({"g3d"})
        return s

    @property
    def visible(self) -> bool:
        return "g1" in self.visible_in

    def to_dict(self) -> dict:
        d = asdict(self)
        d["visible_in"] = sorted(self.visible_in)
        d["label_offset"] = list(self.label_offset)
        return d

    @classmethod
    def from_dict(cls, data: dict, base: "Style | None" = None) -> "Style":
        """Read a style, ignoring unknown keys and invalid values."""
        s = base or cls()
        for f in fields(cls):
            if f.name not in data:
                continue
            v = data[f.name]
            if f.name == "visible_in":
                if isinstance(v, (list, tuple)):
                    s.visible_in = frozenset(x for x in v if x in VIEW_IDS)
            elif f.name == "label_offset":
                if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(k, (int, float)) for k in v):
                    s.label_offset = (int(v[0]), int(v[1]))
            elif f.name == "color":
                if isinstance(v, str) and (_HEX.match(v) or v.lower() in theme.COLOR_NAMES):
                    s.color = v
            elif f.name == "decimals":
                if v is None or (isinstance(v, int) and 0 <= v <= 15):
                    s.decimals = v
            elif f.name in ("line_style", "point_shape", "label_mode", "animation_mode", "equation_form"):
                allowed = {"line_style": LINE_STYLES, "point_shape": POINT_SHAPES, "label_mode": LABEL_MODES,
                           "animation_mode": ANIMATION_MODES, "equation_form": EQUATION_FORMS}[f.name]
                if v in allowed:
                    setattr(s, f.name, v)
            else:
                default = getattr(s, f.name)
                if isinstance(default, bool):
                    if isinstance(v, bool):
                        setattr(s, f.name, v)
                elif isinstance(default, int):
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        setattr(s, f.name, int(v))
                elif isinstance(default, float):
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        setattr(s, f.name, float(v))
                elif isinstance(default, str) and isinstance(v, str):
                    setattr(s, f.name, v)
        s.opacity = min(max(s.opacity, 0.0), 1.0)
        s.layer = min(max(s.layer, 0), 9)
        return s

    def copy(self) -> "Style":
        return Style.from_dict(self.to_dict())
