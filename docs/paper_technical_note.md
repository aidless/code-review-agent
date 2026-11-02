# Paper — CodeAgent Reviewer 技术说明（设计文档）

> 这是一篇**技术设计说明**（非同行评审论文），如实描述 code-review-agent 的真实架构与设计决策。
> 所有结构、参数、阈值均取自仓库真实代码（`agents/`、`graph/`、`tools/`、`tests/`）。

## 1. 问题

自动审查 GitHub Pull Request 需要：拉取 diff → 分析代码质量 → 汇总报告 → 评估报告质量 →
发布到 PR。单一 LLM 调用难以做到「分析出问题可追踪、报告质量可验证、LLM 失败仍可降级」。

## 2. 架构：5-Agent LangGraph 状态机

```
[Fetcher] --diff--> [Analyzer] --问题列表--> [Synthesizer] --报告--> [Reflector] --评分-->
     ^                                                                    |
     |                        needs_replan=True (score<7.0, ≤3 次)         v
     +---------------------------------------------------------------[Notifier] --> PR 评论
```

| Agent | 真实职责 | 文件 |
|---|---|---|
| Fetcher | GitHub API 拉 PR 元数据 + 全文件 diff（分页/限速/缓存） | `agents/fetcher_agent.py` |
| Analyzer | 每文件：AST 静态分析 + LLM 语义分析 | `agents/analyzer_agent.py` |
| Synthesizer | 汇总为 Markdown（必须修复/建议修复/小问题/做得好） | `agents/synthesizer_agent.py` |
| Reflector | 另一 LLM 打分（1-10，四维度），<7 → needs_replan | `agents/reflector_agent.py` |
| Notifier | GitHub API 贴评论 + 返回前端 | `agents/notifier_agent.py` |

**为什么 5 个 Agent 而非一个 LLM 调用**：每个 Agent 只做一件事（问题好定位）；Fetcher 拉完数据后
Analyzer 崩了不用重拉；Reflector 可反复打回；加功能（如安全审查）加一个 Agent 即可。

## 3. 关键设计决策

- **状态机而非手写循环**（LangGraph）：类型化状态 `AgentState`（`graph/state.py`）、条件分支
  （`_should_retry`，`graph/workflow.py:75`）、原生循环、可观测性、断点续传（HITL）。
- **反射式质量门**：Reflector 用**另一个** LLM 调用评估报告，四维度（覆盖面/深度/可操作性/清晰度）
  各 1-10 分；`score < 7.0` → `needs_replan=True` → 退回 Analyzer，**最多 3 次**（`max_reflection_iterations=3`）。
- **few-shot 校准**：给 LLM 看「好报告/差报告」例子校准打分标准；分析与反思用同一模型避免跨模型偏差。
- **降级路径**（fail-closed）：LLM 失败 → `_evaluate_report` 返回保守分（>500 字符→7.0，否则 4.0）；
  整体上「LLM 挂了退回到纯静态 AST 分析，至少抓基础问题」。
- **离线可复现**：15 个单测覆盖纯逻辑（AST + URL 解析），无网络、无 Key。

## 4. 评测方案与成功标准

| 项 | 标准 | 实测 |
|---|---|---|
| URL 解析 | `owner/repo/PR号` 正确提取，非 PR 链接拒绝 | `tests/test_analyzer.py` 4 断言 |
| AST 静态分析 | 行长度/TODO/裸 except/长函数/console.log 识别 + 无效 Python 优雅降级 | 8 断言 |
| 离线上限 | 全部单测通过（`python -m pytest tests/ -q`） | **15 passed** |

## 5. 边界（证明什么 / 不证明什么）

**证明**：
- PR URL 解析器无网络下正确提取并拒绝非 PR 链接。
- AST 静态分析器识别常见问题，并在输入是 diff patch（非完整 Python）时优雅降级不崩溃。
- 15 个离线单测在此树可复算。

**不证明**：
- LLM 审查质量（Analyzer/Reflector/Synthesizer 需 `DEEPSEEK_API_KEY` 与 `GITHUB_TOKEN`，离线未触及）。
- 端到端审查流程（LangGraph 状态机依赖上述 Agent，未在离线测试实例化）。
- 报告是否真的贴回 GitHub PR（notifier 需真实 Token，未测试）。
- 本文是设计说明，**非同行评审**，无外部投稿声明。
