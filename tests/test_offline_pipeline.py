"""Full graph with mocked GitHub and a scripted chat model.

Scripted scores are test inputs. They are not measurements of review quality.
"""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BARE_EXCEPT = "def f():\n    try:\n        return 1\n    except:\n        return 0\n"


class _Resp:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeOpenAI:
    prompts = []
    planned = []

    def __init__(self, *args, **kwargs):
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        prompt = kwargs["messages"][0]["content"]
        FakeOpenAI.prompts.append(prompt)
        if "quality evaluator" in prompt:
            if not FakeOpenAI.planned:
                raise AssertionError("reflector called more times than scripted scores")
            score = FakeOpenAI.planned.pop(0)
            content = json.dumps({"score": score, "feedback": "scripted-self-score"})
        elif "JSON Array:" in prompt:
            content = "[]"
        else:
            content = "# Code Review Report\n\nScripted synthesizer text."
        message = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _install_mocks(monkeypatch, scores):
    FakeOpenAI.prompts = []
    FakeOpenAI.planned = list(scores)
    posts = []
    gets = []

    def fake_get(url, headers=None, timeout=None):
        gets.append(url)
        if str(url).endswith("/files"):
            return _Resp([{
                "filename": "demo.py",
                "status": "modified",
                "additions": 5,
                "deletions": 0,
                "patch": BARE_EXCEPT,
            }])
        return _Resp({
            "title": "demo pr",
            "user": {"login": "octocat"},
            "base": {"ref": "main"},
            "head": {"ref": "feature", "sha": "deadbeef"},
            "state": "open",
            "html_url": "https://github.com/example/repo/pull/1",
        })

    def fake_post(url, json=None, headers=None, timeout=None):
        posts.append(url)
        raise AssertionError(f"graph posted a comment to {url}")

    monkeypatch.setattr("tools.github_tool.requests.get", fake_get)
    monkeypatch.setattr("tools.github_tool.requests.post", fake_post)
    monkeypatch.setattr("agents.analyzer_agent.OpenAI", FakeOpenAI)
    monkeypatch.setattr("agents.synthesizer_agent.OpenAI", FakeOpenAI)
    monkeypatch.setattr("agents.reflector_agent.OpenAI", FakeOpenAI)
    return gets, posts


def _state():
    return {
        "pr_url": "https://github.com/example/repo/pull/1",
        "github_token": "local-test-token",
        "pr_info": None,
        "code_files": None,
        "fetch_error": None,
        "issues": None,
        "analysis_error": None,
        "report": None,
        "synthesis_error": None,
        "reflection_score": None,
        "reflection_score_kind": None,
        "needs_replan": False,
        "reflection_feedback": None,
        "reflection_count": 0,
        "notification_status": None,
        "notification_url": None,
        "notification_error": None,
        "current_step": "start",
        "error_message": None,
        "max_reflection_iterations": 3,
        "dry_run": True,
    }


def _run(monkeypatch, scores):
    gets, posts = _install_mocks(monkeypatch, scores)
    from graph.workflow import create_workflow

    workflow = create_workflow()
    result = asyncio.run(workflow.ainvoke(_state()))
    evaluator_prompts = [p for p in FakeOpenAI.prompts if "quality evaluator" in p]
    return result, gets, posts, evaluator_prompts


def test_pipeline_retries_while_self_score_below_7_then_dry_run(monkeypatch):
    result, gets, posts, evaluator_prompts = _run(monkeypatch, [4.0, 4.0, 4.0])
    assert result["reflection_count"] == 3
    assert result["reflection_score"] == 4.0
    assert result["reflection_score_kind"] == "model_self_score"
    assert result["needs_replan"] is True
    assert result["notification_status"] == "dry_run"
    assert result["notification_url"] is None
    assert posts == []
    assert len(evaluator_prompts) == 3
    assert gets  # fetcher used the GitHub mock
    assert any(issue["category"] == "reliability" for issue in result["issues"])


def test_pipeline_stops_retrying_once_self_score_reaches_7(monkeypatch):
    result, _gets, posts, evaluator_prompts = _run(monkeypatch, [4.0, 8.0, 4.0])
    assert result["reflection_count"] == 2
    assert result["reflection_score"] == 8.0
    assert result["needs_replan"] is False
    assert result["notification_status"] == "dry_run"
    assert posts == []
    assert len(evaluator_prompts) == 2
    assert FakeOpenAI.planned == [4.0]


def test_api_defaults_to_dry_run(monkeypatch):
    captured = {}

    class Workflow:
        def invoke(self, state):
            captured.clear()
            captured.update(state)
            return {
                "report": {"report_markdown": "x", "pr_url": state["pr_url"], "summary": "s",
                           "issues": [], "strengths": [], "overall_score": 0.0},
                "error_message": None,
                "notification_status": "dry_run" if state["dry_run"] else "posted",
                "reflection_score": 4.0,
                "reflection_score_kind": "model_self_score",
            }

    monkeypatch.setattr("api.main.create_workflow", lambda: Workflow())
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    dry = client.post("/review", json={"pr_url": "https://github.com/example/repo/pull/1"})
    assert dry.status_code == 200
    assert captured["dry_run"] is True
    assert captured["github_token"] == ""
    body = dry.json()
    assert body["notification_status"] == "dry_run"
    assert body["reflection_score"] == 4.0
    assert body["reflection_score_kind"] == "model_self_score"

    live = client.post("/review", json={
        "pr_url": "https://github.com/example/repo/pull/1",
        "github_token": "local-test-token",
        "post_comment": True,
    })
    assert live.status_code == 200
    assert captured["dry_run"] is False
    assert captured["github_token"] == "local-test-token"
    assert live.json()["notification_status"] == "posted"
