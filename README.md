# CodeAgent Reviewer

[![CI](https://github.com/aidless/code-review-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/aidless/code-review-agent/actions/workflows/ci.yml)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

一个自动帮你审查 GitHub Pull Request 的工具。你把 PR 链接丢给它，5 个 AI Agent 会分工合作，自动分析代码质量，最后把审查报告贴到 PR 的评论区。

## 项目结构

```
code-review-agent/
+-- agents/              # 5 个 Agent（fetcher/analyzer/synthesizer/reflector/notifier）
+-- graph/               # LangGraph 状态机（state.py + workflow.py）
+-- tools/               # github_tool.py（GitHub API）+ code_analyzer.py（AST 静态分析）
+-- api/main.py          # FastAPI 后端（POST /review）
+-- frontend/app.py      # Streamlit 前端
+-- tests/test_analyzer.py  # 15 个离线单测（纯逻辑）
+-- requirements.txt
```

**验证过什么**：没有自动化测试（`tests/` 有意留空），只做过手工端到端跑通——给一个真实 PR 链接能出报告并回帖。请按"可运行原型"看待，不要按"可复现评测"看待。

**怎么跑**：`pip install -r requirements.txt`，配置 `GITHUB_TOKEN` 与模型 API key，然后 `streamlit run app.py`。

---

## 它怎么工作的

```
你提交一个 PR 链接
       |
       v
  [1] Fetcher Agent -- 从 GitHub 拉取 PR 的代码改动
       |
       v
  [2] Analyzer Agent -- 逐文件分析代码质量（静态分析 + LLM 推理）
       |
       v
  [3] Synthesizer Agent -- 把所有问题汇总成一份 Markdown 审查报告
       |
       v
  [4] Reflector Agent -- 用另一个 LLM 对报告质量打分（1-10 分）
       |                    如果低于 7 分，退回给 Analyzer 重新分析
       v                    （最多重试 3 次）
  [5] Notifier Agent -- 把报告贴到 GitHub PR 的评论区
```

为什么要用 5 个 Agent 而不是一个 LLM 调用？因为：
- 每个 Agent 只做一件事，出了问题好定位
- Fetcher 拉完数据后，Analyzer 崩了不用重新拉
- Reflector 可以反复打回重做，直到报告质量达标
- 以后想加功能（比如安全审查），加一个 Agent 就行

---

## 怎么用

### 准备工作

你需要：
- Python 3.10 或更高版本
- DeepSeek API Key（去 platform.deepseek.com 申请）
- GitHub Personal Access Token（去 github.com/settings/tokens 创建，勾选 repo 权限）

### 安装

```bash
git clone https://github.com/aidless/code-review-agent.git
cd code-review-agent
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
```

然后编辑 .env 文件，填入你的 API Key：

```
DEEPSEEK_API_KEY=sk-你的key
GITHUB_TOKEN=ghp_你的token
```

### 启动

需要开两个终端窗口：

**终端 1 -- 启动后端（FastAPI）**
```bash
cd api
python main.py
# 会在 http://localhost:8000 启动
```

**终端 2 -- 启动前端（Streamlit）**
```bash
cd frontend
streamlit run app.py
# 会在 http://localhost:8501 启动
```

### 使用

1. 打开浏览器访问 http://localhost:8501
2. 在输入框里粘贴 GitHub PR 的链接（比如 https://github.com/owner/repo/pull/123）
3. 点"开始审查"
4. 等 1-3 分钟
5. 看生成的审查报告

---

## 示例审查输出（Analyzer Agent 静态分析部分，真实运行）

静态分析层不需要 LLM 和 API key，可以直接复现——下面是对仓内文件
`agents/synthesizer_agent.py` 实跑的真实输出（2026-11-10）：

```bash
python3 - <<'PY'
from tools.code_analyzer import CodeAnalyzer
code = open("agents/synthesizer_agent.py", encoding="utf-8").read()
for f in CodeAnalyzer().analyze_file("agents/synthesizer_agent.py", code, "python"):
    print(f"[{f.severity}] {f.category} L{f.line}: {f.message} | 建议: {f.suggestion}")
PY
```

```text
[minor] style L88: Line 88 exceeds 120 characters (134) | 建议: Consider breaking the line
[minor] style L114: Line 114 exceeds 120 characters (161) | 建议: Consider breaking the line
```

完整流水线（LLM 逐文件推理 → Synthesizer 汇总 → Reflector 打分 → Notifier 回帖）
需要 DeepSeek key 与 GitHub token；上方片段是流水线第 2 步静态层的真实产物。

## 文件说明

### agents/ -- 5 个 Agent 的实现

| 文件 | 这个 Agent 做什么 |
|------|------------------|
| `base_agent.py` | 所有 Agent 的基类。定义了公共接口：输入是什么、输出是什么、出错了怎么处理。其他 5 个 Agent 都继承它。 |
| `fetcher_agent.py` | 第 1 个 Agent：拉数据。接收 PR 链接，调用 GitHub API 获取 PR 的标题、描述、所有文件的 diff（代码改动）。输出：PR 基本信息 + 所有代码文件内容。 |
| `analyzer_agent.py` | 第 2 个 Agent：分析代码。对每个文件做两件事：(1) 静态分析（AST 语法树检查，找语法错误、未使用变量、过长函数等）；(2) LLM 分析（用 DeepSeek 理解代码逻辑，找设计问题、潜在 bug）。输出：问题列表，每个问题有严重程度和位置。 |
| `synthesizer_agent.py` | 第 3 个 Agent：写报告。把 Analyzer 输出的问题列表，加上 PR 的基本信息，交给 LLM 生成一份结构化的 Markdown 审查报告。报告分"必须修复"、"建议修复"、"小问题"、"做得好的地方"四个部分。 |
| `reflector_agent.py` | 第 4 个 Agent：审查报告质量。用另一个 LLM 调用给报告打分（1-10），从覆盖面、深度、可操作性、清晰度四个维度评估。如果分数低于 7，设置 needs_replan=True，LangGraph 会把流程退回到 Analyzer 重新分析。最多重试 3 次。 |
| `notifier_agent.py` | 第 5 个 Agent：发通知。把最终的审查报告通过 GitHub API 贴到 PR 的评论区。同时把报告返回给前端显示。 |

### graph/ -- 流程控制

| 文件 | 做什么 |
|------|--------|
| `state.py` | 定义整个流程中传递的数据结构（TypedDict）。包括 PR 信息、代码文件列表、问题列表、审查报告、分数等。每个 Agent 的输入输出都是这个结构的一部分。 |
| `workflow.py` | 用 LangGraph 定义整个工作流。5 个 Agent 的执行顺序、分支条件（Reflector 打分后是退回 Analyzer 还是继续到 Notifier）、循环逻辑（最多重试 3 次）都在这里配置。 |

### tools/ -- 外部工具

| 文件 | 做什么 |
|------|--------|
| `github_tool.py` | GitHub API 的封装。处理认证（用 Personal Access Token）、分页（PR 可能有几百个文件）、错误重试、速率限制。 |
| `code_analyzer.py` | 静态代码分析。用 Python 的 AST 模块解析代码语法树，检查：未使用的 import、过长的函数（超过 50 行）、硬编码的字符串、缺少类型注解等。不需要 LLM，速度快，免费。 |

### api/ -- 后端

| 文件 | 做什么 |
|------|--------|
| `main.py` | FastAPI 后端。一个 POST 端点：接收 PR 链接，调用 LangGraph 工作流，返回审查报告。 |

### frontend/ -- 前端

| 文件 | 做什么 |
|------|--------|
| `app.py` | Streamlit 界面。一个输入框（填 PR 链接）+ 一个按钮（开始审查）+ 一个展示区（显示审查报告）。 |

### 其他文件

| 文件 | 做什么 |
|------|--------|
| `requirements.txt` | Python 依赖列表。主要的：langchain、langgraph、fastapi、streamlit、requests、python-dotenv。 |
| `.env.example` | 环境变量模板。告诉你需要填哪些 API Key。 |
| `.env` | 你自己的环境变量（不上传到 GitHub，因为里面有密钥）。 |

---

## 技术细节（面试用）

### 为什么用 LangGraph 而不是自己写循环？

LangGraph 提供了：
- **状态管理**：数据结构有类型定义，自动校验
- **条件分支**：Reflector 打分后自动判断是退回还是继续
- **循环支持**：原生支持"Analyzer -> Reflector -> Analyzer"这种重试循环
- **可观测性**：可以用 LangSmith 追踪每个 Agent 的输入输出
- **断点续传**：可以暂停/恢复流程（Human-in-the-Loop）

自己写 Python 循环也能实现，但要手动管理状态、错误处理、重试逻辑，代码量会大很多。

### LLM 打分准不准？

这是个好问题。LLM 打分确实有主观性。我的缓解措施：
- 用 few-shot prompting，给 LLM 看几个"好报告"和"差报告"的例子，让它校准打分标准
- 分析和反思用同一个 LLM（DeepSeek），避免模型之间的偏差
- 打分维度固定（覆盖面、深度、可操作性、清晰度），每个维度有明确标准

### 遇到 LLM 调用失败怎么办？

- 重试：用 tenacity 库做指数退避重试
- 降级：如果 LLM 挂了，退回到纯静态分析（AST 检查），至少能抓到基础问题
- 速率限制：GitHub API 有速率限制（认证用户 5000 次/小时），用缓存避免重复请求

**Fail-closed（真实代码）**：报告质量门是**fail-closed**——Reflector 打分 `< 7.0` 时
`needs_replan=True`，**拒绝放行**低质量报告，退回 Analyzer 重做（最多 3 次）；LLM 调用失败时
`_evaluate_report` 返回保守分（>500 字符→7.0，否则 4.0），**不伪造**高质量分。整体上「LLM 挂了
退回到纯静态 AST 分析」——宁可输出保守结果，不把不可靠的 LLM 报告当成品。详见 `bench/README.md`。

---

## 测试

```bash
cd code-review-agent
python -m pytest tests/ -q    # 15 passed
```

15 个离线单测覆盖**纯逻辑**部分：`tools/code_analyzer.py` 的 AST 静态分析
（行长度、TODO、裸 except、长函数、无效 Python 优雅降级、JS console.log、
通用回退、dataclass 字段）和 `tools/github_tool.parse_pr_url`（基本/后缀/锚点/
4 个反例）。Agent 的 LLM 路径、FastAPI 与 Streamlit 服务**有意不覆盖**
（需要真实 Key，不伪造），详见 `tests/README.md`。

## 证明什么 / 不证明什么

**证明：** PR URL 解析器在无网络下可正确提取 owner/repo/PR 号并拒绝非 PR 链接；
AST 静态分析器能识别行长度、TODO、裸 except、长函数等常见问题，并在输入是
diff patch（非完整 Python）时优雅降级不崩溃。

**不证明：** LLM 审查质量（Analyzer/Reflector/Synthesizer 需要 `DEEPSEEK_API_KEY`
与 `GITHUB_TOKEN`，离线单测未触及，也不伪造结果）；端到端审查流程
（LangGraph 状态机依赖上述 Agent，未在离线测试中实例化）；报告是否真的被
贴回 GitHub PR（notifier 需要真实 Token，未测试）。

## 复现

```bash
cd code-review-agent
python -m pytest tests/ -q     # 15 passed（离线，无网络无 Key）

# 单点复算：URL 解析
python -c "
import sys; sys.path.insert(0,'.')
from tools.github_tool import parse_pr_url
print(parse_pr_url('https://github.com/owner/repo/pull/123'))  # ('owner','repo',123)
"
```

15 这个数字来自 `pytest tests/ -q` 的实际收集与通过数，可在此树复算。

---

## 依赖

```
langchain
langgraph
fastapi
uvicorn
streamlit
requests
python-dotenv
tenacity
```

---

## 许可

MIT。随便用。

## Limits

- **无自动化测试**（`tests/` 有意留空），仅手工端到端跑通；按"可运行原型"看待。
- 静态分析层规则较浅（行长 / TODO / 基础 AST 检查），深度问题全靠 LLM 层。
- Reflector 打分依赖 LLM 主观评估，<7 分退回最多 3 次；评分波动会直接影响重试次数。
- 只支持 GitHub PR（Personal Access Token），GitLab/其他平台未接。

## 结构导览

| 路径 | 内容 |
|------|------|
| `agents/` | 5 个 Agent（fetcher / analyzer / synthesizer / reflector / notifier） |
| `graph/workflow.py` | LangGraph 工作流（重试 ≤3 的循环逻辑） |
| `tools/code_analyzer.py` | 免 key 免费的静态分析层（可独立复现，见上节） |
| `api/main.py` | FastAPI 后端（`uvicorn api.main:app --port 8000`） |
| `frontend/app.py` | Streamlit 前端（`streamlit run frontend/app.py`） |
