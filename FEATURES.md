# PyKaufGeo feature checklist

Legend: `[x]` done, with evidence (a test or a screenshot in `docs/screenshots/`).
`[~]` partly done; the note says what exists and what is missing. `[ ]` not started.
The tag after each item is the milestone it belongs to. Nothing is checked without evidence.
Test names refer to files in `tests/`.

## Deliverables

- [x] App launches with `python -m pykaufgeo` (also `python -m pykaufgeo file.pkgeo`) (M0): test_gui_smoke::test_python_m_pykaufgeo_launches
- [x] `.pkgeo` format: zip with JSON construction, view settings, styles, spreadsheet, CAS rows, PNG thumbnail (M1): test_pkgeo::test_round_trip_preserves_everything, test_file_layout_and_version. The spreadsheet and CAS sections are stored and round-tripped; their views arrive in M5/M6.
- [x] `.pkgeo` format version and migration hook (M1): test_pkgeo::test_migration_hook, test_newer_and_unmigratable_versions
- [x] `build.py` builds one-file `PyKaufGeo` executable with PyInstaller and prints the path (M0; polish in M9): rebuilt after M2 as `dist/PyKaufGeo.exe` (95.5 MB) on Windows 11; `--quit-after --smoke-report` run of the exe opened a 5-object file and typeset a formula with mathtext (exit code 0)
- [~] Build notes for Linux and macOS (M9): written in the build.py docstring; not tried on those systems
- [ ] Export graphics: PNG (M8)
- [ ] Export graphics: SVG (M8)
- [ ] Export graphics: PDF (M8)
- [ ] Export graphics: TikZ/PGF (M8)
- [ ] Export graphics: image to clipboard (M8)
- [ ] Stretch: import basic `.ggb` (points, lines, circles, functions) (M9)

## Visual design (brutalist)

- [x] All tokens in `pykaufgeo/theme.py`; Qt stylesheet generated from it (M0): test_theme_tokens::test_stylesheet_generated_from_tokens
- [x] Test: no colour, font family or border-width literal outside `theme.py` (M0): test_theme_tokens::test_no_design_literals_outside_theme (+ self-tests of the scanner)
- [x] Palette limited to black/white/red/blue/yellow/green/magenta plus neutral greys for grid/disabled (M0): test_theme_tokens::test_chrome_palette_is_restricted
- [x] Radius 0; 3 px borders (2 px dense, 4 px dialogs and main frame) (M0): test_theme_tokens::test_border_tokens; m0_main.png, m0_dialog_about.png, m1_algebra_list.png
- [x] Bold sans UI font stack, uppercase headings; bold monospace for input/math (M0): m0_main.png, m1_algebra_list.png
- [x] No chrome animation; Qt UI effects disabled (M0): test_gui_smoke::test_ui_effects_disabled
- [x] Hard offset shadow (4 px, solid) for menus/popups, dialogs, tooltips, active tool button (M0): m0_menu_view.png, m0_tool_group_menu.png, m0_tooltip.png, m0_dialog_*.png, m0_main.png; test_gui_smoke::test_dialogs_build (mask)
- [x] Thick black splitters, black panel title bars with white uppercase text (M0): m0_all_views.png
- [~] Hover invert, pressed yellow, 4 px yellow focus ring with black edges (M0): focus ring in m0_focus_ring_toolbar.png and m0_focus_ring_input.png; hover/pressed are implemented in the stylesheet and button painting but have no screenshot yet (hover cannot be simulated offscreen)
- [x] Selected tool: black background with yellow icon (M0): m0_main.png, m0_tool_group_menu.png
- [x] Message blocks: error red/white, success green/black, warning yellow/black (M0): m1_input_error.png, m0_main.png; test_gui_document::test_save_and_open_round_trip (success)
- [x] Selected object: thicker stroke + yellow halo with black outline (M2): m2_main.png (circle c); painter.paint_highlights
- [~] Selected row in algebra/spreadsheet: yellow fill: Algebra done (m2_main.png, test_algebra_view::test_selection_sync_both_ways); spreadsheet in M6
- [x] Graphics light theme: white canvas, 3 px black axes, 1 px grey grid, mono tick labels (M2): test_graphics_view::test_axes_points_and_outline_are_drawn, m2_main.png
- [x] Points: filled circle with 3 px black outline; square-point toggle (M2): test_graphics_view::test_axes_points_and_outline_are_drawn, test_night_high_contrast_and_square_points, m2_square_points.png
- [x] Night theme for chrome and graphics, switchable instantly: m2_night.png, test_gui_smoke::test_theme_switch_is_instant, test_graphics_view::test_night_high_contrast_and_square_points (low-contrast strokes get an ink casing, D-206)
- [x] High-contrast mode removing magenta and green accents, chrome and graphics: test_theme_tokens::test_high_contrast_removes_magenta_and_green, test_graphics_view::test_night_high_contrast_and_square_points, m2_high_contrast.png
- [x] Self-drawn icons, 3 px strokes, pixel aligned, no gradients, for every tool (M0): test_gui_smoke::test_every_tool_has_an_icon, m0_tool_group_menu.png
- [x] WCAG AA body text contrast test (M0): test_theme_tokens::test_text_contrast_meets_wcag_aa, test_no_yellow_or_green_text_on_white
- [x] Hit targets: 28 px toolbar, 24 px elsewhere (M0): test_gui_smoke::test_hit_targets
- [x] Never colour-only: message prefixes, tool shadow, [ACTIVE] marker, filled/hollow-with-slash visibility boxes, halos for selection, points vs strokes vs fills, label fallback to ink (m2_main.png, D-207, D-214)
- [x] Font size setting 10-24 pt (M0): test_gui_smoke::test_font_size_setting_applies, m0_font_20pt.png
- [x] Respect the system font scaling (M0): test_theme_tokens::test_font_size_clamp_and_system_scaling (factor = system UI font pt / 9 pt)
- [~] Keyboard navigation everywhere: Tab order, toolbar arrows/Enter/Down, menu shortcuts, Ctrl+I, input history and autocomplete keys, canvas arrows/+/-/Escape, algebra F2/Enter/Space/Delete (tests in test_graphics_view, test_algebra_view, test_input_bar); each new view adds its own
- [~] docs/DESIGN.md with tokens, state rules and annotated screenshots of every view and dialog: M0 to M2 done; extended each milestone

## Architecture

- [x] Core model independent of GUI (M1): test_module_size::test_core_does_not_import_qt
- [x] Construction as ordered DAG of GeoElements (M1): test_construction::test_dependents_in_topological_order
- [x] Element fields: label, definition, parents, value, free/dependent, style (M1): test_construction::test_labels_and_types
- [~] Style fields: colour, opacity, thickness, dash, point size/shape, label mode, per-view visibility, layer, fixed, trace, animation (M1 model, M3 UI): model and file round trip in test_pkgeo; no editing UI yet
- [x] Recompute only dependents of a changed free object, in topological order (M1): test_construction::test_change_recomputes_only_dependents
- [x] Redefine, transactional with rollback (M1): test_construction::test_redefine_*
- [x] Rename, updating dependents' definitions (M1): test_construction::test_rename_rewrites_dependents
- [x] Delete with dependents (M1): test_construction::test_delete_cascades_to_dependents
- [x] Cycle detection with clear error (M1): test_construction::test_cycles_are_rejected_with_clear_message
- [x] Lexer (M1): test_parser (lexer tests)
- [x] Pratt parser producing an AST (M1): test_parser
- [x] AST evaluator; no eval/exec of user input (M1): test_evaluator; compiled numeric closures in engine/numeric.py
- [x] Implicit multiplication (`2x`, `x y`, `(a)(b)`, `2 sin(x)`, `ab` -> `a b`) (M1): test_parser::test_implicit_multiplication, test_evaluator::test_implicit_multiplication_resolution
- [x] Case-insensitive commands; `[]` and `()` call syntax (M1): test_commands::test_case_insensitive_and_bracket_syntax
- [x] Assignments `A=(1,2)`, `f(x)=x^2`, `a=3`, `c: x^2+y^2=4`, `a := 3` (M1): test_parser::test_statements
- [x] Lists `{1,2,3}` and matrices `{{1,2},{3,4}}` (M1): test_evaluator::test_lists_are_elementwise, test_matrices
- [x] Equations (`x^2+y^2=4`, `y=2x+1`) (M1): test_evaluator::test_equations_classify
- [~] Inequalities (`y>x^2`) as objects (M1 model, M4 drawing): test_evaluator::test_inequalities_and_curves
- [x] Points, polar points `(r; θ)`, vectors (lowercase label), 3D points (M1): test_evaluator::test_points_and_vectors, test_construction::test_vector_from_lowercase_tuple_label
- [x] Complex numbers (`3+2i`) (M1): test_evaluator::test_complex_numbers
- [x] Booleans, comparisons, logic operators (M1): test_evaluator::test_booleans_and_comparisons
- [x] Text strings and text concatenation (M1): test_evaluator::test_text
- [x] Function calls and function application (M1): test_evaluator::test_functions_and_application
- [x] Unicode input: `π`, `°`, `²`, `√`, `≤`, `≠`, `∧`, `∨`, `¬` (M1): test_parser::test_lexer_unicode_operators, test_lexer_superscripts_become_powers
- [x] Undefined values shown as `?` and propagated (M1): test_construction::test_undefined_propagates_and_recovers
- [x] Command registry: classes, typed overloads, help strings (M1): test_commands::test_registry_is_complete_and_documented
- [x] Autocomplete and argument hints generated from registry (M2): test_input_bar, m2_autocomplete.png, m2_argument_hint.png
- [x] docs/COMMANDS.md generated from registry (M1): test_docs::test_commands_md_is_up_to_date
- [x] Undo/redo for every action so far, at least 200 steps: test_undo (200 steps, random sequences); input, edits, renames, deletes, style toggles, label drags, point drags and tool actions are one step each (test_graphics_view, test_algebra_view); view changes are deliberately not undo steps (D-201)
- [~] Event bus syncing all views: Algebra, Graphics and Graphics 2 stay in sync (test_graphics_view, test_algebra_view); CAS, spreadsheet, 3D and protocol subscribe when they land

## Object types

Value model means the type is created, evaluated, saved and shown in the algebra list; drawing comes later.

- [x] Number (M1): test_evaluator::test_numbers
- [~] Angle: value model (test_evaluator::test_angles_keep_degrees, test_commands::test_angles); drawing M3
- [x] Boolean (M1): test_evaluator::test_booleans_and_comparisons
- [~] Text: value model (test_evaluator::test_text); positioned text objects M3
- [x] Point 2D: value model and drawing (test_graphics_view)
- [~] Point 3D: value model; drawing M7
- [x] Vector: value model and drawing (m2_main.png)
- [x] Line: value model and drawing (test_graphics_view::test_function_with_poles_and_hit_testing)
- [x] Ray: value model and drawing (m2_main.png, test_render::test_lines_rays_segments_on_screen)
- [x] Segment: value model and drawing (m2_main.png)
- [x] Circle: value model and drawing (test_graphics_view)
- [~] Conic: ellipse, parabola, hyperbola, general: value model and classification (test_evaluator::test_equations_classify); drawing and construction commands M3
- [x] Polygon: value model and drawing with fill and ink edge (m2_main.png); Polygon tool in M3
- [x] Function incl. piecewise and If: value model and drawing (test_evaluator::test_piecewise_if, test_render, m2_main.png)
- [~] Parametric curve: value from `a(t) = (cos(t), sin(t))`; Curve command and drawing M4
- [~] Implicit curve: value model; drawing M4
- [ ] Locus (M3)
- [x] List (M1): test_evaluator::test_lists_are_elementwise, test_commands::test_list_results
- [x] Matrix (M1): test_evaluator::test_matrices
- [x] Complex number: value model, drawn as a point (scene.make_drawable, test_graphics_view)
- [ ] Slider (M3)
- [ ] Button (M8)
- [ ] Checkbox (M8)
- [ ] Input box (M8)
- [ ] Image (M3)
- [~] Inequality region: value model; drawing M4
- [ ] Plane (M7)
- [ ] Sphere (M7)
- [ ] Surface (M7)
- [ ] Polyhedron (M7)

## Views and UI

- [x] Main window shell with menus, toolbar, panel grid, input bar, status line (M0): m0_main.png
- [x] Panel shells: Algebra, Graphics, Graphics 2, 3D Graphics, CAS, Spreadsheet, Probability, Construction Protocol (M0): m0_all_views.png, test_gui_smoke::test_all_panels_exist_and_toggle (the views themselves are later milestones)
- [x] Algebra view: grouping by dependency/type/order, editable rows (redefine and rename), visibility toggle, colour square, LaTeX, auxiliary objects (test_algebra_view, m2_main.png, m2_algebra_by_type.png, m2_algebra_inline_edit.png)
- [x] Input bar with autocomplete, argument hints and command help (test_input_bar, m2_autocomplete.png, m2_argument_hint.png, m2_dialog_command_help.png)
- [x] 2D Graphics view (two instances): pan, zoom at cursor, rectangle zoom (test_graphics_view::test_wheel_and_rectangle_zoom, test_drag_on_empty_space_pans_without_undo, test_graphics2_is_independent, m2_two_graphics_views.png)
- [x] Axes with 1-2-5 ticks, cartesian/polar/isometric grids, axis ratio lock, snapping, labels (test_render::test_nice_step_is_1_2_5, test_graphics_view::test_every_grid_mode_paints, test_zoom_tools_and_move_view_axis_stretch, test_point_tool_snaps_and_is_one_undo_step, m2_polar_grid.png)
- [ ] 3D Graphics view (M7)
- [ ] CAS view (M5)
- [ ] Spreadsheet (M6)
- [ ] Probability calculator (M6)
- [ ] Construction protocol (M8)
- [ ] Properties dialog: Basic, Color, Style, Algebra, Position, Advanced, Scripting (M3)
- [~] Style bar per view: a view bar with axes, grid and ratio lock exists (D-212); the full style bar is M3
- [~] Toolbar with grouped tools and tooltips: all groups, icons, tooltips, group menus, keyboard navigation; 8 tools work (test_graphics_view::test_implemented_tools_match_catalogue), the rest say "not implemented" until M3/M4/M8
- [~] Menus and keyboard shortcuts: File (New/Open/Save/Save As), Edit (Undo/Redo/Delete/Select All), View (panels, Night, high contrast, Standard View, Show All), Options (font size, square points, preferences), Help (Command Help, About) work; export and properties are greyed out with their milestone
- [~] Preferences: font size, Night, high contrast and square points work (m0_dialog_preferences.png, m2_square_points.png); language takes effect in M8
- [ ] Translations: English and Norwegian Bokmål (M8): `tr()` is in place, catalogue missing

## Tools

All tool groups and tools are in the toolbar with icons and help text. Tools that do not work yet say so when chosen.

- [x] Move: select, drag free points/vectors/labels, pan on empty space (test_graphics_view)
- [x] Move Graphics View: pan, stretch an axis (test_graphics_view::test_zoom_tools_and_move_view_axis_stretch)
- [x] Zoom In / Zoom Out (test_graphics_view::test_zoom_tools_and_move_view_axis_stretch)
- [~] Point: free points with grid snapping (test_graphics_view::test_point_tool_snaps_and_is_one_undo_step); points on objects in M3
- [ ] Intersect (M3)
- [ ] Midpoint or Center (M3)
- [ ] Attach / Detach Point (M3)
- [x] Line (test_graphics_view::test_two_point_tools)
- [ ] Segment (M3)
- [ ] Ray (M3)
- [ ] Vector (M3)
- [ ] Polyline (M3)
- [ ] Perpendicular Line (M3)
- [ ] Parallel Line (M3)
- [ ] Perpendicular Bisector (M3)
- [ ] Angle Bisector (M3)
- [ ] Tangents (M3)
- [ ] Polar or Diameter Line (M3)
- [ ] Best Fit Line (M3)
- [ ] Locus (M3)
- [ ] Polygon (M3)
- [ ] Regular Polygon (M3)
- [ ] Rigid Polygon (M3)
- [x] Circle with Center through Point (test_graphics_view::test_two_point_tools)
- [ ] Circle with Center and Radius (M3)
- [ ] Compass (M3)
- [ ] Circle through 3 Points (M3)
- [ ] Semicircle (M3)
- [ ] Arc and Sector tools (M3)
- [ ] Ellipse (M3)
- [ ] Hyperbola (M3)
- [ ] Parabola (M3)
- [ ] Conic through 5 Points (M3)
- [ ] Angle (M3)
- [ ] Angle with Given Size (M3)
- [ ] Distance or Length (M3)
- [ ] Area (M3)
- [ ] Slope (M3)
- [ ] Reflect about Point (M3)
- [ ] Reflect about Line (M3)
- [ ] Reflect about Circle (inversion) (M3)
- [ ] Rotate around Point (M3)
- [ ] Translate by Vector (M3)
- [ ] Dilate from Point (M3)
- [ ] Slider (M3)
- [ ] Text (M3)
- [ ] Image (M3)
- [ ] Button (M8)
- [ ] Checkbox (M8)
- [ ] Input Box (M8)
- [ ] Relation (M3)
- [ ] Function Inspector (M4)
- [ ] Pen and Freehand Shape (M3)
- [x] Delete (test_graphics_view::test_delete_tool_and_edit_delete)
- [ ] Show/Hide Object, Show/Hide Label (M3)
- [ ] Copy Visual Style (M3)

## Commands

All commands below are listed with syntax and examples in docs/COMMANDS.md (generated).
Predefined functions (`sin`, `ln`, `sqrt`, `floor`, `round`, `gamma`, `erf`, `real`, ... 40+) are listed there too.

### Numbers and algebra
- [x] Sum (M1): test_commands::test_number_results, test_evaluator::test_sequences_sums_with_free_variables
- [x] Product (M1): test_commands::test_number_results
- [x] Sequence (M1): test_commands::test_list_results
- [x] Zip (M1): test_commands::test_list_results
- [x] Iteration, IterationList (M1): test_commands
- [x] Floor, Ceil, Round as predefined functions (M1): test_evaluator::test_numbers
- [x] GCD, LCM (M1): test_commands::test_number_results
- [x] RandomBetween, RandomUniform, random() (M1): test_commands::test_random_commands_in_range, test_construction::test_random_numbers_are_stable_until_update_construction
- [x] Min, Max, Mod, Div, abs (M1): test_commands, test_evaluator
- [ ] PrimeFactors, IsPrime and similar (M4)

### Geometry
- [x] Distance (M1): test_commands::test_distance
- [x] Midpoint, Center (M1): test_commands::test_midpoint_and_center
- [x] Intersect for lines, segments, rays, line/conic, circle/circle (M1): test_commands::test_intersections
- [ ] Intersect for conic/conic, functions, curves (M3/M4)
- [x] Line (M1): test_commands::test_lines
- [x] Segment (M1): test_commands::test_lines
- [x] Ray (M1): test_commands::test_lines
- [x] Vector (M1): test_commands::test_lines
- [x] Circle (M1): test_commands::test_circles
- [ ] Ellipse, Hyperbola, Parabola, Conic (M3)
- [x] Polygon, Polyline (M1): test_commands::test_polygons_area_perimeter
- [ ] Rotate, Reflect, Translate, Dilate (M3)
- [ ] Tangent (M3)
- [ ] Locus (M3)
- [x] Angle (three points, vectors, lines, number) (M1): test_commands::test_angles
- [x] Area, Perimeter, Circumference (M1): test_commands::test_polygons_area_perimeter
- [x] Slope (M1): test_commands::test_lines
- [x] PerpendicularLine, PerpendicularBisector (M1): test_commands::test_lines

### Functions and calculus (M4)
- [ ] Derivative (incl. `f'`): `f'` is parsed and reports "arrives in M4"
- [ ] Integral, IntegralBetween
- [ ] Limit
- [ ] Root, Roots
- [ ] Extremum, TurningPoint, InflectionPoint
- [ ] Asymptote
- [ ] Taylor (TaylorPolynomial)
- [ ] Curvature
- [ ] Newton (root by Newton's method)
- [ ] NSolve
- [ ] SolveODE
- [ ] Polynomial
- [x] If, piecewise functions (M1): test_evaluator::test_piecewise_if
- [ ] Curve
- [ ] ImplicitCurve

### CAS (M5)
- [ ] Solve, Solutions
- [ ] Simplify, Factor, Expand
- [ ] Substitute
- [ ] Limit, Sum, Integral, Derivative (symbolic)
- [ ] LaplaceTransform
- [ ] Eliminate
- [~] Determinant, Inverse, Eigenvalues, Eigenvectors: numeric Determinant and Invert/Inverse plus Transpose exist (test_commands); exact versions and eigen commands in M5
- [~] Matrix and vector operations: numeric +, -, *, ^, ^-1, matrix times point (test_evaluator::test_matrices); symbolic in M5
- [~] Complex functions: numeric real, imaginary, conjugate, arg, abs, sqrt, exp, ln (test_evaluator::test_complex_numbers); CAS in M5

### Statistics (M6)
- [ ] Mean, Median, SD, Variance, Quartiles
- [ ] Correlation, Covariance
- [ ] FitLine, FitPoly, FitExp, FitLog, FitPow, FitSin
- [ ] Histogram, BoxPlot, BarChart, DotPlot
- [ ] Normal, Binomial, Poisson, Student, ChiSquared, F, Exponential, Uniform (PDF, CDF, inverse)
- [ ] ZMeanTest, TMeanTest, ZMeanEstimate, TMeanEstimate and related

### Lists and text
- [x] Length (M1): test_commands::test_number_results
- [x] Element (M1): test_commands
- [x] Take (M1): test_commands::test_list_results
- [x] Append (M1): test_commands::test_list_results
- [x] Reverse (M1): test_commands::test_list_results
- [x] Sort (M1): test_commands::test_sort_by_keys_and_points
- [x] Unique (M1): test_commands::test_list_results
- [x] First, Last, Join, Flatten (M1): test_commands::test_list_results
- [x] Filter, KeepIf, CountIf (M1): test_commands
- [x] Text (M1): test_evaluator::test_text
- [x] FormulaText, LaTeX (test_latex::test_latex_and_formulatext_commands)
- [ ] TableText (M8)

### 3D (M7)
- [ ] Plane, Sphere, Cylinder, Cone, Cube, Prism, Pyramid, Surface, IntersectPath, Net

### Control (M3/M8)
- [ ] SetValue, SetColor, SetVisibleInView, SetCoords
- [ ] StartAnimation
- [ ] Delete
- [ ] UpdateConstruction (model method `update_all` exists; command in M3)
- [ ] ZoomIn, ZoomOut, SetAxesRatio, CenterView

### Scripting (M8)
- [ ] Python scripting console with API (evalCommand, getValue, setValue, getXcoord, setColor, ...)
- [ ] Per-object On Update and On Click scripts (the element has a `scripts` field that is saved)
- [ ] Script sandbox and warning before running scripts from a loaded file

## 2D rendering (M2-M4)

- [x] Adaptive function sampling with discontinuity/asymptote detection (test_render: tan, 1/x, floor, sqrt, ln, steep and wiggly curves)
- [ ] Implicit curves by marching squares with refinement
- [ ] Inequality regions with correct overlaps
- [ ] Parametric and polar curves with adaptive step
- [x] Pixel-accurate hit testing and selection (test_graphics_view::test_function_with_poles_and_hit_testing)
- [ ] Constrained dragging (point on object stays on object)
- [ ] Locus and trace rendering
- [ ] Animations at 60 fps target
- [ ] Dynamic text with live values
- [x] Antialiased math content (painter; m2_main.png)
- [x] Label placement avoiding overlaps; draggable labels (test_render::test_label_placement_avoids_overlap, test_graphics_view::test_label_drag_and_keyboard_nudge)

## Quality bar

- [~] No crash on any input; friendly errors in red block: parser and evaluator fuzz tests (test_parser::test_fuzz_*, test_evaluator::test_fuzz_*), damaged files (test_pkgeo), GUI input catches every exception (m1_input_error.png); re-checked as each view lands
- [x] Undefined shown as `?` and propagated (M1): test_construction::test_undefined_propagates_and_recovers, test_evaluator::test_typed_undefined_keeps_object_type
- [x] Pan/zoom smooth with 200 objects and functions sampled at up to 5000 points: test_graphics_view::test_repaint_performance_with_200_objects (202 objects + 2 functions: pan ~15-21 ms, repaint ~0.4 ms, drag ~1 ms, D-205)
- [x] Recompute after drag under 16 ms for typical constructions (M1): test_performance::test_drag_recompute_under_16ms (180 objects, 175 dependents: about 5 ms median)
- [x] Tests: parser incl. odd inputs (M1): test_parser
- [x] Tests: dependency order (M1): test_construction
- [~] Tests: geometric commands against known results: every implemented geometry command (test_commands); grows per milestone
- [ ] Tests: calculus and CAS against sympy (M4, M5)
- [x] Tests: save/load round trips (M1): test_pkgeo
- [x] Tests: undo/redo invariants (M1): test_undo
- [x] Tests: theme token check (M0): test_theme_tokens
- [x] Headless rendering smoke tests with screenshots (M0): test_gui_smoke, test_gui_document (save to build/test-screenshots)
- [x] docs/ARCHITECTURE.md (M1, kept current)
