"""
GitHub API Tool - Fetches PR data from GitHub.

This module handles:
- Parsing GitHub PR URLs
- Fetching PR metadata via GitHub API
- Fetching PR diff (file changes)
- Filtering non-code files
- Posting review comments to PR
"""
import os
import re
import requests
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PRInfo:
    """PR metadata."""
    repo_owner: str
    repo_name: str
    pr_number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    state: str  # open, closed, merged
    html_url: str


def parse_pr_url(url: str) -> Tuple[str, str, int]:
    """
    Parse a GitHub PR URL to extract owner, repo, and PR number.
    
    Examples:
        https://github.com/owner/repo/pull/123
        https://github.com/owner/repo/pull/123/files
        https://github.com/owner/repo/pull/123#issuecomment-xxx
    
    Returns:
        (owner, repo, pr_number)
    """
    pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.search(pattern, url)
    if not match:
        raise ValueError(f"Invalid GitHub PR URL: {url}")
    owner, repo, pr_number = match.groups()
    return owner, repo, int(pr_number)


class GitHubTool:
    """Tool for interacting with GitHub API."""
    
    def __init__(self, token: str):
        self.token = token
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
    
    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> PRInfo:
        """Fetch PR metadata."""
        url = f"{self.api_base}/repos/{owner}/{repo}/pulls/{pr_number}"
        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return PRInfo(
            repo_owner=owner,
            repo_name=repo,
            pr_number=pr_number,
            title=data["title"],
            author=data["user"]["login"],
            base_branch=data["base"]["ref"],
            head_branch=data["head"]["ref"],
            state=data["state"],
            html_url=data["html_url"],
        )
    
    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetch PR diff (file changes).
        Returns list of dicts with keys: filename, status, additions, deletions, patch.
        """
        url = f"{self.api_base}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        files = resp.json()
        result = []
        for f in files:
            # Skip non-code files
            if self._is_code_file(f["filename"]):
                result.append({
                    "filename": f["filename"],
                    "status": f["status"],  # added, modified, removed
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                    "patch": f.get("patch", ""),  # The actual diff text
                })
        return result
    
    def _is_code_file(self, filename: str) -> bool:
        """Check if file is a code file (not docs, config, etc.)."""
        code_extensions = {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
            ".cpp", ".c", ".h", ".hpp", ".cs", ".php", ".rb", ".swift",
            ".kt", ".scala", ".sh", ".bash", ".sql", ".html", ".css",
            ".vue", ".svelte",
        }
        ext = os.path.splitext(filename)[1].lower()
        return ext in code_extensions
    
    def post_review_comment(self, owner: str, repo: str, pr_number: int, body: str) -> Dict[str, Any]:
        """
        Post a review comment to a PR.
        Returns the created review data.
        """
        url = f"{self.api_base}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        payload = {
            "commit_id": self._get_pr_head_sha(owner, repo, pr_number),
            "body": body,
            "event": "COMMENT",  # COMMENT, APPROVE, REQUEST_CHANGES
        }
        resp = requests.post(url, json=payload, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    
    def _get_pr_head_sha(self, owner: str, repo: str, pr_number: int) -> str:
        """Get the head commit SHA of a PR."""
        url = f"{self.api_base}/repos/{owner}/{repo}/pulls/{pr_number}"
        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()["head"]["sha"]
