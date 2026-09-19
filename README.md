# calcgraph

基于 Python 标准库的内存增量计算库（Python >= 3.10，无第三方依赖）。

## 功能

- `add_input(name, value)` 注册输入节点；`add_formula(name, callback)` 注册公式节点并立即执行 `callback(read)`。
- `get(name)` 读取缓存值，不会触发重算；`update({name: value, ...})` 批量更新输入，返回前完成增量重算。
- 动态依赖：按公式本次 `read` 实际读取的节点维护依赖，分支切换后旧分支不再触发重算。
- 增量传播：空更新、同值更新、无关公式均不重算；公式结果不变时停止向下游传播；每次 `update` 中每个公式最多执行一次（含菱形依赖）。
- 原子性：整批校验通过后才修改；计算失败回滚整批输入、缓存与依赖，并传播异常。
- 异常：`CycleError`（自引用/间接循环）、`EvaluationError`（回调异常、读取缺失节点、非法返回值；`node` 为出错公式名，`__cause__` 保留原异常）。

## 校验规则

- 名称必须为非空字符串：空名抛 `ValueError`，非字符串抛 `TypeError`，重名抛 `ValueError`。
- 输入与公式结果必须为 `int` 且非 `bool`，否则抛 `TypeError`（公式内转为 `EvaluationError`）。
- 直接读写缺失节点抛 `KeyError`；`update` 修改公式节点抛 `TypeError`。
- 注册失败的公式不占用名称。

## 示例

```python
from calcgraph import Graph

graph = Graph()
graph.add_input("width", 3)
graph.add_input("height", 4)
graph.add_formula("area", lambda read: read("width") * read("height"))
graph.update({"width": 5, "height": 6})
assert graph.get("area") == 30
```

## 运行 demo

```bash
python3 demo.py
```

展示分支切换、批量原子更新与失败回滚。

## 运行测试

```bash
python3 -m unittest discover -s tests -v
```

