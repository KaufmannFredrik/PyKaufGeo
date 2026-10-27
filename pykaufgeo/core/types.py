"""Object types of the construction."""

from __future__ import annotations

from enum import Enum


class GeoType(str, Enum):
    NUMBER = "number"
    ANGLE = "angle"
    BOOLEAN = "boolean"
    TEXT = "text"
    POINT = "point"
    POINT3D = "point3d"
    VECTOR = "vector"
    VECTOR3D = "vector3d"
    LINE = "line"
    RAY = "ray"
    SEGMENT = "segment"
    CIRCLE = "circle"
    CONIC = "conic"
    POLYGON = "polygon"
    POLYLINE = "polyline"
    FUNCTION = "function"
    FUNCTION_NVAR = "function_nvar"
    CURVE = "curve"
    IMPLICIT = "implicit"
    LOCUS = "locus"
    LIST = "list"
    MATRIX = "matrix"
    COMPLEX = "complex"
    INEQUALITY = "inequality"
    BUTTON = "button"
    INPUT_BOX = "input_box"
    IMAGE = "image"
    PLANE = "plane"
    SPHERE = "sphere"
    SURFACE = "surface"
    POLYHEDRON = "polyhedron"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        return DISPLAY_NAMES[self]


DISPLAY_NAMES: dict[GeoType, str] = {
    GeoType.NUMBER: "Number", GeoType.ANGLE: "Angle", GeoType.BOOLEAN: "Boolean",
    GeoType.TEXT: "Text", GeoType.POINT: "Point", GeoType.POINT3D: "Point 3D",
    GeoType.VECTOR: "Vector", GeoType.VECTOR3D: "Vector 3D", GeoType.LINE: "Line",
    GeoType.RAY: "Ray", GeoType.SEGMENT: "Segment", GeoType.CIRCLE: "Circle",
    GeoType.CONIC: "Conic", GeoType.POLYGON: "Polygon", GeoType.POLYLINE: "Polyline",
    GeoType.FUNCTION: "Function", GeoType.FUNCTION_NVAR: "Multivariable Function",
    GeoType.CURVE: "Curve", GeoType.IMPLICIT: "Implicit Curve", GeoType.LOCUS: "Locus",
    GeoType.LIST: "List", GeoType.MATRIX: "Matrix", GeoType.COMPLEX: "Complex Number",
    GeoType.INEQUALITY: "Inequality", GeoType.BUTTON: "Button", GeoType.INPUT_BOX: "Input Box",
    GeoType.IMAGE: "Image", GeoType.PLANE: "Plane", GeoType.SPHERE: "Sphere",
    GeoType.SURFACE: "Surface", GeoType.POLYHEDRON: "Polyhedron", GeoType.UNKNOWN: "Object",
}

# Types drawn in the 2D graphics view by default.
GRAPHICAL_2D: frozenset[GeoType] = frozenset({
    GeoType.POINT, GeoType.VECTOR, GeoType.LINE, GeoType.RAY, GeoType.SEGMENT,
    GeoType.CIRCLE, GeoType.CONIC, GeoType.POLYGON, GeoType.POLYLINE, GeoType.FUNCTION,
    GeoType.CURVE, GeoType.IMPLICIT, GeoType.LOCUS, GeoType.INEQUALITY, GeoType.ANGLE,
    GeoType.COMPLEX,
})

# Types whose description is written "label: equation" rather than "label = value".
EQUATION_TYPES: frozenset[GeoType] = frozenset({
    GeoType.LINE, GeoType.RAY, GeoType.CIRCLE, GeoType.CONIC, GeoType.IMPLICIT,
    GeoType.INEQUALITY, GeoType.PLANE, GeoType.SPHERE,
})
