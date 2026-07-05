"""
Fetcher Agent - Fetches PR data from GitHub.

Responsibilities:
1. Parse GitHub PR URL
2. Call GitHub API to get PR metadata
3. Call GitHub API to get PR diff (file changes)
4. Filter non-code files
5. Output: pr_info, code_files
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Any, Dict, List
from agents.base_agent import BaseAgent
from tools.github_tool import GitHubTool, parse_pr_url
from graph.state import AgentState, CodeFile


class FetcherAgent(BaseAgent):
    """
    Agent that fetches PR data from GitHub.
    
    Input state: pr_url, github_token
    Output state: pr_info, code_files, fetch_error
    """
    
    def __init__(self, name: str = "fetcher"):
        super().__init__(name)
    
    async def run(self, state: AgentState) -> Dict[str, Any]:
        """
        Fetch PR data from GitHub.
        
        Args:
            state: Current workflow state with pr_url and github_token
            
        Returns:
            Updated state with pr_info, code_files, or fetch_error
        """
        self.logger.info(f"[FetcherAgent] Starting to fetch PR: {state.get('pr_url', 'N/A')}")
        
        try:
            pr_url = state["pr_url"]
            github_token = state["github_token"]
            
            # Parse PR URL
            owner, repo, pr_number = parse_pr_url(pr_url)
            self.logger.info(f"[FetcherAgent] Parsed: {owner}/{repo}#{pr_number}")
            
            # Create GitHub tool
            github_tool = GitHubTool(token=github_token)
            
            # Fetch PR info
            pr_info = github_tool.get_pr_info(owner, repo, pr_number)
            pr_info_dict = {
                "repo_owner": pr_info.repo_owner,
                "repo_name": pr_info.repo_name,
                "pr_number": pr_info.pr_number,
                "title": pr_info.title,
                "author": pr_info.author,
                "base_branch": pr_info.base_branch,
                "head_branch": pr_info.head_branch,
                "state": pr_info.state,
                "html_url": pr_info.html_url,
            }
            self.logger.info(f"[FetcherAgent] PR info fetched: {pr_info.title}")
            
            # Fetch PR diff (code files)
            raw_files = github_tool.get_pr_diff(owner, repo, pr_number)
            code_files = [
                CodeFile(
                    path=f["filename"],
                    diff=f["patch"],
                    additions=f["additions"],
                    deletions=f["deletions"],
                    language=self._detect_language(f["filename"]),
                )
                for f in raw_files
            ]
            self.logger.info(f"[FetcherAgent] Fetched {len(code_files)} code files")
            
            return {
                "pr_info": pr_info_dict,
                "code_files": [cf.model_dump() for cf in code_files],
                "fetch_error": None,
                "current_step": "fetcher_done",
            }
            
        except Exception as e:
            self.logger.error(f"[FetcherAgent] Error: {e}", exc_info=True)
            return {
                "fetch_error": str(e),
                "current_step": "fetcher_error",
            }
    
    def _detect_language(self, filename: str) -> str:
        """Detect programming language from filename extension."""
        ext_to_lang = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "jsx",
            ".tsx": "tsx",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".cs": "csharp",
            ".php": "php",
            ".rb": "ruby",
            ".swift": "swift",
            ".kt": "kotlin",
            ".sh": "bash",
            ".sql": "sql",
            ".html": "html",
            ".css": "css",
            ".vue": "vue",
            ".svelte": "svelte",
        }
        ext = os.path.splitext(filename)[1].lower()
        return ext_to_lang.get(ext, "unknown")
