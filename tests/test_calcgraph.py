import unittest

from calcgraph import CycleError, EvaluationError, Graph


class RegistrationTests(unittest.TestCase):
    def test_add_input_and_get(self):
        g = Graph()
        g.add_input("a", 1)
        self.assertEqual(g.get("a"), 1)

    def test_empty_name_raises_value_error(self):
        g = Graph()
        with self.assertRaises(ValueError):
            g.add_input("", 1)
        with self.assertRaises(ValueError):
            g.add_formula("", lambda read: 1)

    def test_non_string_name_raises_type_error(self):
        g = Graph()
        with self.assertRaises(TypeError):
            g.add_input(1, 1)
        with self.assertRaises(TypeError):
            g.add_formula(None, lambda read: 1)
        with self.assertRaises(TypeError):
            g.get(5)

    def test_duplicate_name_raises_value_error(self):
        g = Graph()
        g.add_input("a", 1)
        with self.assertRaises(ValueError):
            g.add_input("a", 2)
        with self.assertRaises(ValueError):
            g.add_formula("a", lambda read: 1)
        g.add_formula("f", lambda read: read("a"))
        with self.assertRaises(ValueError):
            g.add_input("f", 3)

    def test_non_int_value_raises_type_error(self):
        g = Graph()
        for bad in (True, 1.5, "3", None):
            with self.assertRaises(TypeError):
                g.add_input("x", bad)

    def test_non_callable_callback_raises_type_error(self):
        g = Graph()
        with self.assertRaises(TypeError):
            g.add_formula("f", 42)

    def test_missing_node_raises_key_error(self):
        g = Graph()
        with self.assertRaises(KeyError):
            g.get("nope")

    def test_formula_runs_immediately(self):
        g = Graph()
        g.add_input("a", 2)
        g.add_formula("f", lambda read: read("a") * 10)
        self.assertEqual(g.get("f"), 20)

    def test_failed_registration_does_not_keep_name(self):
        g = Graph()
        g.add_input("a", 1)
        with self.assertRaises(EvaluationError):
            g.add_formula("f", lambda read: read("missing"))
        g.add_formula("f", lambda read: read("a") + 1)
        self.assertEqual(g.get("f"), 2)


class UpdateValidationTests(unittest.TestCase):
    def setUp(self):
        self.g = Graph()
        self.g.add_input("a", 1)
        self.g.add_input("b", 2)
        self.g.add_formula("f", lambda read: read("a") + read("b"))

    def test_update_formula_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.g.update({"f": 5})

    def test_update_missing_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.g.update({"nope": 5})

    def test_update_bad_value_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.g.update({"a": True})
        with self.assertRaises(TypeError):
            self.g.update({"a": "x"})

    def test_update_non_mapping_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.g.update([("a", 1)])

    def test_batch_is_validated_before_any_change(self):
        with self.assertRaises(TypeError):
            self.g.update({"a": 10, "b": "bad"})
        self.assertEqual(self.g.get("a"), 1)
        self.assertEqual(self.g.get("f"), 3)

    def test_empty_update_is_noop(self):
        calls = []
        g = Graph()
        g.add_input("a", 1)
        g.add_formula("f", lambda read: calls.append(1) or read("a"))
        calls.clear()
        g.update({})
        self.assertEqual(calls, [])


class IncrementalTests(unittest.TestCase):
    def test_basic_update(self):
        g = Graph()
        g.add_input("width", 3)
        g.add_input("height", 4)
        g.add_formula("area", lambda read: read("width") * read("height"))
        g.update({"width": 5, "height": 6})
        self.assertEqual(g.get("area"), 30)

    def test_same_value_update_does_not_recompute(self):
        calls = []
        g = Graph()
        g.add_input("a", 1)
        g.add_formula("f", lambda read: calls.append(1) or read("a"))
        calls.clear()
        g.update({"a": 1})
        self.assertEqual(calls, [])

    def test_unrelated_formula_not_recomputed(self):
        calls = []
        g = Graph()
        g.add_input("a", 1)
        g.add_input("b", 2)
        g.add_formula("fa", lambda read: read("a"))
        g.add_formula("fb", lambda read: calls.append(1) or read("b"))
        calls.clear()
        g.update({"a": 9})
        self.assertEqual(calls, [])
        self.assertEqual(g.get("fa"), 9)

    def test_repeated_get_does_not_recompute(self):
        calls = []
        g = Graph()
        g.add_input("a", 1)
        g.add_formula("f", lambda read: calls.append(1) or read("a"))
        calls.clear()
        g.get("f")
        g.get("f")
        self.assertEqual(calls, [])

    def test_dynamic_dependency_branch_switch(self):
        g = Graph()
        g.add_input("use_a", 1)
        g.add_input("a", 10)
        g.add_input("b", 20)
        g.add_formula("f", lambda read: read("a") if read("use_a") else read("b"))
        self.assertEqual(g.get("f"), 10)
        g.update({"b": 99})
        self.assertEqual(g.get("f"), 10)  # old branch value, no recompute of b-branch
        g.update({"use_a": 0})
        self.assertEqual(g.get("f"), 99)
        g.update({"a": 50})
        self.assertEqual(g.get("f"), 99)  # a no longer a dependency

    def test_unchanged_result_stops_propagation(self):
        calls = []
        g = Graph()
        g.add_input("a", 2)
        g.add_formula("parity", lambda read: read("a") % 2)
        g.add_formula("downstream", lambda read: calls.append(1) or read("parity") * 100)
        calls.clear()
        g.update({"a": 4})  # parity stays 0
        self.assertEqual(calls, [])
        self.assertEqual(g.get("downstream"), 0)
        g.update({"a": 5})  # parity becomes 1
        self.assertEqual(calls, [1])
        self.assertEqual(g.get("downstream"), 100)

    def test_diamond_runs_each_formula_once(self):
        counts = {"b": 0, "c": 0, "d": 0}
        g = Graph()
        g.add_input("a", 1)
        g.add_formula("b", lambda read: counts.__setitem__("b", counts["b"] + 1) or read("a") + 1)
        g.add_formula("c", lambda read: counts.__setitem__("c", counts["c"] + 1) or read("a") * 2)
        g.add_formula(
            "d",
            lambda read: counts.__setitem__("d", counts["d"] + 1) or read("b") + read("c"),
        )
        counts.update({"b": 0, "c": 0, "d": 0})
        g.update({"a": 2})
        self.assertEqual(counts, {"b": 1, "c": 1, "d": 1})
        self.assertEqual(g.get("d"), 3 + 4)

    def test_late_registered_formula_branch_switch(self):
        g = Graph()
        g.add_input("sel", 0)
        g.add_input("x", 1)
        g.add_formula("f", lambda read: read("x") if read("sel") == 0 else read("g"))
        g.add_input("y", 5)
        g.add_formula("g", lambda read: read("y") * 2)
        g.update({"sel": 1, "y": 7})
        self.assertEqual(g.get("f"), 14)
        g.update({"x": 100})
        self.assertEqual(g.get("f"), 14)

    def test_chain_reads_latest_batch_values(self):
        g = Graph()
        g.add_input("a", 1)
        g.add_formula("b", lambda read: read("a") + 1)
        g.add_formula("c", lambda read: read("b") + read("a"))
        g.update({"a": 10})
        self.assertEqual(g.get("b"), 11)
        self.assertEqual(g.get("c"), 21)


class FailureTests(unittest.TestCase):
    def test_callback_exception_wrapped(self):
        g = Graph()
        g.add_input("a", 1)
        boom = RuntimeError("boom")

        def cb(read):
            raise boom

        with self.assertRaises(EvaluationError) as ctx:
            g.add_formula("f", cb)
        self.assertEqual(ctx.exception.node, "f")
        self.assertIs(ctx.exception.__cause__, boom)

    def test_missing_read_wrapped_with_key_error_cause(self):
        g = Graph()
        with self.assertRaises(EvaluationError) as ctx:
            g.add_formula("f", lambda read: read("ghost"))
        self.assertEqual(ctx.exception.node, "f")
        self.assertIsInstance(ctx.exception.__cause__, KeyError)

    def test_bad_return_value_wrapped(self):
        g = Graph()
        with self.assertRaises(EvaluationError) as ctx:
            g.add_formula("f", lambda read: "nope")
        self.assertEqual(ctx.exception.node, "f")
        self.assertIsInstance(ctx.exception.__cause__, TypeError)
        with self.assertRaises(EvaluationError):
            g.add_formula("g", lambda read: True)

    def test_inner_evaluation_error_not_rewrapped(self):
        g = Graph()
        g.add_input("a", 0)
        seen = []

        def inner(read):
            if read("a") > 0:
                raise RuntimeError("inner failed")
            return 0

        g.add_formula("inner", inner)
        g.add_formula("outer", lambda read: read("inner") + 1)
        try:
            g.update({"a": 1})
        except EvaluationError as exc:
            seen.append(exc)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].node, "inner")
        self.assertIsInstance(seen[0].__cause__, RuntimeError)

    def test_update_failure_rolls_back_everything(self):
        calls = {"n": 0}
        g = Graph()
        g.add_input("a", 1)
        g.add_input("b", 2)
        g.add_formula("f", lambda read: read("a") + read("b"))

        def bad(read):
            calls["n"] += 1
            if read("a") > 5:
                raise RuntimeError("bad batch")
            return read("a") * 2

        g.add_formula("g", bad)
        self.assertEqual(g.get("g"), 2)
        with self.assertRaises(EvaluationError) as ctx:
            g.update({"a": 10, "b": 20})
        self.assertEqual(ctx.exception.node, "g")
        self.assertEqual(g.get("a"), 1)
        self.assertEqual(g.get("b"), 2)
        self.assertEqual(g.get("f"), 3)
        self.assertEqual(g.get("g"), 2)
        # graph still usable afterwards
        g.update({"a": 3})
        self.assertEqual(g.get("f"), 5)
        self.assertEqual(g.get("g"), 6)

    def test_self_cycle_raises_cycle_error(self):
        g = Graph()
        with self.assertRaises(CycleError):
            g.add_formula("f", lambda read: read("f"))
        with self.assertRaises(KeyError):
            g.get("f")

    def test_indirect_cycle_raises_cycle_error(self):
        g = Graph()
        g.add_input("flag", 0)
        g.add_formula("a", lambda read: read("flag") and read("b") or 0)
        g.add_formula("b", lambda read: read("flag") and read("a") or 1)
        self.assertEqual(g.get("a"), 0)
        self.assertEqual(g.get("b"), 1)
        with self.assertRaises(CycleError):
            g.update({"flag": 1})
        # rolled back, still usable
        self.assertEqual(g.get("flag"), 0)
        self.assertEqual(g.get("b"), 1)
        g.update({"flag": 0})
        self.assertEqual(g.get("a"), 0)

    def test_cycle_error_not_wrapped(self):
        g = Graph()
        g.add_input("flag", 0)
        g.add_formula("a", lambda read: read("b") if read("flag") else 0)
        g.add_formula("b", lambda read: read("a") if read("flag") else 1)
        try:
            g.update({"flag": 1})
        except CycleError as exc:
            self.assertNotIsInstance(exc, EvaluationError)
        else:
            self.fail("expected CycleError")


if __name__ == "__main__":
    unittest.main()
