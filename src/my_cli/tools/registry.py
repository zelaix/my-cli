"""
Tool registry system for My CLI.

This module provides the tool registration and discovery system,
mirroring the functionality of the original Gemini CLI's ToolRegistry.
"""

import asyncio
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Optional, Type, Any, Set
import logging
from dataclasses import dataclass

from .base import Tool, BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ToolMetadata:
    """Metadata about a registered tool."""
    name: str
    display_name: str
    description: str
    tool_class: Type[Tool]
    source: str  # "builtin", "discovered", "external"
    enabled: bool = True


class ToolRegistry:
    """Registry for managing and discovering tools."""
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, Tool] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
        self._core_tools: Optional[Set[str]] = None
        self._exclude_tools: Optional[Set[str]] = None
    
    def configure_filters(
        self,
        core_tools: Optional[List[str]] = None,
        exclude_tools: Optional[List[str]] = None
    ) -> None:
        """Configure tool filtering.
        
        Args:
            core_tools: List of tools to include (None means all)
            exclude_tools: List of tools to exclude
        """
        self._core_tools = set(core_tools) if core_tools else None
        self._exclude_tools = set(exclude_tools) if exclude_tools else set()
    
    def register_tool(
        self,
        tool: Tool,
        source: str = "external",
        force: bool = False
    ) -> bool:
        """Register a tool instance.
        
        Args:
            tool: Tool instance to register
            source: Source of the tool ("builtin", "discovered", "external")
            force: Force registration even if tool exists
            
        Returns:
            True if tool was registered successfully
        """
        if not force and tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered. Use force=True to override.")
            return False
        
        # Check if tool should be enabled based on filters
        enabled = self._should_enable_tool(tool.name, tool.__class__.__name__)
        
        if not enabled:
            logger.debug(f"Tool '{tool.name}' excluded by configuration")
            return False
        
        self._tools[tool.name] = tool
        self._metadata[tool.name] = ToolMetadata(
            name=tool.name,
            display_name=tool.display_name,
            description=tool.description,
            tool_class=tool.__class__,
            source=source,
            enabled=enabled
        )
        
        logger.info(f"Registered tool: {tool.name} ({source})")
        return True
    
    def register_tool_class(
        self,
        tool_class: Type[BaseTool],
        source: str = "builtin",
        *args,
        **kwargs
    ) -> bool:
        """Register a tool by class.
        
        Args:
            tool_class: Tool class to instantiate and register
            source: Source of the tool
            *args: Arguments to pass to tool constructor
            **kwargs: Keyword arguments to pass to tool constructor
            
        Returns:
            True if tool was registered successfully
        """
        try:
            tool_instance = tool_class(*args, **kwargs)
            return self.register_tool(tool_instance, source)
        except Exception as e:
            logger.error(f"Failed to register tool class {tool_class.__name__}: {e}")
            return False
    
    def unregister_tool(self, name: str) -> bool:
        """Unregister a tool by name.
        
        Args:
            name: Name of tool to unregister
            
        Returns:
            True if tool was unregistered
        """
        if name in self._tools:
            del self._tools[name]
            del self._metadata[name]
            logger.info(f"Unregistered tool: {name}")
            return True
        return False
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)
    
    def get_all_tools(self) -> List[Tool]:
        """Get all registered tools.
        
        Returns:
            List of all registered tool instances
        """
        return list(self._tools.values())
    
    def get_tool_names(self) -> List[str]:
        """Get names of all registered tools.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())
    
    def get_tools_by_source(self, source: str) -> List[Tool]:
        """Get tools from a specific source.
        
        Args:
            source: Tool source to filter by
            
        Returns:
            List of tools from the specified source
        """
        return [
            self._tools[name] for name, metadata in self._metadata.items()
            if metadata.source == source
        ]
    
    def get_tool_metadata(self, name: str) -> Optional[ToolMetadata]:
        """Get metadata for a tool.
        
        Args:
            name: Tool name
            
        Returns:
            Tool metadata or None if not found
        """
        return self._metadata.get(name)
    
    def get_all_metadata(self) -> Dict[str, ToolMetadata]:
        """Get metadata for all tools.
        
        Returns:
            Dictionary of tool metadata
        """
        return self._metadata.copy()
    
    async def execute_tool(
        self,
        name: str,
        params: Dict[str, Any]
    ) -> Optional[ToolResult]:
        """Execute a tool by name.
        
        Args:
            name: Tool name
            params: Tool parameters
            
        Returns:
            Tool result or None if tool not found
        """
        tool = self.get_tool(name)
        if not tool:
            logger.error(f"Tool '{name}' not found")
            return None
        
        try:
            return await tool.execute(params)
        except Exception as e:
            logger.error(f"Error executing tool '{name}': {e}")
            return None
    
    async def discover_builtin_tools(self) -> int:
        """Discover and register built-in tools.
        
        Returns:
            Number of tools discovered
        """
        discovered_count = 0
        
        # Import and register built-in tools
        # This would be expanded to include actual built-in tools
        builtin_tools = [
            # Add built-in tool classes here
            # Example: FileReadTool, FileWriteTool, etc.
        ]
        
        for tool_class in builtin_tools:
            if self.register_tool_class(tool_class, source="builtin"):
                discovered_count += 1
        
        logger.info(f"Discovered {discovered_count} built-in tools")
        return discovered_count
    
    async def discover_tools_from_directory(
        self,
        directory: Path,
        recursive: bool = True
    ) -> int:
        """Discover tools from Python files in a directory.
        
        Args:
            directory: Directory to search
            recursive: Whether to search recursively
            
        Returns:
            Number of tools discovered
        """
        discovered_count = 0
        
        try:
            pattern = "**/*.py" if recursive else "*.py"
            for py_file in directory.glob(pattern):
                if py_file.name.startswith('_'):
                    continue
                
                try:
                    discovered_count += await self._discover_tools_from_file(py_file)
                except Exception as e:
                    logger.error(f"Error discovering tools from {py_file}: {e}")
            
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
        
        logger.info(f"Discovered {discovered_count} tools from directory {directory}")
        return discovered_count
    
    async def _discover_tools_from_file(self, file_path: Path) -> int:
        """Discover tools from a Python file.
        
        Args:
            file_path: Python file to scan
            
        Returns:
            Number of tools discovered
        """
        discovered_count = 0
        
        try:
            # Convert file path to module name
            module_name = str(file_path.with_suffix(''))
            module_name = module_name.replace('/', '.').replace('\\', '.')
            
            # Import the module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                return 0
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find tool classes in the module
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, BaseTool) and 
                    obj is not BaseTool):
                    
                    try:
                        # Try to instantiate and register
                        if self.register_tool_class(obj, source="discovered"):
                            discovered_count += 1
                    except Exception as e:
                        logger.error(f"Failed to register tool class {name}: {e}")
            
        except Exception as e:
            logger.error(f"Error loading module from {file_path}: {e}")
        
        return discovered_count
    
    def _should_enable_tool(self, tool_name: str, class_name: str) -> bool:
        """Check if a tool should be enabled based on configuration.
        
        Args:
            tool_name: Name of the tool
            class_name: Class name of the tool
            
        Returns:
            True if tool should be enabled
        """
        # Check exclude list first
        if self._exclude_tools:
            if tool_name in self._exclude_tools or class_name in self._exclude_tools:
                return False
        
        # If core_tools is specified, only enable tools in the list
        if self._core_tools is not None:
            return (tool_name in self._core_tools or 
                   class_name in self._core_tools or
                   any(tool_name.startswith(core) for core in self._core_tools) or
                   any(class_name.startswith(core) for core in self._core_tools))
        
        # Default: enable all tools not in exclude list
        return True
    
    def clear_tools(self, source: Optional[str] = None) -> int:
        """Clear registered tools.
        
        Args:
            source: If specified, only clear tools from this source
            
        Returns:
            Number of tools cleared
        """
        if source is None:
            # Clear all tools
            count = len(self._tools)
            self._tools.clear()
            self._metadata.clear()
            return count
        else:
            # Clear tools from specific source
            tools_to_remove = [
                name for name, metadata in self._metadata.items()
                if metadata.source == source
            ]
            
            for name in tools_to_remove:
                del self._tools[name]
                del self._metadata[name]
            
            return len(tools_to_remove)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics.
        
        Returns:
            Dictionary with registry statistics
        """
        source_counts = {}
        for metadata in self._metadata.values():
            source_counts[metadata.source] = source_counts.get(metadata.source, 0) + 1
        
        return {
            'total_tools': len(self._tools),
            'enabled_tools': len([m for m in self._metadata.values() if m.enabled]),
            'sources': source_counts,
            'core_tools_filter': list(self._core_tools) if self._core_tools else None,
            'exclude_tools_filter': list(self._exclude_tools) if self._exclude_tools else None
        }