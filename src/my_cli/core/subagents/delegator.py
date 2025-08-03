"""
Simple pattern-based subagent delegation logic.
"""

import logging
from typing import Optional

from .builtin import BUILTIN_SUBAGENTS
from .types import SimpleSubagent

logger = logging.getLogger(__name__)


class SimpleSubagentDelegator:
    """Simple pattern-based subagent delegation."""
    
    def __init__(self):
        """Initialize delegator with built-in subagents."""
        self.subagents = BUILTIN_SUBAGENTS
        logger.info(f"Initialized subagent delegator with {len(self.subagents)} subagents: "
                   f"{[s.name for s in self.subagents]}")
    
    def find_matching_subagent(self, task: str) -> Optional[SimpleSubagent]:
        """
        Find the first subagent that matches the task.
        
        Args:
            task: The user's task/message to analyze
            
        Returns:
            SimpleSubagent instance if a match is found, None otherwise
        """
        if not task or not task.strip():
            return None
            
        task = task.strip()
        
        for subagent in self.subagents:
            if subagent.matches_task(task):
                logger.info(f"Task '{task[:50]}...' matched subagent: {subagent.name}")
                return subagent
        
        logger.debug(f"No subagent match found for task: '{task[:100]}...'")
        return None

    def should_delegate(self, task: str) -> bool:
        """
        Check if task should be delegated to a subagent.
        
        Args:
            task: The user's task/message to analyze
            
        Returns:
            True if task should be delegated to a subagent
        """
        return self.find_matching_subagent(task) is not None
    
    def get_available_subagents(self) -> list[SimpleSubagent]:
        """
        Get list of all available subagents.
        
        Returns:
            List of SimpleSubagent instances
        """
        return self.subagents.copy()
    
    def get_subagent_info(self) -> dict[str, str]:
        """
        Get information about all available subagents.
        
        Returns:
            Dictionary mapping subagent names to descriptions
        """
        return {
            subagent.name: subagent.description 
            for subagent in self.subagents
        }
    
    def test_task_patterns(self, test_tasks: list[str]) -> dict[str, Optional[str]]:
        """
        Test multiple tasks against subagent patterns for debugging.
        
        Args:
            test_tasks: List of tasks to test
            
        Returns:
            Dictionary mapping tasks to matched subagent names (or None)
        """
        results = {}
        for task in test_tasks:
            subagent = self.find_matching_subagent(task)
            results[task] = subagent.name if subagent else None
        return results