"""Measured negative cases. Numbers here are observations of this tree, not quality scores."""
import ast
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.analyzer_agent import AnalyzerAgent
from agents.notifier_agent import NotifierAgent, build_comment
from agents.reflector_agent import ReflectorAgent
from tools.code_analyzer import CodeAnalyzer
from tools.github_tool import GitHubTool

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "seeded_empty_mean.py"


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self._payload


def _load_mean():
    spec = importlib.util.spec_from_file_location("seeded_empty_mean", FIXTURE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.mean


def test_ast_misses_seeded_empty_mean():
    mean = _load_mean()
    with pytest.raises(ZeroDivisionError):
        mean([])

    source = FIXTURE.read_text(encoding="utf-8")
    ast.parse(source)  # the file is valid Python; the miss is not a parse failure
    findings = CodeAnalyzer().analyze_file(str(FIXTURE), source, "python")
    assert findings == []


def test_github_diff_fetch_is_a_single_request(monkeypatch):
    urls = []

    def fake_get(url, headers=None, timeout=None):
        urls.append(url)
        return _Resp([{
            "filename": "a.py",
            "status": "added",
            "additions": 1,
            "deletions": 0,
            "patch": "x = 1\n",
        }])

    monkeypatch.setattr("tools.github_tool.requests.get", fake_get)
    files = GitHubTool(token="local-test-token").get_pr_diff("example", "repo", 1)
    assert urls == ["https://api.github.com/repos/example/repo/pulls/1/files"]
    assert "page=" not in urls[0]
    assert len(files) == 1


def test_analyzer_llm_prompt_drops_lines_after_200(monkeypatch):
    prompts = []

    class Fake:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            prompts.append(kwargs["messages"][0]["content"])
            message = SimpleNamespace(content="[]")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr("agents.analyzer_agent.OpenAI", Fake)
    lines = [f"L{i}" for i in range(1, 201)]
    lines.append("LLM_SHOULD_NOT_SEE_THIS_TOKEN_" + ("x" * 120))
    diff = "\n".join(lines)
    result = asyncio.run(AnalyzerAgent().run({
        "code_files": [{"path": "demo.py", "diff": diff, "language": "python"}],
    }))
    assert len(prompts) == 1
    assert "L200" in prompts[0]
    assert "LLM_SHOULD_NOT_SEE_THIS_TOKEN_" not in prompts[0]
    assert any("exceeds 120" in issue["message"] for issue in result["issues"])


def test_reflector_prompt_truncates_report_at_3000_chars(monkeypatch):
    prompts = []

    class Fake:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            prompts.append(kwargs["messages"][0]["content"])
            message = SimpleNamespace(content='{"score": 8.0, "feedback": "scripted"}')
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr("agents.reflector_agent.OpenAI", Fake)
    marker = "TAIL_MARKER_PAST_3000"
    report = {"report_markdown": ("a" * 3000) + marker, "issues": []}
    score, _feedback, kind = asyncio.run(ReflectorAgent()._evaluate_report(report))
    assert score == 8.0
    assert kind == "model_self_score"
    assert marker not in prompts[0]
    assert ("a" * 3000) in prompts[0]


def test_llm_failure_heuristic_boundary(monkeypatch):
    class Boom:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            raise RuntimeError("llm down")

    monkeypatch.setattr("agents.reflector_agent.OpenAI", Boom)
    agent = ReflectorAgent()

    short = asyncio.run(agent.run({
        "report": {"report_markdown": "a" * 500, "issues": []},
        "reflection_count": 0,
    }))
    long = asyncio.run(agent.run({
        "report": {"report_markdown": "a" * 501, "issues": []},
        "reflection_count": 0,
    }))

    assert short["reflection_score"] == 4.0
    assert short["reflection_score_kind"] == "heuristic_fallback"
    assert short["needs_replan"] is True
    assert long["reflection_score"] == 7.0
    assert long["reflection_score_kind"] == "heuristic_fallback"
    assert long["needs_replan"] is False


def test_notifier_dry_run_does_not_post_even_with_token(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("dry-run called requests")

    monkeypatch.setattr("tools.github_tool.requests.post", explode)
    monkeypatch.setattr("tools.github_tool.requests.get", explode)
    result = asyncio.run(NotifierAgent().run({
        "report": {"report_markdown": "hello"},
        "pr_url": "https://github.com/example/repo/pull/1",
        "github_token": "local-test-token",
        "reflection_score": 4.0,
        "reflection_score_kind": "model_self_score",
        "dry_run": True,
    }))
    assert result["notification_status"] == "dry_run"
    assert result["notification_url"] is None


def test_notifier_refuses_to_post_when_token_missing(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("missing token still called requests")

    monkeypatch.setattr("tools.github_tool.requests.post", explode)
    monkeypatch.setattr("tools.github_tool.requests.get", explode)
    result = asyncio.run(NotifierAgent().run({
        "report": {"report_markdown": "hello"},
        "pr_url": "https://github.com/example/repo/pull/1",
        "github_token": "",
        "dry_run": False,
    }))
    assert result["notification_status"] == "failed"
    assert result["notification_error"] == "GITHUB_TOKEN missing; refusing to post"


def test_notifier_posts_only_when_dry_run_is_false(monkeypatch):
    posts = []

    def fake_get(url, headers=None, timeout=None):
        return _Resp({"head": {"sha": "abc123"}})

    def fake_post(url, json=None, headers=None, timeout=None):
        posts.append({"url": url, "json": json, "auth": headers.get("Authorization")})
        return _Resp({"html_url": "https://github.com/example/repo/pull/1#pullrequestreview-1"})

    monkeypatch.setattr("tools.github_tool.requests.get", fake_get)
    monkeypatch.setattr("tools.github_tool.requests.post", fake_post)

    result = asyncio.run(NotifierAgent().run({
        "report": {"report_markdown": "report body"},
        "pr_url": "https://github.com/example/repo/pull/1",
        "github_token": "local-test-token",
        "reflection_score": 4.0,
        "reflection_score_kind": "model_self_score",
        "dry_run": False,
    }))
    assert result["notification_status"] == "posted"
    assert len(posts) == 1
    assert posts[0]["url"] == "https://api.github.com/repos/example/repo/pulls/1/reviews"
    assert posts[0]["json"]["event"] == "COMMENT"
    assert posts[0]["json"]["commit_id"] == "abc123"
    assert posts[0]["auth"] == "token local-test-token"
    body = posts[0]["json"]["body"]
    assert "https://github.com/aidless/code-review-agent" in body
    assert "yourusername" not in body
    assert "model self-score, not a validated quality metric" in body
    assert "4.0 (model_self_score)" in body

    rendered = build_comment("report body", 4.0, "model_self_score")
    assert rendered == body
