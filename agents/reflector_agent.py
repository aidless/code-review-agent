"""
Reflector Agent - Evaluates report quality, decides if retry is needed.

Responsibilities:
1. Take report from state
2. Use LLM to evaluate report quality (coverage, depth, actionability)
3. Score 1-10, if <7 then needs_replan=True
4. Output: reflection_score, needs_replan, reflection_feedback, reflection_count+1
"""
import os
import json
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from agents.base_agent import BaseAgent
from graph.state import AgentState


class ReflectorAgent(BaseAgent):
    """
    Agent that evaluates report quality and decides retry.
    
    Input state: report
    Output state: reflection_score, needs_replan, reflection_feedback, reflection_count
    """
    
    def __init__(self, name: str = "reflector"):
        super().__init__(name)
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.client = OpenAI(api_key=self.deepseek_api_key, base_url=self.deepseek_base_url)
    
    async def run(self, state: AgentState) -> Dict[str, Any]:
        """
        Evaluate report quality and decide if retry is needed.
        
        Args:
            state: Current workflow state with report
            
        Returns:
            Updated state with reflection results
        """
        self.logger.info("[ReflectorAgent] Evaluating report quality...")
        
        try:
            report_data = state.get("report")
            if not report_data:
                return {
                    "reflection_score": 5.0,
                    "needs_replan": True,
                    "reflection_feedback": "No report to evaluate",
                    "reflection_count": state.get("reflection_count", 0) + 1,
                    "current_step": "reflector_done",
                }
            
            # Evaluate report quality using LLM
            score, feedback = await self._evaluate_report(report_data)
            
            # Decision: if score < 7, needs replan
            needs_replan = score < 7.0
            
            self.logger.info(f"[ReflectorAgent] Score: {score}/10, needs_replan: {needs_replan}")
            
            return {
                "reflection_score": score,
                "needs_replan": needs_replan,
                "reflection_feedback": feedback,
                "reflection_count": state.get("reflection_count", 0) + 1,
                "current_step": "reflector_done",
            }
            
        except Exception as e:
            self.logger.error(f"[ReflectorAgent] Error: {e}", exc_info=True)
            return {
                "reflection_score": 5.0,
                "needs_replan": True,
                "reflection_feedback": f"Error during evaluation: {e}",
                "reflection_count": state.get("reflection_count", 0) + 1,
                "current_step": "reflector_error",
            }
    
    async def _evaluate_report(self, report_data: Dict) -> tuple[float, str]:
        """
        Use LLM to evaluate report quality.
        
        Returns:
            (score 1-10, feedback string)
        """
        report_markdown = report_data.get("report_markdown", "")
        issues = report_data.get("issues", [])
        
        prompt = f"""You are a code review quality evaluator.

Evaluate this code review report on a scale of 1-10 based on:
1. **Coverage** (1-10): Does it cover all important issues in the code?
2. **Depth** (1-10): Are the issue analyses deep enough (not superficial)?
3. **Actionability** (1-10): Are the suggestions specific and actionable?
4. **Clarity** (1-10): Is the report clear and well-organized?

Report to evaluate:
```markdown
{report_markdown[:3000]}
```

Issues found: {len(issues)} issues listed.

Output a JSON object:
```json
{{"score": 7.5, "feedback": "The report covers main issues but lacks depth in performance analysis..."}}
```

Output ONLY the JSON object:"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )
            content = response.choices[0].message.content.strip()
            
            # Parse JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result = json.loads(content)
            score = float(result.get("score", 5.0))
            feedback = result.get("feedback", "")
            
            return score, feedback
            
        except Exception as e:
            self.logger.warning(f"[ReflectorAgent] LLM evaluation failed: {e}")
            # Fallback: simple heuristic
            score = 7.0 if len(report_markdown) > 500 else 4.0
            feedback = "LLM evaluation failed, using heuristic"
            return score, feedback
