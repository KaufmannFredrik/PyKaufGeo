# PyKaufGeo

Dynamic geometry, graphing, CAS, 3D, spreadsheet and probability in one linked
construction, written in Python with PySide6. Brutalist interface.

Status: milestones M0 to M3 are done (application shell, core model, parser,
evaluator, undo/redo, files, two 2D graphics views, the Algebra view with LaTeX, an
input bar with autocomplete and command help, and the geometry tool set: points on
objects, intersections, polygons, conics, arcs, angles, transformations, locus,
sliders with animation, texts, images, pen, a style bar and the Properties dialog).
See `PLAN.md` for the roadmap and `FEATURES.md` for the honest feature checklist.

## Run

```
python -m pip install PySide6 numpy scipy sympy matplotlib pytest pyinstaller
python -m pykaufgeo                 # start the app
python -m pykaufgeo drawing.pkgeo   # open a file
```

Type into the input bar, for example:

```
A = (1, 2)
B = (4, 6)
M = Midpoint(A, B)
f(x) = x^2 - 2x
c: x^2 + y^2 = 4
Intersect(c, Line(A, B))
Sum(k^2, k, 1, 10)
```

## Test, screenshots, build

```
python -m pytest                    # full suite (GUI tests run headless)
python tools/screenshot.py          # design-review screenshots into docs/screenshots
python tools/gen_commands_md.py     # regenerate docs/COMMANDS.md
python build.py                     # one-file executable in dist/
```

## Documentation

* `docs/ARCHITECTURE.md`: layers, evaluation pipeline, DAG, undo, file format
* `docs/DESIGN.md`: design tokens, state rules, annotated screenshots
* `docs/DECISIONS.md`: decisions taken where the brief left room
* `docs/COMMANDS.md`: generated command reference
