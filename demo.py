"""Demo: branch switching, atomic batch updates, and failure rollback."""
from calcgraph import EvaluationError, Graph


def main() -> None:
    graph = Graph()
    graph.add_input("mode", 1)
    graph.add_input("price", 100)
    graph.add_input("discount", 10)

    # Dynamic dependencies: the formula reads different inputs per branch.
    graph.add_formula(
        "total",
        lambda read: read("price") - read("discount") if read("mode") else read("price"),
    )
    print("initial total:", graph.get("total"))  # 90

    # Branch switch: now 'discount' is no longer tracked, 'mode' path changes.
    graph.update({"mode": 0})
    print("after mode=0:", graph.get("total"))  # 100

    # Atomic batch success: both inputs change together.
    graph.update({"mode": 1, "price": 200, "discount": 25})
    print("after batch update:", graph.get("total"))  # 175

    # Failure rollback: a bad formula aborts the batch and restores state.
    graph.add_input("ratio", 2)

    def flaky(read):
        value = read("total") // read("ratio")
        if read("ratio") == 0:
            raise ZeroDivisionError("ratio must not be zero")
        return value

    graph.add_formula("safe", flaky)
    print("safe:", graph.get("safe"))  # 87
    try:
        graph.update({"price": 500, "ratio": 0})
    except EvaluationError as exc:
        print("update failed:", exc, "| node:", exc.node, "| cause:", repr(exc.__cause__))
    print("rolled back total:", graph.get("total"))  # still 175
    print("rolled back ratio:", graph.get("ratio"))  # still 2

    # The graph keeps working after a failed batch.
    graph.update({"ratio": 5})
    print("after recovery:", graph.get("safe"))  # 35


if __name__ == "__main__":
    main()
