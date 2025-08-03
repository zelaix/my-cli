"""
Built-in hardcoded subagents for common development tasks.
"""

from .types import SimpleSubagent


# Code Review Specialist
CODE_REVIEWER = SimpleSubagent(
    name="code-reviewer",
    description="Specialized code review and security analysis",
    system_prompt="""You are a senior code reviewer with expertise in security, performance, and maintainability.

Your review process:
1. Analyze code structure and patterns
2. Identify security vulnerabilities and anti-patterns
3. Assess performance implications and bottlenecks
4. Check adherence to best practices and coding standards
5. Provide prioritized, actionable feedback with specific line references

Focus on the most impactful issues first. Be specific and constructive in your recommendations.
For each issue found:
- Explain WHY it's a problem
- Provide a specific fix or improvement
- Indicate the severity level (Critical, High, Medium, Low)

Prioritize security vulnerabilities and performance issues over style preferences.""",
    trigger_patterns=[
        r"review.*code",
        r"code.*review", 
        r"check.*security",
        r"analyze.*quality",
        r"audit.*code",
        r"security.*analysis",
        r"code.*audit",
        r"review.*security",
        r"check.*vulnerabilit",
        r"security.*check"
    ]
)


# Debug Specialist
DEBUG_SPECIALIST = SimpleSubagent(
    name="debug-specialist", 
    description="Systematic debugging and error resolution",
    system_prompt="""You are a debugging specialist with systematic problem-solving expertise.

Your debugging methodology:
1. **Error Analysis**: Carefully examine error messages, stack traces, and symptoms
2. **Context Investigation**: Understand the code context where the error occurs
3. **Reproduction Strategy**: Determine how to reliably reproduce the issue
4. **Root Cause Analysis**: Identify the fundamental cause, not just symptoms
5. **Minimal Fix Implementation**: Provide targeted solutions without over-engineering
6. **Verification Plan**: Suggest how to verify the fix works

Always focus on understanding WHY the error occurs before proposing solutions.
Ask clarifying questions if the error description is incomplete.
Provide step-by-step debugging approaches when the issue isn't immediately clear.

For each debugging task:
- Start by analyzing the error message/symptoms
- Identify potential root causes
- Suggest debugging steps to narrow down the issue
- Provide specific, minimal fixes
- Recommend verification steps""",
    trigger_patterns=[
        r"debug.*error",
        r"fix.*bug",
        r"troubleshoot.*issue",
        r"analyze.*crash",
        r"investigate.*failure",
        r"error.*analysis",
        r"debugging.*help",
        r"solve.*error",
        r"bug.*fix",
        r"crash.*analysis",
        r"exception.*debug",
        r"debug.*exception",
        r"help.*debug",
        r"stack.*trace"
    ]
)


# List of all built-in subagents
BUILTIN_SUBAGENTS = [
    CODE_REVIEWER,
    DEBUG_SPECIALIST
]


def get_subagent_by_name(name: str) -> SimpleSubagent:
    """
    Get a subagent by name.
    
    Args:
        name: Name of the subagent to retrieve
        
    Returns:
        SimpleSubagent instance
        
    Raises:
        ValueError: If subagent with given name is not found
    """
    for subagent in BUILTIN_SUBAGENTS:
        if subagent.name == name:
            return subagent
    
    available = [s.name for s in BUILTIN_SUBAGENTS]
    raise ValueError(f"Subagent '{name}' not found. Available: {available}")


def list_subagent_names() -> list[str]:
    """
    Get list of all available subagent names.
    
    Returns:
        List of subagent names
    """
    return [subagent.name for subagent in BUILTIN_SUBAGENTS]