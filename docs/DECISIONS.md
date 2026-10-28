# Decision log

Each entry records a choice made where the brief was ambiguous or a feature was
costly, and why. Newest entries at the bottom of each milestone section.

## M0

**D-001 Fusion as the base widget style.** Platform styles (windows11, macOS) add
their own hover animations and rounded focus frames. Fusion renders stylesheets
predictably on every OS and has no chrome animation of its own. All Qt UI effects
(`UI_AnimateMenu`, `UI_FadeMenu`, `UI_AnimateCombo`, `UI_AnimateTooltip`,
`UI_FadeTooltip`, `UI_AnimateToolBox`) are switched off in `gui/app.py`.

**D-002 Headless screenshots need `QT_QPA_FONTDIR`.** On Windows the `offscreen`
platform plugin finds zero font families, so every screenshot would be blank text.
`create_app`, `tests/conftest.py` and `tools/screenshot.py` point it at
`%WINDIR%\Fonts` when it is not set. On Linux the plugin uses fontconfig and needs
nothing.

**D-003 Hard shadows via window masks, not translucency.** Floating elements
(menus, tooltips, dialogs) paint their own border plus a solid block offset 4 px
right and down, and a window mask cuts away the top-right and bottom-left 4 px
notches. Masks work everywhere; translucent top-level windows render with a black
background on X11 without a compositor. QMenu ignores per-edge stylesheet borders
and margins, so `BrutalMenu` reserves the room with contents margins and paints the
frame over Qt's item painting.

**D-004 3D backend: PyOpenGL (decided now, used in M7).** Both PyOpenGL and moderngl
work inside `QOpenGLWidget`. PyOpenGL draws directly into the context Qt already
made current (no second context wrapper and no framebuffer detection step), ships
as a pure-Python wheel that cannot break on a new CPython release, and has a mature
PyInstaller hook. The scene is small (flat-shaded meshes plus edge lines uploaded
as numpy VBOs once per change), so moderngl's lower per-call overhead buys little.
We use the core-profile shader pipeline, not the fixed-function API.

**D-005 Focus ring as an overlay widget.** Qt stylesheets have no `outline` and no
double borders. A transparent, mouse-transparent overlay is positioned over the
focus widget and paints `[2 px edge][4 px yellow][2 px edge]`. The outer edge is
an addition to the brief: yellow on white has a 1.07:1 contrast ratio, so without
it the ring would vanish on the white canvas (WCAG 2.4.11 / 1.4.11). The ring
appears for keyboard focus (Tab, Backtab, shortcuts) on any focusable widget and
for every focus change on text inputs. Widgets with a painted shadow report their
visible body through `focus_rect()`.

**D-006 Selected tool in the Night theme.** Night inverts the chrome. Inverting
"black background with yellow icon" gives a yellow icon on white, which fails
contrast, so the selected tool in Night is a white button with a black icon plus the
white offset shadow. The shadow (shape) also distinguishes it from hover (colour).

**D-007 Error block text is 14 pt bold.** White on #FF0000 is 4.0:1, below the
4.5:1 AA threshold for body text but above the 3:1 threshold for large text
(14 pt bold). The brief requires both "white bold uppercase on red" and AA, so the
error block always renders at `max(font size, 14 pt)`, heavy weight. The contrast
test treats this pair as large text.

**D-008 Custom tooltips.** QToolTip cannot draw an offset shadow. An application
event filter intercepts `QEvent.ToolTip` and shows `BrutalToolTip`: an uppercase
title line in a black chip, then the description. It hides on leave, click, key
press, or after 10 s.

**D-009 Unimplemented tools are visible and say so.** All tool groups appear in the
toolbar from M0 so the layout can be reviewed. Choosing a tool that does not work yet
shows a yellow warning block ("TOOL NOT IMPLEMENTED YET (M3)") and the tooltip says
the same. Nothing fails silently.

**D-010 No pytest-qt.** It is not on the allowed list. `tests/conftest.py` provides
a session `qapp` fixture and tests drive widgets directly.

**D-011 Translation catalogues are JSON.** Qt `.ts/.qm` files need `lrelease` at
build time. Strings are wrapped in `tr()` from day one; English is the source text,
`pykaufgeo/translations/nb.json` arrives in M8.

**D-012 Graphics labels never use yellow or green text.** Objects may be yellow or
green (with black outlines or edges), but their labels are drawn in ink when the
object colour is in `theme.LOW_CONTRAST_ON_LIGHT` (applies from M2).

**D-013 Docstrings are exempt from the literal check.** The token scanner checks
string literals and code; a string that forms a statement on its own (a docstring)
is prose and may say "3 px border". Assigned strings such as QSS fragments are
always checked.

## M1

**D-101 Partial evaluation instead of symbolic functions.** Functions and equations
are evaluated with free variables kept symbolic and every referenced object folded
in as a constant. A dependent function is therefore a closed expression that is
re-bound when its parents change, compiles to numpy closures for fast sampling, and
needs no CAS at recompute time. sympy is used only for genuinely symbolic work
(M4 derivatives, M5 CAS).

**D-102 Canonical stored definitions.** Definitions are stored as the unparsed
*resolved* AST (`2*x`, `Midpoint(A, B)`), not the raw text the user typed. Name
splitting (`ab` -> `a*b`) and call classification happen once; a later object named
`ab` cannot change the meaning of an old file. The algebra view shows a separate
pretty form.

**D-103 Typed undefined and sticky types.** `Undef(GeoType.POINT)` keeps an object's
type when it becomes undefined, so views keep drawing it as a point with `?`.
Recomputation may change a type only outside a redefinition (e.g. `If` returning
different types); during a redefinition a dependent changing type causes a rollback.

**D-104 Transactional redefinition.** GeoGebra refuses a redefinition that breaks
dependents. We evaluate the new definition first (its own errors surface directly),
then recompute dependents strictly; any failure restores the snapshot and reports
which object would break. A non-integral number in an `<Integer>` slot makes the
result undefined rather than an error, so moving a slider through 2.5 does not make
`GCD(a, 6)` block redefinitions.

**D-105 Multi-output commands become indexed definitions.** `Intersect(c, g)`
creates `Intersect(c, g, 1)` and `Intersect(c, g, 2)`. Line/circle and circle/circle
always create two points (one may be undefined) so the number of objects is stable
while dragging. Used inside a larger expression, a multi-output command must be
indexed (clear error otherwise).

**D-106 Reserved names.** `x`, `y`, `z` are free variables and can never be labels,
so `x = 3` is a vertical line and `z = 10` is a 3D plane (M7). Constants (`pi`, `e`,
`i`, `∞`, `deg`), command names and predefined function names (case-insensitive) are
also reserved. Automatic labels skip `e`, `i`, `x`, `y`, `z`.

**D-107 GeoGebra conventions kept.** `log(x)` is the natural logarithm (`lg` base 10,
`ld` base 2, `log(b, x)` base b); `round` rounds halves away from zero; a lowercase
label on a coordinate pair (`u = (1, 2)`) makes a vector; `y = x^2` is a conic
(parabola) while `y = sin(x)` is a function; point ± point is a point and
point · point is the dot product; `{1, 2} + 1` is element-wise; `|x|` is absolute
value; commands accept `[ ]` as well as `( )`.

**D-108 Snapshot undo.** Whole-document canonical JSON snapshots (200 steps) instead
of a command pattern. Every action is undoable by construction, there is no inverse
operation to get wrong, and equality of snapshots makes "nothing changed" detection
exact. Restoring re-evaluates the construction (a few ms for hundreds of objects).
Drags will be grouped into one step per mouse press in M2.

**D-109 Free objects.** An object is free when its definition references no other
object and contains no command call (`a = 3`, `A = (1, 2)`, `f(x) = x^2`,
`c: x^2 + y^2 = 4`). Only free objects can be moved or set; `Circle((0, 0), 3)` is
dependent-but-constant like in GeoGebra. Setting a free value rewrites its literal
definition.

**D-110 Partial algebra view in M1.** M1 includes a basic text list of objects so the
model can be exercised in the app (input, errors, undo, files). It is replaced by the
full Algebra view in M2; FEATURES.md marks the algebra view as not done.

**D-111 Text and display formatting.** Numbers round to 2 decimals by default
(setting per construction, override per object), `∞` and `?` are shown for infinite
and undefined values, exact small fractions in exponents display as `(1/3)`. Free
functions display as typed (`x^(1/3)`), dependent ones with parent values folded in.

**D-112 `--quit-after` launch flag.** `python -m pykaufgeo [file.pkgeo] [--quit-after=MS]`
opens a file and optionally exits after MS milliseconds; tests and the build check
use it to prove the app starts.

## M2

**D-201 Zoom, pan and grid are not undo steps.** View settings are saved in the file,
but undo restores only the construction (plus spreadsheet and CAS data), and
changing the view does not mark the document modified. Otherwise undoing a point
would also undo the last zoom, and every pan would prompt "save changes?".

**D-202 Ticks and snapping.** Tick spacing is the smallest 1-2-5 step at least 45 px
wide (1 unit at the default 50 px per unit, as in GeoGebra's standard view). The
minor grid is a fifth of a 1- or 5-step and a quarter of a 2-step. With snapping on
"auto", new and dragged points snap to minor-grid intersections within 10 px when a
cartesian grid is shown; otherwise coordinates are rounded to the screen resolution.

**D-203 Origin placement.** A new view centres the origin once it has its real size;
after that it keeps origin and scale when resized (GeoGebra behaviour), so panels
opening and closing do not shift the drawing.

**D-204 Adaptive sampling.** About one sample per pixel, curvature refinement to half
a pixel (up to 5000 points), bisection to domain edges, and bisection towards every
large screen jump: a jump that survives at ~1e-9 of the interval is a discontinuity
and the curve is split. Jumps between two points that are both far above (or both
far below) the view are not split, so `ln(x)` and `1/x²` run off the edge instead of
stopping short. Stretches entirely outside the view are trimmed and near-collinear
vertices are removed (vectorised, sub-pixel error) because antialiased 3 px strokes
cost per vertex.

**D-205 Layered painting.** Objects whose geometry did not change since the last frame
are kept in a cached pixmap together with grid, axes and their labels; only objects
rebuilt this frame (a dragged point and its dependents) are painted live, and
selection/hover halos are drawn on top. Measured with 202 objects and two functions:
repaint 0.4 ms, drag 0.7-1 ms, pan 15-21 ms (full re-sample). A side effect is that
selected objects draw above others, which also makes the selection easier to see.

**D-206 Ink casing for low-contrast strokes.** The brief keeps yellow and green readable
on white with dark edges. Night mode has the mirror problem: pure blue on black is
2.4:1, below the 3:1 minimum for graphics (WCAG 1.4.11). Any stroke whose colour is
below 3:1 against the canvas gets a 1 px ink casing on each side (black by day,
white at night). Colours stay the "same saturated colours" the brief asks for.

**D-207 Labels.** New points show their name; other objects do not (GeoGebra's
"automatic" labelling). A label uses its object's colour unless that colour is
below 4.5:1 against the canvas, in which case it uses ink, so no yellow, green or
dark-blue-at-night text. Labels are placed greedily around the anchor avoiding
points and other labels; a dragged label keeps its offset (undoable).

**D-208 LaTeX with mathtext.** Algebra rows are LaTeX rendered by matplotlib mathtext.
mathtext shrinks `\left( ... \right)` around plain content, so stretchy brackets are
used only around fractions and roots, and a leading minus is braced (`{-1}`) to keep
it unary. Text objects are shown as plain text. While an object is being dragged the
changed rows switch to monospace text (rendering a formula costs ~7 ms) and return
to LaTeX when the drag ends. A LATEX toggle switches the whole view to plain text.
A test checks that every row of a broad construction typesets.

**D-209 Editing rows.** The editor shows an "edit form": exact numbers and implicit
products as typed (`a x^2 - 2x`), not the stored canonical form (`a*x^2 - 2*x`).
Changing the label in the editor renames the object (dependents follow) and
redefines it in one undo step.

**D-210 M2 tools.** Point creates free points (attaching points to objects is the M3
Point on Object tool). Line and Circle reuse a point under the cursor or create one.
A multi-click tool is one undo step; Escape cancels it but keeps points already
made (they are part of the step). Dragging a free point, vector tip or complex
number is one undo step per press; dependent objects cannot be dragged yet (M3
translates them by their free parents).

**D-211 Graphics 2.** Objects created by tools in Graphics 2 are shown only there;
input-bar objects go to Graphics. Each view has its own zoom, grid and axes.

**D-212 View bar, not yet a style bar.** Each Graphics panel has a narrow bar with
axes, grid type and axis-ratio lock. Standard View (Ctrl+M) and Show All
(Ctrl+Shift+M) live in the View menu and the canvas context menu so the bar fits at
20 pt. The full per-view style bar (colours, line styles) arrives with M3.

**D-213 Escape.** There is no window-wide Escape shortcut (it would steal Escape from
the autocomplete popup and the inline editor). The canvas cancels its tool and
clears the selection, then lets Escape reach the window, which selects Move.

**D-214 Visibility toggle shape.** Shown = filled box, hidden = hollow box with a slash,
so the state never depends on colour. The toggle hides an object from both Graphics
views and shows it again in Graphics.

**D-215 Autocomplete.** Suggestions appear after three letters (commands, predefined
functions, object names). Accepting one inserts `Circle(<Center>, <Radius>)` with
the first placeholder selected; Tab selects the next. Submitting text that still
contains a `<placeholder>` is an error naming it. The hint bar shows every overload
that fits the current argument count with the current argument inverted.

## M3

**D-301 Points on objects store a parameter.** `Point(c)` keeps `state["param"]`
(angle on a circle, 0..1 on a segment, x on a graph, ...; `core/paths.py`). The point
follows its object when the object moves and dragging projects the mouse onto it.
The parameter is saved, so files reopen with points where they were.

**D-302 Locus by re-evaluation.** `Locus(Q, M)` moves M over its object's parameter
range (240 samples, refined to at most 1200 where neighbours are far apart),
re-evaluating only the chain from M to Q with overrides, and splits the path where
it jumps. No symbolic elimination.

**D-303 Action commands.** Commands that change things (`SetValue`, `ZoomIn`, ...) are
marked `action` and run only when typed on their own; inside a definition they are
an error. Model changes are undo steps; view changes travel as `ViewCommand` events
to Graphics 1 and are not undo steps (as zooming is not).

**D-304 Extras.** View data that is not style (slider range and position, text and
image positions, image width, slope-triangle line) lives in `GeoElement.extras`,
saved with the object and restored by undo. Sliders are free numbers whose
`extras["slider"]` holds min, max and increment; `a = Slider(0, 10, 1)` creates one.

**D-305 Dragging dependent objects.** A dependent line, polygon, conic, ... moves by
translating all of its free ancestor points (GeoGebra's behaviour); a fixed ancestor
point blocks the drag. Dependent points (midpoints, intersections) cannot be dragged.
Free equations are rewritten (`y = 2x + 1` becomes `y = 2x - 1`), functions are
re-expanded so repeated drags do not nest, and shapes built from constant points
have those points shifted, but only if a trial shift really translates the shape.

**D-306 Transformation names.** Tool results are named with primes (`A'`, `A''`,
`poly1'`); functions get an ordinary new name because `f'` means the derivative.

**D-307 Tool patterns.** Most tools are declared as patterns of object kinds
(`"point line"`, ordered or not) plus a builder that types the command. Clicking
empty space where a point is accepted makes a point, on an object or at an
intersection if one is under the cursor. A cancelled tool action (Escape, another
tool, a cancelled prompt) is rolled back completely by `Document.abort_action()`.

**D-308 Pen and freehand.** A pen stroke becomes a polyline of constant points
(simplified to 1.5 px). Freehand Shape recognises a circle (least squares, RMS
error under 7 % of the radius), a straight segment and polygons of 3 to 8 corners;
anything else is reported as not recognised. Freehand function graphs: M4.

**D-309 Style bar.** A second bar under the view bar with icon buttons (colour, line,
point, label, properties) acting on the selection. It is always shown and only
disabled without a selection, so the canvas never changes size when the selection
changes; icons keep it inside narrow panels at 24 pt.

**D-310 Animation.** One timer (the 60 fps token) advances every object with
Animation on; one pass over a slider range or a path takes 10 s at speed 1. Modes:
oscillating, increasing, decreasing (wrapping), once. Frames are not undo steps; the
view bar shows PLAY / PAUSE while some object is animated.

**D-311 Traces.** Objects with Trace on paint into a transparent layer each time they
change. The layer is cleared when the view pans or zooms, the theme changes, or by
Clear Traces in the canvas menu (GeoGebra also drops traces on view changes).

**D-312 Images in the document.** Pictures are stored inside the .pkgeo zip under
`assets/` with sanitised unique names (PNG, JPEG, GIF, BMP; 32 MB each). Only
pictures used by an Image object are saved. `Image("name.png")` is the object's
definition; position and width are extras.

**D-313 Whole-number equations.** Lines and conics without a typed equation print
with the smallest whole-number coefficients when a multiplier up to 1000 exists
(`16x² + 25y² = 400`); nearly horizontal or vertical lines (slope below 1e-7)
print as `y = k` / `x = k`. Otherwise coefficients are shown rounded.

**D-314 Milestone demos and gallery.** Each finished milestone from M1 on has a demo in
`pykaufgeo/demos.py`: input-bar lines plus a little setup, opened unsaved with a fresh
undo history by `--demo` or Help > Milestone Demos, with a hint in the message block of
what to try. `tools/gallery.py` renders every demo and writes docs/GALLERY.md (newest
milestone first, review screenshots folded under each). `tests/test_demos.py` keeps both
honest: a milestone marked done in PLAN.md needs a demo, and the gallery must be current.
Writing the demos showed that message blocks ignored their padding (the stylesheet
applies the box model only at the first polish), clipping the first letter and long
texts; message blocks now get their kind before the first polish and grow to fit.

## M4

**D-401 sympy for symbolic calculus.** Derivatives, antiderivatives, limits, Taylor
polynomials, asymptotes and polynomial expansion go through sympy (already the CAS
library of the plan) via `engine/sym_bridge.py`. Numbers typed as integers become exact
integers; other floats stay floats (as in GeoGebra's Algebra view); the folded
constants e and π are recognised and kept exact. Results are tidied: polynomials
expanded in descending powers, rational functions as one fraction, minus signs on
the leading factor. Every call runs with a 4 s limit (the worker is abandoned if it
overruns) and results are cached by expression.

**D-402 Prime notation.** `f'` is resolved to `Derivative(f)` (`f''` to
`Derivative(f, 2)`) when f is a function, and written back as `f'`, so definitions such
as `g(x) = f'(x) + 1` round-trip. An unnamed derivative of f is called f' if free.

**D-403 Several results and their indices.** Commands with several results create one
object per result whose definition is the command with an index. Commands choose the
indexed form (`Command.indexed`): `Root(f)` expands to `Roots(f, 1)`, ... because
`Root(f, x0)` already means "the root near x0". Polynomials get all their roots and
extrema; other functions need an interval or a start value, and the tools use the
visible x-range.

**D-404 Definite integrals are shaded numbers.** `Integral(f, a, b)` is a number that
remembers f, a, b (an `AreaValue`), shown by default as the shaded area; the same for
IntegralBetween. NIntegral is the plain number.

**D-405 Implicit curves by marching squares.** F(x, y) = 0 is contoured on 3 px cells
with linear interpolation, saddles resolved by the cell centre. A sign change through
a pole is rejected when |F| at the segment's midpoint is not small compared with F
one cell to either side. Segments are chained into polylines (dash patterns would
otherwise restart every 3 px).

**D-406 Regions as a margin field.** A condition becomes one expression M(x, y), positive
inside: a < b gives b - a, ∧ the minimum, ∨ the maximum, ¬ the negation. The fill is
the grid mask M > 0 drawn as a smoothed image; the boundary is the contour M = 0, which
stays smooth where conditions overlap. All-strict conditions get a dashed boundary.

**D-407 Graph transformations.** Translating a function keeps a function; any other map
turns its graph into the curve (t, f(t)), t in [-100, 100]. Implicit curves and regions
are mapped by substituting the inverse map into their equation.

**D-408 Freehand functions.** A sketch that goes left to right (95 % of its steps) becomes
`Function(<polynomial>, x0, x1)` with the lowest degree up to 6 that follows the
stroke within 3 px. There are no table-based freehand functions.

## M5

**D-501 CAS rules.** The CAS uses sympy (D-401) with GeoGebra's CAS conventions: names
without a definition are symbols; a name made of several letters with no definition is
a product (xy = x·y); typed decimals are exact (0.1 + 0.2 = 3/10); ``=`` makes an
equation and ``:=`` an assignment; results are not simplified unless a command asks
(Simplify, Factor, Expand), except that numbers with i are multiplied out.

**D-502 Rows and references.** A row is ``{input, mode}`` plus its results; the session
evaluates all rows top to bottom with one scope, so ``$n`` (dynamic) always shows row n's
current result. ``#n`` is static: the result is pasted as text when the row is entered.
Inserting or deleting rows renumbers ``$n`` references.

**D-503 Sharing with the construction.** CAS rows read construction objects by value
(numbers as exact fractions when they are simple, points as column vectors, functions
by their expression). ``a := 5`` and ``f(x) := ...`` are also executed in the
construction (a = 5, f(x) = ...) when the row is entered, in the same undo step; if that
fails the row says "Only in the CAS". Rows that read construction objects are evaluated
again (80 ms after a change) without exporting, so nothing loops.

**D-504 Solutions.** Solve returns equations ({x = -2, x = 2}) and keeps only real
solutions (symbolic ones whose reality cannot be decided are kept); CSolve keeps complex
ones; periodic equations give sympy's principal solutions, not GeoGebra's general
solution with an integer parameter. NSolve uses numeric roots (all of a polynomial,
otherwise those between -100 and 100, or Newton from a start value).

**D-505 Limits.** Every CAS row runs with a 10 s limit (D-401); integer powers with more
than 100000 binary digits are refused before they are computed.
