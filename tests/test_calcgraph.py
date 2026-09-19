import unittest

from calcgraph import CycleError, EvaluationError, Graph


def counter(fn):
    def wrapped(read):
        wrapped.calls += 1
        return fn(read)

    wrapped.calls = 0
    return wrapped


class ValidationTests(unittest.TestCase):
    def test_empty_name_raises_value_error(self):
        g = Graph()
        with self.assertRaises(ValueError):
            g.add_input("", 1)
        with self.assertRaises(ValueError):
            g.add_formula("", lambda read: 1)

    def test_non_str_name_raises_type_error(self):
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

    def test_value_must_be_int_not_bool(self):
        g = Graph()
        for bad in (True, 1.5, "1", None):
            with self.assertRaises(TypeError):
                g.add_input("x", bad)
        g.add_input("x", 1)
        with self.assertRaises(TypeError):
            g.update({"x": False})

    def test_non_callable_callback_raises_type_error(self):
        g = Graph()
        with self.assertRaises(TypeError):
            g.add_formula("f", 42)

    def test_missing_node_key_error(self):
        g = Graph()
        with self.assertRaises(KeyError):
            g.get("nope")
        with self.assertRaises(KeyError):
            g.update({"nope": 1})

    def test_update_formula_raises_type_error(self):
        g = Graph()
        g.add_input("a", 1)
        g.add_formula("f", lambda read: read("a"))
        with self.assertRaises(TypeError):
            g.update({"f": 2})

    def test_update_requires_mapping(self):
        g = Graph()
        with self.assertRaises(TypeError):
            g.update([("a", 1)])

    def test_failed_registration_does_not_keep_name(self):
        g = Graph()
        with self.assertRaises(EvaluationError):
            g.add_formula("bad", lambda read: 1 / 0)
        g.add_input("bad", 7)  # name must be free again
        self.assertEqual(g.get("bad"), 7)
        with self.assertRaises(EvaluationError):
            g.add_formula("bad2", lambda read: "not an int")
        g.add_formula("bad2", lambda read: 3)
        self.assertEqual(g.get("bad2"), 3)

    def test_batch_validated_before_mutation(self):
        g = Graph()
        g.add_input("a", 1)
        g.add_input("b", 2)
        with self.assertRaises(TypeError):
            g.update({"a": 10, "b": "bad"})
        self.assertEqual(g.get("a"), 1)
        self.assertEqual(g.get("b"), 2)


class EvaluationTests(unittest.TestCase):
    def test_basic_compute_and_update(self):
        g = Graph()
        g.add_input("width", 3)
        g.add_input("height", 4)
        g.add_formula("area", lambda read: read("width") * read("height"))
        self.assertEqual(g.get("area"), 12)
        g.update({"width": 5, "height": 6})
        self.assertEqual(g.get("area"), 30)

    def test_formula_reads_formula(self):
        g = Graph()
        g.add_input("a", 2)
        g.add_formula("b", lambda read: read("a") + 1)
        g.add_formula("c", lambda read: read("b") * 10)
        self.assertEqual(g.get("c"), 30)
        g.update({"a": 5})
        self.assertEqual(g.get("c"), 60)

    def test_get_does_not_recompute(self):
        g = Graph()
        g.add_input("a", 1)
        g.add_formula("f", counter(lambda read: read("a")))
        self.assertEqual(g.get("f"), 1)
        g.get("f")
        g.get("f")
        self.assertEqual(g._formulas["f"]["callback"].calls, 1)

    def test_empty_and_same_value_update_skip_work(self):
        g = Graph()
        g.add_input("a", 1)
        g.add_formula("f", counter(lambda read: read("a") * 2))
        g.update({})
        g.update({"a": 1})
        self.assertEqual(g._formulas["f"]["callback"].calls, 1)

    def test_unrelated_formula_not_recomputed(self):
        g = Graph()
        g.add_input("a", 1)
        g.add_input("b", 2)
        g.add_formula("fa", counter(lambda read: read("a")))
        g.add_formula("fb", counter(lambda read: read("b")))
        g.update({"a": 10})
        self.assertEqual(g._formulas["fa"]["callback"].calls, 2)
        self.assertEqual(g._formulas["fb"]["callback"].calls, 1)

    def test_unchanged_result_stops_propagation(self):
        g = Graph()
        g.add_input("a", 1)
        g.add_formula("parity", counter(lambda read: read("a") % 2))
        g.add_formula("down", counter(lambda read: read("parity") * 100))
        g.update({"a": 3})  # parity stays 1
        self.assertEqual(g._formulas["parity"]["callback"].calls, 2)
        self.assertEqual(g._formulas["down"]["callback"].calls, 1)
        self.assertEqual(g.get("down"), 100)

    def test_dynamic_dependency_branch_switch(self):
        g = Graph()
        g.add_input("flag", 1)
        g.add_input("x", 10)
        g.add_input("y", 20)
        g.add_formula("pick", counter(lambda read: read("x") if read("flag") else read("y")))
        self.assertEqual(g.get("pick"), 10)
        g.update({"y": 99})  # y not a dependency yet: no recompute
        self.assertEqual(g._formulas["pick"]["callback"].calls, 1)
        g.update({"flag": 0})
        self.assertEqual(g.get("pick"), 99)
        g.update({"x": 1})  # x no longer a dependency: no recompute
        self.assertEqual(g._formulas["pick"]["callback"].calls, 2)
        g.update({"y": 7})
        self.assertEqual(g.get("pick"), 7)
        self.assertEqual(g._formulas["pick"]["callback"].calls, 3)

    def test_switch_to_later_registered_formula(self):
        g = Graph()
        g.add_input("flag", 1)
        g.add_input("x", 5)
        g.add_formula("pick", lambda read: read("x") if read("flag") else read("late"))
        g.add_input("z", 3)
        g.add_formula("late", counter(lambda read: read("z") * 2))
        self.assertEqual(g.get("pick"), 5)
        g.update({"flag": 0, "z": 4})
        self.assertEqual(g.get("pick"), 8)
        self.assertEqual(g._formulas["late"]["callback"].calls, 2)

    def test_diamond_runs_each_formula_once(self):
        g = Graph()
        g.add_input("a", 1)
        g.add_formula("b", counter(lambda read: read("a") + 1))
        g.add_formula("c", counter(lambda read: read("a") + 2))
        g.add_formula("d", counter(lambda read: read("b") * read("c")))
        g.update({"a": 2})
        for name in ("b", "c", "d"):
            self.assertEqual(g._formulas[name]["callback"].calls, 2)
        self.assertEqual(g.get("d"), 12)

    def test_reads_see_latest_batch_values(self):
        g = Graph()
        g.add_input("a", 1)
        g.add_input("b", 2)
        g.add_formula("total", lambda read: read("a") + read("b"))
        g.update({"a": 10, "b": 20})
        self.assertEqual(g.get("total"), 30)


class FailureTests(unittest.TestCase):
    def test_callback_exception_wrapped(self):
        g = Graph()
        g.add_input("a", 1)
        boom = ValueError("boom")

        def bad(read):
            raise boom

        with self.assertRaises(EvaluationError) as ctx:
            g.add_formula("f", bad)
        self.assertEqual(ctx.exception.node, "f")
        self.assertIs(ctx.exception.__cause__, boom)

    def test_missing_read_wrapped(self):
        g = Graph()
        with self.assertRaises(EvaluationError) as ctx:
            g.add_formula("f", lambda read: read("ghost"))
        self.assertEqual(ctx.exception.node, "f")
        self.assertIsInstance(ctx.exception.__cause__, KeyError)

    def test_bad_return_wrapped(self):
        g = Graph()
        with self.assertRaises(EvaluationError):
            g.add_formula("f", lambda read: True)
        with self.assertRaises(EvaluationError):
            g.add_formula("g", lambda read: "nope")

    def test_existing_errors_not_rewrapped(self):
        g = Graph()
        g.add_input("a", 1)
        err = EvaluationError("inner")

        def raises(read):
            raise err

        with self.assertRaises(EvaluationError) as ctx:
            g.add_formula("f", raises)
        self.assertIs(ctx.exception, err)

    def test_update_failure_rolls_back_everything(self):
        g = Graph()
        g.add_input("a", 1)
        g.add_input("b", 2)
        g.add_formula("fa", lambda read: read("a") * 10)
        state = {"fail": False}

        def maybe_fail(read):
            value = read("fa") + read("b")
            if state["fail"]:
                raise RuntimeError("nope")
            return value

        g.add_formula("victim", maybe_fail)
        self.assertEqual(g.get("victim"), 12)
        state["fail"] = True
        with self.assertRaises(EvaluationError) as ctx:
            g.update({"a": 5, "b": 7})
        self.assertEqual(ctx.exception.node, "victim")
        self.assertEqual(g.get("a"), 1)
        self.assertEqual(g.get("b"), 2)
        self.assertEqual(g.get("fa"), 10)
        self.assertEqual(g.get("victim"), 12)
        state["fail"] = False
        g.update({"a": 5, "b": 7})  # graph still usable afterwards
        self.assertEqual(g.get("fa"), 50)
        self.assertEqual(g.get("victim"), 57)

    def test_failure_does_not_retry(self):
        g = Graph()
        g.add_input("a", 1)
        calls = []

        def bad(read):
            calls.append(1)
            raise RuntimeError("x")

        g.add_formula("f", lambda read: read("a"))
        g._formulas["f"]["callback"] = bad
        with self.assertRaises(EvaluationError):
            g.update({"a": 2})
        self.assertEqual(len(calls), 1)

    def test_cycle_raises_cycle_error(self):
        g = Graph()
        g.add_input("a", 1)
        g.add_formula("f", lambda read: read("a"))
        g.add_formula("g", lambda read: read("f"))
        # Rewire f -> g to form an indirect cycle (not possible via public API).
        g._formulas["f"]["callback"] = lambda read: read("g")
        g._formulas["f"]["deps"] = {"g"}
        g._dependents["g"].add("f")
        with self.assertRaises(CycleError):
            g.update({"a": 2})

    def test_cycle_error_not_rewrapped(self):
        g = Graph()
        g.add_input("a", 1)
        g.add_formula("f", lambda read: read("a"))
        g.add_formula("g", lambda read: read("f"))
        g._formulas["f"]["callback"] = lambda read: read("g")
        g._formulas["f"]["deps"] = {"g"}
        g._dependents["g"].add("f")
        try:
            g.update({"a": 2})
        except CycleError as exc:
            self.assertNotIsInstance(exc, EvaluationError)
        else:
            self.fail("expected CycleError")


if __name__ == "__main__":
    unittest.main()
