# Paper — CodeAgent Reviewer 技术说明（设计文档）

> 这是一篇**技术设计说明**（非同行评审论文），如实描述 code-review-agent 的真实架构与设计决策。
> 所有结构、参数、阈值均取自仓库真实代码（`agents/`、`graph/`、`tools/`、`tests/`）。

## 1. 问题

这个原型把「拉 diff → 静态分析加模型意见 → 写报告 → 模型给报告打自评分 → 可选地发评论」
拆成五个节点。自评分没有外部对照，不能把它写成「报告质量已验证」。

## 2. 架构：5-Agent LangGraph 状态机

```
[Fetcher] --> [Analyzer] --> [Synthesizer] --> [Reflector]
                 ^                                  |
                 |   needs_replan 且 reflection_count < 3
                 +----------------------------------+
                                                    |  否则（含第 3 次仍低于 7）
                                                    v
                                               [Notifier]  默认 dry-run，不贴评论
```

| Agent | 真实职责 | 文件 |
|---|---|---|
| Fetcher | 一次 GET 拉 PR 元数据，一次 GET 拉文件列表（无分页循环、无限速缓存） | `agents/fetcher_agent.py` |
| Analyzer | 每文件：AST 静态分析 + 聊天模型；模型只看 diff 前 200 行 | `agents/analyzer_agent.py` |
| Synthesizer | 把问题列表交给聊天模型写成 Markdown；模型失败时用本地模板 | `agents/synthesizer_agent.py` |
| Reflector | 聊天模型给这份报告打自评分；`< 7` → needs_replan。不是校验过的质量分 | `agents/reflector_agent.py` |
| Notifier | `dry_run`（默认）不发请求；显式关闭且 token 存在时才 POST 评论 | `agents/notifier_agent.py` |

**为什么 5 个 Agent 而非一个 LLM 调用**：每个 Agent 只做一件事（问题好定位）；Fetcher 拉完数据后
Analyzer 崩了不用重拉；Reflector 可反复打回；加功能（如安全审查）加一个 Agent 即可。

## 3. 关键设计决策

- **状态机**（LangGraph）：类型化状态 `AgentState`（`graph/state.py`）和条件边 `_should_retry`。
  没有配置 LangSmith，也没有 Human-in-the-Loop 断点。
- **自评分**：Reflector 用同系列的 `deepseek-chat` 给报告打分。提示词列出覆盖面、深度、可操作性、清晰度，
  没有好报告/差报告样例。`score < 7.0` 才 `needs_replan`。`reflection_count` 到 3 后进入 Notifier。
- **调用失败**：Reflector 用字符数启发式（长于 500 字符 → 7.0，否则 4.0）。7.0 打开门。
  Analyzer 的模型调用失败时只留下静态结果，静态结果本身会漏报（见 `FAILURE_MODES.md`）。
- **离线复现**：`make check`。本树 `pytest tests -q` 为 26 passed。`test_analyzer.py` 单独是 15 条。

## 4. 评测方案与成功标准

| 项 | 标准 | 实测 |
|---|---|---|
| URL 解析 | `owner/repo/PR号` 正确提取，非 PR 链接拒绝 | `tests/test_analyzer.py` 4 断言 |
| AST 静态分析 | 行长度/TODO/裸 except/长函数/console.log 识别 + 无效 Python 优雅降级 | 8 断言 |
| 离线上限 | `python3 -m pytest tests -q` 全部通过 | **26 passed**（其中 `test_analyzer.py` 15 条） |

## 5. 边界（证明什么 / 不证明什么）

**证明**：
- PR URL 解析器无网络下正确提取并拒绝非 PR 链接。
- AST 静态分析器识别它实现了的检查，并在输入不是合法 Python 时不崩溃。
- mock 掉 GitHub 与聊天客户端后，图能跑完重试环，且 dry-run 不 POST。
- 26 条离线 pytest 在此树可复算。

**不证明**：
- 模型自评分是审查质量。
- 真实 PR 上的效果，或曾经有一条评论被贴回 GitHub。live POST 测试替换了 `requests.post`。
- 本文是设计说明，**非同行评审**，无外部投稿声明。没有 PyPI 包。
