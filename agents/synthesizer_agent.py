"""
Synthesizer Agent - Generates the code review report (Markdown).

Responsibilities:
1. Take issues from state
2. Sort issues by severity
3. Generate Markdown review report (using LLM)
4. Output: report (ReviewReport)
"""
import os
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from agents.base_agent import BaseAgent
from graph.state import AgentState, ReviewReport, CodeIssue


class SynthesizerAgent(BaseAgent):
    """
    Agent that generates the code review report.
    
    Input state: issues, pr_info
    Output state: report, synthesis_error
    """
    
    def __init__(self, name: str = "synthesizer"):
        super().__init__(name)
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.client = OpenAI(api_key=self.deepseek_api_key, base_url=self.deepseek_base_url)
    
    async def run(self, state: AgentState) -> Dict[str, Any]:
        """
        Generate code review report from issues.
        
        Args:
            state: Current workflow state with issues and pr_info
            
        Returns:
            Updated state with report
        """
        self.logger.info("[SynthesizerAgent] Generating review report...")
        
        try:
            issues_data = state.get("issues", [])
            pr_info = state.get("pr_info", {})
            
            if not issues_data:
                # No issues found - generate a positive report
                report = ReviewReport(
                    pr_url=state.get("pr_url", ""),
                    summary="No major issues found. Code looks good!",
                    issues=[],
                    strengths=["Clean code", "No obvious bugs"],
                    overall_score=8.0,
                    report_markdown=self._generate_positive_report(pr_info),
                )
                return {
                    "report": report.model_dump(),
                    "synthesis_error": None,
                    "current_step": "synthesizer_done",
                }
            
            # Convert to CodeIssue objects
            issues = [CodeIssue(**i) for i in issues_data]
            
            # Sort by severity: critical > major > minor > info
            severity_order = {"critical": 0, "major": 1, "minor": 2, "info": 3}
            issues.sort(key=lambda x: severity_order.get(x.severity, 99))
            
            # Generate Markdown report using LLM
            report_markdown = await self._generate_report_with_llm(pr_info, issues)
            
            # Calculate overall score
            avg_severity = sum(
                {"critical": 1, "major": 3, "minor": 7, "info": 9}.get(i.severity, 5)
                for i in issues
            ) / len(issues) if issues else 8
            overall_score = max(1.0, min(10.0, avg_severity + 1.0))
            
            report = ReviewReport(
                pr_url=state.get("pr_url", ""),
                summary=f"Found {len(issues)} issues: {sum(1 for i in issues if i.severity in ['critical', 'major'])} critical/major",
                issues=issues,
                strengths=[],  # LLM will fill this
                overall_score=overall_score,
                report_markdown=report_markdown,
            )
            
            self.logger.info(f"[SynthesizerAgent] Report generated: {len(issues)} issues")
            
            return {
                "report": report.model_dump(),
                "synthesis_error": None,
                "current_step": "synthesizer_done",
            }
            
        except Exception as e:
            self.logger.error(f"[SynthesizerAgent] Error: {e}", exc_info=True)
            return {
                "report": None,
                "synthesis_error": str(e),
                "current_step": "synthesizer_error",
            }
    
    async def _generate_report_with_llm(self, pr_info: Dict, issues: List[CodeIssue]) -> str:
        """Generate Markdown report using DeepSeek LLM."""
        issues_json = json.dumps(
            [{"file": i.file, "line": i.line, "severity": i.severity, "category": i.category, "message": i.message, "suggestion": i.suggestion} for i in issues],
            ensure_ascii=False,
            indent=2
        )
        
        prompt = f"""You are a senior engineer writing a code review report.

PR Info:
- Title: {pr_info.get('title', 'N/A')}
- Author: {pr_info.get('author', 'N/A')}
- Branch: {pr_info.get('head_branch', 'N/A')} -> {pr_info.get('base_branch', 'N/A')}

Issues found ({len(issues)}):
```json
{issues_json}
```

Write a professional code review report in Markdown format. Structure:
1. **Summary**: Brief overview (2-3 sentences)
2. **Overall Assessment**: Score 1-10 with justification
3. **Critical/ Major Issues**: Must fix before merge
4. **Minor Issues**: Should fix but not blocking
5. **Positive Aspects**: What was done well

Use professional, constructive tone. Format as Markdown. Start with "# Code Review Report".

Output ONLY the Markdown report:"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=2000,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.warning(f"[SynthesizerAgent] LLM report generation failed: {e}")
            return self._fallback_report(pr_info, issues)
    
    def _fallback_report(self, pr_info: Dict, issues: List[CodeIssue]) -> str:
        """Generate a simple report without LLM."""
        lines = [
            "# Code Review Report",
            f"\n**PR**: {pr_info.get('title', 'N/A')}",
            f"**Author**: {pr_info.get('author', 'N/A')}",
            f"\n## Summary\nFound {len(issues)} issues.\n"
        ]
        for issue in issues:
            lines.append(f"- **{issue.severity.upper()}** `{issue.file}:{issue.line}` - {issue.message}")
            lines.append(f"  - Suggestion: {issue.suggestion}\n")
        return "\n".join(lines)
    
    def _generate_positive_report(self, pr_info: Dict) -> str:
        return f"""# Code Review Report

**PR**: {pr_info.get('title', 'N/A')}
**Author**: {pr_info.get('author', 'N/A')}

## Summary
No major issues found. Code looks clean and well-written.

## Overall Assessment
**Score: 8/10** - Good quality code.

## Positive Aspects
- Clean code structure
- No obvious bugs
- Good naming conventions

---
*Generated by CodeAgent Reviewer (AI)*"""
