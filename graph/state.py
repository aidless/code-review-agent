"""
LangGraph State Definition for the Code Review Multi-Agent System.

This module defines the shared state that flows between agents.
Each agent reads from and writes to this state.
"""
from typing import Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field


class CodeFile(BaseModel):
    """Represents a code file in the PR."""
    path: str = Field(..., description="File path in the repository")
    diff: str = Field(..., description="Git diff for this file")
    additions: int = Field(0, description="Number of additions")
    deletions: int = Field(0, description="Number of deletions")
    language: str = Field("unknown", description="Programming language")


class CodeIssue(BaseModel):
    """Represents a code issue found during analysis."""
    file: str = Field(..., description="File path")
    line: Optional[int] = Field(None, description="Line number (if applicable)")
    severity: str = Field(..., description="Severity: critical/major/minor/info")
    category: str = Field(..., description="Category: bug/performance/security/style/documentation")
    message: str = Field(..., description="Issue description")
    suggestion: str = Field(..., description="Suggested fix")
    confidence: float = Field(0.5, description="Confidence score 0-1")


class ReviewReport(BaseModel):
    """The final code review report."""
    pr_url: str = Field(..., description="PR URL")
    summary: str = Field(..., description="Executive summary")
    issues: List[CodeIssue] = Field(default_factory=list, description="All issues found")
    strengths: List[str] = Field(default_factory=list, description="Code strengths")
    overall_score: float = Field(0.0, description="Overall code quality score 0-10")
    report_markdown: str = Field(..., description="Full Markdown report")


class AgentState(TypedDict):
    """
    The shared state that flows between agents in the LangGraph workflow.
    
    This is the central data structure that all agents read from and write to.
    """
    # Input
    pr_url: str
    github_token: str
    
    # Fetcher Agent output
    pr_info: Optional[Dict[str, Any]]
    code_files: Optional[List[CodeFile]]
    fetch_error: Optional[str]
    
    # Analyzer Agent output
    issues: Optional[List[CodeIssue]]
    analysis_error: Optional[str]
    
    # Synthesizer Agent output
    report: Optional[ReviewReport]
    synthesis_error: Optional[str]
    
    # Reflector Agent output
    reflection_score: Optional[float]
    needs_replan: bool
    reflection_feedback: Optional[str]
    reflection_count: int  # Number of reflection iterations
    
    # Notifier Agent output
    notification_status: Optional[str]
    notification_url: Optional[str]
    notification_error: Optional[str]
    
    # Control flow
    current_step: str
    error_message: Optional[str]
    max_reflection_iterations: int
