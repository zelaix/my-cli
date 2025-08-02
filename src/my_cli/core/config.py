"""
Core configuration management for My CLI.

This module provides the main configuration system that integrates all
application components, mirroring the functionality of the original
Gemini CLI's Config class.
"""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
from dataclasses import dataclass
from enum import Enum

from ..config.settings import MyCliSettings, ProjectSettings, get_effective_settings
from ..config.hierarchical import HierarchicalConfigLoader, SettingScope
from ..config.env_loader import EnvFileLoader
from ..services.file_discovery import FileDiscoveryService, FileFilteringOptions
from ..services.git_service import GitService
from ..services.workspace import WorkspaceContext
from ..tools.registry import ToolRegistry
from ..prompts.registry import PromptRegistry
from ..core.client import GeminiClient, ContentGeneratorConfig, AuthType, create_gemini_client
from ..core.container import ServiceContainer

logger = logging.getLogger(__name__)


class ApprovalMode(Enum):
    """Tool execution approval modes."""
    DEFAULT = "default"
    AUTO_EDIT = "auto_edit"
    YOLO = "yolo"


@dataclass
class TelemetrySettings:
    """Telemetry configuration settings."""
    enabled: bool = False
    target: str = "console"
    endpoint: Optional[str] = None
    log_prompts: bool = True
    outfile: Optional[str] = None


@dataclass
class SandboxConfig:
    """Sandbox execution configuration."""
    command: str = "docker"  # docker, podman, sandbox-exec
    image: str = "python:3.11-slim"
    timeout: int = 300


class MyCliConfig:
    """
    Main configuration class for My CLI.
    
    This class manages all application configuration, services, and dependencies,
    providing a centralized configuration system similar to the original Gemini CLI.
    """
    
    def __init__(
        self,
        working_directory: Optional[str] = None,
        settings_override: Optional[Dict[str, Any]] = None
    ):
        """Initialize the configuration.
        
        Args:
            working_directory: Working directory for the session
            settings_override: Override settings for testing/customization
        """
        # Core settings
        self.working_directory = Path(working_directory or Path.cwd()).resolve()
        self._settings = self._load_settings(settings_override)
        
        # Session configuration
        self.session_id = self._generate_session_id()
        self.debug_mode = self._settings.debug
        
        # Service instances (initialized lazily)
        self._api_client: Optional[GeminiClient] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._prompt_registry: Optional[PromptRegistry] = None
        self._file_service: Optional[FileDiscoveryService] = None
        self._git_service: Optional[GitService] = None
        self._workspace_context: Optional[WorkspaceContext] = None
        self._container: Optional[ServiceContainer] = None
        
        # Hierarchical configuration
        self._config_loader: Optional[HierarchicalConfigLoader] = None
        self._env_loader: Optional[EnvFileLoader] = None
        
        # Configuration state
        self._initialized = False
        self.approval_mode = ApprovalMode.DEFAULT
        self.telemetry_settings = TelemetrySettings()
        self.sandbox_config: Optional[SandboxConfig] = None
        
        # Ensure directories exist
        self._settings.ensure_directories()
    
    async def initialize(self) -> None:
        """Initialize the configuration and all services."""
        if self._initialized:
            return
        
        logger.info(f"Initializing My CLI configuration for session {self.session_id}")
        
        try:
            # Load hierarchical configuration first
            await self._load_hierarchical_config()
            
            # Initialize container
            await self._setup_container()
            
            # Initialize core services
            await self._initialize_services()
            
            # Setup tool registry
            await self._setup_tools()
            
            # Setup prompt registry
            await self._setup_prompts()
            
            self._initialized = True
            logger.info("Configuration initialization completed")
            
        except Exception as e:
            logger.error(f"Failed to initialize configuration: {e}")
            raise
    
    # Property accessors for services
    @property
    def settings(self) -> MyCliSettings:
        """Get the current settings."""
        return self._settings
    
    async def get_api_client(self) -> GeminiClient:
        """Get the API client instance."""
        if not self._api_client:
            if not self._settings.api_key:
                raise ValueError("API key not configured. Set MY_CLI_API_KEY environment variable.")
            
            self._api_client = create_gemini_client(
                api_key=self._settings.api_key,
                model=self._settings.model,
                temperature=self._settings.temperature,
                max_tokens=self._settings.max_tokens
            )
            await self._api_client.initialize()
        
        return self._api_client
    
    async def get_tool_registry(self) -> ToolRegistry:
        """Get the tool registry instance."""
        if not self._tool_registry:
            await self._setup_tools()
        return self._tool_registry
    
    def get_prompt_registry(self) -> PromptRegistry:
        """Get the prompt registry instance."""
        if not self._prompt_registry:
            self._prompt_registry = PromptRegistry()
        return self._prompt_registry
    
    async def get_file_service(self) -> FileDiscoveryService:
        """Get the file discovery service."""
        if not self._file_service:
            self._file_service = FileDiscoveryService(str(self.working_directory))
        return self._file_service
    
    async def get_git_service(self) -> GitService:
        """Get the Git service."""
        if not self._git_service:
            self._git_service = GitService(str(self.working_directory))
            await self._git_service.initialize()
        return self._git_service
    
    async def get_workspace_context(self) -> WorkspaceContext:
        """Get the workspace context."""
        if not self._workspace_context:
            self._workspace_context = WorkspaceContext(str(self.working_directory))
            await self._workspace_context.initialize()
        return self._workspace_context
    
    def get_container(self) -> ServiceContainer:
        """Get the dependency injection container."""
        if not self._container:
            raise ValueError("Container not initialized. Call initialize() first.")
        return self._container
    
    # Configuration methods
    def get_session_id(self) -> str:
        """Get the current session ID."""
        return self.session_id
    
    def get_working_directory(self) -> Path:
        """Get the working directory."""
        return self.working_directory
    
    def get_model(self) -> str:
        """Get the current AI model."""
        return self._settings.model
    
    def set_model(self, model: str) -> None:
        """Set the AI model."""
        self._settings.model = model
        # Reset API client to use new model
        self._api_client = None
    
    def get_debug_mode(self) -> bool:
        """Get debug mode status."""
        return self.debug_mode
    
    def get_approval_mode(self) -> ApprovalMode:
        """Get the current approval mode."""
        return self.approval_mode
    
    def set_approval_mode(self, mode: ApprovalMode) -> None:
        """Set the approval mode."""
        self.approval_mode = mode
    
    def get_file_filtering_options(self) -> FileFilteringOptions:
        """Get default file filtering options."""
        return FileFilteringOptions(
            respect_git_ignore=True,
            respect_gemini_ignore=True,
            enable_recursive_file_search=True
        )
    
    def is_configured(self) -> bool:
        """Check if the configuration is properly set up."""
        return self._settings.is_configured
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the current configuration."""
        summary = {
            'session_id': self.session_id,
            'working_directory': str(self.working_directory),
            'model': self._settings.model,
            'theme': self._settings.theme,
            'debug_mode': self.debug_mode,
            'approval_mode': self.approval_mode.value,
            'is_configured': self.is_configured(),
            'initialized': self._initialized
        }
        
        # Add hierarchical config info if available
        if self._config_loader:
            hierarchical_summary = self._config_loader.get_config_summary()
            summary['hierarchical_config'] = hierarchical_summary
        
        if self._env_loader:
            summary['env_file'] = str(self._env_loader.get_loaded_file()) if self._env_loader.get_loaded_file() else None
            summary['env_vars_loaded'] = len(self._env_loader.get_loaded_vars())
        
        return summary
    
    # Hierarchical configuration methods
    def get_config_loader(self) -> HierarchicalConfigLoader:
        """Get the hierarchical configuration loader."""
        if not self._config_loader:
            self._config_loader = HierarchicalConfigLoader(self.working_directory)
        return self._config_loader
    
    def get_env_loader(self) -> EnvFileLoader:
        """Get the environment file loader.""" 
        if not self._env_loader:
            self._env_loader = EnvFileLoader(self.working_directory)
            self._env_loader.load_env_file()
        return self._env_loader
    
    def reload_configuration(self) -> Dict[str, Any]:
        """Reload all configuration from hierarchical sources.
        
        Returns:
            Merged configuration dictionary
        """
        # Load environment file first
        env_loader = self.get_env_loader()
        env_file = env_loader.load_env_file()
        
        # Load hierarchical configuration
        config_loader = self.get_config_loader()
        merged_config = config_loader.load_all_settings()
        
        # Create new settings from merged config
        try:
            # Update pydantic settings with hierarchical config
            for key, value in merged_config.items():
                if hasattr(self._settings, key):
                    setattr(self._settings, key, value)
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Error applying hierarchical configuration: {e}")
        
        return merged_config
    
    def save_setting(self, key: str, value: Any, scope: SettingScope = SettingScope.USER) -> bool:
        """Save a setting to a specific scope.
        
        Args:
            key: Setting key
            value: Setting value
            scope: Configuration scope to save to
            
        Returns:
            True if saved successfully
        """
        config_loader = self.get_config_loader()
        
        # Get current settings for the scope
        settings_file = config_loader.get_settings_file(scope)
        if settings_file:
            current_settings = settings_file.settings.copy()
        else:
            current_settings = {}
        
        # Update the setting
        current_settings[key] = value
        
        # Save the updated settings
        success = config_loader.save_settings(scope, current_settings)
        
        if success:
            # Update in-memory settings if it's a known field
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
                logger.info(f"Updated setting {key} = {value} in {scope.value}")
        
        return success
    
    def get_setting_sources(self, key: str) -> Dict[str, Any]:
        """Get information about where a setting comes from.
        
        Args:
            key: Setting key to trace
            
        Returns:
            Dictionary showing setting value in each scope
        """
        config_loader = self.get_config_loader()
        sources = {}
        
        for scope, settings_file in config_loader.get_all_settings_files().items():
            if key in settings_file.settings:
                sources[scope.value] = {
                    "value": settings_file.settings[key],
                    "path": str(settings_file.path),
                    "exists": settings_file.exists
                }
        
        return sources
    
    # Private methods
    def _load_settings(self, override: Optional[Dict[str, Any]]) -> MyCliSettings:
        """Load settings from various sources."""
        settings = get_effective_settings(self.working_directory)
        
        # Apply overrides if provided
        if override:
            for key, value in override.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
        
        return settings
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        import uuid
        return str(uuid.uuid4())[:8]
    
    async def _setup_container(self) -> None:
        """Setup the dependency injection container."""
        self._container = ServiceContainer()
        
        # Register core services
        self._container.register_singleton(MyCliConfig, instance=self)
        self._container.register_singleton(MyCliSettings, instance=self._settings)
        
        # Register services as singletons
        self._container.register_singleton(
            FileDiscoveryService,
            factory=lambda: FileDiscoveryService(str(self.working_directory))
        )
        
        self._container.register_singleton(
            GitService,
            factory=lambda: GitService(str(self.working_directory))
        )
        
        self._container.register_singleton(
            WorkspaceContext,
            factory=lambda: WorkspaceContext(str(self.working_directory))
        )
        
        self._container.register_singleton(ToolRegistry)
        self._container.register_singleton(PromptRegistry)
    
    async def _initialize_services(self) -> None:
        """Initialize all core services."""
        # Initialize services that need async initialization
        git_service = await self.get_git_service()
        workspace_context = await self.get_workspace_context()
        
        logger.debug("Core services initialized")
    
    async def _setup_tools(self) -> None:
        """Setup the tool registry."""
        if self._tool_registry:
            return
        
        self._tool_registry = ToolRegistry()
        
        # Configure tool filters based on settings
        allowed_tools = self._settings.allowed_tools
        if allowed_tools:
            self._tool_registry.configure_filters(core_tools=allowed_tools)
        
        # Discover built-in tools
        builtin_count = await self._tool_registry.discover_builtin_tools()
        logger.debug(f"Registered {builtin_count} built-in tools")
        
        # TODO: Discover external tools from configured paths
    
    async def _setup_prompts(self) -> None:
        """Setup the prompt registry."""
        if self._prompt_registry:
            return
        
        self._prompt_registry = PromptRegistry()
        
        # Load additional prompts from config directory
        prompts_dir = self._settings.config_dir / "prompts"
        if prompts_dir.exists():
            loaded_count = await self._prompt_registry.load_prompts_from_directory(prompts_dir)
            logger.debug(f"Loaded {loaded_count} custom prompts")
    
    async def refresh_auth(self, auth_type: Optional[AuthType] = None) -> None:
        """Refresh authentication configuration."""
        # Reset API client to re-initialize with new auth
        self._api_client = None
        
        if self._settings.api_key:
            await self.get_api_client()
            logger.info("Authentication refreshed")
    
    async def create_checkpoint(self, message: str) -> bool:
        """Create a Git checkpoint if possible."""
        try:
            git_service = await self.get_git_service()
            if git_service.is_git_repository:
                return await git_service.create_checkpoint(message)
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
        return False
    
    def dispose(self) -> None:
        """Clean up resources."""
        if self._container:
            self._container.clear()
        
        self._initialized = False
        logger.debug("Configuration disposed")
    
    async def _load_hierarchical_config(self) -> None:
        """Load hierarchical configuration from all sources."""
        try:
            # Load environment file first
            env_loader = self.get_env_loader()
            env_file = env_loader.load_env_file()
            if env_file:
                logger.debug(f"Loaded .env file: {env_file}")
            
            # Load hierarchical configuration
            config_loader = self.get_config_loader()
            merged_config = config_loader.load_all_settings()
            
            # Apply configuration to settings
            for key, value in merged_config.items():
                if hasattr(self._settings, key):
                    try:
                        setattr(self._settings, key, value)
                    except Exception as e:
                        logger.warning(f"Could not set {key} = {value}: {e}")
            
            logger.debug("Hierarchical configuration loaded")
            
        except Exception as e:
            logger.error(f"Error loading hierarchical configuration: {e}")
            # Continue with existing settings if hierarchical loading fails


# Global configuration instance
_global_config: Optional[MyCliConfig] = None


def get_config() -> MyCliConfig:
    """Get the global configuration instance.
    
    Returns:
        Global configuration instance
    """
    global _global_config
    if _global_config is None:
        _global_config = MyCliConfig()
    return _global_config


def set_config(config: MyCliConfig) -> None:
    """Set the global configuration instance.
    
    Args:
        config: Configuration to set as global
    """
    global _global_config
    _global_config = config


async def initialize_config(
    working_directory: Optional[str] = None,
    settings_override: Optional[Dict[str, Any]] = None
) -> MyCliConfig:
    """Initialize and return a configuration instance.
    
    Args:
        working_directory: Working directory for the session
        settings_override: Override settings
        
    Returns:
        Initialized configuration instance
    """
    config = MyCliConfig(working_directory, settings_override)
    await config.initialize()
    return config