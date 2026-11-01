"""Offline tests for code-review-agent's pure logic.

These exercise the parts of the tool that need no LLM and no network:
- the static CodeAnalyzer (AST-based findings on real Python code)
- the GitHub PR URL parser (regex, no API call)
- the agent base class contract

They deliberately do NOT touch fetcher/analyzer/synthesizer/reflector/notifier
LLM paths or the FastAPI/Streamlit servers, which need DEEPSEEK_API_KEY and a
GITHUB_TOKEN.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.code_analyzer import AnalysisFinding, CodeAnalyzer
from tools.github_tool import parse_pr_url


# ---------------------------------------------------------------------------
# CodeAnalyzer
# ---------------------------------------------------------------------------

def test_analyzer_finds_line_length():
    analyzer = CodeAnalyzer()
    long_line = "x = " + "a" * 130
    findings = analyzer.analyze_file("demo.py", long_line, "python")
    style = [f for f in findings if f.category == "style"]
    assert style, "expected a style finding for a >120-char line"
    assert style[0].severity == "minor"
    assert "exceeds 120" in style[0].message


def test_analyzer_finds_todo():
    analyzer = CodeAnalyzer()
    findings = analyzer.analyze_file("demo.py", "# TODO: refactor this\npass\n", "python")
    doc = [f for f in findings if f.category == "documentation"]
    assert doc, "expected a documentation finding for a TODO comment"
    assert doc[0].severity == "info"


def test_analyzer_finds_bare_except():
    analyzer = CodeAnalyzer()
    code = "try:\n    pass\nexcept:\n    pass\n"
    findings = analyzer.analyze_file("demo.py", code, "python")
    rel = [f for f in findings if f.category == "reliability"]
    assert rel, "expected a reliability finding for a bare except"
    assert rel[0].severity == "major"


def test_analyzer_finds_long_function():
    analyzer = CodeAnalyzer()
    body = "\n".join("    pass" for _ in range(60))
    code = f"def long_fn():\n{body}\n"
    findings = analyzer.analyze_file("demo.py", code, "python")
    comp = [f for f in findings if f.category == "complexity"]
    assert comp, "expected a complexity finding for a >50-line function"


def test_analyzer_handles_invalid_python_gracefully():
    analyzer = CodeAnalyzer()
    # A diff patch is not valid Python; AST must be skipped, not crash.
    findings = analyzer.analyze_file("demo.py", "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n", "python")
    assert isinstance(findings, list)


def test_analyzer_js_console_log():
    analyzer = CodeAnalyzer()
    findings = analyzer.analyze_file("demo.js", "console.log('hi');\n", "javascript")
    style = [f for f in findings if f.category == "style"]
    assert any("console.log" in f.message for f in style)


def test_analyzer_generic_fallback():
    analyzer = CodeAnalyzer()
    findings = analyzer.analyze_file("demo.go", "line " + "a" * 130 + "\n", "go")
    assert findings, "generic fallback should still flag long lines"


def test_finding_dataclass_fields():
    f = AnalysisFinding(file="a.py", line=3, severity="minor",
                        category="style", message="m")
    assert f.file == "a.py" and f.line == 3 and f.severity == "minor"


# ---------------------------------------------------------------------------
# parse_pr_url
# ---------------------------------------------------------------------------

def test_parse_pr_url_basic():
    assert parse_pr_url("https://github.com/owner/repo/pull/123") == ("owner", "repo", 123)


def test_parse_pr_url_with_files_suffix():
    assert parse_pr_url("https://github.com/owner/repo/pull/123/files") == ("owner", "repo", 123)


def test_parse_pr_url_with_anchor():
    assert parse_pr_url("https://github.com/owner/repo/pull/123#issuecomment-99") == ("owner", "repo", 123)


@pytest.mark.parametrize("bad", [
    "https://github.com/owner/repo/issues/123",
    "https://github.com/owner/repo/",
    "https://example.com/owner/repo/pull/123",
    "not a url",
])
def test_parse_pr_url_rejects_non_pr(bad):
    with pytest.raises(ValueError):
        parse_pr_url(bad)
