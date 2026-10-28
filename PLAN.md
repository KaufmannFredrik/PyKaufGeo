# PyKaufGeo: plan

PyKaufGeo is a desktop mathematics application (dynamic geometry, graphing, CAS,
3D, spreadsheet, probability) written from scratch in Python with a brutalist UI.
This file holds the architecture, module layout, dependency choices, risks and the
milestone log. `FEATURES.md` is the feature checklist; `docs/` holds the detailed
architecture, design and decision records.

## 1. Architecture in one picture

```
            +---------------------- pykaufgeo.gui (PySide6) ----------------------+
            |  MainWindow  Toolbar  Panels  InputBar  AlgebraView  Graphics(2D/3D) |
            |  CAS  Spreadsheet  Probability  Protocol  Dialogs  FocusRing  Tooltips |
            +------------------------------^--------------------------------------+
                         commands/queries  |  events (EventBus, Qt-free)
            +------------------------------v--------------------------------------+
            |  core.Document = Construction + UndoManager + EventBus + view state  |
            |  core.Construction: ordered DAG of GeoElements, topo recompute       |
            +------^-------------------^-------------------------^----------------+
                   |                   |                         |
          parser (lexer, Pratt,   engine (resolver, partial   commands (registry of
          AST, unparse)           evaluator, operators,       Command classes with typed
                                  numeric compiler, polys)    overloads + help text)
                   |                   |                         |
                   +---------- core.values (immutable math values) ---------+
                                       |
                               theme.py (all design tokens, Qt-free)
```

Rules:

* `pykaufgeo.core`, `parser`, `engine`, `commands`, `io` never import Qt. They can be
  used and tested headless; the GUI is a client of `Document`.
* User input is never passed to `eval`/`exec`. Text goes lexer -> parser -> AST ->
  resolver -> evaluator. Scripting (M8) runs in a restricted interpreter, not `exec`
  of untrusted files without a warning.
* Every visual constant (colour, font family, border width) lives in `theme.py`.
  A test fails if one appears anywhere else.

## 2. Module layout

```
pykaufgeo/
  __main__.py          python -m pykaufgeo
  theme.py             design tokens + Qt stylesheet generator (pure Python)
  i18n.py              tr() lookup; en / nb catalogues (M8)
  core/
    errors.py          error hierarchy with user-facing messages
    types.py           GeoType enum, display names
    values.py          immutable values: Point, Vector, Line, Circle, Conic, Polygon, ...
    style.py           Style dataclass (colour token, thickness, dash, point shape, ...)
    element.py         GeoElement (label, definition, parents, value, style, state)
    labels.py          label validation and automatic naming per type
    graph.py           topological helpers (stable topo sort, descendants)
    construction.py    Construction: add / redefine / rename / delete / recompute
    events.py          EventBus and event dataclasses
    undo.py            snapshot UndoManager (>= 200 steps, transactions)
    document.py        Document: construction + undo + bus + view/CAS/sheet state
    format.py          value -> display text (numbers, equations, "?")
  parser/
    tokens.py lexer.py ast.py parser.py unparse.py
  engine/
    resolver.py        classify calls, split implicit products, collect dependencies
    evaluator.py       AST -> value, partial evaluation for free variables x, y, t
    symbolic.py        residual expressions (Sym) used for functions/equations
    operators.py       arithmetic semantics across value types
    builtins.py        predefined math functions (sin, ln, sqrt, ...)
    numeric.py         compile residual AST to vectorised numpy closures
    polynomial.py      polynomial extraction, equation -> Line / Circle / Conic / Implicit
  commands/
    registry.py        Command base class, typed signatures, dispatch, help
    numbers.py lists.py logic.py geometry.py ...  (one module per family)
  io/
    pkgeo.py           .pkgeo zip read/write, format version, migration hook
  gui/
    app.py             QApplication bootstrap (Fusion, effects off, fonts, scaling)
    main_window.py     menus, toolbar, panel grid, input bar, status
    chrome.py          hard-shadow menu / dialog / tooltip, focus ring overlay
    panel.py toolbar.py tools_catalog.py icons.py messages.py preferences.py ...
tools/                 screenshot.py, gallery.py, gen_commands_md.py
tests/                 pytest suite (headless, QT_QPA_PLATFORM=offscreen)
docs/                  ARCHITECTURE.md DESIGN.md DECISIONS.md COMMANDS.md GALLERY.md screenshots/
build.py               PyInstaller one-file build
```

## 3. Dependency choices

| Need | Choice | Why |
|---|---|---|
| GUI | PySide6 | Official Qt binding, LGPL, QPainter + QOpenGLWidget in one toolkit. |
| 2D canvas | QPainter on a QWidget | Full control over pixels, antialiasing per primitive, export to SVG/PDF via QPaintDevice. |
| 3D | QOpenGLWidget + PyOpenGL (M7) | See docs/DECISIONS.md D-004. |
| Numerics | numpy, scipy | Vectorised sampling, root finding, ODEs, statistics distributions. |
| CAS | sympy | Exact algebra; our AST converts to and from sympy expressions. |
| Formula rendering | matplotlib mathtext | LaTeX subset to cached QPixmaps, no TeX install needed. |
| Tests | pytest | Plain fixtures; no pytest-qt (not on the allowed list). |
| Packaging | PyInstaller | One-file executable. |

## 4. Key design decisions (summary; details in docs/DECISIONS.md)

* Values are immutable. An element's value is replaced on recompute, never mutated,
  so views can hold references safely and undo snapshots stay cheap.
* Undefined is typed: `Undef(GeoType.POINT)`. Element types are sticky, so a point
  that becomes undefined is still drawn and listed as a point showing `?`.
* Functions and equations are produced by *partial evaluation*: free variables
  (`x`, `y`, function parameters, command-local variables) stay symbolic and
  everything else folds into constants. A dependent function `f(x) = a x^2` is a
  closed expression that is re-bound whenever `a` changes.
* Definitions are stored in a canonical input form (`unparse` of the resolved AST),
  so files and undo snapshots replay exactly regardless of how the user typed them.
* Multi-output commands (e.g. `Intersect(c, f)`) expand into indexed single-output
  definitions (`Intersect(c, f, 1)`, `Intersect(c, f, 2)`), as GeoGebra does.
* Undo uses whole-construction snapshots (canonical JSON). Simple, provably correct,
  and fast enough for constructions of several hundred objects.

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Scope is enormous (GeoGebra parity). | Strict milestones; FEATURES.md tracks every item honestly. Unimplemented items stay unchecked and unimplemented tools say so in the UI. |
| Python speed for 200 objects at 60 fps. | Recompute only descendants; numpy-vectorised sampling; compiled closures for residual expressions; caching of sampled paths keyed by view rectangle. |
| Adaptive sampling and poles. | Interval-based subdivision with jump detection (M2), tests on tan, 1/x, floor. |
| CAS fidelity vs GeoGebra (Giac). | Use sympy; document differences in DECISIONS.md; test against sympy results. |
| 3D in Python. | Keep geometry on the CPU in numpy, upload VBOs once per change, flat shading only. |
| Brutalist style vs usability. | Accessibility guardrails in theme tokens, focus ring overlay, contrast tests. |
| Headless screenshots on Windows. | Offscreen QPA needs `QT_QPA_FONTDIR`; set automatically by tests and tools. |
| Scripting safety. | Restricted API surface, AST-checked Python subset, warning dialog on load (M8). |
| Large single modules. | Enforced soft cap of about 800 lines per module (test). |

## 6. Milestones

| | Scope | Status |
|---|---|---|
| M0 | Skeleton, packaging, tests, theme tokens, brutalist shell with empty panels | done |
| M1 | Core model, DAG, parser, evaluator, command registry (core subset), undo/redo, save/load | done |
| M2 | 2D graphics view, input bar, algebra view | done |
| M3 | Full tool set, transformations, conics, polygons, locus, sliders, animation, styling, properties | done |
| M4 | Calculus/analysis commands, implicit and parametric curves, inequalities | not started |
| M5 | CAS view | not started |
| M6 | Spreadsheet, statistics, regression, probability calculator | not started |
| M7 | 3D view | not started |
| M8 | Protocol, scripting, action objects, translations, export, Night/high contrast polish | not started |
| M9 | Polish, performance, build, docs, .ggb import | not started |

## 7. Milestone notes

(Appended at the end of each milestone.)

Finishing a milestone: tests green; review screenshots (`tools/screenshot.py`) and fix
what they show; add a demo for it to `pykaufgeo/demos.py`; run `tools/gallery.py`;
update FEATURES.md, this file and docs/; commit and push. `tests/test_demos.py` fails if
a milestone is marked done without a demo or if docs/GALLERY.md is stale.

### M0: skeleton, packaging, tests, tokens, shell (2026-10-27)

* `theme.py` holds every token and generates the stylesheet; the literal scanner,
  palette, contrast (WCAG AA) and border-token tests guard it.
* Shell: menus, toolbar with all 12 tool groups (70 tools) and 74 self-drawn icons, a four-column
  panel grid with all eight views as honest placeholders, input bar, message block.
* Hard shadows use window masks plus self-painted frames (QMenu ignores per-edge
  borders and margins). Custom tooltips, focus-ring overlay, frameless dialogs.
* Design review fixes made from screenshots: broken menu-bar underline, missing menu
  shadow, mnemonic eating `&` in "Center & Radius", tiny menu icons, focus ring
  offset by the button shadow, "X" close buttons clipping at 20 pt.
* `build.py` produces `dist/PyKaufGeo.exe`; offscreen screenshots need
  `QT_QPA_FONTDIR` on Windows (D-002).

### M1: model, parser, evaluator, undo, files (2026-10-27)

* Lexer + Pratt parser + statement layer; resolver; partial evaluator; numeric
  compiler; polynomial classification of equations; 52 commands in a typed
  registry (docs/COMMANDS.md is generated); 40+ predefined functions.
* Construction DAG with transactional redefine (rollback), rename, cascading delete,
  cycle detection, typed undefined values, reproducible random numbers.
* Snapshot undo (200 steps), `.pkgeo` zip format with version and migration chain.
* GUI: input bar with history and red error block, basic algebra list, undo/redo,
  New/Open/Save/Save As with thumbnail and unsaved-changes prompt.
* Screenshot review caught QLabel rendering `<Center>` in syntax hints as HTML;
  every label showing command text is now plain text (regression test added), and
  the active row of tool-group menus lost its icon (fixed with an active-mode pixmap).
* Numbers: 308 tests pass; drag recompute with 175 dependents takes about 5 ms
  (median); a 5000-point function sample takes about 0.14 ms.
* Not done (by plan): every drawing view, tools, autocomplete, LaTeX. The algebra
  list is a stand-in for the M2 Algebra view (D-110).
* Next: M2 (2D graphics view, Move/Point/Line/Circle tools, full algebra view with
  autocomplete and LaTeX, drag grouping into single undo steps).

### M2: graphics view, algebra view, input bar (2026-10-28)

* Qt-free `render` package: viewport (zoom about the cursor, rectangle zoom, ratio
  lock, 1-2-5 ticks), adaptive sampling with discontinuity/asymptote detection,
  domain edges, off-screen trimming and vertex decimation; clipping; label placement.
* Two Graphics views: cartesian/major/polar/isometric grids, axes with monospace
  ticks, points/vectors/lines/rays/segments/circles/polygons/functions/complex
  numbers, labels, hover and selection halos, Night and high contrast, square points,
  right-drag zoom, context menu, view bar. Tools: Move, Move Graphics View, Zoom
  In/Out, Point, Line, Circle with Center through Point, Delete. Drags and
  multi-click tools are single undo steps; zoom and grid are not undo steps (D-201).
* Algebra view: grouping (dependency, type, order), collapsible headers, visibility
  boxes, colour squares, LaTeX via mathtext, inline editing with rename, error chips,
  selection shared with the graphics views.
* Input bar: autocomplete from the registry, templates with placeholders and Tab,
  argument hints with the current argument highlighted, command help dialog (F1).
* Performance work found by profiling: O(n²) label placement (spatial hash),
  `strokePath` (now `drawPath`), wide antialiased strokes on dense curves (trimming
  and decimation), and a cached static layer. 202 objects + 2 functions: repaint
  ~0.4 ms, drag ~1 ms, pan ~15-21 ms.
* Design review fixes from screenshots: tiny `\left(` brackets and spaced minus signs in
  mathtext, view-bar buttons truncating at 20 pt, clipped group headers at 20 pt,
  blue curves nearly invisible at night (ink casing, D-206), tick labels clipped at
  the edge, labels on every object (now points only, as in GeoGebra).
* Test suite: 402 tests in about 21 s (an autouse fixture deletes test windows;
  restyling dozens of dead windows had made it take 5 minutes).
* Not done (by plan): conics, curves, implicit curves, inequality regions, angles and
  text are computed but not drawn yet (M3/M4); points on objects, transformations and
  the full style bar are M3.
* Next: M3 (full tool set, transformations, conics, polygons, locus, sliders,
  animation, styling, properties dialog).

### M3: tools, transformations, conics, sliders, properties (2026-10-28)

* Model: conic geometry (canonical frame, parameterisation, sampling, conic/conic
  intersection), points on objects with a stored parameter (`core/paths.py`), Locus,
  arcs and sectors, transformations (rotate, reflect in point/line/circle, translate,
  dilate) for every geometric type, Relation, conic commands (Ellipse, Hyperbola,
  Parabola, Conic, Vertex, Tangent, Polar, Diameter, AngleBisector, FitLine), regular
  polygons, polygon angles, Image. Equations print with whole-number coefficients
  where possible (`16x² + 25y² = 400`).
* Action commands (SetValue, SetColor, SetCoords, SetVisibleInView, Delete,
  StartAnimation, UpdateConstruction, ZoomIn/Out, SetAxesRatio, CenterView) run when
  typed on their own; `a = Slider(min, max, step)` makes a slider. Objects carry
  `extras` (slider range, positions, image size), saved in files and undo.
* Dragging (`core/dragging.py`): points along their objects, dependent objects by
  their free points, free equations and functions, constant shapes, vector-polygon
  vertices; sliders, texts and images in the view.
* Graphics: conics, arcs, sectors, angles (square for right angles), loci, texts,
  images, sliders, slope triangles; trace layer; hidden objects ghosted by the
  Show / Hide tool.
* All 56 M3 tools (`tools_build.py` pattern tools, `tools_extra.py` vertex, rectangle,
  position, click and stroke tools); clicks attach new points to objects and
  intersections; Escape removes a half-finished action (`Document.abort_action`).
* Properties dialog (Ctrl+E, object menu, style bar), icon style bar, object
  right-click menu, animation with play/pause.
* Design review fixes: style bar text truncated at 20 pt (now icons), the canvas
  jumping when the style bar appeared (now always shown), Properties tabs cut off
  (no scroll buttons; the dialog widens), object names upper-cased in the dialog
  title, spin-box text touching the border (an M0 bug: Fusion ignores QSS padding
  there), horizontal tangents printed as `0.45y = 2.34`, sliders without an Algebra
  visibility box, a vector hit-test crash.
* Test suite: 456 tests in about 35 s (`test_m3_model`, `test_m3_tools`, `test_m3_ui`).
* Not done: rigid polygons do not rotate; freehand function graphs; scripting tab
  (M8); LaTeX texts in the Graphics view (M8).
* Next: M4 (calculus and analysis commands, implicit and parametric curves,
  inequality regions, function tools).
