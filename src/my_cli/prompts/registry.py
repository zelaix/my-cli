"""
Prompt registry system for My CLI.

This module provides the prompt registration and template management system,
mirroring the functionality of the original Gemini CLI's PromptRegistry.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import logging
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)


class PromptType(Enum):
    """Types of prompts in the system."""
    SYSTEM = "system"
    USER = "user"
    TOOL = "tool"
    CONTEXT = "context"
    MEMORY = "memory"


@dataclass
class PromptTemplate:
    """A prompt template with metadata."""
    name: str
    type: PromptType
    template: str
    description: str
    variables: List[str]
    source: str = "builtin"
    
    def render(self, **kwargs) -> str:
        """Render the template with provided variables.
        
        Args:
            **kwargs: Variables to substitute in template
            
        Returns:
            Rendered prompt string
        """
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            missing_var = str(e).strip("'")
            logger.error(f"Missing variable '{missing_var}' for prompt '{self.name}'")
            return self.template
        except Exception as e:
            logger.error(f"Error rendering prompt '{self.name}': {e}")
            return self.template


class PromptRegistry:
    """Registry for managing prompt templates."""
    
    def __init__(self):
        """Initialize the prompt registry."""
        self._prompts: Dict[str, PromptTemplate] = {}
        self._prompt_processors: Dict[str, Callable] = {}
        self._load_builtin_prompts()
    
    def register_prompt(
        self,
        name: str,
        template: str,
        prompt_type: PromptType,
        description: str = "",
        variables: Optional[List[str]] = None,
        source: str = "external"
    ) -> bool:
        """Register a prompt template.
        
        Args:
            name: Unique name for the prompt
            template: Template string with placeholders
            prompt_type: Type of prompt
            description: Description of the prompt
            variables: List of variable names used in template
            source: Source of the prompt
            
        Returns:
            True if prompt was registered successfully
        """
        if name in self._prompts:
            logger.warning(f"Prompt '{name}' already exists. Overwriting.")
        
        # Extract variables from template if not provided
        if variables is None:
            variables = self._extract_variables(template)
        
        prompt = PromptTemplate(
            name=name,
            type=prompt_type,
            template=template,
            description=description,
            variables=variables,
            source=source
        )
        
        self._prompts[name] = prompt
        logger.debug(f"Registered prompt: {name}")
        return True
    
    def get_prompt(self, name: str) -> Optional[PromptTemplate]:
        """Get a prompt template by name.
        
        Args:
            name: Prompt name
            
        Returns:
            PromptTemplate or None if not found
        """
        return self._prompts.get(name)
    
    def render_prompt(self, name: str, **kwargs) -> Optional[str]:
        """Render a prompt with variables.
        
        Args:
            name: Prompt name
            **kwargs: Variables to substitute
            
        Returns:
            Rendered prompt string or None if not found
        """
        prompt = self.get_prompt(name)
        if not prompt:
            logger.error(f"Prompt '{name}' not found")
            return None
        
        # Apply any registered processors
        if name in self._prompt_processors:
            try:
                kwargs = self._prompt_processors[name](kwargs)
            except Exception as e:
                logger.error(f"Error in prompt processor for '{name}': {e}")
        
        return prompt.render(**kwargs)
    
    def get_prompts_by_type(self, prompt_type: PromptType) -> List[PromptTemplate]:
        """Get all prompts of a specific type.
        
        Args:
            prompt_type: Type of prompts to retrieve
            
        Returns:
            List of matching prompt templates
        """
        return [
            prompt for prompt in self._prompts.values()
            if prompt.type == prompt_type
        ]
    
    def get_all_prompts(self) -> Dict[str, PromptTemplate]:
        """Get all registered prompts.
        
        Returns:
            Dictionary of all prompt templates
        """
        return self._prompts.copy()
    
    def unregister_prompt(self, name: str) -> bool:
        """Unregister a prompt.
        
        Args:
            name: Prompt name to unregister
            
        Returns:
            True if prompt was removed
        """
        if name in self._prompts:
            del self._prompts[name]
            if name in self._prompt_processors:
                del self._prompt_processors[name]
            logger.debug(f"Unregistered prompt: {name}")
            return True
        return False
    
    def register_processor(
        self,
        prompt_name: str,
        processor: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """Register a processor function for a prompt.
        
        Args:
            prompt_name: Name of prompt to process
            processor: Function that processes prompt variables
        """
        self._prompt_processors[prompt_name] = processor
        logger.debug(f"Registered processor for prompt: {prompt_name}")
    
    async def load_prompts_from_file(self, file_path: Path) -> int:
        """Load prompts from a JSON file.
        
        Args:
            file_path: Path to JSON file containing prompts
            
        Returns:
            Number of prompts loaded
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            count = 0
            for prompt_data in data.get('prompts', []):
                if self._load_prompt_from_dict(prompt_data, source=str(file_path)):
                    count += 1
            
            logger.info(f"Loaded {count} prompts from {file_path}")
            return count
            
        except Exception as e:
            logger.error(f"Error loading prompts from {file_path}: {e}")
            return 0
    
    async def load_prompts_from_directory(
        self,
        directory: Path,
        recursive: bool = True
    ) -> int:
        """Load prompts from JSON files in a directory.
        
        Args:
            directory: Directory to search
            recursive: Whether to search recursively
            
        Returns:
            Number of prompts loaded
        """
        count = 0
        try:
            pattern = "**/*.json" if recursive else "*.json"
            for json_file in directory.glob(pattern):
                count += await self.load_prompts_from_file(json_file)
        except Exception as e:
            logger.error(f"Error loading prompts from directory {directory}: {e}")
        
        return count
    
    def _load_prompt_from_dict(self, data: Dict[str, Any], source: str = "file") -> bool:
        """Load a prompt from dictionary data.
        
        Args:
            data: Dictionary with prompt data
            source: Source identifier
            
        Returns:
            True if prompt was loaded successfully
        """
        try:
            name = data.get('name')
            template = data.get('template')
            prompt_type_str = data.get('type', 'user')
            
            if not name or not template:
                logger.error("Prompt data missing name or template")
                return False
            
            try:
                prompt_type = PromptType(prompt_type_str.lower())
            except ValueError:
                logger.error(f"Invalid prompt type: {prompt_type_str}")
                prompt_type = PromptType.USER
            
            return self.register_prompt(
                name=name,
                template=template,
                prompt_type=prompt_type,
                description=data.get('description', ''),
                variables=data.get('variables'),
                source=source
            )
            
        except Exception as e:
            logger.error(f"Error loading prompt from data: {e}")
            return False
    
    def _extract_variables(self, template: str) -> List[str]:
        """Extract variable names from a template string.
        
        Args:
            template: Template string
            
        Returns:
            List of variable names found in template
        """
        import re
        
        # Find variables in {variable} format
        variables = re.findall(r'\{(\w+)\}', template)
        return list(set(variables))
    
    def _load_builtin_prompts(self) -> None:
        """Load built-in prompt templates."""
        builtin_prompts = [
            {
                'name': 'system_base',
                'type': 'system',
                'template': """You are My CLI, an AI-powered command-line assistant.

You help users with software engineering tasks including:
- Code analysis and generation
- File operations and management
- Git operations and version control
- Project understanding and navigation
- Tool execution and automation

Always be helpful, accurate, and concise in your responses.
Current working directory: {working_directory}
Project context: {project_context}""",
                'description': 'Base system prompt for My CLI',
                'variables': ['working_directory', 'project_context']
            },
            {
                'name': 'tool_confirmation',
                'type': 'user',
                'template': """The following tool will be executed:

Tool: {tool_name}
Description: {tool_description}
Parameters: {tool_parameters}

Do you want to proceed? (y/n): """,
                'description': 'Prompt for tool execution confirmation',
                'variables': ['tool_name', 'tool_description', 'tool_parameters']
            },
            {
                'name': 'file_context',
                'type': 'context',
                'template': """File: {file_path}
Last modified: {last_modified}
Size: {file_size} bytes

Content:
```{file_extension}
{file_content}
```""",
                'description': 'Template for including file context',
                'variables': ['file_path', 'last_modified', 'file_size', 'file_extension', 'file_content']
            },
            {
                'name': 'memory_context',
                'type': 'memory',
                'template': """Previous conversation context:

{conversation_summary}

Key points from previous interactions:
{key_points}

Relevant project information:
{project_info}""",
                'description': 'Template for memory context inclusion',
                'variables': ['conversation_summary', 'key_points', 'project_info']
            },
            {
                'name': 'error_context',
                'type': 'system',
                'template': """An error occurred while executing a tool:

Tool: {tool_name}
Error: {error_message}
Command: {command}
Exit code: {exit_code}

Please analyze the error and suggest a solution.""",
                'description': 'Template for error reporting',
                'variables': ['tool_name', 'error_message', 'command', 'exit_code']
            }
        ]
        
        for prompt_data in builtin_prompts:
            self._load_prompt_from_dict(prompt_data, source="builtin")
        
        logger.debug(f"Loaded {len(builtin_prompts)} built-in prompts")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics.
        
        Returns:
            Dictionary with registry statistics
        """
        source_counts = {}
        type_counts = {}
        
        for prompt in self._prompts.values():
            source_counts[prompt.source] = source_counts.get(prompt.source, 0) + 1
            type_counts[prompt.type.value] = type_counts.get(prompt.type.value, 0) + 1
        
        return {
            'total_prompts': len(self._prompts),
            'sources': source_counts,
            'types': type_counts,
            'processors': len(self._prompt_processors)
        }