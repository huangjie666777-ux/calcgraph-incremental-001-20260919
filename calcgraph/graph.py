"""In-memory incremental calculation graph (standard library only)."""
from collections.abc import Callable, Mapping


class CycleError(Exception):
    """The active dependency graph contains a cycle."""


class EvaluationError(Exception):
    """A formula failed; the original exception is kept as __cause__."""

    def __init__(self, node: str):
        self.node = node
        super().__init__(f"Formula evaluation failed: {node}")


class Graph:
    def __init__(self) -> None:
        self._inputs: dict[str, int] = {}
        self._formulas: dict[str, Callable] = {}
        self._cache: dict[str, int] = {}
        self._deps: dict[str, set[str]] = {}
        self._dependents: dict[str, set[str]] = {}
        self._evaluating: list[str] = []
        self._stale: set[str] | None = None
        self._done: set[str] | None = None

    @staticmethod
    def _check_name(name) -> None:
        if not isinstance(name, str):
            raise TypeError(f"node name must be str, got {type(name).__name__}")
        if not name:
            raise ValueError("node name must be non-empty")

    @staticmethod
    def _check_value(value) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"node value must be int (not bool), got {type(value).__name__}")

    def add_input(self, name: str, value: int) -> None:
        self._check_name(name)
        if name in self._inputs or name in self._formulas:
            raise ValueError(f"duplicate node name: {name!r}")
        self._check_value(value)
        self._inputs[name] = value

    def _read(self, name: str, deps: set[str]) -> int:
        self._check_name(name)
        if name in self._inputs:
            deps.add(name)
            return self._inputs[name]
        if name in self._formulas:
            deps.add(name)
            if name in self._evaluating:
                raise CycleError(f"cycle detected at node {name!r}")
            if self._stale is not None and name in self._stale and name not in self._done:
                self._recompute(name)
            return self._cache[name]
        raise KeyError(name)

    def _run_formula(self, name: str) -> None:
        if name in self._evaluating:
            raise CycleError(f"cycle detected at node {name!r}")
        self._evaluating.append(name)
        deps: set[str] = set()
        try:
            result = self._formulas[name](lambda n: self._read(n, deps))
        except (CycleError, EvaluationError):
            raise
        except Exception as exc:
            raise EvaluationError(name) from exc
        finally:
            self._evaluating.pop()
        if isinstance(result, bool) or not isinstance(result, int):
            raise EvaluationError(name) from TypeError(
                f"formula {name!r} returned non-int value {result!r}"
            )
        old_deps = self._deps.get(name, set())
        for dep in old_deps - deps:
            self._dependents[dep].discard(name)
        for dep in deps - old_deps:
            self._dependents.setdefault(dep, set()).add(name)
        self._deps[name] = deps
        self._cache[name] = result

    def _recompute(self, name: str) -> None:
        self._done.add(name)
        self._run_formula(name)

    def add_formula(self, name: str, callback: Callable[[Callable[[str], int]], int]) -> None:
        self._check_name(name)
        if name in self._inputs or name in self._formulas:
            raise ValueError(f"duplicate node name: {name!r}")
        if not callable(callback):
            raise TypeError("callback must be callable")
        self._formulas[name] = callback
        try:
            self._run_formula(name)
        except Exception:
            del self._formulas[name]
            self._cache.pop(name, None)
            self._deps.pop(name, None)
            raise

    def get(self, name: str) -> int:
        self._check_name(name)
        if name in self._inputs:
            return self._inputs[name]
        if name in self._formulas:
            return self._cache[name]
        raise KeyError(name)

    def update(self, changes: Mapping[str, int]) -> None:
        if not isinstance(changes, Mapping):
            raise TypeError("changes must be a Mapping")
        for key, value in changes.items():
            self._check_name(key)
            if key in self._formulas:
                raise TypeError(f"cannot update formula node: {key!r}")
            if key not in self._inputs:
                raise KeyError(key)
            self._check_value(value)
        if not changes:
            return
        snapshot = (
            dict(self._inputs),
            dict(self._cache),
            {k: set(v) for k, v in self._deps.items()},
            {k: set(v) for k, v in self._dependents.items()},
        )
        try:
            changed = set()
            for key, value in changes.items():
                if self._inputs[key] != value:
                    self._inputs[key] = value
                    changed.add(key)
            affected: set[str] = set()
            stack = [d for c in changed for d in self._dependents.get(c, ())]
            while stack:
                node = stack.pop()
                if node in affected:
                    continue
                affected.add(node)
                stack.extend(self._dependents.get(node, ()))
            self._stale = affected
            self._done = set()
            pending = [f for c in changed for f in self._dependents.get(c, ())]
            while pending:
                node = pending.pop()
                if node in self._done:
                    continue
                old_value = self._cache[node]
                self._recompute(node)
                if self._cache[node] != old_value:
                    for dependent in self._dependents.get(node, ()):
                        if dependent not in self._done:
                            pending.append(dependent)
        except Exception:
            (self._inputs, self._cache, self._deps, self._dependents) = snapshot
            raise
        finally:
            self._stale = None
            self._done = None

