"""Tests for autonomous behavior patterns."""

import pytest
from my_cli.core.prompts.autonomous_patterns import (
    get_pattern_for_query,
    get_autonomous_patterns,
    generate_workflow_guidance,
    get_enhanced_system_prompt_with_patterns,
    WorkflowType
)


class TestAutonomousPatterns:
    """Test autonomous behavior pattern detection and generation."""
    
    def test_get_autonomous_patterns_returns_all_workflow_types(self):
        """Test that all workflow types have patterns defined."""
        patterns = get_autonomous_patterns()
        
        expected_types = [
            WorkflowType.PROJECT_ANALYSIS,
            WorkflowType.CODE_REVIEW,
            WorkflowType.BUG_FIXING,
            WorkflowType.FEATURE_DEVELOPMENT,
            WorkflowType.TESTING,
            WorkflowType.SETUP_CONFIGURATION
        ]
        
        for workflow_type in expected_types:
            assert workflow_type in patterns
            assert len(patterns[workflow_type]) > 0
    
    def test_pattern_detection_project_analysis(self):
        """Test pattern detection for project analysis queries."""
        test_queries = [
            "what does this project do",
            "tell me about this project",
            "analyze this codebase",
            "What is this project about?",
            "PROJECT OVERVIEW",
            "help me understand this project"
        ]
        
        for query in test_queries:
            pattern = get_pattern_for_query(query)
            assert pattern is not None
            assert pattern.workflow_type == WorkflowType.PROJECT_ANALYSIS
    
    def test_pattern_detection_bug_fixing(self):
        """Test pattern detection for bug fixing queries."""
        test_queries = [
            "fix this bug",
            "debug this issue", 
            "there's an error in the code",
            "something is not working",
            "troubleshoot this problem",
            "Fix the bug please"
        ]
        
        for query in test_queries:
            pattern = get_pattern_for_query(query)
            assert pattern is not None
            assert pattern.workflow_type == WorkflowType.BUG_FIXING
    
    def test_pattern_detection_feature_development(self):
        """Test pattern detection for feature development queries."""
        test_queries = [
            "implement a new feature",
            "add feature to the app",
            "new feature request",
            "build feature xyz",
            "develop feature abc",
            "IMPLEMENT this please"
        ]
        
        for query in test_queries:
            pattern = get_pattern_for_query(query)
            assert pattern is not None
            assert pattern.workflow_type == WorkflowType.FEATURE_DEVELOPMENT
    
    def test_pattern_detection_testing(self):
        """Test pattern detection for testing queries."""
        test_queries = [
            "write tests for this",
            "create unit tests",
            "test this code",
            "add test coverage",
            "Write comprehensive tests"
        ]
        
        for query in test_queries:
            pattern = get_pattern_for_query(query)
            assert pattern is not None
            assert pattern.workflow_type == WorkflowType.TESTING
    
    def test_pattern_detection_code_review(self):
        """Test pattern detection for code review queries."""
        test_queries = [
            "review code in this file",
            "code review please", 
            "check implementation quality",
            "analyze code quality",
            "review changes made"
        ]
        
        for query in test_queries:
            pattern = get_pattern_for_query(query)
            assert pattern is not None
            assert pattern.workflow_type == WorkflowType.CODE_REVIEW
    
    def test_pattern_detection_setup_configuration(self):
        """Test pattern detection for setup/configuration queries."""
        test_queries = [
            "setup the project",
            "configure development environment",
            "initialize project",
            "create config files",
            "Setup everything please"
        ]
        
        for query in test_queries:
            pattern = get_pattern_for_query(query)
            assert pattern is not None
            assert pattern.workflow_type == WorkflowType.SETUP_CONFIGURATION
    
    def test_pattern_detection_no_match(self):
        """Test that unrelated queries don't match patterns."""
        test_queries = [
            "hello",
            "what's the weather",
            "random question",
            "just chatting",
            "tell me a joke"
        ]
        
        for query in test_queries:
            pattern = get_pattern_for_query(query)
            assert pattern is None
    
    def test_generate_workflow_guidance(self):
        """Test workflow guidance generation."""
        patterns = get_autonomous_patterns()
        project_pattern = patterns[WorkflowType.PROJECT_ANALYSIS][0]
        
        guidance = generate_workflow_guidance(project_pattern)
        
        # Check that guidance contains expected sections
        assert "Autonomous Workflow:" in guidance
        assert project_pattern.name in guidance
        assert "Description" in guidance
        assert "Required Tools" in guidance
        assert "Workflow Steps" in guidance
        assert "Safety Checks" in guidance
        assert "Execution Approach" in guidance
        
        # Check that workflow steps are numbered
        for i, step in enumerate(project_pattern.workflow_steps, 1):
            assert f"{i}." in guidance
        
        # Check that safety checks are included
        for check in project_pattern.safety_checks:
            assert check in guidance
    
    def test_enhanced_system_prompt_with_pattern(self):
        """Test enhanced system prompt generation with patterns."""
        base_prompt = "You are an AI assistant."
        patterns = get_autonomous_patterns()
        project_pattern = patterns[WorkflowType.PROJECT_ANALYSIS][0]
        
        enhanced_prompt = get_enhanced_system_prompt_with_patterns(
            base_prompt, project_pattern
        )
        
        # Should contain the base prompt
        assert base_prompt in enhanced_prompt
        
        # Should contain pattern-specific information
        assert "Detected Workflow Pattern" in enhanced_prompt
        assert project_pattern.name in enhanced_prompt
        assert "Workflow Steps" in enhanced_prompt
        assert "Execution Instructions" in enhanced_prompt
    
    def test_enhanced_system_prompt_without_pattern(self):
        """Test enhanced system prompt generation without patterns."""
        base_prompt = "You are an AI assistant."
        
        enhanced_prompt = get_enhanced_system_prompt_with_patterns(
            base_prompt, None
        )
        
        # Should return unchanged base prompt
        assert enhanced_prompt == base_prompt
    
    def test_pattern_has_required_attributes(self):
        """Test that all patterns have required attributes."""
        patterns = get_autonomous_patterns()
        
        for workflow_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                # Check required attributes exist
                assert hasattr(pattern, 'workflow_type')
                assert hasattr(pattern, 'name')
                assert hasattr(pattern, 'description')
                assert hasattr(pattern, 'trigger_patterns')
                assert hasattr(pattern, 'workflow_steps')
                assert hasattr(pattern, 'required_tools')
                assert hasattr(pattern, 'safety_checks')
                
                # Check attributes are not empty
                assert pattern.name
                assert pattern.description
                assert len(pattern.trigger_patterns) > 0
                assert len(pattern.workflow_steps) > 0
                assert len(pattern.required_tools) > 0
                assert len(pattern.safety_checks) > 0
                
                # Check workflow type matches
                assert pattern.workflow_type == workflow_type
    
    def test_pattern_tools_are_valid(self):
        """Test that pattern required tools are valid tool names."""
        patterns = get_autonomous_patterns()
        valid_tools = {
            "read_file", "write_file", "edit_file", 
            "list_directory", "run_shell_command"
        }
        
        for workflow_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                for tool in pattern.required_tools:
                    assert tool in valid_tools, f"Invalid tool '{tool}' in pattern '{pattern.name}'"
    
    def test_case_insensitive_pattern_matching(self):
        """Test that pattern matching is case insensitive."""
        # Test with different cases
        test_cases = [
            ("what does this project do", WorkflowType.PROJECT_ANALYSIS),
            ("WHAT DOES THIS PROJECT DO", WorkflowType.PROJECT_ANALYSIS),
            ("What Does This Project Do", WorkflowType.PROJECT_ANALYSIS),
            ("fix this bug", WorkflowType.BUG_FIXING),
            ("FIX THIS BUG", WorkflowType.BUG_FIXING),
            ("Fix This Bug", WorkflowType.BUG_FIXING)
        ]
        
        for query, expected_type in test_cases:
            pattern = get_pattern_for_query(query)
            assert pattern is not None
            assert pattern.workflow_type == expected_type