"""
Configuration settings for My CLI.

This module provides configuration management using Pydantic settings
with support for environment variables, configuration files, and
hierarchical configuration loading.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MyCliSettings(BaseSettings):
    """
    Main configuration settings for My CLI.
    
    Settings are loaded from multiple sources in order of preference:
    1. Environment variables (prefixed with MY_CLI_)
    2. Configuration files (.env, config files)
    3. Default values
    """
    
    model_config = SettingsConfigDict(
        env_prefix="MY_CLI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # API Configuration
    api_key: Optional[str] = Field(
        default=None,
        description="AI API key"
    )
    
    # Model Configuration
    model: str = Field(
        default="gemini-2.0-flash-exp",
        description="Default AI model to use"
    )
    
    # UI Configuration
    theme: str = Field(
        default="default",
        description="Color theme for the CLI interface"
    )
    
    auto_confirm: bool = Field(
        default=False,
        description="Automatically confirm tool executions"
    )
    
    # Advanced Configuration
    max_tokens: int = Field(
        default=8192,
        description="Maximum tokens for responses",
        gt=0,
        le=32768
    )
    
    temperature: float = Field(
        default=0.7,
        description="Temperature for response generation",
        ge=0.0,
        le=1.0
    )
    
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
        gt=0
    )
    
    # Tool Configuration
    allowed_tools: List[str] = Field(
        default_factory=lambda: [
            "read_file",
            "write_file", 
            "list_directory",
            "grep",
            "shell",
            "web_search"
        ],
        description="List of allowed tools"
    )
    
    # Directory Configuration
    config_dir: Path = Field(
        default_factory=lambda: Path.home() / ".config" / "my-cli",
        description="Configuration directory path"
    )
    
    cache_dir: Path = Field(
        default_factory=lambda: Path.home() / ".cache" / "my-cli",
        description="Cache directory path"
    )
    
    # Memory Configuration
    max_history_length: int = Field(
        default=100,
        description="Maximum number of conversation history items to keep",
        gt=0
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        """Validate theme name."""
        valid_themes = {
            "default", "default-light", "dracula", "github", "github-light",
            "ansi", "ansi-light", "atom-one", "ayu", "ayu-light", "xcode"
        }
        if v not in valid_themes:
            raise ValueError(f"Invalid theme '{v}'. Valid themes: {', '.join(sorted(valid_themes))}")
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level '{v}'. Valid levels: {', '.join(sorted(valid_levels))}")
        return v_upper
    
    def ensure_directories(self) -> None:
        """Ensure configuration and cache directories exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def config_file_path(self) -> Path:
        """Path to the main configuration file."""
        return self.config_dir / "config.toml"
    
    @property
    def is_configured(self) -> bool:
        """Check if the CLI is properly configured."""
        return self.api_key is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary, excluding sensitive data."""
        data = self.model_dump()
        # Mask sensitive data
        if data.get("api_key"):
            data["api_key"] = "***masked***"
        return data


class ProjectSettings(BaseSettings):
    """
    Project-specific settings loaded from .gemini directory.
    
    These settings override global settings when working within
    a specific project directory.
    """
    
    model_config = SettingsConfigDict(
        env_file=".gemini/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Project-specific model preferences
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    
    # Project-specific tool restrictions
    allowed_tools: Optional[List[str]] = None
    auto_confirm: Optional[bool] = None
    
    # Project ignore patterns  
    ignore_patterns: List[str] = Field(
        default_factory=lambda: [
            "*.pyc",
            "__pycache__/",
            "node_modules/",
            ".git/",
            "*.log"
        ]
    )
    
    @classmethod
    def load_from_directory(cls, directory: Path) -> Optional["ProjectSettings"]:
        """Load project settings from a directory if .my-cli exists."""
        my_cli_dir = directory / ".my-cli"
        if not my_cli_dir.exists():
            return None
        
        config_file = my_cli_dir / "config.toml"
        if config_file.exists():
            # TODO: Implement TOML loading in Phase 1.3
            pass
        
        return cls()


def get_settings() -> MyCliSettings:
    """Get the current My CLI settings."""
    return MyCliSettings()


def get_effective_settings(project_dir: Optional[Path] = None) -> MyCliSettings:
    """
    Get effective settings by combining global and project settings.
    
    Args:
        project_dir: Project directory to check for project-specific settings
        
    Returns:
        Combined settings with project settings taking precedence
    """
    global_settings = get_settings()
    
    if project_dir:
        project_settings = ProjectSettings.load_from_directory(project_dir)
        if project_settings:
            # Merge project settings into global settings
            # TODO: Implement proper merging logic in Phase 1.3
            pass
    
    return global_settings