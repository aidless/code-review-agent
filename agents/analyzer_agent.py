"""
Analyzer Agent - Analyzes code quality using static analysis + LLM.

Responsibilities:
1. Take code_files from state
2. Run static analysis (CodeAnalyzer)
3. Run LLM analysis (DeepSeek API) for deeper insights
4. Output: issues list
"""
import os
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from agents.base_agent import BaseAgent
from tools.code_analyzer import CodeAnalyzer
from graph.state import AgentState, CodeIssue


class AnalyzerAgent(BaseAgent):
    """
    Agent that analyzes code quality.
    
    Input state: code_files
    Output state: issues, analysis_error
    """
    
    def __init__(self, name: str = "analyzer"):
        super().__init__(name)
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.client = OpenAI(api_key=self.deepseek_api_key, base_url=self.deepseek_base_url)
    
    async def run(self, state: AgentState) -> Dict[str, Any]:
        """
        Analyze code files for quality issues.
        
        Args:
            state: Current workflow state with code_files
            
        Returns:
            Updated state with issues list
        """
        self.logger.info("[AnalyzerAgent] Starting code analysis...")
        
        try:
            code_files = state.get("code_files", [])
            if not code_files:
                return {
                    "issues": [],
                    "analysis_error": "No code files to analyze",
                    "current_step": "analyzer_done",
                }
            
            all_issues = []
            analyzer = CodeAnalyzer()
            
            for file_data in code_files:
                file_path = file_data.get("path", "unknown")
                file_diff = file_data.get("diff", "")
                file_lang = file_data.get("language", "unknown")
                
                self.logger.info(f"[AnalyzerAgent] Analyzing {file_path}...")
                
                # 1. Static analysis
                static_findings = analyzer.analyze_file(file_path, file_diff, file_lang)
                for finding in static_findings:
                    all_issues.append(CodeIssue(
                        file=file_path,
                        line=finding.line,
                        severity=finding.severity,
                        category=finding.category,
                        message=finding.message,
                        suggestion=finding.suggestion,
                        confidence=0.7,
                    ))
                
                # 2. LLM analysis (sample first 200 lines of diff to avoid token limits)
                diff_sample = "\n".join(file_diff.split("\n")[:200])
                llm_issues = await self._analyze_with_llm(file_path, diff_sample, file_lang)
                all_issues.extend(llm_issues)
            
            self.logger.info(f"[AnalyzerAgent] Found {len(all_issues)} issues total")
            
            return {
                "issues": [issue.model_dump() for issue in all_issues],
                "analysis_error": None,
                "current_step": "analyzer_done",
            }
            
        except Exception as e:
            self.logger.error(f"[AnalyzerAgent] Error: {e}", exc_info=True)
            return {
                "issues": [],
                "analysis_error": str(e),
                "current_step": "analyzer_error",
            }
    
    async def _analyze_with_llm(self, file_path: str, diff: str, language: str) -> List[CodeIssue]:
        """
        Use DeepSeek LLM to analyze code diff for issues.
        
        Returns list of CodeIssue objects.
        """
        prompt = f"""You are a senior software engineer doing code review.

File: {file_path}
Language: {language}

Code diff:
```
{diff}
```

Analyze this code diff and identify potential issues. Focus on:
1. Bugs (logic errors, edge cases)
2. Security issues (injection, XSS, etc.)
3. Performance problems (inefficient algorithms, memory leaks)
4. Code quality (readability, maintainability)

For each issue found, output a JSON object with keys:
- "line": line number (int or null)
- "severity": "critical" | "major" | "minor" | "info"
- "category": "bug" | "security" | "performance" | "style" | "documentation"
- "message": clear description of the issue
- "suggestion": how to fix it
- "confidence": 0.0-1.0

Output ONLY a JSON array of issue objects. If no issues found, output [].

JSON Array:"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000,
            )
            
            content = response.choices[0].message.content.strip()
            # Try to parse JSON
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            issues_data = json.loads(content)
            
            issues = []
            for item in issues_data:
                issues.append(CodeIssue(
                    file=file_path,
                    line=item.get("line"),
                    severity=item.get("severity", "minor"),
                    category=item.get("category", "style"),
                    message=item.get("message", ""),
                    suggestion=item.get("suggestion", ""),
                    confidence=item.get("confidence", 0.5),
                ))
            return issues
            
        except Exception as e:
            self.logger.warning(f"[AnalyzerAgent] LLM analysis failed for {file_path}: {e}")
            return []
