"""In-memory incremental calculation graph (standard library only)."""
from collections.abc import Callable, Mapping


class CycleError(Exception):
    """The active dependency graph contains a cycle."""


class EvaluationError(Exception):
    """A formula failed; preserve the original exception with `raise ... from`."""

    def __init__(self, node: str):
        self.node = node
        super().__init__(f"Formula evaluation failed: {node}")


class Graph:
    def __init__(self) -> None:
        self._inputs: dict[str, int] = {}
        self._formulas: dict[str, dict] = {}
        self._dependents: dict[str, set[str]] = {}
        # Runtime state for the update currently being evaluated, else None.
        self._rt: tuple[dict, set, set, set] | None = None

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

    def _check_new_name(self, name) -> None:
        self._check_name(name)
        if name in self._inputs or name in self._formulas:
            raise ValueError(f"duplicate node name: {name!r}")

    def _read(self, deps: set[str], name: str) -> int:
        deps.add(name)
        if name in self._inputs:
            return self._inputs[name]
        if name in self._formulas:
            rt = self._rt
            if rt is not None:
                memo, affected, changed_inputs, stack = rt
                if name in stack:
                    raise CycleError(f"cycle detected at node {name!r}")
                self._compute(name, memo, affected, changed_inputs, stack)
            return self._formulas[name]["value"]
        raise KeyError(name)

    def _compute(self, name, memo, affected, changed_inputs, stack) -> None:
        if name in memo:
            return
        if name in stack:
            raise CycleError(f"cycle detected at node {name!r}")
        formula = self._formulas[name]
        if name not in affected:
            memo[name] = False
            return
        stack.add(name)
        try:
            dep_changed = False
            for dep in formula["deps"]:
                if dep in self._formulas:
                    self._compute(dep, memo, affected, changed_inputs, stack)
                    if memo[dep]:
                        dep_changed = True
                elif dep in changed_inputs:
                    dep_changed = True
            if not dep_changed:
                memo[name] = False
                return
            new_deps: set[str] = set()

            def reader(node: str) -> int:
                return self._read(new_deps, node)

            try:
                value = formula["callback"](reader)
            except (EvaluationError, CycleError):
                raise
            except Exception as exc:
                raise EvaluationError(name) from exc
            if isinstance(value, bool) or not isinstance(value, int):
                raise EvaluationError(name) from TypeError(
                    f"formula {name!r} returned non-int value {value!r}"
                )
            for old in formula["deps"] - new_deps:
                self._dependents[old].discard(name)
            for new in new_deps - formula["deps"]:
                self._dependents[new].add(name)
            formula["deps"] = new_deps
            changed = value != formula["value"]
            formula["value"] = value
            memo[name] = changed
        finally:
            stack.discard(name)

    def add_input(self, name: str, value: int) -> None:
        self._check_new_name(name)
        self._check_value(value)
        self._inputs[name] = value
        self._dependents[name] = set()

    def add_formula(self, name: str, callback: Callable[[Callable[[str], int]], int]) -> None:
        self._check_new_name(name)
        if not callable(callback):
            raise TypeError("callback must be callable")
        deps: set[str] = set()

        def reader(node: str) -> int:
            return self._read(deps, node)

        try:
            value = callback(reader)
        except (EvaluationError, CycleError):
            raise
        except Exception as exc:
            raise EvaluationError(name) from exc
        if isinstance(value, bool) or not isinstance(value, int):
            raise EvaluationError(name) from TypeError(
                f"formula {name!r} returned non-int value {value!r}"
            )
        self._formulas[name] = {"callback": callback, "value": value, "deps": deps}
        self._dependents[name] = set()
        for dep in deps:
            self._dependents[dep].add(name)

    def get(self, name: str) -> int:
        self._check_name(name)
        if name in self._inputs:
            return self._inputs[name]
        if name in self._formulas:
            return self._formulas[name]["value"]
        raise KeyError(name)

    def update(self, changes: Mapping[str, int]) -> None:
        if not isinstance(changes, Mapping):
            raise TypeError("changes must be a Mapping of input names to int values")
        items = list(changes.items())
        for key, value in items:  # validate the whole batch before mutating
            self._check_name(key)
            if key in self._formulas:
                raise TypeError(f"cannot update formula node: {key!r}")
            if key not in self._inputs:
                raise KeyError(key)
            self._check_value(value)
        changed_inputs = {k for k, v in items if self._inputs[k] != v}
        if not changed_inputs:
            return
        saved_inputs = dict(self._inputs)
        saved_formulas = {
            n: (f["value"], set(f["deps"])) for n, f in self._formulas.items()
        }
        saved_dependents = {n: set(d) for n, d in self._dependents.items()}
        try:
            for key in changed_inputs:
                self._inputs[key] = changes[key]
            affected: set[str] = set()
            queue = [d for k in changed_inputs for d in self._dependents[k]]
            while queue:
                node = queue.pop()
                if node in affected:
                    continue
                affected.add(node)
                queue.extend(self._dependents[node])
            memo: dict[str, bool] = {}
            self._rt = (memo, affected, changed_inputs, set())
            try:
                for name in list(affected):
                    self._compute(name, memo, affected, changed_inputs, self._rt[3])
            finally:
                self._rt = None
        except BaseException:
            self._inputs = saved_inputs
            for n, (value, deps) in saved_formulas.items():
                self._formulas[n]["value"] = value
                self._formulas[n]["deps"] = deps
            self._dependents = saved_dependents
            raise
