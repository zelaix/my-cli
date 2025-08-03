#!/usr/bin/env python3
"""
Demonstration script for the new subagents feature.
Shows how different types of tasks are automatically delegated to specialized agents.
"""

import sys
sys.path.append('src')

from my_cli.core.subagents import SimpleSubagentDelegator, CODE_REVIEWER, DEBUG_SPECIALIST

def demo_subagents():
    """Demonstrate the subagents feature with example tasks."""
    
    print("🤖 Subagents Feature Demo")
    print("=" * 50)
    print()
    
    # Initialize delegator
    delegator = SimpleSubagentDelegator()
    
    print("📋 Available Specialists:")
    for subagent in delegator.get_available_subagents():
        print(f"  • {subagent.name}: {subagent.description}")
    print()
    
    # Example tasks that demonstrate delegation
    demo_tasks = [
        # Code review tasks (should trigger code-reviewer)
        ("Code Review", "Please review the authentication code for security vulnerabilities"),
        ("Security Audit", "Audit this code for potential security issues"),
        ("Quality Check", "Analyze the code quality in the user management module"),
        
        # Debug tasks (should trigger debug-specialist)  
        ("Error Debug", "Debug this AttributeError: 'NoneType' object has no attribute 'username'"),
        ("Bug Fix", "Fix the bug causing the application to crash on startup"),
        ("Issue Investigation", "Investigate the failure in the payment processing system"),
        
        # General tasks (should use main agent)
        ("General Question", "Explain how dependency injection works"),
        ("Documentation", "Write documentation for the API endpoints"),
        ("Feature Request", "Create a new user registration form")
    ]
    
    print("🎯 Task Delegation Examples:")
    print()
    
    for category, task in demo_tasks:
        subagent = delegator.find_matching_subagent(task)
        
        if subagent:
            specialist = f"🤖 {subagent.name}"
            indicator = "🎯"
        else:
            specialist = "🤖 main-agent"
            indicator = "🔄"
        
        print(f"{indicator} {category}")
        print(f"   Task: \"{task}\"")
        print(f"   → Delegated to: {specialist}")
        print()
    
    print("🔍 Pattern Analysis:")
    print()
    
    print("📋 Code Reviewer Patterns:")
    for pattern in CODE_REVIEWER.trigger_patterns:
        print(f"   • {pattern}")
    print()
    
    print("🐛 Debug Specialist Patterns:")
    for pattern in DEBUG_SPECIALIST.trigger_patterns:
        print(f"   • {pattern}")
    print()
    
    print("✨ Key Benefits:")
    print("  • Specialized system prompts for different task types")
    print("  • Automatic task delegation based on pattern matching")  
    print("  • Code review tasks get security-focused prompts")
    print("  • Debug tasks get systematic debugging methodology")
    print("  • General tasks continue using the main agent")
    print("  • No configuration files needed - everything is built-in")
    print()
    
    print("🚀 Usage:")
    print("  my-cli chat \"Review this code for security issues\"  # → code-reviewer")
    print("  my-cli chat \"Debug this error message\"             # → debug-specialist") 
    print("  my-cli chat \"Explain how Python works\"            # → main-agent")

if __name__ == "__main__":
    demo_subagents()