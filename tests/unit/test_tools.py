"""
Tests for the tool system components.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any

from my_cli.tools.base import (
    Tool, BaseTool, ReadOnlyTool, ModifyingTool, ToolResult, 
    Icon, ToolConfirmationOutcome, ToolConfirmationDetails
)
from my_cli.tools.registry import ToolRegistry, ToolMetadata


class SampleTool(BaseTool):
    """Sample tool implementation for testing."""
    
    def __init__(self):
        super().__init__(
            name="test_tool",
            display_name="Test Tool",
            description="A tool for testing",
            icon=Icon.HAMMER
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        return self.create_result(
            content=f"Executed test tool with params: {params}",
            summary="Test execution completed"
        )


class SampleReadOnlyTool(ReadOnlyTool):
    """Sample read-only tool for testing."""
    
    def __init__(self):
        super().__init__(
            name="readonly_tool",
            display_name="Read Only Tool", 
            description="A read-only test tool",
            icon=Icon.FILE_SEARCH
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        return self.create_result(
            content="Read-only operation completed"
        )


class SampleModifyingTool(ModifyingTool):
    """Sample modifying tool for testing."""
    
    def __init__(self):
        super().__init__(
            name="modifying_tool",
            display_name="Modifying Tool",
            description="A modifying test tool", 
            icon=Icon.PENCIL
        )
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        return self.create_result(
            content="Modifying operation completed"
        )


class TestBaseTool:
    """Test the BaseTool abstract class."""
    
    @pytest.fixture
    def tool(self):
        return SampleTool()
    
    def test_tool_initialization(self, tool):
        """Test tool is initialized correctly."""
        assert tool.name == "test_tool"
        assert tool.display_name == "Test Tool"
        assert tool.description == "A tool for testing"
        assert tool.icon == Icon.HAMMER
        assert tool.is_output_markdown is True
        assert tool.can_update_output is False
    
    def test_validate_params_default(self, tool):
        """Test default parameter validation."""
        result = tool.validate_params({"test": "value"})
        assert result is None  # No validation errors
    
    def test_get_description_default(self, tool):
        """Test default description generation."""
        params = {"param1": "value1"}
        result = tool.get_description(params)
        assert "Test Tool" in result
        assert "param1" in result
    
    def test_get_tool_locations_default(self, tool):
        """Test default tool locations."""
        result = tool.get_tool_locations({})
        assert result == []
    
    @pytest.mark.asyncio
    async def test_should_confirm_execute_default(self, tool):
        """Test default confirmation behavior."""
        result = await tool.should_confirm_execute({})
        assert result is False
    
    @pytest.mark.asyncio
    async def test_execute(self, tool):
        """Test tool execution."""
        params = {"test_param": "test_value"}
        result = await tool.execute(params)
        
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "test_param" in result.content
        assert result.summary == "Test execution completed"
    
    def test_create_result_minimal(self, tool):
        """Test creating a minimal result."""
        result = tool.create_result("Test content")
        
        assert result.content == "Test content"
        assert result.display == "Test content"
        assert result.success is True
        assert result.error is None
        assert result.summary is None
    
    def test_create_result_full(self, tool):
        """Test creating a full result."""
        result = tool.create_result(
            content="Test content",
            display="Display content", 
            summary="Test summary",
            success=False,
            error="Test error"
        )
        
        assert result.content == "Test content"
        assert result.display == "Display content"
        assert result.summary == "Test summary"
        assert result.success is False
        assert result.error == "Test error"


class TestReadOnlyTool:
    """Test the ReadOnlyTool class."""
    
    @pytest.fixture
    def tool(self):
        return SampleReadOnlyTool()
    
    @pytest.mark.asyncio
    async def test_execute(self, tool):
        """Test read-only tool execution."""
        result = await tool.execute({})
        assert isinstance(result, ToolResult)
        assert "Read-only operation completed" in result.content
        assert result.success is True


class TestModifyingTool:
    """Test the ModifyingTool class."""
    
    @pytest.fixture
    def tool(self):
        return SampleModifyingTool()
    
    @pytest.mark.asyncio
    async def test_should_confirm_execute(self, tool):
        """Test modifying tool requires confirmation."""
        result = await tool.should_confirm_execute({})
        
        assert isinstance(result, ToolConfirmationDetails)
        assert result.type == "modify"
        assert "Confirm Modifying Tool" in result.title
    
    @pytest.mark.asyncio
    async def test_execute(self, tool):
        """Test modifying tool execution."""
        result = await tool.execute({})
        assert isinstance(result, ToolResult)
        assert "Modifying operation completed" in result.content
        assert result.success is True


class TestToolRegistry:
    """Test the ToolRegistry class."""
    
    @pytest.fixture
    def registry(self):
        return ToolRegistry()
    
    @pytest.fixture
    def test_tool(self):
        return SampleTool()
    
    def test_register_tool(self, registry, test_tool):
        """Test registering a tool."""
        result = registry.register_tool(test_tool)
        assert result is True
        assert "test_tool" in registry.get_tool_names()
    
    def test_register_duplicate_tool(self, registry, test_tool):
        """Test registering a duplicate tool."""
        registry.register_tool(test_tool)
        result = registry.register_tool(test_tool)  # Should warn but not fail
        assert result is False
    
    def test_register_tool_with_force(self, registry, test_tool):
        """Test force registering a duplicate tool."""
        registry.register_tool(test_tool)
        result = registry.register_tool(test_tool, force=True)
        assert result is True
    
    def test_register_tool_class(self, registry):
        """Test registering a tool by class."""
        result = registry.register_tool_class(SampleTool)
        assert result is True
        assert "test_tool" in registry.get_tool_names()
    
    def test_get_tool(self, registry, test_tool):
        """Test getting a tool by name."""
        registry.register_tool(test_tool)
        retrieved_tool = registry.get_tool("test_tool")
        assert retrieved_tool is test_tool
    
    def test_get_nonexistent_tool(self, registry):
        """Test getting a non-existent tool."""
        result = registry.get_tool("nonexistent")
        assert result is None
    
    def test_get_all_tools(self, registry):
        """Test getting all tools."""
        tool1 = SampleTool()
        tool2 = SampleReadOnlyTool()
        
        registry.register_tool(tool1)
        registry.register_tool(tool2)
        
        all_tools = registry.get_all_tools()
        assert len(all_tools) == 2
        assert tool1 in all_tools
        assert tool2 in all_tools
    
    def test_get_tools_by_source(self, registry):
        """Test getting tools by source."""
        tool1 = SampleTool()
        tool2 = SampleReadOnlyTool()
        
        registry.register_tool(tool1, source="builtin")
        registry.register_tool(tool2, source="external")
        
        builtin_tools = registry.get_tools_by_source("builtin")
        external_tools = registry.get_tools_by_source("external")
        
        assert len(builtin_tools) == 1
        assert len(external_tools) == 1
        assert tool1 in builtin_tools
        assert tool2 in external_tools
    
    def test_unregister_tool(self, registry, test_tool):
        """Test unregistering a tool."""
        registry.register_tool(test_tool)
        assert "test_tool" in registry.get_tool_names()
        
        result = registry.unregister_tool("test_tool")
        assert result is True
        assert "test_tool" not in registry.get_tool_names()
    
    def test_unregister_nonexistent_tool(self, registry):
        """Test unregistering a non-existent tool."""
        result = registry.unregister_tool("nonexistent")
        assert result is False
    
    def test_configure_filters(self, registry):
        """Test configuring tool filters."""
        registry.configure_filters(
            core_tools=["test_tool"],
            exclude_tools=["bad_tool"]
        )
        
        # Tool should be enabled if in core_tools
        tool = SampleTool()
        result = registry.register_tool(tool)
        assert result is True
    
    def test_configure_filters_exclude(self, registry):
        """Test excluding tools with filters."""
        registry.configure_filters(exclude_tools=["test_tool"])
        
        # Tool should be disabled if in exclude_tools
        tool = SampleTool()
        result = registry.register_tool(tool)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_execute_tool(self, registry, test_tool):
        """Test executing a tool through registry."""
        registry.register_tool(test_tool)
        
        result = await registry.execute_tool("test_tool", {"param": "value"})
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "param" in result.content
    
    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self, registry):
        """Test executing a non-existent tool."""
        result = await registry.execute_tool("nonexistent", {})
        assert result is None
    
    def test_clear_tools_all(self, registry):
        """Test clearing all tools."""
        registry.register_tool(SampleTool())
        registry.register_tool(SampleReadOnlyTool())
        
        count = registry.clear_tools()
        assert count == 2
        assert len(registry.get_all_tools()) == 0
    
    def test_clear_tools_by_source(self, registry):
        """Test clearing tools by source."""
        registry.register_tool(SampleTool(), source="builtin")
        registry.register_tool(SampleReadOnlyTool(), source="external")
        
        count = registry.clear_tools("builtin")
        assert count == 1
        assert len(registry.get_all_tools()) == 1
    
    def test_get_stats(self, registry):
        """Test getting registry statistics."""
        registry.register_tool(SampleTool(), source="builtin")
        registry.register_tool(SampleReadOnlyTool(), source="external")
        
        stats = registry.get_stats()
        assert stats['total_tools'] == 2
        assert stats['enabled_tools'] == 2
        assert stats['sources']['builtin'] == 1
        assert stats['sources']['external'] == 1
    
    def test_get_tool_metadata(self, registry, test_tool):
        """Test getting tool metadata."""
        registry.register_tool(test_tool, source="test")
        
        metadata = registry.get_tool_metadata("test_tool")
        assert isinstance(metadata, ToolMetadata)
        assert metadata.name == "test_tool"
        assert metadata.display_name == "Test Tool"
        assert metadata.source == "test"
        assert metadata.enabled is True