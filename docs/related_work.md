# Related Work — 自动代码审查 Agent 的先行对照

> 本文件把 code-review-agent 与**真实存在的先行工作**对照，说明借鉴了什么、相对什么有增量。
> 所有引用均为真实开源框架/工具/产品，未虚构。

## 1. 编排框架

| 先行 | 真实内容 | 与本仓库的关系 |
|---|---|---|
| **LangGraph**（LangChain 官方） | 有状态图编排：类型化状态、条件分支、原生循环、可观测性、断点续传 | **借鉴**：本仓库用它定义 5-Agent 工作流（`graph/workflow.py`），Reflector→Analyzer 重试循环、HITL 暂停都靠它 |
| **LangSmith** | 追踪每个节点的输入/输出 | **借鉴**：可观测性（README 技术细节） |

## 2. 自动代码审查（LLM Agent）

| 先行 | 真实内容 | 与本仓库的关系 |
|---|---|---|
| **CodeRabbit / Codacy**（商业 AI 代码审查） | 在 PR 上自动贴 AI 审查评论 | **对比**：本仓库是**自托管、开源、可审计**的实现，5-Agent 分工（fetcher/analyzer/synthesizer/reflector/notifier）显式可追踪 |
| **PR-Agent / AI 审查研究** | LLM 生成 PR 审查报告 | **对比**：本仓库的增量是**反射式质量门**（Reflector 打分 <7 退回重做，≤3 次） |

## 3. 静态分析（非 LLM）

| 先行 | 真实内容 | 与本仓库的关系 |
|---|---|---|
| **pylint / flake8 / ruff** | AST/规则静态检查 | **对比**：本仓库 `code_analyzer.py` 用 Python `ast` 做同类检查（行长度、TODO、裸 except、长函数），但**轻量、零依赖、离线**，且作为 LLM 分析的**降级路径** |

## 4. 相对先行的定位与边界

- **独特材料**：本仓库的增量不是新算法，而是把「自动代码审查」做成**可复现、可审计、可降级**的
  5-Agent 状态机——LLM 失败时降级到纯 AST 静态分析，报告质量有显式反射门。
- **不声称**：①不声称 LLM 审查质量（离线单测未触及，也不伪造）；②不声称端到端流程已在真实 PR 验证；
  ③不声称报告一定被贴回 GitHub（notifier 需真实 Token，未测试）。
- **主要局限**：15 个单测只覆盖纯逻辑；Agent 的 LLM 路径、FastAPI、Streamlit **有意不覆盖**（需真实 Key）。

## 5. 一句话定位

> 相对商业 AI 代码审查（CodeRabbit/Codacy），本仓库把审查流程做成**开源、显式 5-Agent、带反射质量门、
> 可降级到静态分析**的实现；相对 pylint/flake8 的纯静态检查，它**叠加 LLM 语义分析**但保留静态检查作为降级路径。
