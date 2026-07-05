"""
LangGraph Workflow Definition for the Code Review Multi-Agent System.

This module defines the agent orchestration graph:
- Fetcher Agent: Fetch PR data from GitHub
- Analyzer Agent: Analyze code quality (static + LLM)
- Synthesizer Agent: Generate review report (Markdown)
- Reflector Agent: Evaluate report quality, decide retry
- Notifier Agent: Post report to GitHub PR
"""
from typing import Any, Dict, Literal
from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, END

from agents.fetcher_agent import FetcherAgent
from agents.analyzer_agent import AnalyzerAgent
from agents.synthesizer_agent import SynthesizerAgent
from agents.reflector_agent import ReflectorAgent
from agents.notifier_agent import NotifierAgent
from graph.state import AgentState


def create_workflow() -> Runnable:
    """
    Create the LangGraph workflow for code review.
    
    Flow:
    1. Fetcher -> Analyzer -> Synthesizer -> Reflector
    2. Reflector decides: if needs_replan, go back to Analyzer; else go to Notifier
    3. Notifier -> END
    
    Returns:
        Compiled LangGraph Runnable
    """
    # Create the state graph
    workflow = StateGraph(AgentState)
    
    # Add nodes (agents)
    workflow.add_node("fetcher", FetcherAgent(name="fetcher").run)
    workflow.add_node("analyzer", AnalyzerAgent(name="analyzer").run)
    workflow.add_node("synthesizer", SynthesizerAgent(name="synthesizer").run)
    workflow.add_node("reflector", ReflectorAgent(name="reflector").run)
    workflow.add_node("notifier", NotifierAgent(name="notifier").run)
    
    # Add edges (flow)
    # Start -> Fetcher
    workflow.set_entry_point("fetcher")
    
    # Fetcher -> Analyzer
    workflow.add_edge("fetcher", "analyzer")
    
    # Analyzer -> Synthesizer
    workflow.add_edge("analyzer", "synthesizer")
    
    # Synthesizer -> Reflector
    workflow.add_edge("synthesizer", "reflector")
    
    # Reflector -> conditional: if needs_replan, go to Analyzer; else go to Notifier
    workflow.add_conditional_edges(
        "reflector",
        _should_retry,
        {
            "retry": "analyzer",
            "continue": "notifier",
        }
    )
    
    # Notifier -> END
    workflow.add_edge("notifier", END)
    
    # Compile the graph
    return workflow.compile()


def _should_retry(state: AgentState) -> Literal["retry", "continue"]:
    """
    Conditional edge function: decide whether to retry analysis or continue to notification.
    
    Logic:
    - If needs_replan is True AND reflection_count < max_reflection_iterations: retry
    - Else: continue to notifier
    """
    if state.get("needs_replan", False) and state.get("reflection_count", 0) < state.get("max_reflection_iterations", 3):
        return "retry"
    return "continue"
