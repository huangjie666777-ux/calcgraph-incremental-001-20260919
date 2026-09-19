# calcgraph

本地工程参数增量计算库的初始接口项目。Python >= 3.10，仅标准库，无需安装依赖。

当前仅有公开 API 和异常定义，计算引擎尚未实现。需求以本次任务提示词为准。

预期实现后：

```python
from calcgraph import Graph

graph = Graph()
graph.add_input("width", 3)
graph.add_input("height", 4)
graph.add_formula("area", lambda read: read("width") * read("height"))
graph.update({"width": 5, "height": 6})
assert graph.get("area") == 30
```

请实现库，补充 `tests/`、`demo.py` 与使用说明。
