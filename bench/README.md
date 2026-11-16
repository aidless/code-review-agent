# Bench — CodeAgent Reviewer 验证基准

> 本目录登记 code-review-agent 的离线检查。全库条数以 `python3 -m pytest tests -q` 为准
> （本树为 **26 passed**，无 token）。其中 `tests/test_analyzer.py` 是 15 条。
> 聊天模型在新增测试里被替换，脚本返回的数字不是审查质量分。
> Streamlit 没有进 pytest。没有真实 PR 评测。

## 基准 1 — `tests/test_analyzer.py`（15 条，只这一文件）

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

- **判读**：这 15 条 = 12 个 `def test_` + 4 个参数化反例减掉被展开的那个函数本身。CR-18 复算的是这个文件，不是全库。
- **全库另外 11 条**在 `tests/test_negative_cases.py`（8）和 `tests/test_offline_pipeline.py`（3），见 `FAILURE_MODES.md`。

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
| 自评分阈值 | 分数 < **7.0** → `needs_replan=True`；7.0 不退回 | `agents/reflector_agent.py` |
| 最大重试 | `max_reflection_iterations = 3`，达到后仍进入 Notifier | `graph/workflow.py` `_should_retry` |
| 提示里的维度 | 覆盖面 / 深度 / 可操作性 / 清晰度（无 few-shot 样例） | `agents/reflector_agent.py` |
| 调用失败 | 报告长于 500 字符 → 7.0，否则 4.0；kind=`heuristic_fallback` | `agents/reflector_agent.py` |

## 复现（离线）

```bash
make check
# 或：python3 -m pytest tests -q    # 本树 26 passed（无 token）

python3 -c "
import sys; sys.path.insert(0,'.')
from tools.github_tool import parse_pr_url
print(parse_pr_url('https://github.com/owner/repo/pull/123'))  # ('owner','repo',123)
"
```

## 门不是 fail-closed

- 自评分 `< 7.0` 且 `reflection_count < 3` 时退回 Analyzer。
- 第 3 次之后进入 Notifier，即使分数仍低于 7。默认 `dry_run`，所以不会因此贴评论；这不是质量拒绝。
- 模型调用失败且报告长于 500 字符时，启发式给出 7.0，门打开。
- Analyzer 的模型调用失败时只保留静态结果。静态结果会漏掉 `tests/fixtures/seeded_empty_mean.py`。
