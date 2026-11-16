# CodeAgent Reviewer

[![CI](https://github.com/aidless/code-review-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/aidless/code-review-agent/actions/workflows/ci.yml)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

LangGraph 上的 5-Agent GitHub PR 审查原型（fetcher / analyzer / synthesizer / reflector / notifier）。

**离线能证明的**：`make check` 不需要 `GITHUB_TOKEN` 或模型 key。它跑 pytest：AST 分析器、用 mock 替换的 GitHub 与聊天模型、Reflector 自评分 `< 7` 时退回（最多 3 次）、Notifier dry-run 不发评论。

**离线不能证明的**：对真实 PR 的审查质量。Reflector 的分数是模型给本流水线自己报告的自评分，不是经过人工或基准校验的质量指标。本仓库没有 PyPI 包，也没有“已在大量真实 PR 上验证”的数据。失败模式见 [FAILURE_MODES.md](FAILURE_MODES.md)。

作者与仓库路径：[aidless/code-review-agent](https://github.com/aidless/code-review-agent)（GitHub 用户 aidless）。评论页脚里的链接指向这个仓库。

## 项目结构

```
code-review-agent/
+-- agents/              # 5 个 Agent（fetcher/analyzer/synthesizer/reflector/notifier）
+-- graph/               # LangGraph 状态机（state.py + workflow.py）
+-- tools/               # github_tool.py（GitHub API）+ code_analyzer.py（AST 静态分析）
+-- api/main.py          # FastAPI 后端（POST /review，默认不发评论）
+-- frontend/app.py      # Streamlit 前端（从仓库根目录：streamlit run frontend/app.py）
+-- tests/               # 离线 pytest（AST、mock 的重试环、notifier dry-run、负例）
+-- requirements.txt
+-- FAILURE_MODES.md
```

**怎么跑离线检查**（不需要 token）：`make check`。它会先 `pip install`（这一步要网络拉依赖），再跑测试。带界面的用法见下面「怎么用」，需要 key，并且默认不往 PR 贴评论。

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
- Reflector 可以打回重做；自评分低于 7 且未到 3 次时退回 Analyzer。到 3 次后仍会进入 Notifier（见 FAILURE_MODES.md）
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

从仓库根目录开两个终端。文件在 `api/main.py` 和 `frontend/app.py`，不是仓库根上的 `app.py`。

**终端 1 -- 启动后端（FastAPI）**
```bash
python -m uvicorn api.main:app --port 8000
# 等价：python api/main.py
```

**终端 2 -- 启动前端（Streamlit）**
```bash
streamlit run frontend/app.py
# 等价：cd frontend && streamlit run app.py
```

### 使用

1. 打开浏览器访问 http://localhost:8501
2. 在输入框里粘贴 GitHub PR 的链接（比如 https://github.com/owner/repo/pull/123）
3. 点"开始审查"
4. 等 1-3 分钟
5. 看生成的审查报告。默认不往 PR 贴评论；只有勾选 “Post the report as a PR comment” 且 token 有效时才会贴。

---

## 示例审查输出（Analyzer Agent 静态分析部分，真实运行）

静态分析层不需要 LLM 和 API key，可以直接复现——下面是对仓内文件
`agents/synthesizer_agent.py` 的输出（2026-11-16 在本树重跑，与下面两行一致）：

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

上面只是静态分析。完整流水线还要 DeepSeek key 才能调用模型，要 GitHub token 才能拉 PR。默认 `post_comment` 为 false，不会回帖。本仓库没有附带某次真实 PR 回帖的记录。

## 文件说明

### agents/ -- 5 个 Agent 的实现

| 文件 | 这个 Agent 做什么 |
|------|------------------|
| `base_agent.py` | 所有 Agent 的基类。定义了公共接口：输入是什么、输出是什么、出错了怎么处理。其他 5 个 Agent 都继承它。 |
| `fetcher_agent.py` | 第 1 个 Agent：拉数据。接收 PR 链接，调用 GitHub API 获取 PR 的标题、描述、所有文件的 diff（代码改动）。输出：PR 基本信息 + 所有代码文件内容。 |
| `analyzer_agent.py` | 第 2 个 Agent：分析代码。对每个文件做两件事：(1) 静态分析（AST 语法树检查，找语法错误、未使用变量、过长函数等）；(2) LLM 分析（用 DeepSeek 理解代码逻辑，找设计问题、潜在 bug）。输出：问题列表，每个问题有严重程度和位置。 |
| `synthesizer_agent.py` | 第 3 个 Agent：写报告。把 Analyzer 输出的问题列表，加上 PR 的基本信息，交给 LLM 生成一份结构化的 Markdown 审查报告。报告分"必须修复"、"建议修复"、"小问题"、"做得好的地方"四个部分。 |
| `reflector_agent.py` | 第 4 个 Agent：让聊天模型给**本流水线刚写出的报告**打自评分（1-10），提示里写了覆盖面、深度、可操作性、清晰度。`score < 7` 时 `needs_replan=True`，LangGraph 退回 Analyzer。`reflection_count` 达到 3 后不再退回。这个分数不是经过校验的质量指标。 |
| `notifier_agent.py` | 第 5 个 Agent：发通知。把最终的审查报告通过 GitHub API 贴到 PR 的评论区。同时把报告返回给前端显示。 |

### graph/ -- 流程控制

| 文件 | 做什么 |
|------|--------|
| `state.py` | 定义整个流程中传递的数据结构（TypedDict）。包括 PR 信息、代码文件列表、问题列表、审查报告、分数等。每个 Agent 的输入输出都是这个结构的一部分。 |
| `workflow.py` | 用 LangGraph 定义整个工作流。5 个 Agent 的执行顺序、分支条件（Reflector 打分后是退回 Analyzer 还是继续到 Notifier）、循环逻辑（最多重试 3 次）都在这里配置。 |

### tools/ -- 外部工具

| 文件 | 做什么 |
|------|--------|
| `github_tool.py` | GitHub API 的封装：解析 PR URL、用 token 做一次 GET 拉 PR 元数据和一次 GET 拉文件列表、在 `dry_run=False` 且 token 存在时 POST 一条 review comment。没有分页循环，也没有在代码里实现速率限制缓存。 |
| `code_analyzer.py` | 静态代码分析，不调用 LLM。已实现的检查：行长超过 120、TODO/FIXME/HACK/XXX、裸 `except`、函数超过 50 行、JS/TS 的 `console.log`/`console.debug`。不检查未使用的 import、硬编码字符串、缺类型注解，也会漏掉 `tests/fixtures/seeded_empty_mean.py` 这种空列表除法。 |

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

## 技术细节

`graph/workflow.py` 用 LangGraph 把五个节点串起来。Reflector 之后的条件边是 `_should_retry`：`needs_replan` 为真且 `reflection_count < max_reflection_iterations`（默认 3）才退回 Analyzer，否则进入 Notifier。

本仓库**没有**接入 LangSmith，也**没有**配置 Human-in-the-Loop 断点。`requirements.txt` 里有 `tenacity`，agent 代码没有 import 它，失败时不会做指数退避。GitHub 调用没有分页，也没有响应缓存。

Reflector 与 Analyzer、Synthesizer 默认都请求 `deepseek-chat`（`DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL`）。提示词列出四个维度，**没有**附上「好报告 / 差报告」的 few-shot 样例。返回的数字是模型自评分；解析失败时走字符数启发式（报告长于 500 字符记 7.0，否则 4.0）。7.0 不触发重试。Analyzer 的 LLM 调用失败时丢掉该文件的模型意见，静态分析结果仍然保留。这些都不是 fail-closed 的质量门。详见 [FAILURE_MODES.md](FAILURE_MODES.md)。

---

## 测试

```bash
make check    # pip install，然后 pytest（含覆盖率表）和 eval/run_cases.py
```

这次改动在本树跑出 **26 passed**（`python3 -m pytest tests -q`，无 token）。构成：

- `tests/test_analyzer.py`：15 条。AST 与 `parse_pr_url`。`eval` 题 CR-18 从该文件数出 12 个测试函数、展开后 15 条，**不代表全库条数**。
- `tests/test_negative_cases.py`：8 条。空列表除法漏报、diff 只 GET 一次、LLM 提示截到 200 行、报告截到 3000 字符、启发式 500/501 边界、dry-run、缺 token、以及仅在 mock 下才会走到的 POST。
- `tests/test_offline_pipeline.py`：3 条。脚本化自评分 4.0 连打三次后退尽、4.0 然后 8.0 时第二次停、API 默认 `dry_run`。

脚本化的 4.0 / 8.0 是测试输入，不是测出来的审查质量。Streamlit 页面没有进 pytest。覆盖率表覆盖 `agents`、`graph`、`tools`、`api`，百分比以 `make check` 的输出为准，不写死在这里。

## 证明什么 / 不证明什么

**证明：** 无 token 时，URL 解析、AST 规则、mock 掉 GitHub 与聊天客户端之后的重试环、以及 notifier 在 dry-run 下不调用 `requests.post`。

**不证明：** 真实 PR 上的审查质量；模型自评分是否可靠；一条评论是否曾经被贴到某个真实 PR。live POST 只在 `requests.post` 被替换的测试里走到，那次测试没有创建 GitHub 评论。

## 复现

```bash
git clone https://github.com/aidless/code-review-agent.git
cd code-review-agent
make check

python3 -c "
import sys; sys.path.insert(0,'.')
from tools.github_tool import parse_pr_url
print(parse_pr_url('https://github.com/owner/repo/pull/123'))  # ('owner','repo',123)
"
```

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
tenacity   # 列在 requirements.txt 中；当前 agent 代码未 import
```

---

## 许可

MIT。随便用。

## Limits

- 离线套件是 26 条 pytest，外加 `eval/cases.jsonl` 的 20 题。它不测量真实 PR 的审查质量。
- 静态分析只有行长、TODO、裸 except、长函数、JS `console.log`/`debug`。`tests/fixtures/seeded_empty_mean.py` 的空列表除法是一条复现得到的漏报。
- Reflector 分数是模型自评分。低于 7 且次数未到 3 才退回；第 3 次之后照样进入 Notifier。长报告上的启发式 7.0 不会退回。
- 只接 GitHub PR。默认不发评论；`post_comment: true` 且 token 有效时会发。没有 PyPI 包。

## 结构导览

| 路径 | 内容 |
|------|------|
| `agents/` | 5 个 Agent（fetcher / analyzer / synthesizer / reflector / notifier） |
| `graph/workflow.py` | LangGraph 工作流（重试 ≤3 的循环逻辑） |
| `tools/code_analyzer.py` | 免 key 免费的静态分析层（可独立复现，见上节） |
| `api/main.py` | FastAPI 后端（`python -m uvicorn api.main:app --port 8000`） |
| `frontend/app.py` | Streamlit 前端（`streamlit run frontend/app.py`） |

## 验收题库与复算

`eval/cases.jsonl` 是 20 条可执行验收题（n=20，16 个 axis，同一 axis 最多 2 条），覆盖静态分析层、
GitHub 工具层、状态模型、工作流条件边、API 契约与文档口径：行长阈值边界（120 字符不报 / 121 字符报）、
TODO 与裸 except 的 category/severity、长函数 `>50` 行判据、JS 只拦 `console.log|debug`、PR URL 解析
与 `/pull/abc` 拒绝、代码文件扩展名白名单（`.hpp` 收 / `.md` 不收 / 大小写不敏感）、扩展名→语言映射
（`.hpp` 落到 unknown）、pydantic 默认值与必填校验、reflector 重试边界（count 与上限相等时放行）、
FastAPI 的 title/version，以及从 `tests/test_analyzer.py` 复算「12 个测试函数、展开 15 条」（CR-18）。全库 pytest 是 26 条，不由 CR-18 代表。其中 **≥12 条必须是 expr/raises 且真调
本仓库 API 或真解析仓内文件**（现为 18 条 expr/raises + 2 条 doc），期望值不抄文档，都是现算出来的：

```bash
cd code-review-agent
python3 eval/run_cases.py            # 20/20 cases passed，退出码 0
python3 eval/run_cases.py --save     # 顺带把结果写进 eval/run-report.json
python3 eval/run_cases.py --selftest # 篡改第一条期望值，必须变红（19/20，证明这套题会失败）
python3 eval/run_cases.py --json     # 机器可读（含 failed_by_axis）
```

**数字如何复算**：`eval/run-report.json` 里每条 case 都带 `id` / `axis` / `detail`，把 `detail` 与
`cases.jsonl` 里的 `verify` 代码一起看，就能从源码复现该数字；`--save` 重跑一次即可重建整份报告，
不需要手工抄数。例如 `CR-06` 的 `detail` 是 `0|1|Function 'f' is too long (51 lines)`，对应的
`verify` 就是现构造 50 行与 51 行函数体再跑 `CodeAnalyzer().analyze_file(...)`。

**失败归因**：`run_cases.py` 不只报通过率，失败时按 `axis` 汇总（例如
`analyzer/line-length: 1 条 —— CR-01`），直接指出是哪个模块的哪个口径坏了，不用逐条翻输出。
