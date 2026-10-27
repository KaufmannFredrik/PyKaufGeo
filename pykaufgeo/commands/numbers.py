"""Numbers and algebra: GCD, LCM, Min, Max, Mod, Div, random numbers."""

from __future__ import annotations

import math
from functools import reduce

from pykaufgeo.commands.registry import Command, register, sig
from pykaufgeo.core.types import GeoType
from pykaufgeo.core.values import ListValue, Undef, is_real

N = GeoType.NUMBER
CAT = "Numbers and algebra"


def _ints(items: ListValue) -> list[int]:
    out = []
    for v in items.items:
        if not is_real(v) or not math.isfinite(v) or float(v) != int(v):
            raise ValueError("GCD/LCM need whole numbers")
        out.append(int(v))
    return out


def _numbers(items: ListValue) -> list[float]:
    vals = []
    for v in items.items:
        if not is_real(v):
            raise ValueError("list must contain numbers")
        vals.append(float(v))
    return vals


@register
class GCD(Command):
    category = CAT
    description = "Greatest common divisor of whole numbers."
    examples = ("GCD(12, 18)  ->  6", "GCD({12, 18, 30})  ->  6")

    @sig("<Integer>", "<Integer>", returns=N)
    def two(self, call, a: int, b: int) -> float:
        return float(math.gcd(a, b))

    @sig("<List>", returns=N)
    def of_list(self, call, items: ListValue) -> float:
        return float(reduce(math.gcd, _ints(items), 0))


@register
class LCM(Command):
    category = CAT
    description = "Least common multiple of whole numbers."
    examples = ("LCM(4, 6)  ->  12",)

    @sig("<Integer>", "<Integer>", returns=N)
    def two(self, call, a: int, b: int) -> float:
        return float(abs(a * b) // math.gcd(a, b)) if a and b else 0.0

    @sig("<List>", returns=N)
    def of_list(self, call, items: ListValue) -> float:
        return float(reduce(lambda a, b: abs(a * b) // math.gcd(a, b) if a and b else 0, _ints(items), 1))


@register
class Min(Command):
    category = CAT
    description = "Smaller of two numbers, or the minimum of a list."
    examples = ("Min(3, 5)  ->  3", "Min({4, 1, 7})  ->  1", "f(x) = Min(x, 2)")
    pointwise = True

    @sig("<Number>", "<Number>", returns=N)
    def two(self, call, a: float, b: float) -> float:
        return a if a <= b else b

    @sig("<List>", returns=N)
    def of_list(self, call, items: ListValue):
        vals = _numbers(items)
        return min(vals) if vals else Undef(N)


@register
class Max(Command):
    category = CAT
    description = "Larger of two numbers, or the maximum of a list."
    examples = ("Max(3, 5)  ->  5", "Max({4, 1, 7})  ->  7")
    pointwise = True

    @sig("<Number>", "<Number>", returns=N)
    def two(self, call, a: float, b: float) -> float:
        return a if a >= b else b

    @sig("<List>", returns=N)
    def of_list(self, call, items: ListValue):
        vals = _numbers(items)
        return max(vals) if vals else Undef(N)


@register
class Mod(Command):
    category = CAT
    description = "Remainder of a divided by b (same sign as b)."
    examples = ("Mod(17, 5)  ->  2", "Mod(-7, 3)  ->  2")
    pointwise = True

    @sig("<Dividend:Number>", "<Divisor:Number>", returns=N)
    def mod(self, call, a: float, b: float) -> float:
        if b == 0:
            return math.nan
        return float(a % b)


@register
class Div(Command):
    category = CAT
    description = "Integer quotient: floor(a / b)."
    examples = ("Div(17, 5)  ->  3",)
    pointwise = True

    @sig("<Dividend:Number>", "<Divisor:Number>", returns=N)
    def div(self, call, a: float, b: float) -> float:
        if b == 0:
            return math.nan
        return float(math.floor(a / b))


@register
class RandomBetween(Command):
    category = CAT
    description = "Random whole number between min and max (inclusive). Kept until UpdateConstruction."
    examples = ("RandomBetween(1, 6)",)
    random = True

    @sig("<Min:Integer>", "<Max:Integer>", returns=N)
    def between(self, call, a: int, b: int) -> float:
        lo, hi = min(a, b), max(a, b)
        return float(call.random(lambda rng: float(rng.randint(lo, hi))))


@register
class RandomUniform(Command):
    category = CAT
    description = "Random real number, uniformly distributed between min and max."
    examples = ("RandomUniform(0, 1)",)
    random = True

    @sig("<Min:Number>", "<Max:Number>", returns=N)
    def uniform(self, call, a: float, b: float) -> float:
        return float(call.random(lambda rng: rng.uniform(a, b)))


@register
class Random(Command):
    category = CAT
    description = "random(): random real number in [0, 1)."
    examples = ("random()",)
    random = True

    @sig(returns=N)
    def unit(self, call) -> float:
        return float(call.random(lambda rng: rng.random()))
