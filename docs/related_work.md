# Related Work — 自动代码审查 Agent 的先行对照

> 本文件把 code-review-agent 与**真实存在的先行工作**对照，说明借鉴了什么、相对什么有增量。
> 所有引用均为真实开源框架/工具/产品，未虚构。

## 1. 编排框架

| 先行 | 真实内容 | 与本仓库的关系 |
|---|---|---|
| **LangGraph**（LangChain 官方） | 有状态图编排：类型化状态、条件分支、循环 | **本仓库用它**定义 5-Agent 工作流（`graph/workflow.py`）和 Reflector→Analyzer 重试。没有配置断点或 checkpointer |
| **LangSmith** | 追踪每个节点的输入/输出 | **未接入**。仓库里没有 LangSmith 客户端调用 |

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

- **定位**：5-Agent 状态机原型。模型调用失败时 Analyzer 留下 AST 结果，Reflector 改用字符数启发式。
  自评分不是校验过的质量门。AST 会漏报，见 `tests/fixtures/seeded_empty_mean.py`。
- **不声称**：①不把模型自评分当成审查质量；②不声称在真实 PR 上验证过；③不声称测试往 GitHub 贴过评论
  （dry-run 是默认，live 路径的测试替换了 `requests.post`）。没有 PyPI 包。
- **离线范围**：26 条 pytest。Streamlit 页面不在其中。聊天模型在这些测试里是替换掉的。

## 5. 一句话定位

> 相对商业 AI 代码审查（CodeRabbit/Codacy），本仓库是开源的 5-Agent 原型，Reflector 只产模型自评分；
> 相对 pylint/flake8，静态检查更窄，模型意见没有在真实 PR 上对照过。
