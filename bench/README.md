# Bench — CodeAgent Reviewer 验证基准

> 本目录登记 code-review-agent 的**真实验证基准**：15 个离线单测 + AST 静态分析器的真实检查项。
> 所有数字都能从仓库树重取（`python -m pytest tests/ -q`，无网络、无 Key）。
> **关键边界**：本仓库**有意不覆盖** Agent 的 LLM 路径、FastAPI 与 Streamlit 服务
> （需要真实 `DEEPSEEK_API_KEY` 与 `GITHUB_TOKEN`）——**不伪造结果**。

## 基准 1 — 离线单测（15 个，`tests/test_analyzer.py`，实测）

| 测试 | 真实断言 | 覆盖项 |
|---|---|---|
| `test_analyzer_finds_line_length` | >120 字符行 → style finding（severity=minor） | `code_analyzer.py` AST |
| `test_analyzer_finds_todo` | TODO 注释 → documentation finding（severity=info） | 同上 |
| `test_analyzer_finds_bare_except` | 裸 `except:` → reliability finding（severity=major） | 同上 |
| `test_analyzer_finds_long_function` | >50 行函数 → complexity finding | 同上 |
| `test_analyzer_handles_invalid_python_gracefully` | 无效 Python → 优雅降级不崩溃（返回 list） | 同上 |
| `test_analyzer_js_console_log` | `console.log` → style finding | 同上 |
| `test_analyzer_generic_fallback` | 通用回退仍标记长行 | 同上 |
| `test_finding_dataclass_fields` | dataclass 字段完整 | 同上 |
| `test_parse_pr_url_basic` | `.../pull/123` → `("owner","repo",123)` | `github_tool.parse_pr_url` |
| `test_parse_pr_url_with_files_suffix` | `.../pull/123/files` → 同上 | 同上 |
| `test_parse_pr_url_with_anchor` | `.../pull/123#issuecomment-99` → 同上 | 同上 |
| `test_parse_pr_url_rejects_non_pr`（4 反例） | 非 PR 链接 → `ValueError` | 同上 |

- **判读**：15 = 12 个 `def test_` + 4 个参数化反例（`test_parse_pr_url_rejects_non_pr`）的实际收集与通过数。
- **边界**：只覆盖**纯逻辑**部分（AST + URL 解析）；LLM 路径、端到端流程、notifier 贴回 GitHub **有意不覆盖**。

## 基准 2 — AST 静态分析检查项（真实，`tools/code_analyzer.py`）

| 检查 | 真实触发 | 严重度 |
|---|---|---|
| 行长度 | 行 > 120 字符 | minor |
| TODO/FIXME/HACK/XXX | 注释含这些标记 | info |
| 裸 except | `except:` 无异常类型 | major |
| 长函数 | 函数 > 50 行 | complexity |
| `console.log/debug` | 生产代码含调试输出 | style |

## 基准 3 — 工作流阈值（真实，`graph/workflow.py` + `agents/reflector_agent.py`）

| 参数 | 真实值 | 位置 |
|---|---|---|
| 报告质量阈值 | 分数 < **7.0** → `needs_replan=True` | `agents/reflector_agent.py:64` |
| 最大重试 | `max_reflection_iterations = 3` | `graph/workflow.py:83` / `graph/state.py:78` |
| 打分维度 | 覆盖面 / 深度 / 可操作性 / 清晰度 | `agents/reflector_agent.py:101-103` |
| LLM 失败降级 | 报告 >500 字符 → 7.0，否则 4.0 | `agents/reflector_agent.py:142` |

## 复现（离线）

```bash
python -m pytest tests/ -q          # 15 passed（无网络无 Key）

# 单点复算：URL 解析
python -c "
import sys; sys.path.insert(0,'.')
from tools.github_tool import parse_pr_url
print(parse_pr_url('https://github.com/owner/repo/pull/123'))  # ('owner','repo',123)
"
```

## Fail-closed（真实代码）

- **Reflector 打分 < 7.0 → 退回 Analyzer 重做**（`needs_replan=True`），最多 3 次——不把低质量报告直接发出去。
- **LLM 失败降级**：`_evaluate_report` 在 LLM 调用失败时返回保守分（7.0/4.0），**不伪造**高质量分。
- **整体降级**：README 明确「如果 LLM 挂了，退回到纯静态分析（AST 检查），至少能抓到基础问题」。
