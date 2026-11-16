# tests/

离线套件。不需要 `GITHUB_TOKEN`，不需要模型 key，不访问 GitHub 或模型 API。
`tests/conftest.py` 会拦住发往 `api.github.com`、`api.deepseek.com`、`api.openai.com` 的 `requests` / `httpx` 调用。

| 文件 | 覆盖 | 条数（pytest 收集） |
|---|---|---|
| `test_analyzer.py` | `CodeAnalyzer` 与 `parse_pr_url` | 15 |
| `test_negative_cases.py` | AST 漏报、单次 GET、截断、启发式边界、dry-run、缺 token、mock 下的 POST | 8 |
| `test_offline_pipeline.py` | 自评分 `< 7` 的重试环（最多 3 次）、API 默认 dry-run | 3 |

合计 **26**。以 `python3 -m pytest tests -q` 的输出为准。`test_analyzer.py` 的 15 条不是全库条数。

## 运行

```bash
make check
```

聊天模型在这些测试里被替换成脚本。脚本返回的 4.0 或 8.0 是测试输入，不是审查质量分。
Reflector 在真实运行时产出的数字是模型自评分，见 `FAILURE_MODES.md`。

## 有意不覆盖

- Streamlit 页面（`frontend/app.py`）没有进 pytest。
- 没有任何一条测试对真实 PR 打过分或贴过评论。
