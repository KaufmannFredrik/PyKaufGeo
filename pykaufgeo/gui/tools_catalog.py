"""The tool catalogue: groups shown in the toolbar and the tools inside them.

``implemented`` is set per tool when the tool really works; the toolbar shows a
yellow warning block for tools that are not implemented yet instead of silently
doing nothing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    id: str
    name: str
    help: str
    milestone: str
    implemented: bool = False


@dataclass(frozen=True)
class ToolGroup:
    id: str
    name: str
    tools: tuple[ToolSpec, ...]


# Milestones whose tools all work; every other tool says "not implemented yet" when chosen.
DONE_MILESTONES = frozenset({"M2", "M3", "M4"})


def _t(id_: str, name: str, help_: str, milestone: str) -> ToolSpec:
    return ToolSpec(id_, name, help_, milestone, milestone in DONE_MILESTONES)


TOOL_GROUPS: tuple[ToolGroup, ...] = (
    ToolGroup("move", "Move", (
        _t("move", "Move", "Drag or select objects", "M2"),
        _t("pen", "Pen", "Write or sketch in the Graphics View", "M3"),
        _t("freehand", "Freehand Shape", "Sketch a function graph, circle, segment or polygon", "M3"),
    )),
    ToolGroup("point", "Point", (
        _t("point", "Point", "Click on the Graphics View, an object or an intersection", "M2"),
        _t("point_on_object", "Point on Object", "Click inside an object or on its boundary", "M3"),
        _t("attach_detach", "Attach / Detach Point", "Select point, then object to attach it to", "M3"),
        _t("intersect", "Intersect", "Select intersecting objects or click their intersection", "M3"),
        _t("midpoint", "Midpoint or Center", "Select two points, a segment, circle, or conic", "M3"),
        _t("complex_number", "Complex Number", "Select position for the complex number", "M3"),
        _t("extremum", "Extremum", "Select a function", "M4"),
        _t("roots", "Roots", "Select a function", "M4"),
    )),
    ToolGroup("line", "Line", (
        _t("line", "Line", "Select two points or positions", "M2"),
        _t("segment", "Segment", "Select two points or positions", "M3"),
        _t("segment_fixed", "Segment with Given Length", "Select point, then enter length", "M3"),
        _t("ray", "Ray", "Select starting point, then point on ray", "M3"),
        _t("polyline", "Polyline", "Select all vertices, then first vertex again", "M3"),
        _t("vector", "Vector", "Select starting point, then end point", "M3"),
        _t("vector_from_point", "Vector from Point", "Select point and a vector", "M3"),
    )),
    ToolGroup("special_line", "Special Lines", (
        _t("perpendicular", "Perpendicular Line", "Select point and perpendicular line", "M3"),
        _t("parallel", "Parallel Line", "Select point and parallel line", "M3"),
        _t("perp_bisector", "Perpendicular Bisector", "Select two points or a segment", "M3"),
        _t("angle_bisector", "Angle Bisector", "Select three points or two lines", "M3"),
        _t("tangents", "Tangents", "Select point, then circle, conic, or function", "M3"),
        _t("polar", "Polar or Diameter Line", "Select point or line, then circle or conic", "M3"),
        _t("best_fit", "Best Fit Line", "Select points using selection rectangle or a list", "M3"),
        _t("locus", "Locus", "Select locus point, then point on object", "M3"),
    )),
    ToolGroup("polygon", "Polygon", (
        _t("polygon", "Polygon", "Select all vertices, then first vertex again", "M3"),
        _t("regular_polygon", "Regular Polygon", "Select two points, then enter number of vertices", "M3"),
        _t("rigid_polygon", "Rigid Polygon", "Select all vertices, then first vertex again", "M3"),
        _t("vector_polygon", "Vector Polygon", "Select all vertices, then first vertex again", "M3"),
    )),
    ToolGroup("circle", "Circle", (
        _t("circle_center_point", "Circle with Center through Point", "Select center point, then point on circle", "M2"),
        _t("circle_center_radius", "Circle: Center & Radius", "Select center point, then enter radius", "M3"),
        _t("compass", "Compass", "Select segment or two points for radius, then center", "M3"),
        _t("circle_3points", "Circle through 3 Points", "Select three points", "M3"),
        _t("semicircle", "Semicircle through 2 Points", "Select two points", "M3"),
        _t("arc_center", "Circular Arc", "Select center, then two points", "M3"),
        _t("circumarc", "Circumcircular Arc", "Select three points", "M3"),
        _t("sector_center", "Circular Sector", "Select center, then two points", "M3"),
        _t("circumsector", "Circumcircular Sector", "Select three points", "M3"),
    )),
    ToolGroup("conic", "Conic", (
        _t("ellipse", "Ellipse", "Select two foci, then point on ellipse", "M3"),
        _t("hyperbola", "Hyperbola", "Select two foci, then point on hyperbola", "M3"),
        _t("parabola", "Parabola", "Select focus, then directrix", "M3"),
        _t("conic5", "Conic through 5 Points", "Select five points", "M3"),
    )),
    ToolGroup("measure", "Measure", (
        _t("angle", "Angle", "Select three points or two lines", "M3"),
        _t("angle_fixed", "Angle with Given Size", "Select leg point, vertex, then enter size", "M3"),
        _t("distance", "Distance or Length", "Select two points, a segment, polygon, or circle", "M3"),
        _t("area", "Area", "Select polygon, circle, or ellipse", "M3"),
        _t("slope", "Slope", "Select a line", "M3"),
        _t("create_list", "List", "Select objects with a rectangle", "M3"),
    )),
    ToolGroup("transform", "Transform", (
        _t("reflect_line", "Reflect about Line", "Select object, then line of reflection", "M3"),
        _t("reflect_point", "Reflect about Point", "Select object, then center point", "M3"),
        _t("reflect_circle", "Reflect about Circle", "Select object, then circle (inversion)", "M3"),
        _t("rotate", "Rotate around Point", "Select object, center point, then enter angle", "M3"),
        _t("translate", "Translate by Vector", "Select object, then vector", "M3"),
        _t("dilate", "Dilate from Point", "Select object, center point, then enter factor", "M3"),
    )),
    ToolGroup("special", "Special Objects", (
        _t("text", "Text", "Select position or point for text", "M3"),
        _t("image", "Image", "Select position for image", "M3"),
        _t("relation", "Relation", "Select two objects", "M3"),
        _t("function_inspector", "Function Inspector", "Select a function", "M4"),
    )),
    ToolGroup("action", "Action Objects", (
        _t("slider", "Slider", "Select position for slider", "M3"),
        _t("checkbox", "Checkbox", "Select position for checkbox", "M8"),
        _t("button", "Button", "Select position for button", "M8"),
        _t("input_box", "Input Box", "Select position for input box", "M8"),
    )),
    ToolGroup("general", "General", (
        _t("move_view", "Move Graphics View", "Drag the Graphics View or an axis", "M2"),
        _t("zoom_in", "Zoom In", "Click the Graphics View to zoom in", "M2"),
        _t("zoom_out", "Zoom Out", "Click the Graphics View to zoom out", "M2"),
        _t("show_hide_object", "Show / Hide Object", "Select objects to show or hide", "M3"),
        _t("show_hide_label", "Show / Hide Label", "Select objects to show or hide their labels", "M3"),
        _t("copy_style", "Copy Visual Style", "Select model object, then objects to copy to", "M3"),
        _t("delete", "Delete", "Select objects to delete", "M2"),
    )),
)


def all_tools() -> list[ToolSpec]:
    return [t for g in TOOL_GROUPS for t in g.tools]


def tool_by_id(tool_id: str) -> ToolSpec:
    for t in all_tools():
        if t.id == tool_id:
            return t
    raise KeyError(tool_id)
