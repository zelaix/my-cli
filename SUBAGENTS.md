# Minimal Subagents Implementation Roadmap

## Overview

This document outlines a minimal implementation of subagents for the kimi-code project. The focus is on the core value proposition: **specialized system prompts for different types of development tasks**.

## What are Minimal Subagents?

Our minimal subagents implementation provides:

- **Specialized system prompts** for different task types (code review, debugging, etc.)
- **Automatic task delegation** based on simple pattern matching
- **Same tool access** as the main agent (no complex tool filtering)
- **Hardcoded built-in agents** (no external configuration needed)

### Core Value Proposition

Instead of having one generic system prompt for all tasks, subagents provide **task-specific expertise** through specialized prompts:

- **Code Review tasks** → Get a system prompt focused on security, quality, and best practices
- **Debugging tasks** → Get a systematic debugging-focused prompt with error analysis steps
- **General tasks** → Continue using the main agent's prompt

### Key Simplifications

1. **No Complex Configuration**: Subagents are hardcoded in the source code
2. **Simple Pattern Matching**: Use regex/keyword matching for task delegation
3. **Shared Tools**: All subagents use the same tools as the main agent
4. **No Registry System**: Just a few hardcoded subagent classes

## Integration Points

Our current system needs minimal changes:

1. **AgenticOrchestrator** - Add simple delegation check before normal processing
2. **System Prompt System** - Use subagent-specific prompts when delegated
3. **Existing Tools** - No changes needed, subagents use same tools

## Implementation Plan

### Single Phase Implementation (2-3 Days)

#### Step 1: Create Simple Subagent Classes
- **Goal**: Define basic subagent interface and built-in agents
- **Deliverables**:
  - `SimpleSubagent` class with name, description, and system_prompt
  - Hardcoded `CodeReviewerAgent` and `DebugSpecialistAgent`
  - Simple pattern matching for task identification

#### Step 2: Add Delegation Logic  
- **Goal**: Add delegation check to AgenticOrchestrator
- **Deliverables**:
  - Pattern matching function to detect task type
  - Delegation logic in `send_message()` method
  - Fallback to main agent for non-matching tasks

#### Step 3: Integration and Testing
- **Goal**: Test subagent delegation end-to-end
- **Deliverables**:
  - Test code review scenarios
  - Test debugging scenarios  
  - Verify main agent still handles general tasks

## Technical Design

### Simple Subagent Classes

```python
@dataclass
class SimpleSubagent:
    """Simple subagent with hardcoded configuration."""
    name: str
    description: str
    system_prompt: str
    trigger_patterns: List[str]
    
    def matches_task(self, task: str) -> bool:
        """Check if this subagent should handle the task."""
        task_lower = task.lower()
        return any(
            re.search(pattern, task_lower) 
            for pattern in self.trigger_patterns
        )

# Hardcoded built-in subagents
CODE_REVIEWER = SimpleSubagent(
    name="code-reviewer",
    description="Specialized code review and security analysis",
    system_prompt="""You are a senior code reviewer with expertise in security, performance, and maintainability.

Your review process:
1. Analyze code structure and patterns
2. Identify security vulnerabilities
3. Assess performance implications  
4. Check adherence to best practices
5. Provide prioritized, actionable feedback

Focus on the most impactful issues first. Be specific and constructive.""",
    trigger_patterns=[
        r"review.*code",
        r"check.*security", 
        r"analyze.*quality",
        r"audit.*code",
        r"code.*review"
    ]
)

DEBUG_SPECIALIST = SimpleSubagent(
    name="debug-specialist", 
    description="Systematic debugging and error resolution",
    system_prompt="""You are a debugging specialist with systematic problem-solving expertise.

Your debugging process:
1. Capture and analyze error details
2. Reproduce the issue systematically
3. Identify root cause through methodical investigation
4. Implement minimal, targeted fixes
5. Verify the solution works

Focus on understanding WHY the error occurs, not just fixing symptoms.""",
    trigger_patterns=[
        r"debug.*error",
        r"fix.*bug", 
        r"troubleshoot.*issue",
        r"analyze.*crash",
        r"investigate.*failure",
        r"error.*analysis"
    ]
)

BUILTIN_SUBAGENTS = [CODE_REVIEWER, DEBUG_SPECIALIST]
```

### Simple Delegation Logic

```python
class SimpleSubagentDelegator:
    """Simple pattern-based subagent delegation."""
    
    def __init__(self):
        self.subagents = BUILTIN_SUBAGENTS
    
    def find_matching_subagent(self, task: str) -> Optional[SimpleSubagent]:
        """Find the first subagent that matches the task."""
        for subagent in self.subagents:
            if subagent.matches_task(task):
                return subagent
        return None

    def should_delegate(self, task: str) -> bool:
        """Check if task should be delegated to a subagent."""
        return self.find_matching_subagent(task) is not None
```

### Integration with AgenticOrchestrator

```python
# Simple modification to existing AgenticOrchestrator
class AgenticOrchestrator:
    def __init__(self, *args, **kwargs):
        # ... existing initialization ...
        self.subagent_delegator = SimpleSubagentDelegator()
    
    async def send_message(self, message: str, **kwargs):
        """Enhanced message handling with simple subagent delegation."""
        # Check for subagent delegation
        if self.subagent_delegator.should_delegate(message):
            subagent = self.subagent_delegator.find_matching_subagent(message)
            if subagent:
                # Use subagent's system prompt instead of default
                kwargs['system_instruction'] = subagent.system_prompt
                # Optionally add indication in output
                if self.output_handler:
                    self.output_handler(f"🤖 Using {subagent.name} specialist...\n\n")
        
        # Continue with normal processing (using custom system prompt if delegated)
        return await super().send_message(message, **kwargs)
```

## Minimal File Structure

```
src/my_cli/core/subagents/
├── __init__.py
├── types.py               # SimpleSubagent class
├── builtin.py             # Hardcoded built-in subagents
└── delegator.py           # Simple delegation logic
```

## Usage Examples

### Code Review Task
```bash
# User input that triggers code reviewer subagent
my-cli chat "Please review the code in auth.py for security issues"

# Output:
🤖 Using code-reviewer specialist...

# Agent responds with specialized code review prompt focusing on:
# - Security vulnerabilities  
# - Code quality and maintainability
# - Performance implications
# - Best practices adherence
```

### Debugging Task
```bash  
# User input that triggers debug specialist subagent
my-cli chat "Debug this error: AttributeError in the login function"

# Output:
🤖 Using debug-specialist specialist...

# Agent responds with systematic debugging approach:
# - Error analysis and reproduction
# - Root cause investigation  
# - Minimal fix implementation
# - Solution verification
```

### General Task (No Delegation)
```bash
# User input that uses main agent
my-cli chat "Explain how async/await works in Python"

# Output: 
# (No specialist indicator, uses main agent's general system prompt)
```

## Testing Plan

### Simple Tests
- **Pattern Matching**: Verify subagent trigger patterns work correctly
- **Delegation Logic**: Test that correct subagents are selected for tasks
- **System Prompt Override**: Confirm custom system prompts are used
- **Fallback Behavior**: Ensure main agent handles non-matching tasks

### Test Cases
```python
# Test code review delegation
assert CODE_REVIEWER.matches_task("Please review this code for security issues")
assert CODE_REVIEWER.matches_task("Can you audit the authentication code?")

# Test debug specialist delegation  
assert DEBUG_SPECIALIST.matches_task("Debug this error in the login function")
assert DEBUG_SPECIALIST.matches_task("Fix the bug causing the crash")

# Test no delegation for general tasks
delegator = SimpleSubagentDelegator()
assert not delegator.should_delegate("Explain how Python works")
assert not delegator.should_delegate("What is machine learning?")
```

## Implementation Checklist

### Day 1: Core Structure
- [ ] Create `src/my_cli/core/subagents/` directory
- [ ] Implement `SimpleSubagent` class in `types.py`
- [ ] Define hardcoded subagents in `builtin.py`
- [ ] Create `SimpleSubagentDelegator` in `delegator.py`

### Day 2: Integration
- [ ] Modify `AgenticOrchestrator` to add delegation check
- [ ] Test pattern matching with sample inputs
- [ ] Verify system prompt override works
- [ ] Add user indication when subagent is used

### Day 3: Testing & Polish
- [ ] Test code review scenarios end-to-end
- [ ] Test debugging scenarios end-to-end
- [ ] Verify main agent still handles general tasks
- [ ] Add any necessary error handling

## Benefits of Minimal Implementation

1. **Quick Value**: Get specialized prompts working in 2-3 days
2. **Low Risk**: Minimal changes to existing codebase
3. **Easy to Understand**: Simple pattern matching logic
4. **Easy to Extend**: Adding new subagents is just adding to the list
5. **No Complex Dependencies**: No configuration files or external systems

## Future Extensions (Post-MVP)

Once the minimal implementation proves valuable, we can add:

1. **More Subagents**: Data analysis, testing, documentation specialists
2. **Better Pattern Matching**: More sophisticated task analysis
3. **Configuration Files**: External configuration for custom subagents
4. **Tool Filtering**: Restrict tools per subagent if needed
5. **Context Awareness**: Use conversation history for better delegation

## Conclusion

This minimal subagents implementation focuses on the core value: **providing specialized system prompts for different development tasks**. 

The approach is pragmatic:
- ✅ **2-3 days to implement**
- ✅ **Low risk and complexity**  
- ✅ **Immediate user value**
- ✅ **Easy to extend later**

By starting with this minimal implementation, we can quickly validate the concept and gather user feedback before investing in more complex features.