# tests/

这个目录**有意留空**——本仓库目前没有自动化测试套件。

## 现在的验证方式

| 入口 | 说明 |
|---|---|
| `api/main.py` | FastAPI 应用主入口，`python api/main.py` 起服务后手动验证各端点 |
| `agents/` | 各 agent（analyzer / fetcher / reflector / synthesizer / notifier）可单独导入运行 |
| `tools/code_analyzer.py` | 代码分析工具，可独立执行 |

## 与 agent-platform 的区别

`agent-platform` 有 `make smoke-offline` / `make gates` 门禁；本仓库体量小得多，
还没有引入等价机制。如果后续要补，建议照搬那边思路：**每个模块一个 `--smoke` 入口**，
而不是直接堆 pytest 用例。

## 需要测试时

测试文件放在这里，命名 `test_*.py`，用 `pytest tests` 运行。
