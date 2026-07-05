"""
Base Agent class for the Code Review Multi-Agent System.
All agents inherit from this base class.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the Code Review system.
    
    Each agent has:
    - A name (for logging/debugging)
    - A run() method (the main execution logic)
    - Access to shared state
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent's main logic.
        
        Args:
            state: The current state of the LangGraph workflow.
                   Each agent reads from and writes to this state.
        
        Returns:
            Updated state dictionary with the agent's contributions.
        """
        pass
    
    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"
