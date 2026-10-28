"""CAS commands (exact, through sympy).

Each command takes already converted arguments (sympy expressions, equations, lists,
matrices) and returns a sympy result. Solving follows GeoGebra: Solve gives
equations such as {x = -2, x = 2} (real solutions), Solutions only the values,
CSolve / CSolutions include complex ones, NSolve / NSolutions are numeric.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from pykaufgeo.core.errors import EvalError
from pykaufgeo.engine import sym_bridge as sb


@dataclass(frozen=True)
class CasCommand:
    name: str
    fn: Callable[..., Any]
    syntax: tuple[str, ...]
    description: str
    min_args: int
    max_args: int

    def run(self, args: list[Any]) -> Any:
        if not self.min_args <= len(args) <= self.max_args:
            raise EvalError(f"{self.name}: " + " or ".join(self.syntax))
        return self.fn(*args)


CAS_COMMANDS: dict[str, CasCommand] = {}


def command(name: str, syntax: tuple[str, ...], description: str, min_args: int, max_args: int,
            aliases: tuple[str, ...] = ()) -> Callable:
    def deco(fn: Callable) -> Callable:
        cmd = CasCommand(name, fn, syntax, description, min_args, max_args)
        for n in (name,) + aliases:
            CAS_COMMANDS[n.lower()] = cmd
        return fn
    return deco


def sp():
    return sb.sympy()


# ----------------------------------------------------------------------- helpers

def _expr(v: Any) -> Any:
    """An equation lhs = rhs as the expression lhs - rhs."""
    s = sp()
    if isinstance(v, s.Equality):
        return v.lhs - v.rhs
    if isinstance(v, (list, s.MatrixBase)):
        raise EvalError("This needs an expression or an equation, not a list.")
    return v


def _symbols(v: Any) -> set:
    s = sp()
    if isinstance(v, list):
        out: set = set()
        for i in v:
            out |= _symbols(i)
        return out
    return set(getattr(v, "free_symbols", set())) - {s.I}


def _default_var(*exprs: Any) -> Any:
    """x if it occurs, else the only (or first) symbol."""
    free = set()
    for e in exprs:
        free |= _symbols(e)
    names = sorted(free, key=lambda t: (t.name != "x", t.name))
    if not names:
        return sp().Symbol("x")
    return names[0]


def _as_var(v: Any) -> Any:
    if not isinstance(v, sp().Symbol):
        raise EvalError("Give the variable as a name, e.g. x.")
    return v


def _vars(v: Any) -> list:
    return [_as_var(t) for t in (v if isinstance(v, list) else [v])]


def _limited(fn: Callable[[], Any], what: str) -> Any:
    return sb.limited(fn, what=what)


def _real(v: Any) -> bool:
    """False only for values that are certainly not real (symbolic ones like -b/a are kept)."""
    try:
        im = sp().im(v)
        if im == 0:
            return True
        if im.is_number:
            return abs(complex(im.evalf())) < 1e-12
        return v.is_real is not False and not v.has(sp().I)
    except (TypeError, ValueError):
        return True


# ----------------------------------------------------------------------- solving

def _solve(eqs: Any, variables: Any, real: bool) -> Any:
    s = sp()
    many = isinstance(eqs, list)
    items = eqs if many else [eqs]
    if not items:
        raise EvalError("Nothing to solve.")
    if any(isinstance(e, s.Rel) and not isinstance(e, s.Equality) for e in items):   # inequalities
        var = _vars(variables)[0] if variables is not None else _default_var(*items)
        if not var.is_real:
            real_var = s.Symbol(var.name, real=True)
            items = [e.subs(var, real_var) for e in items]
            var = real_var
        result = _limited(lambda: s.reduce_inequalities(items, var), "Solving")
        return result.subs({var: s.Symbol(var.name)})
    exprs = [_expr(e) for e in items]
    vs = _vars(variables) if variables is not None else (
        [_default_var(*exprs)] if not many else sorted(_symbols(exprs), key=lambda t: t.name))
    if not many and len(vs) == 1:
        sols = _limited(lambda: s.solve(exprs[0], vs[0]), "Solving")
        sols = [v for v in sols if not real or _real(v)]
        return [("one", vs[0], v) for v in _sorted(sols)]
    dicts = _limited(lambda: s.solve(exprs, vs, dict=True), "Solving")
    if real:
        dicts = [d for d in dicts if all(_real(v) for v in d.values())]
    return [("many", vs, d) for d in dicts]


def _value_key(v: Any) -> tuple:
    """Numbers by size (real part, then imaginary); symbolic values after them."""
    try:
        z = complex(v.evalf())
        return (0, z.real, z.imag, "")
    except (TypeError, ValueError):
        return (1, 0.0, 0.0, str(v))


def _sorted(values: list) -> list:
    return sorted(values, key=_value_key)


def _as_equations(solved: list) -> list:
    s = sp()
    out = []
    for kind, var, val in solved:
        if kind == "one":
            out.append(s.Eq(var, val, evaluate=False))
        else:
            out.append([s.Eq(v, val.get(v, v), evaluate=False) for v in var])
    return out


def _as_values(solved: list) -> list:
    out = []
    for kind, var, val in solved:
        out.append(val if kind == "one" else [val.get(v, v) for v in var])
    return out


@command("Solve", ("Solve(<Equation>)", "Solve(<Equation>, <Variable>)", "Solve({<Equations>}, {<Variables>})"),
         "Exact real solutions of equations, systems and inequalities.", 1, 2)
def solve(eqs: Any, variables: Any = None) -> Any:
    s = sp()
    result = _solve(eqs, variables, real=True)
    return result if isinstance(result, s.Basic) else _as_equations(result)


@command("Solutions", ("Solutions(<Equation>)", "Solutions(<Equation>, <Variable>)"),
         "Exact real solutions as values.", 1, 2)
def solutions(eqs: Any, variables: Any = None) -> Any:
    result = _solve(eqs, variables, real=True)
    return result if isinstance(result, sp().Basic) else _as_values(result)


@command("CSolve", ("CSolve(<Equation>)", "CSolve(<Equation>, <Variable>)"), "Exact complex solutions.", 1, 2)
def csolve(eqs: Any, variables: Any = None) -> Any:
    return _as_equations(_solve(eqs, variables, real=False))


@command("CSolutions", ("CSolutions(<Equation>)",), "Exact complex solutions as values.", 1, 2)
def csolutions(eqs: Any, variables: Any = None) -> Any:
    return _as_values(_solve(eqs, variables, real=False))


def _nsolve(eq: Any, start: Any = None) -> tuple[Any, list]:
    import numpy as np

    from pykaufgeo.engine import analysis

    s = sp()
    if isinstance(eq, list):
        raise EvalError("NSolve solves one equation; use Solve for systems.")
    e = _expr(eq)
    var = _default_var(e)
    if isinstance(start, s.Equality):
        var, start = start.lhs, start.rhs
    if _symbols(e) - {var}:
        raise EvalError("NSolve needs an equation in one variable.")
    fn = s.lambdify(var, e, "numpy")
    f = lambda t: np.asarray(fn(t), dtype=complex).real if np.iscomplexobj(fn(t)) else fn(t)  # noqa: E731
    if start is not None:
        x = analysis.newton(f, float(start))
        return var, ([x] if math.isfinite(x) else [])
    poly = s.Poly(e, var) if e.is_polynomial(var) else None
    if poly is not None:
        roots = [complex(r) for r in poly.nroots(n=15)]
        return var, sorted(r.real for r in roots if abs(r.imag) < 1e-10)
    return var, analysis.roots_in(f, -100.0, 100.0)


@command("NSolve", ("NSolve(<Equation>)", "NSolve(<Equation>, <Variable> = <Start>)"),
         "Numeric real solutions (near a start value if given).", 1, 2)
def nsolve(eq: Any, start: Any = None) -> list:
    var, xs = _nsolve(eq, start)
    return [sp().Eq(var, sp().Float(x, 15), evaluate=False) for x in xs]


@command("NSolutions", ("NSolutions(<Equation>)",), "Numeric real solutions as values.", 1, 2)
def nsolutions(eq: Any, start: Any = None) -> list:
    return [sp().Float(x, 15) for x in _nsolve(eq, start)[1]]


@command("Eliminate", ("Eliminate({<Equations>}, {<Variables>})",),
         "Equations without the given variables (Gröbner basis).", 2, 2)
def eliminate(eqs: Any, variables: Any) -> list:
    s = sp()
    exprs = [_expr(e) for e in (eqs if isinstance(eqs, list) else [eqs])]
    gone = _vars(variables)
    rest = sorted(_symbols(exprs) - set(gone), key=lambda t: t.name)
    basis = _limited(lambda: s.groebner(exprs, *gone, *rest, order="lex"), "Eliminate")
    return [s.Eq(g.as_expr(), 0, evaluate=False) for g in basis.exprs if not (g.free_symbols & set(gone))]


# ----------------------------------------------------------------------- algebra

def _on_parts(v: Any, fn: Callable[[Any], Any]) -> Any:
    """Apply to both sides of an equation and to list items."""
    s = sp()
    if isinstance(v, list):
        return [_on_parts(i, fn) for i in v]
    if isinstance(v, s.Equality):
        return s.Eq(fn(v.lhs), fn(v.rhs), evaluate=False)
    if isinstance(v, s.MatrixBase):
        return v.applyfunc(fn)
    return fn(v)


@command("Simplify", ("Simplify(<Expression>)",), "Simplest form found.", 1, 1)
def simplify(v: Any) -> Any:
    return _limited(lambda: _on_parts(v, sp().simplify), "Simplify")


@command("Expand", ("Expand(<Expression>)",), "Multiply out.", 1, 1)
def expand(v: Any) -> Any:
    return _on_parts(v, sp().expand)


@command("Factor", ("Factor(<Expression>)", "Factor(<Integer>)"), "Factor a polynomial (over the rationals) "
         "or a whole number into primes.", 1, 1)
def factor(v: Any) -> Any:
    s = sp()
    if isinstance(v, s.Integer) and abs(int(v)) > 1:
        parts = s.factorint(int(v))
        factors = [s.Pow(p, e, evaluate=False) if e > 1 else s.Integer(p) for p, e in sorted(parts.items())]
        out = s.Mul(*factors, evaluate=False)
        return -out if v < 0 else out
    return _limited(lambda: _on_parts(v, s.factor), "Factor")


@command("CFactor", ("CFactor(<Expression>)",), "Factor over the complex numbers.", 1, 1)
def cfactor(v: Any) -> Any:
    s = sp()
    return _limited(lambda: s.factor(v, extension=s.I), "CFactor")


@command("PartialFractions", ("PartialFractions(<Expression>)",), "Partial fraction decomposition.", 1, 2)
def partial_fractions(v: Any, var: Any = None) -> Any:
    return _limited(lambda: sp().apart(v, var or _default_var(v)), "PartialFractions")


@command("Substitute", ("Substitute(<Expression>, <From>, <To>)", "Substitute(<Expression>, <Var> = <Value>)",
                        "Substitute(<Expression>, {<Var> = <Value>, ...})"), "Replace variables by values.", 2, 3)
def substitute(v: Any, a: Any, b: Any = None) -> Any:
    s = sp()
    if b is not None:
        pairs = {a: b}
    else:
        eqs = a if isinstance(a, list) else [a]
        if not all(isinstance(e, s.Equality) for e in eqs):
            raise EvalError("Write the replacements as equations, e.g. Substitute(x^2, x = 3).")
        pairs = {e.lhs: e.rhs for e in eqs}
    return _on_parts(v, lambda t: t.subs(pairs, simultaneous=True))


@command("Numeric", ("Numeric(<Expression>)", "Numeric(<Expression>, <Significant Figures>)"),
         "Decimal value.", 1, 2)
def numeric(v: Any, digits: Any = 15) -> Any:
    return _on_parts(v, lambda t: sp().N(t, int(digits)))


@command("Numerator", ("Numerator(<Expression>)",), "Numerator of a fraction.", 1, 1)
def numerator(v: Any) -> Any:
    return sp().fraction(sp().together(v))[0]


@command("Denominator", ("Denominator(<Expression>)",), "Denominator of a fraction.", 1, 1)
def denominator(v: Any) -> Any:
    return sp().fraction(sp().together(v))[1]


@command("Degree", ("Degree(<Polynomial>)", "Degree(<Polynomial>, <Variable>)"), "Degree of a polynomial.", 1, 2)
def degree(v: Any, var: Any = None) -> Any:
    return sp().Integer(sp().degree(v, var or _default_var(v)))


@command("Coefficients", ("Coefficients(<Polynomial>)", "Coefficients(<Polynomial>, <Variable>)"),
         "Coefficients, highest power first.", 1, 2)
def coefficients(v: Any, var: Any = None) -> list:
    return list(sp().Poly(v, var or _default_var(v)).all_coeffs())


def _poly_divide(a: Any, b: Any) -> tuple[Any, Any]:
    s = sp()
    if a.is_Integer and b.is_Integer:
        return s.Integer(int(a) // int(b)), s.Integer(int(a) % int(b))
    return s.div(a, b, _default_var(a, b))


@command("Div", ("Div(<Dividend>, <Divisor>)",), "Quotient of whole numbers or polynomials.", 2, 2)
def div(a: Any, b: Any) -> Any:
    return _poly_divide(a, b)[0]


@command("Mod", ("Mod(<Dividend>, <Divisor>)",), "Remainder of whole numbers or polynomials.", 2, 2)
def mod(a: Any, b: Any) -> Any:
    return _poly_divide(a, b)[1]


@command("GCD", ("GCD(<A>, <B>)",), "Greatest common divisor of numbers or polynomials.", 2, 2)
def gcd(a: Any, b: Any) -> Any:
    return sp().gcd(a, b)


@command("LCM", ("LCM(<A>, <B>)",), "Least common multiple of numbers or polynomials.", 2, 2)
def lcm(a: Any, b: Any) -> Any:
    return sp().lcm(a, b)


# ----------------------------------------------------------------------- calculus

@command("Derivative", ("Derivative(<Expression>)", "Derivative(<Expression>, <Variable>)",
                        "Derivative(<Expression>, <Variable>, <Order>)"), "Exact derivative.", 1, 3)
def derivative(v: Any, var: Any = None, n: Any = 1) -> Any:
    s = sp()
    if var is not None and not isinstance(var, s.Symbol):
        var, n = None, var
    return _on_parts(v, lambda t: s.diff(t, var or _default_var(v), int(n)))


@command("Integral", ("Integral(<Expression>)", "Integral(<Expression>, <Variable>)",
                      "Integral(<Expression>, <Start>, <End>)", "Integral(<Expression>, <Variable>, <Start>, <End>)"),
         "Antiderivative (without + c) or exact definite integral.", 1, 4)
def integral(v: Any, *rest: Any) -> Any:
    s = sp()
    if len(rest) in (0, 1):
        var = _as_var(rest[0]) if rest else _default_var(v)
        result = _limited(lambda: s.integrate(_expr(v), var), "The integral")
    else:
        var, a, b = (_default_var(v), *rest) if len(rest) == 2 else (_as_var(rest[0]), rest[1], rest[2])
        result = _limited(lambda: s.integrate(_expr(v), (var, a, b)), "The integral")
    return result


@command("Limit", ("Limit(<Expression>, <Value>)", "Limit(<Expression>, <Variable>, <Value>)"), "Exact limit.", 2, 3)
def limit(v: Any, *rest: Any) -> Any:
    return _limit(v, rest, "+-")


@command("LimitAbove", ("LimitAbove(<Expression>, <Value>)",), "Limit from the right.", 2, 3)
def limit_above(v: Any, *rest: Any) -> Any:
    return _limit(v, rest, "+")


@command("LimitBelow", ("LimitBelow(<Expression>, <Value>)",), "Limit from the left.", 2, 3)
def limit_below(v: Any, *rest: Any) -> Any:
    return _limit(v, rest, "-")


def _limit(v: Any, rest: tuple, direction: str) -> Any:
    s = sp()
    var, a = (_default_var(v), rest[0]) if len(rest) == 1 else (_as_var(rest[0]), rest[1])
    kwargs = {"dir": direction} if a not in (s.oo, -s.oo) else {}
    return _limited(lambda: s.limit(v, var, a, **kwargs), "The limit")


@command("Sum", ("Sum(<Expression>, <Variable>, <Start>, <End>)", "Sum(<List>)"), "Exact sum.", 1, 4)
def total(v: Any, *rest: Any) -> Any:
    s = sp()
    if not rest:
        if not isinstance(v, list):
            raise EvalError("Sum(<List>) or Sum(<Expression>, <Variable>, <Start>, <End>).")
        return s.Add(*v)
    if len(rest) != 3:
        raise EvalError("Sum(<Expression>, <Variable>, <Start>, <End>).")
    return _limited(lambda: s.summation(v, (_as_var(rest[0]), rest[1], rest[2])), "The sum")


@command("Product", ("Product(<Expression>, <Variable>, <Start>, <End>)", "Product(<List>)"), "Exact product.", 1, 4)
def product(v: Any, *rest: Any) -> Any:
    s = sp()
    if not rest:
        return s.Mul(*v) if isinstance(v, list) else v
    if len(rest) != 3:
        raise EvalError("Product(<Expression>, <Variable>, <Start>, <End>).")
    return _limited(lambda: s.product(v, (_as_var(rest[0]), rest[1], rest[2])), "The product")


@command("TaylorPolynomial", ("TaylorPolynomial(<Expression>, <x-Value>, <Order>)",
                              "TaylorPolynomial(<Expression>, <Variable>, <x-Value>, <Order>)"),
         "Taylor polynomial.", 3, 4, aliases=("TaylorSeries", "Taylor"))
def taylor(v: Any, *rest: Any) -> Any:
    s = sp()
    var, a, n = (_default_var(v), *rest) if len(rest) == 2 else (_as_var(rest[0]), rest[1], rest[2])
    return _limited(lambda: s.series(v, var, a, int(n) + 1).removeO(), "The Taylor polynomial")


@command("Laplace", ("Laplace(<Function of t>)", "Laplace(<Function>, <Variable>, <Transform Variable>)"),
         "Laplace transform (in s).", 1, 3, aliases=("LaplaceTransform",))
def laplace(v: Any, t: Any = None, s_var: Any = None) -> Any:
    s = sp()
    t = t or (s.Symbol("t") if s.Symbol("t") in _symbols(v) else _default_var(v))
    s_var = s_var or s.Symbol("s")
    return _limited(lambda: s.laplace_transform(v, t, s_var, noconds=True), "The Laplace transform")


@command("InverseLaplace", ("InverseLaplace(<Function of s>)",
                            "InverseLaplace(<Function>, <Variable>, <Transform Variable>)"),
         "Inverse Laplace transform (in t).", 1, 3)
def inverse_laplace(v: Any, s_var: Any = None, t: Any = None) -> Any:
    s = sp()
    s_var = s_var or (s.Symbol("s") if s.Symbol("s") in _symbols(v) else _default_var(v))
    t = t or s.Symbol("t")
    positive = s.Symbol(t.name, positive=True)   # no Heaviside(t) factor for t > 0
    result = _limited(lambda: s.inverse_laplace_transform(v, s_var, positive), "The inverse Laplace transform")
    return result.subs(positive, t)


# ----------------------------------------------------------------------- matrices and vectors

def _matrix(v: Any) -> Any:
    s = sp()
    if isinstance(v, s.MatrixBase):
        return v
    if isinstance(v, list) and v and all(isinstance(r, list) for r in v):
        return s.Matrix(v)
    raise EvalError("This needs a matrix, e.g. {{1, 2}, {3, 4}}.")


@command("Determinant", ("Determinant(<Matrix>)",), "Exact determinant.", 1, 1)
def determinant(m: Any) -> Any:
    return _matrix(m).det()


@command("Invert", ("Invert(<Matrix>)",), "Exact inverse matrix.", 1, 1, aliases=("Inverse",))
def invert(m: Any) -> Any:
    m = _matrix(m)
    if m.det() == 0:
        raise EvalError("The matrix is singular (determinant 0).")
    return m.inv()


@command("Transpose", ("Transpose(<Matrix>)",), "Transposed matrix.", 1, 1)
def transpose(m: Any) -> Any:
    return _matrix(m).T


@command("Eigenvalues", ("Eigenvalues(<Matrix>)",), "Eigenvalues (with repetition).", 1, 1)
def eigenvalues(m: Any) -> list:
    vals = _limited(lambda: _matrix(m).eigenvals(), "Eigenvalues")
    out = []
    for v, k in vals.items():
        out += [v] * k
    return _sorted(out)


@command("Eigenvectors", ("Eigenvectors(<Matrix>)",), "One eigenvector per eigenvalue.", 1, 1)
def eigenvectors(m: Any) -> list:
    triples = _limited(lambda: _matrix(m).eigenvects(), "Eigenvectors")
    out = []
    for _val, _mult, vecs in sorted(triples, key=lambda t: _value_key(t[0])):
        out += [v for v in vecs]
    return out


@command("Rank", ("Rank(<Matrix>)",), "Rank of a matrix.", 1, 1)
def rank(m: Any) -> Any:
    return sp().Integer(_matrix(m).rank())


@command("Dot", ("Dot(<Vector>, <Vector>)",), "Scalar product.", 2, 2)
def dot(u: Any, v: Any) -> Any:
    return sp().Matrix(u).dot(sp().Matrix(v))


@command("Cross", ("Cross(<Vector>, <Vector>)",), "Cross product (3D vectors; in 2D the z-component).", 2, 2)
def cross(u: Any, v: Any) -> Any:
    s = sp()
    u, v = s.Matrix(u), s.Matrix(v)
    if u.shape[0] == 2 and v.shape[0] == 2:
        return u[0] * v[1] - u[1] * v[0]
    return u.cross(v)
