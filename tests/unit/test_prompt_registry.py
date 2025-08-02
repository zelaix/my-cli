"""
Tests for the prompt registry system.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch

from my_cli.prompts.registry import PromptRegistry, PromptTemplate, PromptType


class TestPromptTemplate:
    """Test the PromptTemplate class."""
    
    @pytest.fixture
    def template(self):
        return PromptTemplate(
            name="test_template",
            type=PromptType.USER,
            template="Hello {name}, you have {count} messages.",
            description="Test template",
            variables=["name", "count"]
        )
    
    def test_template_initialization(self, template):
        """Test template is initialized correctly."""
        assert template.name == "test_template"
        assert template.type == PromptType.USER
        assert template.template == "Hello {name}, you have {count} messages."
        assert template.description == "Test template"
        assert template.variables == ["name", "count"]
        assert template.source == "builtin"
    
    def test_render_with_all_variables(self, template):
        """Test rendering with all variables provided."""
        result = template.render(name="Alice", count=5)
        assert result == "Hello Alice, you have 5 messages."
    
    def test_render_with_missing_variable(self, template):
        """Test rendering with missing variable."""
        result = template.render(name="Alice")
        # Should return original template when variable is missing
        assert result == "Hello {name}, you have {count} messages."
    
    def test_render_with_extra_variables(self, template):
        """Test rendering with extra variables."""
        result = template.render(name="Alice", count=5, extra="ignored")
        assert result == "Hello Alice, you have 5 messages."
    
    def test_render_with_type_conversion(self, template):
        """Test rendering with automatic type conversion."""
        result = template.render(name="Alice", count="5")
        assert result == "Hello Alice, you have 5 messages."


class TestPromptRegistry:
    """Test the PromptRegistry class."""
    
    @pytest.fixture
    def registry(self):
        return PromptRegistry()
    
    def test_builtin_prompts_loaded(self, registry):
        """Test that built-in prompts are loaded on initialization."""
        prompts = registry.get_all_prompts()
        assert len(prompts) > 0
        
        # Check for specific built-in prompts
        assert "system_base" in prompts
        assert "tool_confirmation" in prompts
        assert "file_context" in prompts
    
    def test_register_prompt(self, registry):
        """Test registering a new prompt."""
        result = registry.register_prompt(
            name="test_prompt",
            template="Test template with {variable}",
            prompt_type=PromptType.USER,
            description="Test description",
            variables=["variable"]
        )
        
        assert result is True
        prompt = registry.get_prompt("test_prompt")
        assert prompt is not None
        assert prompt.name == "test_prompt"
        assert prompt.template == "Test template with {variable}"
        assert prompt.type == PromptType.USER
    
    def test_register_prompt_auto_extract_variables(self, registry):
        """Test automatic variable extraction."""
        registry.register_prompt(
            name="auto_vars",
            template="Hello {name}, welcome to {place}!",
            prompt_type=PromptType.USER
        )
        
        prompt = registry.get_prompt("auto_vars")
        assert set(prompt.variables) == {"name", "place"}
    
    def test_register_duplicate_prompt(self, registry):
        """Test registering a duplicate prompt."""
        registry.register_prompt(
            name="duplicate",
            template="First template",
            prompt_type=PromptType.USER
        )
        
        # Should overwrite with warning
        result = registry.register_prompt(
            name="duplicate",
            template="Second template",
            prompt_type=PromptType.USER
        )
        
        assert result is True
        prompt = registry.get_prompt("duplicate")
        assert prompt.template == "Second template"
    
    def test_get_nonexistent_prompt(self, registry):
        """Test getting a non-existent prompt."""
        prompt = registry.get_prompt("nonexistent")
        assert prompt is None
    
    def test_render_prompt(self, registry):
        """Test rendering a prompt through registry."""
        registry.register_prompt(
            name="render_test",
            template="Hello {name}!",
            prompt_type=PromptType.USER
        )
        
        result = registry.render_prompt("render_test", name="World")
        assert result == "Hello World!"
    
    def test_render_nonexistent_prompt(self, registry):
        """Test rendering a non-existent prompt."""
        result = registry.render_prompt("nonexistent", name="test")
        assert result is None
    
    def test_get_prompts_by_type(self, registry):
        """Test getting prompts by type."""
        registry.register_prompt("user1", "template", PromptType.USER)
        registry.register_prompt("user2", "template", PromptType.USER)
        registry.register_prompt("system1", "template", PromptType.SYSTEM)
        
        user_prompts = registry.get_prompts_by_type(PromptType.USER)
        system_prompts = registry.get_prompts_by_type(PromptType.SYSTEM)
        
        user_names = [p.name for p in user_prompts]
        system_names = [p.name for p in system_prompts]
        
        assert "user1" in user_names
        assert "user2" in user_names
        assert "system1" in system_names
        assert "system1" not in user_names
    
    def test_unregister_prompt(self, registry):
        """Test unregistering a prompt."""
        registry.register_prompt("to_remove", "template", PromptType.USER)
        assert registry.get_prompt("to_remove") is not None
        
        result = registry.unregister_prompt("to_remove")
        assert result is True
        assert registry.get_prompt("to_remove") is None
    
    def test_unregister_nonexistent_prompt(self, registry):
        """Test unregistering a non-existent prompt."""
        result = registry.unregister_prompt("nonexistent")
        assert result is False
    
    def test_register_processor(self, registry):
        """Test registering a prompt processor."""
        def test_processor(kwargs):
            kwargs["processed"] = True
            return kwargs
        
        registry.register_prompt("with_processor", "Hello {name}!", PromptType.USER)
        registry.register_processor("with_processor", test_processor)
        
        result = registry.render_prompt("with_processor", name="World")
        assert result == "Hello World!"
    
    def test_processor_error_handling(self, registry):
        """Test processor error handling."""
        def failing_processor(kwargs):
            raise ValueError("Processor failed")
        
        registry.register_prompt("with_failing_processor", "Hello {name}!", PromptType.USER)
        registry.register_processor("with_failing_processor", failing_processor)
        
        # Should still render even if processor fails
        result = registry.render_prompt("with_failing_processor", name="World")
        assert result == "Hello World!"
    
    @pytest.mark.asyncio
    async def test_load_prompts_from_file(self, registry):
        """Test loading prompts from a JSON file."""
        prompts_data = {
            "prompts": [
                {
                    "name": "file_prompt_1",
                    "template": "Template 1 with {var1}",
                    "type": "user",
                    "description": "First prompt from file",
                    "variables": ["var1"]
                },
                {
                    "name": "file_prompt_2",
                    "template": "Template 2 with {var2}",
                    "type": "system",
                    "description": "Second prompt from file"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(prompts_data, f)
            temp_path = Path(f.name)
        
        try:
            count = await registry.load_prompts_from_file(temp_path)
            assert count == 2
            
            prompt1 = registry.get_prompt("file_prompt_1")
            prompt2 = registry.get_prompt("file_prompt_2")
            
            assert prompt1 is not None
            assert prompt2 is not None
            assert prompt1.type == PromptType.USER
            assert prompt2.type == PromptType.SYSTEM
            
        finally:
            temp_path.unlink()
    
    @pytest.mark.asyncio
    async def test_load_prompts_from_invalid_file(self, registry):
        """Test loading prompts from invalid file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json")
            temp_path = Path(f.name)
        
        try:
            count = await registry.load_prompts_from_file(temp_path)
            assert count == 0
        finally:
            temp_path.unlink()
    
    @pytest.mark.asyncio
    async def test_load_prompts_from_directory(self, registry):
        """Test loading prompts from directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test JSON files
            prompts1 = {"prompts": [{"name": "dir_prompt_1", "template": "Template 1", "type": "user"}]}
            prompts2 = {"prompts": [{"name": "dir_prompt_2", "template": "Template 2", "type": "system"}]}
            
            (temp_path / "prompts1.json").write_text(json.dumps(prompts1))
            (temp_path / "prompts2.json").write_text(json.dumps(prompts2))
            
            count = await registry.load_prompts_from_directory(temp_path)
            assert count == 2
            
            assert registry.get_prompt("dir_prompt_1") is not None
            assert registry.get_prompt("dir_prompt_2") is not None
    
    def test_extract_variables(self, registry):
        """Test variable extraction from templates."""
        # Access private method for testing
        variables = registry._extract_variables("Hello {name}, you have {count} {items}!")
        assert set(variables) == {"name", "count", "items"}
        
        # Test with no variables
        no_vars = registry._extract_variables("Hello world!")
        assert no_vars == []
        
        # Test with duplicate variables
        dup_vars = registry._extract_variables("{name} says hello to {name}")
        assert variables.count("name") == 1  # Should be deduplicated
    
    def test_get_stats(self, registry):
        """Test getting registry statistics."""
        registry.register_prompt("test1", "template", PromptType.USER, source="custom")
        registry.register_prompt("test2", "template", PromptType.SYSTEM, source="custom")
        
        stats = registry.get_stats()
        
        assert stats['total_prompts'] > 2  # Includes built-ins
        assert stats['sources']['builtin'] > 0
        assert stats['sources']['custom'] == 2
        assert stats['types']['user'] > 0
        assert stats['types']['system'] > 0
        assert stats['processors'] == 0