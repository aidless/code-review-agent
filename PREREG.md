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
| Reflector | 另一 LLM 打分（1-10，四维度） | 报告 → score, needs_replan |
| Notifier | GitHub API 贴评论 + 返回前端 | 报告 → PR 评论 |

## 3. 声明假设 / 阈值（预先设定）

- **反射阈值**：报告质量分 `< 7.0` → `needs_replan=True`（退回 Analyzer 重做）。
- **最大重试**：`max_reflection_iterations = 3`（超限放行，避免死循环）。
- **打分维度**：覆盖面 / 深度 / 可操作性 / 清晰度，各 1-10。
- **LLM 失败降级**：`_evaluate_report` 返回保守分（>500 字符→7.0，否则 4.0）——**不伪造**高质量分。

## 4. 评测方案 / 成功标准

- **成功**：`python -m pytest tests/ -q` 全部通过（**15 passed**，离线、无网络、无 Key）。
- **复算**：单点复算 `parse_pr_url('https://github.com/owner/repo/pull/123')` → `('owner','repo',123)`。
- **覆盖**：AST 静态分析（行长度/TODO/裸 except/长函数/console.log/无效 Python 优雅降级）+ URL 解析
  （基本/后缀/锚点/4 反例）。
- **诚实边界**：LLM 路径、FastAPI、Streamlit **有意不覆盖**（需真实 Key，不伪造）。

## 5. 边界（证明什么 / 不证明什么）

**证明（能承诺的）**：
- URL 解析器无网络下正确提取并拒绝非 PR 链接。
- AST 分析器识别常见问题，diff patch 输入优雅降级。
- 15 个离线单测在此树可复算。

**不证明（明确不声称）**：
- LLM 审查质量（需真实 `DEEPSEEK_API_KEY` 与 `GITHUB_TOKEN`，离线未触及）。
- 端到端审查流程（依赖上述 Agent，未在离线测试实例化）。
- 报告确实贴回 GitHub PR（notifier 需真实 Token，未测试）。
- 非外部时间戳预注册。
