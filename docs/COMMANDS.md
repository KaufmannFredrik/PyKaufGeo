# Command reference

Generated from the command registry by `python tools/gen_commands_md.py`; do not
edit by hand (`tests/test_docs.py` fails when this file is out of date).

Command names are case-insensitive and accept `()` or `[]`. Arguments written
`<Expression>` or `<Condition>` are evaluated by the command itself (they may use
the command's `<Variable>`); all other arguments are evaluated first and checked
against the type in brackets.

## Contents

* **Action Objects**: [Slider](#slider)
* **Conics**: [CircularArc](#circulararc), [CircularSector](#circularsector), [CircumcircularArc](#circumcirculararc), [CircumcircularSector](#circumcircularsector), [Conic](#conic), [Diameter](#diameter), [Ellipse](#ellipse), [Hyperbola](#hyperbola), [Parabola](#parabola), [Polar](#polar), [Semicircle](#semicircle), [Tangent](#tangent)
* **Functions & Calculus**: [Asymptote](#asymptote), [Curvature](#curvature), [Curve](#curve), [Derivative](#derivative), [Extremum](#extremum), [FitPoly](#fitpoly), [Function](#function), [ImplicitCurve](#implicitcurve), [InflectionPoint](#inflectionpoint), [Integral](#integral), [IntegralBetween](#integralbetween), [Limit](#limit), [LimitAbove](#limitabove), [LimitBelow](#limitbelow), [NIntegral](#nintegral), [NSolve](#nsolve), [OsculatingCircle](#osculatingcircle), [Polynomial](#polynomial), [Root](#root), [Roots](#roots), [SolveODE](#solveode), [TaylorPolynomial](#taylorpolynomial)
* **Geometry**: [Angle](#angle), [AngleBisector](#anglebisector), [Area](#area), [Center](#center), [Circle](#circle), [Circumference](#circumference), [Distance](#distance), [Intersect](#intersect), [Line](#line), [Locus](#locus), [Midpoint](#midpoint), [Perimeter](#perimeter), [PerpendicularBisector](#perpendicularbisector), [PerpendicularLine](#perpendicularline), [Point](#point), [Polygon](#polygon), [Polyline](#polyline), [Ray](#ray), [Relation](#relation), [Segment](#segment), [Slope](#slope), [Vector](#vector), [Vertex](#vertex)
* **Lists**: [Append](#append), [CountIf](#countif), [Element](#element), [Filter](#filter), [First](#first), [Flatten](#flatten), [Iteration](#iteration), [IterationList](#iterationlist), [Join](#join), [KeepIf](#keepif), [Last](#last), [Length](#length), [Product](#product), [Reverse](#reverse), [Sequence](#sequence), [Sort](#sort), [Sum](#sum), [Take](#take), [Unique](#unique), [Zip](#zip)
* **Logic**: [If](#if)
* **Matrices**: [Determinant](#determinant), [Invert](#invert), [Transpose](#transpose)
* **Numbers and algebra**: [Div](#div), [Divisors](#divisors), [DivisorsList](#divisorslist), [DivisorsSum](#divisorssum), [GCD](#gcd), [IsPrime](#isprime), [LCM](#lcm), [Max](#max), [Min](#min), [Mod](#mod), [NextPrime](#nextprime), [PreviousPrime](#previousprime), [PrimeFactors](#primefactors), [Random](#random), [RandomBetween](#randombetween), [RandomUniform](#randomuniform)
* **Scripting**: [CenterView](#centerview), [Delete](#delete), [SetAxesRatio](#setaxesratio), [SetColor](#setcolor), [SetCoords](#setcoords), [SetValue](#setvalue), [SetVisibleInView](#setvisibleinview), [StartAnimation](#startanimation), [UpdateConstruction](#updateconstruction), [ZoomIn](#zoomin), [ZoomOut](#zoomout)
* **Special Objects**: [Image](#image)
* **Statistics**: [FitLine](#fitline)
* **Text**: [LaTeX](#latex), [Text](#text)
* **Transformations**: [Dilate](#dilate), [Reflect](#reflect), [Rotate](#rotate), [Translate](#translate)
* **Predefined functions**: [list](#predefined-functions)

## Action Objects

### Slider

A number (or angle) you can drag in the Graphics view. Typed on its own line, e.g. a = Slider(0, 10, 0.5), it creates a slider object.

* `Slider( <Min>, <Max> )`
* `Slider( <Min>, <Max>, <Increment> )`

Examples:

* `a = Slider(0, 10)`
* `k = Slider(-5, 5, 0.1)`
* `α = Slider(0°, 360°, 1°)`

## Conics

### CircularArc

Arc of the circle around a midpoint through A, counterclockwise to the ray towards B.

* `CircularArc( <Midpoint>, <Point>, <Point> )`

Examples:

* `CircularArc((0, 0), (2, 0), (0, 5))`

### CircularSector

Sector of the circle around a midpoint, from A counterclockwise to the ray towards B.

* `CircularSector( <Midpoint>, <Point>, <Point> )`

Examples:

* `CircularSector((0, 0), (2, 0), (0, 2))`

### CircumcircularArc

Arc through three points (from the first, through the second, to the third).

* `CircumcircularArc( <Point>, <Point>, <Point> )`

Examples:

* `CircumcircularArc((1, 0), (0, 1), (-1, 0))`

### CircumcircularSector

Sector of the circle through three points.

* `CircumcircularSector( <Point>, <Point>, <Point> )`

Examples:

* `CircumcircularSector((1, 0), (0, 1), (-1, 0))`

### Conic

Conic through five points, or from the coefficients of a x² + b xy + c y² + d x + e y + f = 0.

* `Conic( <Point>, <Point>, <Point>, <Point>, <Point> )`
* `Conic( <Number>, <Number>, <Number>, <Number>, <Number>, <Number> )`

Examples:

* `Conic(A, B, C, D, E)`
* `Conic(1, 0, 4, 0, 0, -4)`

### Diameter

Diameter of a conic conjugate to a line or vector direction.

* `Diameter( <Line>, <Conic> )`
* `Diameter( <Vector>, <Conic> )`

Examples:

* `Diameter(y = x, x^2 / 4 + y^2 = 1)`

### Ellipse

Ellipse from its two foci and the semi-major axis length, or a point on it.

* `Ellipse( <Focus>, <Focus>, <Semimajor Axis Length> )`
* `Ellipse( <Focus>, <Focus>, <Point on Ellipse> )`

Examples:

* `Ellipse((-3, 0), (3, 0), 5)`
* `Ellipse(F, G, P)`

### Hyperbola

Hyperbola from its two foci and the semi-major axis length, or a point on it.

* `Hyperbola( <Focus>, <Focus>, <Semimajor Axis Length> )`
* `Hyperbola( <Focus>, <Focus>, <Point on Hyperbola> )`

Examples:

* `Hyperbola((-5, 0), (5, 0), 3)`
* `Hyperbola(F, G, P)`

### Parabola

Parabola with a focus and a directrix line.

* `Parabola( <Focus>, <Directrix> )`

Examples:

* `Parabola((0, 1), y = -1)  ->  x² = 4y`

### Polar

Polar line of a point with respect to a conic.

* `Polar( <Point>, <Conic> )`

Examples:

* `Polar((0, 2), x^2 + y^2 = 1)  ->  y = 0.5`

### Semicircle

Semicircle over the segment AB, on the left when walking from A to B.

* `Semicircle( <Point>, <Point> )`

Examples:

* `Semicircle((-2, 0), (2, 0))`

### Tangent

Tangent lines from a point to a conic, to a function at a point or x-value, or parallel to a line.

* `Tangent( <Point>, <Conic> )`
* `Tangent( <Point>, <Conic>, <Index> )`
* `Tangent( <x-Value>, <Function> )`
* `Tangent( <Point>, <Function> )`
* `Tangent( <Line>, <Circle> )`
* `Tangent( <Line>, <Circle>, <Index> )`

Examples:

* `Tangent((0, 2), x^2 + y^2 = 1)`
* `Tangent(1, f)`
* `Tangent(A, f)`
* `Tangent(y = 0, c)`

## Functions & Calculus

### Asymptote

Asymptotes of a function (vertical, horizontal, oblique) or of a hyperbola, as a list of lines.

* `Asymptote( <Function> )`
* `Asymptote( <Conic> )`

Examples:

* `Asymptote((x^2 + 1) / (x - 1))  ->  {x = 1, y = x + 1}`
* `Asymptote(x^2 / 4 - y^2 = 1)`

### Curvature

Curvature of the graph of f at the x-coordinate of a point.

* `Curvature( <Point>, <Function> )`

Examples:

* `Curvature((0, 0), x^2)  ->  2`

### Curve

Parametric curve (x(t), y(t)) for t from a to b; polar curves via (r(t); t).

* `Curve( <Expression>, <Expression>, <Parameter Variable>, <Start Value>, <End Value> )`

Examples:

* `Curve(cos(t), sin(t), t, 0, 2π)`
* `Curve(3cos(t) t / 6, 3sin(t) t / 6, t, 0, 6π)`

### Derivative

Derivative of a function (also written f', f''); partial derivative by a variable; of a curve.

* `Derivative( <Function> )`
* `Derivative( <Function>, <Number of Derivatives> )`
* `Derivative( <Function>, <Variable> )`
* `Derivative( <Function>, <Variable>, <Number of Derivatives> )`
* `Derivative( <Curve> )`

Examples:

* `Derivative(x^3)  ->  3x²`
* `f'(x)`
* `Derivative(f, 2)`
* `Derivative(x^2 y, y)`

### Extremum

Local maxima and minima: all of a polynomial, or of any function between two x-values.

* `Extremum( <Polynomial> )`
* `Extremum( <Polynomial>, <Index> )`
* `Extremum( <Function>, <Start x-Value>, <End x-Value> )`
* `Extremum( <Function>, <Start x-Value>, <End x-Value>, <Index> )`

Examples:

* `Extremum(x^3 - 3x)`
* `Extremum(sin(x), 0, 7)`

### FitPoly

Least-squares polynomial of the given degree through a list of points.

* `FitPoly( <List of Points>, <Degree> )`

Examples:

* `FitPoly({(0, 1), (1, 2), (2, 5), (3, 10)}, 2)`

### Function

A function restricted to the interval from a to b (undefined outside).

* `Function( <Function>, <Start x-Value>, <End x-Value> )`

Examples:

* `Function(x^2, -1, 2)`

### ImplicitCurve

The curve f(x, y) = 0.

* `ImplicitCurve( <f(x, y)> )`

Examples:

* `ImplicitCurve(x^3 + y^3 - 3x y)`

### InflectionPoint

Inflection points of a polynomial (where the curvature changes sign).

Also available as: `TurningPoint`

* `InflectionPoint( <Polynomial> )`
* `InflectionPoint( <Polynomial>, <Index> )`

Examples:

* `InflectionPoint(x^3 - 3x^2)  ->  (1, -2)`

### Integral

Antiderivative of a function, or the definite integral from a to b (shown as a shaded area).

* `Integral( <Function> )`
* `Integral( <Function>, <Start x-Value>, <End x-Value> )`

Examples:

* `Integral(x^2)  ->  x³ / 3`
* `Integral(f, 0, 2)`

### IntegralBetween

Integral of f - g from a to b (the area between the graphs, shaded).

* `IntegralBetween( <Function>, <Function>, <Start x-Value>, <End x-Value> )`

Examples:

* `IntegralBetween(f, g, 0, 2)`

### Limit

Limit of a function at a value (use ∞ or -∞ for the ends of the axis).

* `Limit( <Function>, <Value> )`

Examples:

* `Limit(sin(x) / x, 0)  ->  1`
* `Limit((2x + 1) / (x - 3), ∞)  ->  2`

### LimitAbove

Limit from the right.

* `LimitAbove( <Function>, <Value> )`

Examples:

* `LimitAbove(1 / x, 0)  ->  ∞`

### LimitBelow

Limit from the left.

* `LimitBelow( <Function>, <Value> )`

Examples:

* `LimitBelow(1 / x, 0)  ->  -∞`

### NIntegral

Numeric value of the integral of f from a to b (no shading).

* `NIntegral( <Function>, <Start x-Value>, <End x-Value> )`

Examples:

* `NIntegral(e^(-x^2), -1, 1)`

### NSolve

Numeric solutions of an equation in x (all real ones for polynomials, otherwise those between -100 and 100), or the one near a start value.

Also available as: `NSolutions`

* `NSolve( <Equation> )`
* `NSolve( <Equation>, <Start> )`

Examples:

* `NSolve(x^2 = 2)  ->  {-1.41, 1.41}`
* `NSolve(cos(x) = x)`
* `NSolve(e^x = 3 - x, x = 1)`

### OsculatingCircle

The circle that best fits the graph of f at the x-coordinate of a point.

* `OsculatingCircle( <Point>, <Function> )`

Examples:

* `OsculatingCircle((0, 0), x^2)`

### Polynomial

Expanded form of a polynomial function, or the polynomial through a list of points.

* `Polynomial( <Function> )`
* `Polynomial( <List of Points> )`

Examples:

* `Polynomial((x - 1)(x + 2))  ->  x² + x - 2`
* `Polynomial({(0, 1), (1, 0), (2, 3)})`

### Root

Roots of a function: all roots of a polynomial, the root near a start value, or the root between two x-values.

* `Root( <Polynomial> )`
* `Root( <Function>, <Initial x-Value> )`
* `Root( <Function>, <Start x-Value>, <End x-Value> )`

Examples:

* `Root(x^3 - x)`
* `Root(cos(x), 1)`
* `Root(cos(x), 0, 3)`

### Roots

All roots of a function between two x-values (or the n-th root of a polynomial).

* `Roots( <Function>, <Start x-Value>, <End x-Value> )`
* `Roots( <Function>, <Start x-Value>, <End x-Value>, <Index> )`
* `Roots( <Polynomial>, <Index> )`

Examples:

* `Roots(sin(x), -5, 5)`
* `Roots(x^2 - 4, 2)  ->  (2, 0)`

### SolveODE

Numeric solution of y' = f(x, y) from a start point to an end x (a curve of points).

* `SolveODE( <f'(x, y)>, <Start x>, <Start y>, <End x>, <Step> )`
* `SolveODE( <f'(x, y)>, <Start Point>, <End x> )`

Examples:

* `SolveODE(x y, 0, 1, 2, 0.01)`
* `SolveODE(-y, (0, 2), 5)`

### TaylorPolynomial

Taylor polynomial of f around x = a up to the given order.

Also available as: `TaylorSeries`, `Taylor`

* `TaylorPolynomial( <Function>, <x-Value>, <Order> )`

Examples:

* `TaylorPolynomial(sin(x), 0, 5)  ->  x - x³/6 + x⁵/120`

## Geometry

### Angle

Angle measured counterclockwise: Angle(A, B, C) at apex B from BA to BC; between two vectors or two lines; or a number turned into an angle.

* `Angle( <Point>, <Apex>, <Point> )`
* `Angle( <Vector>, <Vector> )`
* `Angle( <Line>, <Line> )`
* `Angle( <Polygon> )`
* `Angle( <Polygon>, <Index> )`
* `Angle( <Vector> )`
* `Angle( <Number> )`

Examples:

* `Angle((1, 0), (0, 0), (0, 1))  ->  90°`
* `Angle(Vector((1, 0)), Vector((1, 1)))  ->  45°`

### AngleBisector

Bisector of the angle ABC, or the two bisectors of two lines.

* `AngleBisector( <Point>, <Vertex>, <Point> )`
* `AngleBisector( <Line>, <Line> )`
* `AngleBisector( <Line>, <Line>, <Index> )`

Examples:

* `AngleBisector((1, 0), (0, 0), (0, 1))  ->  -x + y = 0`
* `AngleBisector(g, h)`

### Area

Area of a polygon, circle or ellipse, or of the polygon through given points.

* `Area( <Polygon> )`
* `Area( <Conic> )`
* `Area( <Point>, <Point>, <Point>, ... )`

Examples:

* `Area(Polygon((0, 0), (4, 0), (0, 3)))  ->  6`
* `Area(Circle((0, 0), 1))  ->  3.14`

### Center

Center of a circle or conic.

* `Center( <Conic> )`

Examples:

* `Center(x^2 + y^2 = 9)  ->  (0, 0)`

### Circle

Circle from center and radius, center and a point on it, or through three points.

* `Circle( <Center>, <Radius> )`
* `Circle( <Center>, <Point on Circle> )`
* `Circle( <Point>, <Point>, <Point> )`

Examples:

* `Circle((0, 0), 3)`
* `Circle(A, B)`
* `Circle(A, B, C)`
* `Circle(A, Segment(B, C))`

### Circumference

Circumference of a circle.

* `Circumference( <Circle> )`

Examples:

* `Circumference(Circle((0, 0), 1))  ->  6.28`

### Distance

Distance between two points, a point and a line, or two parallel lines.

* `Distance( <Point>, <Point> )`
* `Distance( <Point>, <Line> )`
* `Distance( <Line>, <Line> )`

Examples:

* `Distance((0, 0), (3, 4))  ->  5`
* `Distance((0, 0), x + y = 2)  ->  1.41`

### Intersect

Intersection points of two objects. Without an index, objects with several intersections create one point per intersection.

* `Intersect( <Object>, <Object> )`
* `Intersect( <Object>, <Object>, <Index of Intersection Point> )`
* `Intersect( <Object>, <Object>, <Initial Point> )`
* `Intersect( <Function>, <Object>, <Start x-Value>, <End x-Value> )`
* `Intersect( <Function>, <Object>, <Start x-Value>, <End x-Value>, <Index> )`

Examples:

* `Intersect(f, g)`
* `Intersect(c, f)`
* `Intersect(c, f, 1)`

### Line

Line through two points, through a point parallel to a line, or through a point with a direction.

* `Line( <Point>, <Point> )`
* `Line( <Point>, <Parallel Line> )`
* `Line( <Point>, <Direction Vector> )`

Examples:

* `Line((0, 0), (1, 1))`
* `Line(A, g)`
* `Line(A, Vector((1, 2)))`

### Locus

Path traced by a point while another point moves along its object.

* `Locus( <Locus Point>, <Point on Object> )`

Examples:

* `Locus(M, P)`

### Midpoint

Midpoint of two points or a segment; center of a circle or conic.

* `Midpoint( <Point>, <Point> )`
* `Midpoint( <Segment> )`
* `Midpoint( <Conic> )`

Examples:

* `Midpoint((0, 0), (4, 2))  ->  (2, 1)`

### Perimeter

Perimeter of a polygon or circle.

* `Perimeter( <Polygon> )`
* `Perimeter( <Circle> )`

Examples:

* `Perimeter(Polygon((0, 0), (3, 0), (3, 4)))  ->  12`

### PerpendicularBisector

Perpendicular bisector of two points or of a segment.

* `PerpendicularBisector( <Point>, <Point> )`
* `PerpendicularBisector( <Segment> )`

Examples:

* `PerpendicularBisector((0, 0), (4, 0))  ->  x = 2`

### PerpendicularLine

Line through a point perpendicular to a line or vector.

* `PerpendicularLine( <Point>, <Line> )`
* `PerpendicularLine( <Point>, <Vector> )`

Examples:

* `PerpendicularLine((1, 1), y = 2x)`

### Point

A point on an object (line, segment, ray, circle, conic, arc, polygon, function graph). It stays on the object and can be dragged along it.

* `Point( <Path> )`
* `Point( <Path>, <Parameter> )`

Examples:

* `Point(c)`
* `Point(f, 2)`

### Polygon

Polygon through the given vertices (or a list of points).

* `Polygon( <Point>, <Point>, <Point>, ... )`
* `Polygon( <List of Points> )`
* `Polygon( <Point>, <Point>, <Number of Vertices> )`

Examples:

* `Polygon((0, 0), (4, 0), (0, 3))`
* `Polygon({(0, 0), (1, 0), (1, 1), (0, 1)})`

### Polyline

Open path through the given points.

* `Polyline( <Point>, <Point>, ... )`
* `Polyline( <List of Points> )`

Examples:

* `Polyline((0, 0), (1, 2), (3, 1))`

### Ray

Ray from a start point through a point, or in the direction of a vector.

* `Ray( <Start Point>, <Point> )`
* `Ray( <Start Point>, <Direction Vector> )`

Examples:

* `Ray((0, 0), (1, 1))`

### Relation

Describes how two objects relate: equal, incident, parallel, perpendicular, tangent, ...

* `Relation( <Object>, <Object> )`

Examples:

* `Relation(A, g)`
* `Relation(g, h)`

### Segment

Segment between two points.

* `Segment( <Point>, <Point> )`
* `Segment( <Point>, <Length> )`

Examples:

* `Segment((0, 0), (3, 4))`

### Slope

Slope of a line (undefined for vertical lines).

* `Slope( <Line> )`

Examples:

* `Slope(y = 2x + 1)  ->  2`

### Vector

Vector from a start point to an end point, or position vector of a point.

* `Vector( <Start Point>, <End Point> )`
* `Vector( <Point> )`

Examples:

* `Vector((1, 1), (4, 5))  ->  (3, 4)`
* `Vector((2, 3))`

### Vertex

Vertices of a polygon or a conic (all, or the n-th).

* `Vertex( <Polygon> )`
* `Vertex( <Polygon>, <Index> )`
* `Vertex( <Conic> )`
* `Vertex( <Conic>, <Index> )`

Examples:

* `Vertex(poly1, 2)`
* `Vertex(poly1)`
* `Vertex(ell)`

## Lists

### Append

Add an object at the end (or the start) of a list.

* `Append( <List>, <Object> )`
* `Append( <Object>, <List> )`

Examples:

* `Append({1, 2}, 3)  ->  {1, 2, 3}`
* `Append(0, {1, 2})  ->  {0, 1, 2}`

### CountIf

Number of list elements that satisfy a condition.

* `CountIf( <Condition>, <List> )`
* `CountIf( <Condition>, <Variable>, <List> )`

Examples:

* `CountIf(x > 2, {1, 2, 3, 4})  ->  2`

### Element

Element of a list at a position (1-based), or of a matrix at row and column.

* `Element( <List>, <Position of Element> )`
* `Element( <Matrix>, <Row>, <Column> )`

Examples:

* `Element({4, 5, 6}, 2)  ->  5`
* `Element({{1, 2}, {3, 4}}, 2, 1)  ->  3`

### Filter

Same as KeepIf: elements of a list that satisfy a condition in x.

* `Filter( <Condition>, <List> )`

Examples:

* `Filter(x > 0, {-1, 2, -3, 4})  ->  {2, 4}`

### First

The first element, or the first n elements, of a list.

* `First( <List> )`
* `First( <List>, <Number of Elements> )`

Examples:

* `First({4, 5, 6})  ->  {4}`
* `First({4, 5, 6}, 2)  ->  {4, 5}`

### Flatten

Remove all nesting from a list.

* `Flatten( <List> )`

Examples:

* `Flatten({1, {2, {3}}})  ->  {1, 2, 3}`

### Iteration

Apply a function repeatedly to a start value.

* `Iteration( <Function>, <Start Value>, <Number of Iterations> )`

Examples:

* `Iteration(x^2, 2, 3)  ->  256`

### IterationList

List of the start value and each repeated application of a function.

* `IterationList( <Function>, <Start Value>, <Number of Iterations> )`

Examples:

* `IterationList(2x, 1, 3)  ->  {1, 2, 4, 8}`

### Join

Join several lists, or the lists inside a list, into one list.

* `Join( <List of Lists> )`
* `Join( <List>, <List>, ... )`

Examples:

* `Join({1, 2}, {3})  ->  {1, 2, 3}`
* `Join({{1}, {2, 3}})  ->  {1, 2, 3}`

### KeepIf

Elements of a list that satisfy a condition (in x, or in a named variable).

* `KeepIf( <Condition>, <List> )`
* `KeepIf( <Condition>, <Variable>, <List> )`

Examples:

* `KeepIf(x < 3, {1, 2, 3, 4})  ->  {1, 2}`
* `KeepIf(Mod(k, 2) == 0, k, {1, 2, 3, 4})  ->  {2, 4}`

### Last

The last element, or the last n elements, of a list.

* `Last( <List> )`
* `Last( <List>, <Number of Elements> )`

Examples:

* `Last({4, 5, 6})  ->  {6}`

### Length

Number of elements of a list, length of a vector or segment, or characters of a text.

* `Length( <List> )`
* `Length( <Text> )`
* `Length( <Vector> )`
* `Length( <Point> )`
* `Length( <Segment> )`

Examples:

* `Length({4, 5, 6})  ->  3`
* `Length(Vector((3, 4)))  ->  5`

### Product

Product of list elements, or of an expression over a range of a variable.

* `Product( <List> )`
* `Product( <List>, <Number of Elements> )`
* `Product( <Expression>, <Variable>, <Start Value>, <End Value> )`

Examples:

* `Product({1, 2, 3, 4})  ->  24`
* `Product(k, k, 1, 5)  ->  120`

### Reverse

The list in reverse order.

* `Reverse( <List> )`

Examples:

* `Reverse({1, 2, 3})  ->  {3, 2, 1}`

### Sequence

List of values of an expression as a variable runs over a range.

* `Sequence( <End Value> )`
* `Sequence( <Expression>, <Variable>, <Start Value>, <End Value> )`
* `Sequence( <Expression>, <Variable>, <Start Value>, <End Value>, <Increment> )`

Examples:

* `Sequence(4)  ->  {1, 2, 3, 4}`
* `Sequence(k^2, k, 1, 4)  ->  {1, 4, 9, 16}`
* `Sequence((k, k^2), k, -2, 2, 0.5)`

### Sort

Sort numbers ascending, points by x then y, texts alphabetically; or values by keys.

* `Sort( <List> )`
* `Sort( <Values>, <Keys> )`

Examples:

* `Sort({3, 1, 2})  ->  {1, 2, 3}`
* `Sort({"a", "b", "c"}, {3, 1, 2})  ->  {"b", "c", "a"}`

### Sum

Sum of list elements, or of an expression over a range of a variable.

* `Sum( <List> )`
* `Sum( <List>, <Number of Elements> )`
* `Sum( <Expression>, <Variable>, <Start Value>, <End Value> )`

Examples:

* `Sum({1, 2, 3})  ->  6`
* `Sum(k^2, k, 1, 4)  ->  30`
* `Sum(x^k / k!, k, 0, 5)`

### Take

Elements (or characters) from a start position to an end position.

* `Take( <List>, <Start Position> )`
* `Take( <List>, <Start Position>, <End Position> )`
* `Take( <Text>, <Start Position> )`
* `Take( <Text>, <Start Position>, <End Position> )`

Examples:

* `Take({1, 2, 3, 4, 5}, 2, 4)  ->  {2, 3, 4}`

### Unique

The list without repeated elements (first occurrences kept, in order).

* `Unique( <List> )`

Examples:

* `Unique({1, 2, 1, 3})  ->  {1, 2, 3}`

### Zip

Evaluate an expression for corresponding elements of one or more lists.

* `Zip( <Expression>, <Variable>, <List> )`
* `Zip( <Expression>, <Variable>, <List>, <Variable>, <List> )`
* `Zip( <Expression>, <Variable>, <List>, <Variable>, <List>, <Variable>, <List> )`

Examples:

* `Zip(a + b, a, {1, 2}, b, {10, 20})  ->  {11, 22}`

## Logic

### If

Choose a value by a condition. With a free variable the result is a piecewise function. Without an else value the result is undefined where no condition holds.

* `If( <Condition>, <Then> )`
* `If( <Condition>, <Then>, <Else> )`
* `If( <Condition>, <Then>, <Condition>, <Then>, ... )`

Examples:

* `If(a > 0, 1, -1)`
* `f(x) = If(x < 0, -x, x^2)`
* `If(x < -1, -1, x < 1, x, 1)`

## Matrices

### Determinant

Determinant of a square matrix (numeric; the exact CAS version arrives in M5).

* `Determinant( <Matrix> )`

Examples:

* `Determinant({{1, 2}, {3, 4}})  ->  -2`

### Invert

Inverse of a square matrix (numeric; undefined if singular).

Also available as: `Inverse`

* `Invert( <Matrix> )`

Examples:

* `Invert({{2, 0}, {0, 4}})  ->  {{0.5, 0}, {0, 0.25}}`

### Transpose

Transpose of a matrix.

* `Transpose( <Matrix> )`

Examples:

* `Transpose({{1, 2}, {3, 4}})  ->  {{1, 3}, {2, 4}}`

## Numbers and algebra

### Div

Integer quotient: floor(a / b).

* `Div( <Dividend>, <Divisor> )`

Examples:

* `Div(17, 5)  ->  3`

### Divisors

Number of divisors of a whole number.

* `Divisors( <Integer> )`

Examples:

* `Divisors(12)  ->  6`

### DivisorsList

All divisors of a whole number.

* `DivisorsList( <Integer> )`

Examples:

* `DivisorsList(12)  ->  {1, 2, 3, 4, 6, 12}`

### DivisorsSum

Sum of all divisors of a whole number.

* `DivisorsSum( <Integer> )`

Examples:

* `DivisorsSum(12)  ->  28`

### GCD

Greatest common divisor of whole numbers.

* `GCD( <Integer>, <Integer> )`
* `GCD( <List> )`

Examples:

* `GCD(12, 18)  ->  6`
* `GCD({12, 18, 30})  ->  6`

### IsPrime

true if the whole number is a prime.

* `IsPrime( <Integer> )`

Examples:

* `IsPrime(97)  ->  true`

### LCM

Least common multiple of whole numbers.

* `LCM( <Integer>, <Integer> )`
* `LCM( <List> )`

Examples:

* `LCM(4, 6)  ->  12`

### Max

Larger of two numbers, or the maximum of a list.

* `Max( <Number>, <Number> )`
* `Max( <List> )`

Examples:

* `Max(3, 5)  ->  5`
* `Max({4, 1, 7})  ->  7`

### Min

Smaller of two numbers, or the minimum of a list.

* `Min( <Number>, <Number> )`
* `Min( <List> )`

Examples:

* `Min(3, 5)  ->  3`
* `Min({4, 1, 7})  ->  1`
* `f(x) = Min(x, 2)`

### Mod

Remainder of a divided by b (same sign as b).

* `Mod( <Dividend>, <Divisor> )`

Examples:

* `Mod(17, 5)  ->  2`
* `Mod(-7, 3)  ->  2`

### NextPrime

The smallest prime greater than the number.

* `NextPrime( <Number> )`

Examples:

* `NextPrime(10)  ->  11`

### PreviousPrime

The largest prime smaller than the number (undefined below 3).

* `PreviousPrime( <Number> )`

Examples:

* `PreviousPrime(10)  ->  7`

### PrimeFactors

Prime factors of a whole number, with repetition.

* `PrimeFactors( <Integer> )`

Examples:

* `PrimeFactors(360)  ->  {2, 2, 2, 3, 3, 5}`

### Random

random(): random real number in [0, 1).

* `Random( )`

Examples:

* `random()`

### RandomBetween

Random whole number between min and max (inclusive). Kept until UpdateConstruction.

* `RandomBetween( <Min>, <Max> )`

Examples:

* `RandomBetween(1, 6)`

### RandomUniform

Random real number, uniformly distributed between min and max.

* `RandomUniform( <Min>, <Max> )`

Examples:

* `RandomUniform(0, 1)`

## Scripting

### CenterView

Move the Graphics view so that a point is in the centre.

* `CenterView( <Center> )`

Examples:

* `CenterView((0, 0))`
* `CenterView(A)`

### Delete

Delete an object and everything that depends on it.

* `Delete( <Object> )`

Examples:

* `Delete(A)`

### SetAxesRatio

Set the ratio of the x and y axis scales (x units : y units on screen).

* `SetAxesRatio( <x>, <y> )`

Examples:

* `SetAxesRatio(1, 1)`
* `SetAxesRatio(1, 10)`

### SetColor

Change the colour of an object: a palette name or #RRGGBB, or red, green, blue between 0 and 1.

* `SetColor( <Object>, <Color Name> )`
* `SetColor( <Object>, <Red>, <Green>, <Blue> )`

Examples:

* `SetColor(A, "red")`
* `SetColor(c, "magenta")`
* `SetColor(A, 0, 0, 1)`

### SetCoords

Move a free point or vector to new coordinates.

* `SetCoords( <Object>, <x>, <y> )`

Examples:

* `SetCoords(A, 1, 2)`

### SetValue

Set a free object to a value (or move a point on its object to a position).

* `SetValue( <Object>, <Value> )`

Examples:

* `SetValue(a, 3)`
* `SetValue(A, (1, 2))`

### SetVisibleInView

Show or hide an object in Graphics view 1 or 2.

* `SetVisibleInView( <Object>, <View Number>, <Visible> )`

Examples:

* `SetVisibleInView(A, 1, false)`

### StartAnimation

Start or stop animation: all animated objects, or turn animation on for given sliders and points.

* `StartAnimation( )`
* `StartAnimation( <Run> )`
* `StartAnimation( <Object>, <Object>, ... )`
* `StartAnimation( <Object> )`

Examples:

* `StartAnimation()`
* `StartAnimation(false)`
* `StartAnimation(a, B)`

### UpdateConstruction

Recompute every object and draw new random numbers.

* `UpdateConstruction( )`

Examples:

* `UpdateConstruction()`

### ZoomIn

Zoom the Graphics view in by a factor around its centre, or show a rectangle.

* `ZoomIn( <Factor> )`
* `ZoomIn( <Min x>, <Min y>, <Max x>, <Max y> )`

Examples:

* `ZoomIn(2)`
* `ZoomIn(-5, -5, 5, 5)`

### ZoomOut

Zoom the Graphics view out by a factor around its centre.

* `ZoomOut( <Factor> )`

Examples:

* `ZoomOut(2)`

## Special Objects

### Image

A picture stored in the document (made by the Image tool, which adds the file). Its position and size are set in the Graphics view or in Properties.

* `Image( <File Name> )`

Examples:

* `Image("photo.png")`

## Statistics

### FitLine

Least-squares regression line y = m x + b through a list of points.

* `FitLine( <List of Points> )`

Examples:

* `FitLine({(0, 1), (1, 3), (2, 5)})  ->  y = 2x + 1`

## Text

### LaTeX

The value of an object or expression as LaTeX source (as shown in the Algebra view).

Also available as: `FormulaText`

* `LaTeX( <Object> )`

Examples:

* `LaTeX(x^2 / 2)  ->  "\frac{x^{2}}{2}"`
* `FormulaText(f)`

### Text

The value of an object as text (rounded with the current number of decimals).

* `Text( <Object> )`

Examples:

* `Text(1/3)  ->  "0.33"`
* `"Area: " + Text(Area(p))`

## Transformations

### Dilate

Scale an object by a factor from the origin or from a point.

* `Dilate( <Object>, <Factor> )`
* `Dilate( <Object>, <Factor>, <Center> )`

Examples:

* `Dilate((1, 2), 3)  ->  (3, 6)`
* `Dilate(poly1, 2, A)`

### Reflect

Mirror an object about a point, a line, or a circle (inversion).

* `Reflect( <Object>, <Point> )`
* `Reflect( <Object>, <Line> )`
* `Reflect( <Object>, <Circle> )`

Examples:

* `Reflect((1, 2), (0, 0))  ->  (-1, -2)`
* `Reflect(A, x = 0)`
* `Reflect(A, Circle((0, 0), 2))`

### Rotate

Rotate an object counterclockwise by an angle, around the origin or a point.

* `Rotate( <Object>, <Angle> )`
* `Rotate( <Object>, <Angle>, <Center> )`

Examples:

* `Rotate((2, 0), 90°)  ->  (0, 2)`
* `Rotate(poly1, 30°, A)`

### Translate

Move an object by a vector, or place a vector at a start point.

* `Translate( <Object>, <Vector> )`
* `Translate( <Vector>, <Start Point> )`

Examples:

* `Translate((1, 1), Vector((2, 3)))  ->  (3, 4)`
* `Translate(f, Vector((0, 1)))`
* `Translate(u, A)`

## Predefined functions

| Function | Arguments | Meaning |
|---|---|---|
| `abs` | 1 | Absolute value |x| |
| `arccos`, `acos` | 1 | Inverse cosine |
| `arccosh`, `acosh` | 1 | Inverse hyperbolic cosine |
| `arccot`, `acot` | 1 | Inverse cotangent |
| `arcsin`, `asin` | 1 | Inverse sine |
| `arcsinh`, `asinh` | 1 | Inverse hyperbolic sine |
| `arctan`, `atan` | 1 | Inverse tangent |
| `arctanh`, `atanh` | 1 | Inverse hyperbolic tangent |
| `arg` | 1 | Argument (angle) of a complex number |
| `atan2` | 2 | atan2(y, x): angle of the point (x, y) |
| `beta` | 2 | Beta function B(a, b) |
| `cbrt` | 1 | Cube root |
| `ceil`, `ceiling` | 1 | Least integer >= x |
| `conjugate`, `conj` | 1 | Complex conjugate |
| `cos` | 1 | Cosine |
| `cosh` | 1 | Hyperbolic cosine |
| `cot` | 1 | Cotangent |
| `coth` | 1 | Hyperbolic cotangent |
| `csc` | 1 | Cosecant |
| `csch` | 1 | Hyperbolic cosecant |
| `erf` | 1 | Error function |
| `exp` | 1 | Exponential e^x |
| `factorial` | 1 | n! (Gamma(n + 1) for non-integers) |
| `floor` | 1 | Greatest integer <= x |
| `fractionalpart`, `frac` | 1 | x minus its integer part |
| `gamma` | 1 | Gamma function |
| `imaginary`, `im` | 1 | Imaginary part of a complex number |
| `ld`, `log2` | 1 | Logarithm to base 2 |
| `lg`, `log10` | 1 | Logarithm to base 10 |
| `ln` | 1 | Natural logarithm |
| `log` | 1-2 | log(x): natural logarithm; log(b, x): logarithm of x to base b |
| `nroot` | 2 | nroot(x, n): n-th root (real for odd n) |
| `real`, `re` | 1 | Real part of a complex number |
| `round` | 1-2 | round(x) or round(x, decimals), halves away from zero |
| `sec` | 1 | Secant |
| `sech` | 1 | Hyperbolic secant |
| `sgn`, `sign` | 1 | Sign: -1, 0 or 1 |
| `sin` | 1 | Sine |
| `sinh` | 1 | Hyperbolic sine |
| `sqrt` | 1 | Square root |
| `tan` | 1 | Tangent |
| `tanh` | 1 | Hyperbolic tangent |

Constants: `pi` (`π`), `e` (`ℯ`), `i` (`ί`), `∞` (`infinity`), `deg` (one degree, as in `30deg`). Postfix operators: `!` factorial, `°` degrees, `%` percent.
