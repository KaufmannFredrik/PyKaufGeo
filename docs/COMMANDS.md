# Command reference

Generated from the command registry by `python tools/gen_commands_md.py`; do not
edit by hand (`tests/test_docs.py` fails when this file is out of date).

Command names are case-insensitive and accept `()` or `[]`. Arguments written
`<Expression>` or `<Condition>` are evaluated by the command itself (they may use
the command's `<Variable>`); all other arguments are evaluated first and checked
against the type in brackets.

## Contents

* **Geometry**: [Angle](#angle), [Area](#area), [Center](#center), [Circle](#circle), [Circumference](#circumference), [Distance](#distance), [Intersect](#intersect), [Line](#line), [Midpoint](#midpoint), [Perimeter](#perimeter), [PerpendicularBisector](#perpendicularbisector), [PerpendicularLine](#perpendicularline), [Polygon](#polygon), [Polyline](#polyline), [Ray](#ray), [Segment](#segment), [Slope](#slope), [Vector](#vector)
* **Lists**: [Append](#append), [CountIf](#countif), [Element](#element), [Filter](#filter), [First](#first), [Flatten](#flatten), [Iteration](#iteration), [IterationList](#iterationlist), [Join](#join), [KeepIf](#keepif), [Last](#last), [Length](#length), [Product](#product), [Reverse](#reverse), [Sequence](#sequence), [Sort](#sort), [Sum](#sum), [Take](#take), [Unique](#unique), [Zip](#zip)
* **Logic**: [If](#if)
* **Matrices**: [Determinant](#determinant), [Invert](#invert), [Transpose](#transpose)
* **Numbers and algebra**: [Div](#div), [GCD](#gcd), [LCM](#lcm), [Max](#max), [Min](#min), [Mod](#mod), [Random](#random), [RandomBetween](#randombetween), [RandomUniform](#randomuniform)
* **Text**: [LaTeX](#latex), [Text](#text)
* **Predefined functions**: [list](#predefined-functions)

## Geometry

### Angle

Angle measured counterclockwise: Angle(A, B, C) at apex B from BA to BC; between two vectors or two lines; or a number turned into an angle.

* `Angle( <Point>, <Apex>, <Point> )`
* `Angle( <Vector>, <Vector> )`
* `Angle( <Line>, <Line> )`
* `Angle( <Vector> )`
* `Angle( <Number> )`

Examples:

* `Angle((1, 0), (0, 0), (0, 1))  ->  90°`
* `Angle(Vector((1, 0)), Vector((1, 1)))  ->  45°`

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

### Polygon

Polygon through the given vertices (or a list of points).

* `Polygon( <Point>, <Point>, <Point>, ... )`
* `Polygon( <List of Points> )`

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

### Segment

Segment between two points.

* `Segment( <Point>, <Point> )`

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

### GCD

Greatest common divisor of whole numbers.

* `GCD( <Integer>, <Integer> )`
* `GCD( <List> )`

Examples:

* `GCD(12, 18)  ->  6`
* `GCD({12, 18, 30})  ->  6`

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
