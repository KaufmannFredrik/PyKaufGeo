"""AST -> LaTeX, restricted to the subset matplotlib mathtext can render.

mathtext has no ``matrix``/``array`` environments and no ``\\text``; text uses
``\\mathrm`` with escaped spaces. Division is shown as ``\\frac``, powers as
superscripts, roots as ``\\sqrt``, absolute value with ``\\left| \\right|``.
"""

from __future__ import annotations

import re

from pykaufgeo.parser.ast import (
    Abs,
    Apply,
    Binary,
    BoolLit,
    Call,
    Compare,
    Equation,
    Ident,
    ListNode,
    Node,
    Num,
    Postfix,
    Str,
    TupleNode,
    Unary,
    UndefLit,
)
from pykaufgeo.parser.unparse import PREC_BINARY, _simple_fraction, precedence

GREEK = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "ε": r"\epsilon", "ζ": r"\zeta",
    "η": r"\eta", "θ": r"\theta", "ι": r"\iota", "κ": r"\kappa", "λ": r"\lambda", "μ": r"\mu",
    "ν": r"\nu", "ξ": r"\xi", "ο": "o", "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau",
    "υ": r"\upsilon", "φ": r"\phi", "χ": r"\chi", "ψ": r"\psi", "ω": r"\omega",
    "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta", "Λ": r"\Lambda", "Π": r"\Pi", "Σ": r"\Sigma",
    "Φ": r"\Phi", "Ψ": r"\Psi", "Ω": r"\Omega",
}
NAMED_FUNCS = {"sin", "cos", "tan", "cot", "sec", "csc", "sinh", "cosh", "tanh", "coth", "exp", "ln", "log",
               "arcsin", "arccos", "arctan", "lg"}
CMP = {"<": "<", ">": ">", "<=": r"\leq", ">=": r"\geq", "==": r"\stackrel{?}{=}", "!=": r"\neq"}
LOGIC = {"and": r"\wedge", "or": r"\vee", "xor": r"\oplus", "cross": r"\times", "in": r"\in"}
CONSTANTS = {"pi": r"\pi", "π": r"\pi", "∞": r"\infty", "infinity": r"\infty", "ℯ": "e", "ί": "i"}
_SPECIAL = re.compile(r"([\\{}$&#^_%~])")


def escape_text(text: str) -> str:
    """Plain text inside ``\\mathrm{}`` (spaces kept, specials escaped)."""
    out = _SPECIAL.sub(lambda m: "\\" + m.group(1) if m.group(1) not in "\\^~" else " ", text)
    return r"\mathrm{" + out.replace(" ", r"\ ") + "}"


def latex_name(name: str) -> str:
    """``A_1`` -> ``A_{1}``, ``α`` -> ``\\alpha``, ``text1`` -> ``\\mathrm{text1}``, primes kept."""
    primes = len(name) - len(name.rstrip("'"))
    base = name.rstrip("'")
    sub = ""
    if "_" in base:
        base, sub = base.split("_", 1)
        sub = sub.strip("{}")
    if base in CONSTANTS:
        body = CONSTANTS[base]
    elif base in GREEK:
        body = GREEK[base]
    elif len(base) > 1:
        body = r"\mathrm{" + base + "}"
    else:
        body = base
    if sub:
        sub_tex = sub if len(sub) == 1 else (r"\mathrm{" + sub + "}" if sub.isalpha() else sub)
        body += "_{" + sub_tex + "}"
    return body + "'" * primes


def _tall(content: str) -> bool:
    return "\\frac" in content or "\\sqrt" in content


def paren(content: str, left: str = "(", right: str = ")") -> str:
    """Brackets that grow only around tall content (mathtext shrinks \\left( around plain text)."""
    if _tall(content):
        return "\\left" + left + content + "\\right" + right
    return left + content + right


def neg_number(text: str) -> str:
    """Braces keep a leading minus unary in mathtext: ``(4, {-1})`` not ``(4, - 1)``."""
    return "{" + text + "}" if text.startswith("-") else text


def to_latex(node: Node, decimals: int = 2) -> str:
    return _Latex(decimals).p(node)


class _Latex:
    def __init__(self, decimals: int) -> None:
        self.decimals = decimals

    def num(self, node: Num) -> str:
        from pykaufgeo.core.format import format_complex, format_number

        from pykaufgeo.parser.unparse import exact_digits

        if isinstance(node.value, complex):
            return neg_number(format_complex(node.value, self.decimals).replace("∞", r"\infty"))
        exact = exact_digits(node.text, self.decimals)
        if exact is not None:
            return exact
        return neg_number(format_number(float(node.value), self.decimals).replace("∞", r"\infty"))

    def wrap(self, child: Node, need: bool) -> str:
        s = self.p(child)
        return paren(s) if need else s

    def args(self, args: tuple[Node, ...]) -> str:
        return paren(", ".join(self.p(a) for a in args))

    def p(self, node: Node) -> str:  # noqa: C901 - dispatch
        if isinstance(node, Num):
            return self.num(node)
        if isinstance(node, Str):
            return escape_text('"' + node.value + '"')
        if isinstance(node, BoolLit):
            return r"\mathrm{true}" if node.value else r"\mathrm{false}"
        if isinstance(node, UndefLit):
            return "?"
        if isinstance(node, Ident):
            return latex_name(node.name)
        if isinstance(node, Unary):
            if node.op == "not":
                return r"\neg " + self.wrap(node.operand, precedence(node.operand) < 40)
            inner = node.operand
            need = precedence(inner) < 70 or (isinstance(inner, Num) and precedence(inner) == 70)
            return "{" + node.op + self.wrap(inner, need) + "}"
        if isinstance(node, Postfix):
            base = self.wrap(node.operand, precedence(node.operand) < 90)
            return base + {"!": "!", "°": r"^{\circ}", "%": r"\%"}[node.op]
        if isinstance(node, Binary):
            return self.binary(node)
        if isinstance(node, Compare):
            parts = [self.wrap(node.operands[0], precedence(node.operands[0]) <= 40)]
            for op, operand in zip(node.ops, node.operands[1:]):
                parts.append(f" {CMP[op]} " + self.wrap(operand, precedence(operand) <= 40))
            return "".join(parts)
        if isinstance(node, Equation):
            return f"{self.p(node.lhs)} = {self.p(node.rhs)}"
        if isinstance(node, Call):
            return self.call(node)
        if isinstance(node, Apply):
            callee = self.wrap(node.func, not isinstance(node.func, (Ident, Call, Apply)))
            return callee + self.args(node.args)
        if isinstance(node, TupleNode):
            sep = "; " if node.polar else ", "
            return paren(sep.join(self.p(i) for i in node.items))
        if isinstance(node, ListNode):
            return paren(", ".join(self.p(i) for i in node.items), "\\{", "\\}")
        if isinstance(node, Abs):
            return paren(self.p(node.operand), "|", "|")
        raise TypeError(f"cannot render {node!r}")

    def call(self, node: Call) -> str:
        from pykaufgeo.engine.resolver import prime_name

        primed = prime_name(node)
        if primed is not None:
            return primed
        name, args = node.name, node.args
        if name == "sqrt" and len(args) == 1:
            return r"\sqrt{" + self.p(args[0]) + "}"
        if name == "cbrt" and len(args) == 1:
            return r"\sqrt[3]{" + self.p(args[0]) + "}"
        if name == "nroot" and len(args) == 2:
            return r"\sqrt[" + self.p(args[1]) + "]{" + self.p(args[0]) + "}"
        if name == "abs" and len(args) == 1:
            return paren(self.p(args[0]), "|", "|")
        head = "\\" + name if name in NAMED_FUNCS else r"\mathrm{" + name + "}"
        return head + self.args(args)

    def binary(self, node: Binary) -> str:
        op = node.op
        prec = PREC_BINARY[op]
        lp, rp = precedence(node.left), precedence(node.right)
        if op == "/":
            if isinstance(node.left, Unary) and node.left.op == "-":   # -1/2 as -\frac{1}{2}
                return r"-\frac{" + self.p(node.left.operand) + "}{" + self.p(node.right) + "}"
            return r"\frac{" + self.p(node.left) + "}{" + self.p(node.right) + "}"
        if op == "^":
            left = self.wrap(node.left, lp <= prec or isinstance(node.left, Binary) and node.left.op == "/")
            frac = _simple_fraction(node.right)
            right = (r"\frac{" + frac.replace("/", "}{") + "}") if frac else self.p(node.right)
            return left + "^{" + right + "}"
        left = self.wrap(node.left, lp < prec)
        assoc = op == "+" or (op == "*" and isinstance(node.right, Binary) and node.right.op in ("*", "/"))
        right = self.wrap(node.right, rp < prec if assoc else rp <= prec)
        if op == "*":
            if self._juxtapose(node.left, node.right, right):
                return left + (" " if left[-1:].isalpha() and right[:1].isalpha() else "") + right
            return left + r" \cdot " + right
        sym = LOGIC.get(op, op)
        return f"{left} {sym} {right}"

    @staticmethod
    def _juxtapose(left: Node, right: Node, right_text: str) -> bool:
        if isinstance(right, Num) or right_text.startswith("-"):
            return False
        if isinstance(left, Num):
            return not (isinstance(right, Binary) and right.op == "*" and isinstance(right.left, Num))
        return isinstance(left, (Ident, Binary, Postfix, Abs, Call, Apply)) and \
            isinstance(right, (Ident, Call, Apply, Abs, Binary))
