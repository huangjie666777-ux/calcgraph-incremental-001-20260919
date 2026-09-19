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

## 实现说明

计算引擎已实现，要点：

- **动态依赖**：按公式本次 `read` 实际读取的节点更新依赖边，分支切换后旧分支依赖被移除。
- **增量重算**：`update` 只重算受变更输入影响的公式；空更新、同值输入、无关公式不触发计算；公式结果不变时停止向下游传播；每批中每个公式最多执行一次（菱形依赖安全），连续 `get` 只读缓存。
- **原子批量**：整批先校验再修改；任一公式失败时回滚本批输入、缓存与依赖边，异常向外传播且不重试，之后图仍可正常使用。
- **异常**：回调抛普通异常、读取缺失节点或返回非 int 值会包装为 `EvaluationError`（`node` 为出错公式名，`__cause__` 保留原异常）；已有 `EvaluationError`/`CycleError` 原样传播；循环依赖抛 `CycleError`。

## 运行测试

```bash
python3 -m unittest discover -s tests -v
```

## 运行示例

```bash
python3 demo.py
```

展示分支切换（动态依赖）、批量原子更新与失败回滚。
