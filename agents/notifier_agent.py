"""
Notifier Agent - Posts review report to GitHub PR.

Responsibilities:
1. Take report from state
2. Post report to GitHub PR as a comment
3. Output: notification_status, notification_url, notification_error
"""
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base_agent import BaseAgent
from tools.github_tool import GitHubTool, parse_pr_url
from graph.state import AgentState

# This repository. Not a placeholder account and not a PyPI project page.
REPO_URL = "https://github.com/aidless/code-review-agent"


def build_comment(report_markdown: str, reflection_score, score_kind: str) -> str:
    """Comment body. The score line labels a model self-score, not a quality metric."""
    if reflection_score is None:
        score_line = "Reflector self-score: not produced."
    else:
        kind = score_kind or "unspecified"
        score_line = (
            f"Reflector self-score: {reflection_score} ({kind}). "
            "This is a model self-score, not a validated quality metric."
        )
    return f"""## AI Code Review (CodeAgent Reviewer)

{report_markdown}

---
{score_line}
Source repository: {REPO_URL}
"""


class NotifierAgent(BaseAgent):
    """
    Agent that posts the review report to GitHub PR.
    
    Input state: report, pr_url, github_token
    Output state: notification_status, notification_url, notification_error
    """
    
    def __init__(self, name: str = "notifier"):
        super().__init__(name)
    
    async def run(self, state: AgentState) -> Dict[str, Any]:
        """
        Post review report to GitHub PR.
        
        Args:
            state: Current workflow state with report and pr_url
            
        Returns:
            Updated state with notification results
        """
        self.logger.info("[NotifierAgent] Preparing review notification...")
        
        try:
            report_data = state.get("report")
            pr_url = state.get("pr_url", "")
            github_token = state.get("github_token", "")
            
            if not report_data:
                return {
                    "notification_status": "failed",
                    "notification_error": "No report to post",
                    "current_step": "notifier_error",
                }

            report_markdown = report_data.get("report_markdown", "")
            comment_body = build_comment(
                report_markdown,
                state.get("reflection_score"),
                state.get("reflection_score_kind") or "",
            )

            # Default is dry-run. A missing flag must not post a comment.
            if state.get("dry_run", True):
                self.logger.info("[NotifierAgent] dry_run: comment was not posted")
                return {
                    "notification_status": "dry_run",
                    "notification_url": None,
                    "notification_error": None,
                    "current_step": "notifier_done",
                }

            if not github_token:
                return {
                    "notification_status": "failed",
                    "notification_error": "GITHUB_TOKEN missing; refusing to post",
                    "notification_url": None,
                    "current_step": "notifier_error",
                }

            # Parse PR URL
            owner, repo, pr_number = parse_pr_url(pr_url)

            # Create GitHub tool
            github_tool = GitHubTool(token=github_token)

            # Post review comment to PR. This is the live path.
            result = github_tool.post_review_comment(owner, repo, pr_number, comment_body)
            
            self.logger.info(f"[NotifierAgent] Posted review to PR: {result.get('html_url', 'N/A')}")
            
            return {
                "notification_status": "posted",
                "notification_url": result.get("html_url", ""),
                "notification_error": None,
                "current_step": "notifier_done",
            }
            
        except Exception as e:
            self.logger.error(f"[NotifierAgent] Error: {e}", exc_info=True)
            return {
                "notification_status": "failed",
                "notification_error": str(e),
                "current_step": "notifier_error",
            }
