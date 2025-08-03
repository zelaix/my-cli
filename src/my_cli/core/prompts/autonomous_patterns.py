"""
Autonomous behavior patterns for My CLI agent workflows.

This module defines specific autonomous behavior patterns that the AI agent
should follow for different types of tasks, building upon the core system prompt.
"""

from typing import Dict, List, Optional
from enum import Enum


class WorkflowType(Enum):
    """Types of autonomous workflows."""
    PROJECT_ANALYSIS = "project_analysis"
    CODE_REVIEW = "code_review"
    BUG_FIXING = "bug_fixing"
    FEATURE_DEVELOPMENT = "feature_development"
    REFACTORING = "refactoring"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    SETUP_CONFIGURATION = "setup_configuration"


class AutonomousPattern:
    """Represents an autonomous behavior pattern for specific workflows."""
    
    def __init__(
        self,
        workflow_type: WorkflowType,
        name: str,
        description: str,
        trigger_patterns: List[str],
        workflow_steps: List[str],
        required_tools: List[str],
        safety_checks: List[str]
    ):
        self.workflow_type = workflow_type
        self.name = name
        self.description = description
        self.trigger_patterns = trigger_patterns
        self.workflow_steps = workflow_steps
        self.required_tools = required_tools
        self.safety_checks = safety_checks


def get_autonomous_patterns() -> Dict[WorkflowType, List[AutonomousPattern]]:
    """Get all defined autonomous behavior patterns."""
    patterns = {}
    
    # Project Analysis Patterns
    patterns[WorkflowType.PROJECT_ANALYSIS] = [
        AutonomousPattern(
            workflow_type=WorkflowType.PROJECT_ANALYSIS,
            name="Project Discovery",
            description="Automatically discover and analyze project structure and purpose",
            trigger_patterns=[
                "what does this project do",
                "tell me about this project",
                "analyze this codebase",
                "what is this project",
                "project overview",
                "understand this project"
            ],
            workflow_steps=[
                "Use list_directory to explore project root structure",
                "Read README.md, package.json, pyproject.toml, or similar config files",
                "Identify main source directories and entry points",
                "Read key source files to understand functionality",
                "Analyze dependencies and tech stack",
                "Provide comprehensive project summary"
            ],
            required_tools=["list_directory", "read_file"],
            safety_checks=["Only read files, never modify during analysis"]
        ),
        
        AutonomousPattern(
            workflow_type=WorkflowType.PROJECT_ANALYSIS,
            name="Architecture Analysis",  
            description="Deep dive into project architecture and design patterns",
            trigger_patterns=[
                "analyze the architecture",
                "how is this code organized",
                "explain the project structure",
                "code architecture review"
            ],
            workflow_steps=[
                "Map directory structure and module organization",
                "Identify architectural patterns (MVC, microservices, etc.)",
                "Analyze data flow and dependencies",
                "Review design patterns and coding standards",
                "Identify potential architectural improvements"
            ],
            required_tools=["list_directory", "read_file"],
            safety_checks=["Read-only analysis, no code modifications"]
        )
    ]
    
    # Code Review Patterns
    patterns[WorkflowType.CODE_REVIEW] = [
        AutonomousPattern(
            workflow_type=WorkflowType.CODE_REVIEW,
            name="Automated Code Review",
            description="Comprehensive code review with best practices analysis",
            trigger_patterns=[
                "review code",
                "code review",
                "check implementation",
                "code quality",
                "review changes"
            ],
            workflow_steps=[
                "Read the target files or recent changes",
                "Analyze code style and conventions",
                "Check for security vulnerabilities",
                "Review error handling and edge cases",
                "Verify documentation and comments",
                "Suggest improvements and optimizations"
            ],
            required_tools=["read_file", "list_directory"],
            safety_checks=["Review only, no automatic fixes without explicit approval"]
        )
    ]
    
    # Bug Fixing Patterns
    patterns[WorkflowType.BUG_FIXING] = [
        AutonomousPattern(
            workflow_type=WorkflowType.BUG_FIXING,
            name="Systematic Bug Investigation",
            description="Methodical approach to bug diagnosis and fixing",
            trigger_patterns=[
                "fix",
                "debug",
                "error",
                "not working",
                "troubleshoot",
                "bug"
            ],
            workflow_steps=[
                "Reproduce the error by understanding the context",
                "Read relevant source files to understand the problem area",
                "Identify root cause through code analysis",
                "Develop and test a fix",
                "Run tests to verify the fix works",
                "Check for regression issues"
            ],
            required_tools=["read_file", "edit_file", "run_shell_command", "list_directory"],
            safety_checks=[
                "Always run tests after making changes",
                "Create backup before modifying critical files",
                "Verify fix doesn't break existing functionality"
            ]
        )
    ]
    
    # Feature Development Patterns
    patterns[WorkflowType.FEATURE_DEVELOPMENT] = [
        AutonomousPattern(
            workflow_type=WorkflowType.FEATURE_DEVELOPMENT,
            name="Feature Implementation Workflow",
            description="End-to-end feature development with testing",
            trigger_patterns=[
                "implement",
                "add feature",
                "new feature",
                "build feature",
                "develop feature"
            ],
            workflow_steps=[
                "Understand requirements and scope",
                "Analyze existing codebase for integration points",
                "Design the implementation approach",
                "Create/modify necessary files",
                "Write comprehensive tests",
                "Run tests and verify functionality",
                "Update documentation if needed"
            ],
            required_tools=["read_file", "write_file", "edit_file", "run_shell_command", "list_directory"],
            safety_checks=[
                "Follow existing code conventions",
                "Write tests for new functionality",
                "Verify integration with existing code",
                "Run full test suite before completion"
            ]
        )
    ]
    
    # Testing Patterns
    patterns[WorkflowType.TESTING] = [
        AutonomousPattern(
            workflow_type=WorkflowType.TESTING,
            name="Comprehensive Test Creation",
            description="Generate thorough test suites for code coverage",
            trigger_patterns=[
                "write tests",
                "create tests",
                "test",
                "coverage"
            ],
            workflow_steps=[
                "Analyze the code to understand functionality",
                "Identify test scenarios (happy path, edge cases, errors)",
                "Examine existing test patterns and frameworks",
                "Write comprehensive test cases",
                "Run tests to verify they work correctly",
                "Check test coverage and add missing tests"
            ],
            required_tools=["read_file", "write_file", "run_shell_command", "list_directory"],
            safety_checks=[
                "Follow existing test conventions",
                "Ensure tests are independent and repeatable",
                "Verify tests catch intended edge cases"
            ]
        )
    ]
    
    # Setup/Configuration Patterns
    patterns[WorkflowType.SETUP_CONFIGURATION] = [
        AutonomousPattern(
            workflow_type=WorkflowType.SETUP_CONFIGURATION,
            name="Project Setup Automation",
            description="Automate project configuration and setup tasks",
            trigger_patterns=[
                "setup",
                "configure",
                "initialize",
                "config files",
                "development environment"
            ],
            workflow_steps=[
                "Understand the desired setup requirements",
                "Check existing configuration files",
                "Create or update configuration files",
                "Set up development dependencies",
                "Initialize necessary directories and files",
                "Verify setup works correctly"
            ],
            required_tools=["read_file", "write_file", "run_shell_command", "list_directory"],
            safety_checks=[
                "Don't overwrite existing configurations without approval",
                "Verify commands are safe before execution",
                "Create backups of existing configs"
            ]
        )
    ]
    
    return patterns


def get_pattern_for_query(query: str) -> Optional[AutonomousPattern]:
    """
    Find the most appropriate autonomous pattern for a given query.
    
    Args:
        query: User query string
        
    Returns:
        Matching AutonomousPattern or None if no match found
    """
    query_lower = query.lower()
    all_patterns = get_autonomous_patterns()
    
    # Collect all matches with their trigger length (for prioritization)
    matches = []
    
    for workflow_type, patterns in all_patterns.items():
        for pattern in patterns:
            for trigger in pattern.trigger_patterns:
                if trigger.lower() in query_lower:
                    matches.append((pattern, len(trigger), trigger))
    
    if not matches:
        return None
    
    # Sort by trigger length (descending) to prioritize longer, more specific matches
    matches.sort(key=lambda x: x[1], reverse=True)
    
    # Return the pattern with the longest matching trigger
    return matches[0][0]


def generate_workflow_guidance(pattern: AutonomousPattern) -> str:
    """
    Generate specific workflow guidance for an autonomous pattern.
    
    Args:
        pattern: The autonomous pattern to generate guidance for
        
    Returns:
        Formatted workflow guidance string
    """
    guidance = f"""
# Autonomous Workflow: {pattern.name}

## Description
{pattern.description}

## Required Tools
{', '.join(pattern.required_tools)}

## Workflow Steps
"""
    
    for i, step in enumerate(pattern.workflow_steps, 1):
        guidance += f"{i}. {step}\n"
    
    guidance += "\n## Safety Checks\n"
    for check in pattern.safety_checks:
        guidance += f"- {check}\n"
    
    guidance += f"""
## Execution Approach
Follow the workflow steps systematically. Use the required tools proactively to gather information and complete the task. Always prioritize safety checks and get user confirmation for destructive operations.
"""
    
    return guidance.strip()


def get_enhanced_system_prompt_with_patterns(
    base_system_prompt: str,
    detected_pattern: Optional[AutonomousPattern] = None
) -> str:
    """
    Enhance the base system prompt with specific autonomous pattern guidance.
    
    Args:
        base_system_prompt: The core system prompt
        detected_pattern: Optional detected autonomous pattern
        
    Returns:
        Enhanced system prompt with pattern-specific guidance
    """
    if not detected_pattern:
        return base_system_prompt
    
    pattern_guidance = generate_workflow_guidance(detected_pattern)
    
    enhanced_prompt = f"""{base_system_prompt}

# Detected Workflow Pattern

{pattern_guidance}

# Execution Instructions

You have been provided with a specific autonomous workflow pattern that matches the user's request. Follow the workflow steps systematically while adhering to all safety checks. Use the required tools proactively and maintain focus on completing the full workflow unless the user requests otherwise.
"""
    
    return enhanced_prompt