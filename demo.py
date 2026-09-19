"""Demo: branch switching, atomic batch update, and failure rollback."""
from calcgraph import EvaluationError, Graph


def main() -> None:
    graph = Graph()
    graph.add_input("use_metric", 1)
    graph.add_input("width_cm", 100)
    graph.add_input("width_in", 40)

    graph.add_formula(
        "width",
        lambda read: read("width_cm") if read("use_metric") else read("width_in"),
    )
    graph.add_formula("double_width", lambda read: read("width") * 2)

    print("== branch switching ==")
    print("metric   :", graph.get("width"), graph.get("double_width"))
    graph.update({"use_metric": 0})
    print("imperial :", graph.get("width"), graph.get("double_width"))
    graph.update({"width_cm": 250})  # no longer on the active branch
    print("cm change ignored while imperial:", graph.get("width"))
    graph.update({"use_metric": 1})
    print("back to metric:", graph.get("width"), graph.get("double_width"))

    print("== atomic batch update ==")
    graph.update({"width_cm": 120, "use_metric": 1})
    print("batch ok :", graph.get("width"), graph.get("double_width"))

    print("== failure rolls the batch back ==")
    graph.add_input("limit", 500)

    def guarded(read):
        value = read("width")
        if value > read("limit"):
            raise RuntimeError("width exceeds limit")
        return value

    graph.add_formula("guarded_width", guarded)
    print("guarded  :", graph.get("guarded_width"))
    try:
        graph.update({"width_cm": 600, "limit": 100})
    except EvaluationError as exc:
        print("update failed:", exc, "| cause:", repr(exc.__cause__))
    print("rolled back:", graph.get("width_cm"), graph.get("limit"),
          graph.get("width"), graph.get("guarded_width"))
    graph.update({"width_cm": 200})
    print("graph still works:", graph.get("width"), graph.get("guarded_width"))


if __name__ == "__main__":
    main()

