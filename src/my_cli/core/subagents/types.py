"""
Core types for minimal subagent implementation.
"""

import re
from dataclasses import dataclass
from typing import List


@dataclass
class SimpleSubagent:
    """Simple subagent with hardcoded configuration."""
    name: str
    description: str
    system_prompt: str
    trigger_patterns: List[str]
    
    def matches_task(self, task: str) -> bool:
        """
        Check if this subagent should handle the task.
        
        Args:
            task: The user's task/message to analyze
            
        Returns:
            True if this subagent should handle the task
        """
        task_lower = task.lower()
        return any(
            re.search(pattern, task_lower, re.IGNORECASE) 
            for pattern in self.trigger_patterns
        )
    
    def __str__(self) -> str:
        """String representation of the subagent."""
        return f"SimpleSubagent(name='{self.name}', patterns={len(self.trigger_patterns)})"
    
    def __repr__(self) -> str:
        """Detailed representation of the subagent."""
        return (f"SimpleSubagent(name='{self.name}', "
                f"description='{self.description[:50]}...', "
                f"patterns={self.trigger_patterns})")