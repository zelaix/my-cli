"""
Minimal subagents implementation for specialized task handling.

This module provides simple subagent functionality focused on the core value:
specialized system prompts for different types of development tasks.
"""

from .types import SimpleSubagent
from .builtin import BUILTIN_SUBAGENTS, CODE_REVIEWER, DEBUG_SPECIALIST
from .delegator import SimpleSubagentDelegator

__all__ = [
    'SimpleSubagent',
    'BUILTIN_SUBAGENTS', 
    'CODE_REVIEWER',
    'DEBUG_SPECIALIST',
    'SimpleSubagentDelegator'
]