"""Implement the documented graph contract; no calculation engine exists yet."""
from collections.abc import Callable, Mapping


class CycleError(Exception):
    """The active dependency graph contains a cycle."""


class EvaluationError(Exception):
    """A formula failed; preserve the original exception with `raise ... from`."""

    def __init__(self, node: str):
        self.node = node
        super().__init__(f"Formula evaluation failed: {node}")


class Graph:
    def add_input(self, name: str, value: int) -> None:
        raise NotImplementedError

    def add_formula(self, name: str, callback: Callable[[Callable[[str], int]], int]) -> None:
        raise NotImplementedError

    def get(self, name: str) -> int:
        raise NotImplementedError

    def update(self, changes: Mapping[str, int]) -> None:
        raise NotImplementedError
