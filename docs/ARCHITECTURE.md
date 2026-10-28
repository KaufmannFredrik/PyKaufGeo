# Architecture

This describes the code as it stands (M0 to M2). Later milestones add views as
subscribers of the same model; they do not change the core pipeline.

## Layers

```
gui/         PySide6 widgets. Talks to the model only through Document methods,
             and listens to the EventBus.
core/        Document, Construction (DAG), GeoElement, Style, values, events, undo,
             labels, formatting. No Qt.
engine/      Resolver, Evaluator (partial evaluation), operators, predefined
             functions, numeric compiler, polynomial/equation classification. No Qt.
commands/    Command registry and command families. No Qt.
parser/      Lexer, Pratt parser, AST, unparser. No Qt.
io/          .pkgeo reader/writer with format versions and migrations. No Qt.
render/      Drawing geometry without Qt: viewport maths, adaptive function sampling,
             clipping, label placement. Unit-tested on its own.
theme.py     Every design token; Qt-free so the core can read default colour tokens.
```

`tests/test_module_size.py` checks that `core`, `parser`, `engine`, `commands`
and `io` never import Qt, and that no module exceeds 800 lines.

## From text to object

```
"g(x) = a x^2 + 1"
   |  parser.lexer.tokenize        tokens (unicode operators, subscripts, primes, superscripts)
   |  parser.parser.parse_statement   Statement(label="g", params=("x",), expr=<AST>, kind="function")
   v
engine.resolver.Resolver.resolve   resolved AST + dependencies {"a"}
   |  - Call("Circle", ...) -> canonical command name
   |  - Call("sin", ...) -> predefined function
   |  - Call("f", ...) with f a function -> Apply(Ident f, ...); with f a number -> f * (...)
   |  - unknown "xy" -> x * y, "ab" -> a * b (only into known names)
   |  - command-local variables (Sequence(k^2, k, 1, 5)) bound inside lazy arguments only
   v
engine.evaluator.Evaluator.evaluate_definition
   |  - free variables x, y, z and parameters evaluate to Sym (residual expressions)
   |  - everything else folds to concrete values: a -> 3
   |  - result Sym(3 * x^2 + 1) is finalised into FunctionValue(("x",), body)
   v
core.construction.Construction._add_resolved
      GeoElement(label, expr, params, parents, value, geo_type, style, free, state)
      inserted at the end of the construction order; ElementsAdded emitted
```

Stored definitions are `unparse.to_input(resolved AST)`: canonical, with explicit
`*` and every needed bracket, so a file or undo snapshot replays identically no
matter how the user typed the input. The display form (`to_display`) is separate:
implicit products, superscripts, unicode operators, rounded numbers.

### Values

`core/values.py`. Numbers are `float` (`Angle` is a float subclass shown in
degrees), booleans `bool`, complex numbers `complex`, text `str`. Geometric values
are frozen dataclasses: `Point`, `Point3D`, `Vector`, `Line` (a·x + b·y + c = 0),
`Segment`, `Ray`, `Circle`, `Conic` (6 coefficients, classified on demand),
`Polygon`, `Polyline`, `ListValue` (matrices are rectangular lists of lists),
`FunctionValue` (parameters + closed body AST, compiled lazily to numpy),
`CurveValue`, `ImplicitValue`, `InequalityValue`.

`Undef(kind)` is a typed undefined value; NaN coordinates also count as undefined.
Element types are sticky: a point that becomes undefined is still a point and shows
`?`. Commands return `Undef(returns)` when any argument is undefined.

### Partial evaluation

`engine/symbolic.py` defines `Sym(node, free)`. Arithmetic on a Sym builds a
residual node with constants folded in. Applying a function to a Sym inlines the
function body. `If` with a residual condition becomes a pointwise `If` node.
Finalisation turns a top-level Sym into:

* `FunctionValue` (parameters as declared, or the free variables ordered x, y, z),
* `InequalityValue` if the residual is a comparison or logic expression,
* `CurveValue` if the residual is a tuple in one parameter.

Equations (`lhs = rhs`) go through `engine/polynomial.py`: a polynomial of degree 1
is a `Line`, degree 2 a `Circle` or `Conic`, higher degrees or non-polynomials an
`ImplicitValue`; `y = <expression in x>` that is not polynomial is a function in
`y =` form.

### Numeric evaluation

`engine/numeric.py` compiles a residual AST into nested closures over numpy
operations (no `eval`). The same closure handles scalars and arrays, so a function
is sampled at 5000 points in about 0.1 ms. Constant odd-denominator exponents take
real roots (`x^(1/3)` is defined for x < 0).

### Commands

`commands/registry.py`. A command is a class; each overload is a method decorated
with `@sig("<Center:Point>", "<Radius:Number>", returns=GeoType.CIRCLE)`. The spec
text is both the documentation and the type declaration. `<Expression>` and
`<Condition>` arguments are lazy (passed as AST), `<Variable>` arguments are names;
together they declare which names are local to the command, which the resolver uses
to compute dependencies. Dispatch tries overloads in order, coercing arguments
(segments count as numbers, expressions in x as functions), and turns numeric
failures into `Undef`. Wrong arguments raise `CommandError` listing every valid
syntax. `commands/docs.py` generates `docs/COMMANDS.md` and the help data used by
autocomplete (M2).

Commands with several results (`Intersect(c, g)`) return `MultiOutput` at the top
level only; the construction expands them into indexed definitions
`Intersect(c, g, 1)`, `Intersect(c, g, 2)` so every element has exactly one value.

## The construction (DAG)

`core/construction.py` keeps:

* `_el`: label -> GeoElement
* `_order`: construction order, always a topological order
* `_children`: label -> labels that reference it directly

Operations:

* **add**: resolve, evaluate, label (given or automatic per type), append.
* **set_value** (drags, sliders, SetValue): only for free objects; the literal
  definition is regenerated from the value, then **only descendants** are
  recomputed, sorted by construction order. 175 dependents take about 5 ms.
* **redefine**: rejects self-reference and cycles (with the dependency path in the
  message), evaluates the new definition, rewires parent edges, re-sorts the order
  (stable topological sort) if a new parent comes later, then recomputes
  descendants in strict mode. If any descendant fails or would change type, the
  whole construction is restored from a snapshot and `RedefineError` names the
  object that would break.
* **rename**: rewrites the ASTs of direct children (refusing names that would be
  captured by a command-local variable).
* **delete**: removes the object and all descendants.
* **to_dict / load_dict**: canonical JSON (label, type, definition, params, style,
  caption, state). Loading re-runs every definition in order; objects that fail are
  skipped and reported, never crashing the load.

Random numbers (`RandomBetween`, `random()`) are stored in the element's `state`, so
recomputation, undo and files reproduce them until `update_all(reroll_random=True)`.

## Events

`core/events.py`: a synchronous, Qt-free `EventBus` with `ElementsAdded`,
`ElementsRemoved`, `ElementsUpdated`, `ElementsRedefined`, `ElementRenamed`,
`StyleChanged`, `ConstructionReset`, `UndoStateChanged`, `DocumentChanged`.
`bus.batch()` merges events (labels de-duplicated). A failing handler is logged and
does not stop the model or other views.

## Document, undo, files

`core/document.py` bundles the construction, view settings, spreadsheet and CAS
data, the undo manager and the bus. Every user action runs through
`Document.run(description, action)`, which is one undo transaction. Actions that
span several GUI events (a drag) use `Document.begin_action()` / `end_action()`.

`core/undo.py` stores whole-document snapshots as canonical JSON strings (at least
200 steps). Identical consecutive snapshots are not stored. A transaction that
raises restores the last snapshot if anything changed. Tests replay random action
sequences and check that every intermediate state comes back exactly.

`io/pkgeo.py`: a zip with `document.json` (format marker, `format_version`, app
version, sections `construction`, `views`, `spreadsheet`, `cas`) and an optional
`thumbnail.png`. Writes are atomic (temporary file, then rename). Reading validates
size, JSON, format and version, and upgrades older files through `MIGRATIONS`.

## 2D graphics (M2)

```
Construction --ElementsUpdated--> GraphicsCanvas.update()
paintEvent:
  Scene.build(construction, viewport)      one cached Drawable per visible object
      key = (id(value), id(style), viewport, theme)  values and styles are immutable
      make_drawable: point / vector / clipped line, ray, segment / circle / polygon /
                     function (render.sampling.sample_function -> QPainterPath)
  static drawables  -> cached QPixmap layer with grid, axes and their labels
  rebuilt drawables -> painted live on top (the dragged point and its dependents)
  selected / hovered -> halo + redraw on top
  tool preview, zoom rectangle
```

* `render/viewport.py`: origin + pixels-per-unit; zoom about a point, rectangle zoom,
  ratio lock, 1-2-5 ticks.
* `render/sampling.py`: adaptive sampling with discontinuity detection, domain edges,
  off-screen trimming and vertex decimation (D-204).
* `gui/graphics/scene.py`: drawables, numpy-to-QPainterPath via QDataStream
  (~1 ms for 5000 vertices), hit testing in pixels (points first, then vectors,
  curves, filled areas), Show All bounds.
* `gui/graphics/painter.py`: grid (cartesian, major, polar, isometric), axes with
  monospace tick labels, objects, ink casing, halos, labels (spatial hash, D-207).
* `gui/graphics/tools.py`: Move, Move Graphics View, Zoom In/Out, Point, Line,
  Circle with Center through Point, Delete. Tools change the model through the
  Document; a drag or a multi-click tool is one undo step via
  `Document.begin_action()` / `end_action()`.
* `gui/graphics/canvas.py`: events (mouse, wheel zoom at cursor, right-drag rectangle
  zoom, arrow keys move selected points or pan), snapping, view settings stored in
  `Document.views` (not undoable, D-201).

## Algebra view and input bar (M2)

* `gui/algebra/model.py`: rows grouped by dependency, object type or construction order,
  collapsible group headers, auxiliary objects on demand.
* `gui/algebra/delegate.py`: visibility box, colour square, LaTeX formula from
  `GeoElement.describe_latex()` rendered by `gui/mathtext.py` (matplotlib mathtext,
  cached QImages), error chip.
* `gui/algebra/view.py`: inline editor (`GeoElement.edit_string()`, applied with
  `Document.edit()`, which renames and redefines in one undo step), selection shared
  with the graphics views through `gui/selection.py`, value updates coalesced while
  dragging (plain text until the drag ends).
* `gui/autocomplete.py`, `gui/input_bar.py`, `gui/command_help.py`: suggestions,
  templates with `<placeholders>`, argument hints and help, all generated from
  `commands.docs.help_entries()` (the registry).
* `parser/latex.py` and `core/format_latex.py`: AST and value to the mathtext subset.

## Geometry, tools and properties (M3)

Model (Qt-free):

* `core/conics.py`: canonical frame of a conic (`shape_of`), parameterisation,
  projection, sampling for drawing, conic/conic intersection, conic through 5 points.
* `core/paths.py`: objects a point can live on and their parameter (D-301).
* `core/locus.py`: locus by re-evaluating the chain from mover to traced point (D-302).
* `core/dragging.py`: `DragSession.start(construction, label, grab)` chooses free /
  path / offset / parents / value / literal mode; `move_anchor(x, y)` (D-305).
* `commands/transform.py` (affine maps on every value type), `commands/conics.py`,
  `commands/pathcmds.py` (Point, Locus, Relation), `commands/control.py` (actions,
  Slider; D-303).
* `Construction`: `extras` per object (D-304), `perform` for actions, `set_values`,
  `set_definition_node`, `place_on_path` / `set_path_param`, `evaluate_text`,
  `add_text(text, state, extras)`. `Document`: `assets` (D-312), `abort_action`.

GUI:

```
canvas.set_tool(id) -> tools.make_tool: Move, MoveView, Zoom, Point, Line, Circle, Delete
                        -> tools_build.make_build_tool: pattern tools (D-307)
                        -> tools_extra.make_extra_tool: vertex lists, rectangles,
                           positions (text, image, slider), clicks, strokes
canvas.pick_or_create_point -> placing.attach_point: intersection / point on object / free
Scene.build(..., SceneContext(font, assets, lookup, show_hidden))
    make_drawable -> shapes.make_extra: conics, arcs, angles, loci, texts, images,
                     sliders, slope triangles
paintEvent: base layer + trace layer (D-311) + live drawables + halos + tool preview
```

* `gui/properties.py`: Properties dialog; every control applies at once as one undo
  step for all its objects.
* `gui/graphics/view.py`: view bar (axes, grid, ratio, play/pause) and style bar
  (D-309). `GraphicsCanvas.object_menu` is the right-click menu of an object.
* `gui/animation.py`: `Animator` (D-310), driven by `AnimationCommand` events and the
  play button; `tick(dt)` is callable from tests.

## Calculus, curves, regions (M4)

* `engine/sym_bridge.py`: tree <-> sympy (`to_sympy`, `from_sympy`, `tidy`), lazy import
  and background `preload()`, `limited(fn, seconds)` time limit (D-401).
* `engine/analysis.py`: polynomial coefficients (`poly_coeffs`, `poly_node`), real roots,
  roots / extrema in an interval, Newton, definite integrals.
* `commands/calculus.py` (Derivative, Integral, Limit, Taylor, Asymptote, Polynomial,
  FitPoly, Function, Curve, ImplicitCurve, Curvature, OsculatingCircle, SolveODE) and
  `commands/analysis_cmds.py` (Root, Roots, Extremum, InflectionPoint, NSolve,
  intersections with graphs). `Command.indexed()` names the k-th result (D-403).
* `engine/resolver.py`: `f'` -> Derivative (D-402); `parser/unparse.py` and `latex.py`
  print it back with primes.
* `render/curves.py`, `render/implicit.py`, `render/regions.py` (Qt-free) and
  `gui/graphics/shapes_analysis.py` (paths, region images); drawable kind `region`.
* `gui/function_inspector.py`: the Function Inspector dialog.

## CAS (M5)

```
CasView (gui/cas_view.py) --Enter--> Document.cas_evaluate(index, text, mode)   one undo step
    Document.cas["rows"] = [{input, mode, output, value_text, latex, error, note, labels}]
    CasSession.evaluate(rows, export_from)       cas/session.py: top to bottom, one CasScope
        parse_statement -> to_cas (cas/convert.py) -> sympy -> CAS_COMMANDS (cas/commands.py)
        result -> sym_bridge.from_sympy(strict=False) -> to_display / to_latex
        := assignments -> Construction.execute (export)
    CasChanged event -> CasView.sync()
ElementsUpdated for labels a row reads -> CasView (debounced) -> Document.cas_refresh()
```

## GUI (M0/M1)

* `gui/app.py`: QApplication with Fusion, all UI effects off, font substitutions,
  system font scaling, ThemeManager, ToolTipManager, FocusRingManager.
* `gui/main_window.py`: menus, toolbar, panel grid, input bar, message block; owns a
  `Document` and implements New / Open / Save / Save As / Undo / Redo.
* `gui/chrome.py`: hard-shadow menus/dialogs/tooltips, focus ring, message blocks.
* `gui/toolbar.py`, `gui/icons.py`, `gui/tools_catalog.py`: tools and icons.

## Testing

`pytest` from the project root. GUI tests run on the offscreen platform and save
screenshots to `build/test-screenshots/`; `tools/screenshot.py` renders the design
review set into `docs/screenshots/`.
