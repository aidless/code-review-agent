# PREREG — CodeAgent Reviewer 分析设计（内部规格，非外部时间戳预注册）

> **诚实边界（最重要）**：本文件是**内部分析设计规格**，**不是**外部时间戳预注册。
> 它如实记录仓库中**实际存在**的预先设定设计——5-Agent 架构、评测协议、成功标准与边界。
> 凡与「在数据前写定并时间戳封存」相关的声明，一律不出现。预注册语义仅限「**预先设定的评估方案**」。

## 1. 研究问题

R1：能否用一个**显式 5-Agent LangGraph 状态机**自动审查 GitHub PR——分析代码质量、汇总报告、
评估报告质量（反射门）、发布到 PR 评论，并在 LLM 失败时**降级到纯静态分析**？

## 2. 预先设定的架构（非事后挑选）

| 节点 | 真实职责 | 输入 → 输出 |
|---|---|---|
| Fetcher | GitHub API 拉 PR 元数据 + 全文件 diff | PR 链接 → PR 信息 + 文件内容 |
| Analyzer | AST 静态分析 + LLM 语义分析 | 文件内容 → 问题列表 |
| Synthesizer | 汇总为 Markdown | 问题列表 → 报告 |
| Reflector | 同一类聊天模型给本流水线的报告打自评分（1-10）。不是校验过的质量指标 | 报告 → score, score_kind, needs_replan |
| Notifier | GitHub API 贴评论 + 返回前端 | 报告 → PR 评论 |

## 3. 声明假设 / 阈值（预先设定）

- **反射阈值**：自评分 `< 7.0` → `needs_replan=True`（退回 Analyzer）。等于 7.0 不退回。
- **最大重试**：`max_reflection_iterations = 3`。计数达到 3 后进入 Notifier，即使 `needs_replan` 仍为真。
- **打分维度**：提示词里写了覆盖面 / 深度 / 可操作性 / 清晰度。没有 few-shot 样例。
- **LLM 失败**：`_evaluate_report` 在调用失败时用字符数启发式（长于 500 字符 → 7.0，否则 4.0）。7.0 会通过门。这不是校验过的质量分。

## 4. 评测方案 / 成功标准

- **成功**：`make check` 通过。其中 `python3 -m pytest tests -q` 在本树为 **26 passed**（无 token）。
- **复算**：`parse_pr_url('https://github.com/owner/repo/pull/123')` → `('owner','repo',123)`。
- **覆盖**：AST 与 URL 解析（`test_analyzer.py` 15 条）；mock 的 GitHub 与聊天客户端下的重试环和 notifier dry-run；`FAILURE_MODES.md` 里的负例。
- **诚实边界**：脚本化的分数不是审查质量。Streamlit 未进 pytest。没有真实 PR 评测。

## 5. 边界（证明什么 / 不证明什么）

**证明（能承诺的）**：
- URL 解析器无网络下正确提取并拒绝非 PR 链接。
- AST 分析器识别它实现了的那些问题，diff patch 输入解析失败时不崩溃。
- mock 掉 GitHub 与聊天客户端后，自评分低于 7 会重试，第 3 次后 dry-run 结束且不 POST。
- 26 条离线 pytest 可在此树复算。条数以 pytest 输出为准。

**不证明（明确不声称）**：
- 模型自评分等于审查质量。
- 在真实 PR 上的审查效果或回帖记录。
- `dry_run=False` 且 token 有效时的那次 POST 曾在测试中打到 GitHub（测试替换了 `requests.post`）。
- 非外部时间戳预注册。
