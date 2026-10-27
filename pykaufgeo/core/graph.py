"""Graph helpers for the construction DAG."""

from __future__ import annotations

import heapq
from typing import Iterable, Mapping

from pykaufgeo.core.errors import CycleError


def descendants(start: Iterable[str], children: Mapping[str, set[str]]) -> set[str]:
    """All nodes reachable from ``start`` (excluding the start nodes themselves)."""
    seen: set[str] = set()
    stack = list(start)
    starts = set(stack)
    while stack:
        n = stack.pop()
        for c in children.get(n, ()):
            if c not in seen:
                seen.add(c)
                stack.append(c)
    return seen - starts


def find_path(src: str, dst: str, children: Mapping[str, set[str]]) -> list[str] | None:
    """A dependency path src -> ... -> dst, used in cycle error messages."""
    prev: dict[str, str] = {}
    stack = [src]
    seen = {src}
    while stack:
        n = stack.pop()
        if n == dst:
            path = [n]
            while path[-1] != src:
                path.append(prev[path[-1]])
            return path[::-1]
        for c in sorted(children.get(n, ())):
            if c not in seen:
                seen.add(c)
                prev[c] = n
                stack.append(c)
    return None


def stable_topo_sort(order: list[str], parents: Mapping[str, Iterable[str]]) -> list[str]:
    """Topological order that keeps the existing order wherever the DAG allows."""
    pos = {n: i for i, n in enumerate(order)}
    indeg = {n: 0 for n in order}
    kids: dict[str, list[str]] = {n: [] for n in order}
    for n in order:
        for p in parents.get(n, ()):
            if p in indeg:
                indeg[n] += 1
                kids[p].append(n)
    heap = [(pos[n], n) for n in order if indeg[n] == 0]
    heapq.heapify(heap)
    out: list[str] = []
    while heap:
        _, n = heapq.heappop(heap)
        out.append(n)
        for c in kids[n]:
            indeg[c] -= 1
            if indeg[c] == 0:
                heapq.heappush(heap, (pos[c], c))
    if len(out) != len(order):
        stuck = sorted(n for n in order if indeg[n] > 0)
        raise CycleError(f"Circular dependency among: {', '.join(stuck)}")
    return out
