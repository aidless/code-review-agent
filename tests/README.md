# tests/

离线测试套件，针对**纯逻辑**部分（不需要 LLM、不需要网络）：

| 文件 | 覆盖 | 数量 |
|---|---|---|
| `test_analyzer.py` | `tools/code_analyzer.py`（AST 静态分析）+ `tools/github_tool.parse_pr_url`（URL 解析） | 15 |

## 运行

```bash
cd code-review-agent
python -m pytest tests/ -q     # 15 passed
```

## 有意不覆盖的部分

- `agents/`（fetcher / analyzer / synthesizer / reflector / notifier）走真实
  LLM 路径，需要 `DEEPSEEK_API_KEY` 与 `GITHUB_TOKEN`，离线测试不伪造。
- `api/main.py`（FastAPI 服务）与 `frontend/app.py`（Streamlit）需要服务进程，
  手动验证，不纳入单测。
- `graph/workflow.py`（LangGraph 编排）依赖上述 LLM Agent，未在离线单测中实例化。

## 与 agent-platform 的区别

`agent-platform` 有 `make smoke-offline` / `make gates` 门禁；本仓库体量较小，
先覆盖纯逻辑。若后续要扩，建议每个模块一个 `--smoke` 入口，而不是堆 pytest。
