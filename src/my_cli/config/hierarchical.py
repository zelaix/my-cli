"""
Hierarchical configuration system for My CLI.

This module implements a hierarchical configuration system that loads and merges
settings from multiple sources in order of precedence, similar to the original
Gemini CLI's configuration system.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import logging
from enum import Enum
from dataclasses import dataclass

import commentjson
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class SettingScope(Enum):
    """Configuration scope levels."""
    DEFAULT = "default"
    USER = "user" 
    PROJECT = "project"
    SYSTEM = "system"
    ENVIRONMENT = "environment"
    COMMAND_LINE = "command_line"


@dataclass
class SettingsFile:
    """Represents a settings file with its path and content."""
    path: Path
    settings: Dict[str, Any]
    scope: SettingScope
    exists: bool = True
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class HierarchicalConfigLoader:
    """
    Hierarchical configuration loader that merges settings from multiple sources.
    
    Configuration precedence (higher numbers override lower):
    1. Default values (hardcoded)
    2. User settings (~/.config/my-cli/settings.json)
    3. Project settings (.my-cli/settings.json)
    4. System settings (/etc/my-cli/settings.json)
    5. Environment variables
    6. Command-line arguments
    """
    
    # Configuration directory names
    CONFIG_DIR_NAME = ".my-cli"
    SETTINGS_FILE_NAME = "settings.json"
    
    def __init__(self, working_directory: Optional[Path] = None):
        """Initialize the hierarchical config loader.
        
        Args:
            working_directory: Working directory for project settings discovery
        """
        self.working_directory = Path(working_directory or Path.cwd()).resolve()
        self._settings_files: Dict[SettingScope, SettingsFile] = {}
        self._merged_settings: Optional[Dict[str, Any]] = None
        
    def load_all_settings(self) -> Dict[str, Any]:
        """Load and merge all configuration sources.
        
        Returns:
            Merged configuration dictionary
        """
        # Load settings from all sources
        self._load_default_settings()
        self._load_user_settings()
        self._load_project_settings()
        self._load_system_settings()
        self._load_environment_variables()
        
        # Merge in precedence order
        self._merged_settings = self._merge_settings()
        
        return self._merged_settings
    
    def get_settings_file(self, scope: SettingScope) -> Optional[SettingsFile]:
        """Get settings file for a specific scope.
        
        Args:
            scope: Configuration scope
            
        Returns:
            Settings file or None if not loaded
        """
        return self._settings_files.get(scope)
    
    def get_all_settings_files(self) -> Dict[SettingScope, SettingsFile]:
        """Get all loaded settings files.
        
        Returns:
            Dictionary of settings files by scope
        """
        return self._settings_files.copy()
    
    def save_settings(self, scope: SettingScope, settings: Dict[str, Any]) -> bool:
        """Save settings to a specific scope.
        
        Args:
            scope: Configuration scope to save to
            settings: Settings dictionary to save
            
        Returns:
            True if saved successfully
        """
        if scope == SettingScope.DEFAULT:
            raise ValueError("Cannot save to DEFAULT scope")
        
        if scope == SettingScope.ENVIRONMENT:
            raise ValueError("Cannot save to ENVIRONMENT scope")
        
        settings_file = self._settings_files.get(scope)
        if not settings_file:
            # Create new settings file
            file_path = self._get_settings_path(scope)
            settings_file = SettingsFile(
                path=file_path,
                settings={},
                scope=scope,
                exists=False
            )
            self._settings_files[scope] = settings_file
        
        try:
            # Ensure directory exists
            settings_file.path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write settings file
            with open(settings_file.path, 'w', encoding='utf-8') as f:
                commentjson.dump(settings, f, indent=2, ensure_ascii=False)
            
            # Update in-memory settings
            settings_file.settings = settings
            settings_file.exists = True
            
            # Invalidate merged settings cache
            self._merged_settings = None
            
            logger.info(f"Saved settings to {scope.value}: {settings_file.path}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to save settings to {scope.value}: {e}"
            logger.error(error_msg)
            settings_file.errors.append(error_msg)
            return False
    
    def _load_default_settings(self) -> None:
        """Load default hardcoded settings."""
        default_settings = {
            "api_key": None,
            "model": "gemini-2.0-flash-exp",
            "theme": "default",
            "auto_confirm": False,
            "max_tokens": 8192,
            "temperature": 0.7,
            "timeout": 30,
            "log_level": "INFO",
            "debug": False,
            "allowed_tools": [
                "read_file",
                "write_file", 
                "list_directory",
                "grep",
                "shell",
                "web_search"
            ],
            "file_filtering": {
                "respect_git_ignore": True,
                "respect_my_cli_ignore": True,
                "enable_recursive_file_search": True
            },
            "max_history_length": 100
        }
        
        self._settings_files[SettingScope.DEFAULT] = SettingsFile(
            path=Path("(default)"),
            settings=default_settings,
            scope=SettingScope.DEFAULT,
            exists=True
        )
    
    def _load_user_settings(self) -> None:
        """Load user-level settings."""
        user_config_dir = self._get_user_config_dir()
        settings_path = user_config_dir / self.SETTINGS_FILE_NAME
        
        self._settings_files[SettingScope.USER] = self._load_settings_file(
            settings_path, SettingScope.USER
        )
    
    def _load_project_settings(self) -> None:
        """Load project-level settings."""
        project_config_dir = self._find_project_config_dir()
        if project_config_dir:
            settings_path = project_config_dir / self.SETTINGS_FILE_NAME
            self._settings_files[SettingScope.PROJECT] = self._load_settings_file(
                settings_path, SettingScope.PROJECT
            )
        else:
            # Create empty project settings
            self._settings_files[SettingScope.PROJECT] = SettingsFile(
                path=self.working_directory / self.CONFIG_DIR_NAME / self.SETTINGS_FILE_NAME,
                settings={},
                scope=SettingScope.PROJECT,
                exists=False
            )
    
    def _load_system_settings(self) -> None:
        """Load system-level settings."""
        system_settings_path = self._get_system_settings_path()
        
        self._settings_files[SettingScope.SYSTEM] = self._load_settings_file(
            system_settings_path, SettingScope.SYSTEM
        )
    
    def _load_environment_variables(self) -> None:
        """Load settings from environment variables."""
        env_settings = {}
        
        # Map environment variables to settings
        env_mapping = {
            "MY_CLI_API_KEY": "api_key",
            "MY_CLI_MODEL": "model", 
            "MY_CLI_THEME": "theme",
            "MY_CLI_AUTO_CONFIRM": ("auto_confirm", self._parse_bool),
            "MY_CLI_MAX_TOKENS": ("max_tokens", int),
            "MY_CLI_TEMPERATURE": ("temperature", float),
            "MY_CLI_TIMEOUT": ("timeout", int),
            "MY_CLI_LOG_LEVEL": "log_level",
            "MY_CLI_DEBUG": ("debug", self._parse_bool),
        }
        
        for env_var, setting_info in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    if isinstance(setting_info, tuple):
                        setting_key, converter = setting_info
                        env_settings[setting_key] = converter(value)
                    else:
                        env_settings[setting_info] = value
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid value for {env_var}: {value} - {e}")
        
        self._settings_files[SettingScope.ENVIRONMENT] = SettingsFile(
            path=Path("(environment)"),
            settings=env_settings,
            scope=SettingScope.ENVIRONMENT,
            exists=bool(env_settings)
        )
    
    def _load_settings_file(self, file_path: Path, scope: SettingScope) -> SettingsFile:
        """Load settings from a JSON file.
        
        Args:
            file_path: Path to settings file
            scope: Configuration scope
            
        Returns:
            SettingsFile with loaded data
        """
        settings_file = SettingsFile(
            path=file_path,
            settings={},
            scope=scope,
            exists=file_path.exists()
        )
        
        if not settings_file.exists:
            logger.debug(f"Settings file not found: {file_path}")
            return settings_file
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Parse JSON with comments
            parsed_settings = commentjson.loads(content)
            
            # Resolve environment variables in settings
            resolved_settings = self._resolve_env_vars(parsed_settings)
            
            settings_file.settings = resolved_settings
            logger.debug(f"Loaded settings from {scope.value}: {file_path}")
            
        except commentjson.JSONDecodeError as e:
            error_msg = f"Invalid JSON in {file_path}: {e}"
            logger.error(error_msg)
            settings_file.errors.append(error_msg)
            
        except Exception as e:
            error_msg = f"Error loading {file_path}: {e}"
            logger.error(error_msg)
            settings_file.errors.append(error_msg)
        
        return settings_file
    
    def _resolve_env_vars(self, obj: Any) -> Any:
        """Resolve environment variables in configuration values.
        
        Supports both $VAR_NAME and ${VAR_NAME} syntax.
        
        Args:
            obj: Object to process (recursive)
            
        Returns:
            Object with environment variables resolved
        """
        if isinstance(obj, str):
            return self._resolve_env_vars_in_string(obj)
        elif isinstance(obj, dict):
            return {key: self._resolve_env_vars(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._resolve_env_vars(item) for item in obj]
        else:
            return obj
    
    def _resolve_env_vars_in_string(self, value: str) -> str:
        """Resolve environment variables in a string.
        
        Args:
            value: String that may contain environment variables
            
        Returns:
            String with environment variables resolved
        """
        # Pattern to match $VAR_NAME or ${VAR_NAME}
        env_var_pattern = re.compile(r'\$(?:(\w+)|\{([^}]+)\})')
        
        def replace_env_var(match):
            var_name = match.group(1) or match.group(2)
            env_value = os.environ.get(var_name)
            if env_value is not None:
                return env_value
            else:
                logger.warning(f"Environment variable not found: {var_name}")
                return match.group(0)  # Return original if not found
        
        return env_var_pattern.sub(replace_env_var, value)
    
    def _merge_settings(self) -> Dict[str, Any]:
        """Merge settings from all sources in precedence order.
        
        Returns:
            Merged settings dictionary
        """
        merged = {}
        
        # Merge in precedence order (lower precedence first)
        precedence_order = [
            SettingScope.DEFAULT,
            SettingScope.USER,
            SettingScope.PROJECT,
            SettingScope.SYSTEM,
            SettingScope.ENVIRONMENT,
        ]
        
        for scope in precedence_order:
            settings_file = self._settings_files.get(scope)
            if settings_file and settings_file.settings:
                merged = self._deep_merge(merged, settings_file.settings)
        
        return merged
    
    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            overlay: Dictionary to overlay on base
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in overlay.items():
            if (key in result 
                and isinstance(result[key], dict) 
                and isinstance(value, dict)):
                # Recursively merge nested dictionaries
                result[key] = self._deep_merge(result[key], value)
            else:
                # Override value
                result[key] = value
        
        return result
    
    def _get_user_config_dir(self) -> Path:
        """Get user configuration directory path.
        
        Returns:
            Path to user config directory
        """
        # Use XDG_CONFIG_HOME if set, otherwise ~/.config
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            return Path(xdg_config_home) / "my-cli"
        else:
            return Path.home() / ".config" / "my-cli"
    
    def _find_project_config_dir(self) -> Optional[Path]:
        """Find project configuration directory by searching upward.
        
        Returns:
            Path to project config directory or None if not found
        """
        current_dir = self.working_directory
        
        while current_dir != current_dir.parent:
            config_dir = current_dir / self.CONFIG_DIR_NAME
            if config_dir.exists() and config_dir.is_dir():
                return config_dir
            
            # Stop at git repository root
            if (current_dir / ".git").exists():
                break
                
            current_dir = current_dir.parent
        
        return None
    
    def _get_system_settings_path(self) -> Path:
        """Get system settings file path.
        
        Returns:
            Path to system settings file
        """
        system_override = os.environ.get("MY_CLI_SYSTEM_SETTINGS_PATH")
        if system_override:
            return Path(system_override)
        
        # Platform-specific system settings paths
        import platform
        system = platform.system().lower()
        
        if system == "darwin":  # macOS
            return Path("/Library/Application Support/my-cli/settings.json")
        elif system == "windows":
            return Path("C:/ProgramData/my-cli/settings.json")
        else:  # Linux and others
            return Path("/etc/my-cli/settings.json")
    
    def _get_settings_path(self, scope: SettingScope) -> Path:
        """Get settings file path for a specific scope.
        
        Args:
            scope: Configuration scope
            
        Returns:
            Path to settings file
        """
        if scope == SettingScope.USER:
            return self._get_user_config_dir() / self.SETTINGS_FILE_NAME
        elif scope == SettingScope.PROJECT:
            return self.working_directory / self.CONFIG_DIR_NAME / self.SETTINGS_FILE_NAME
        elif scope == SettingScope.SYSTEM:
            return self._get_system_settings_path()
        else:
            raise ValueError(f"Cannot get path for scope: {scope}")
    
    def _parse_bool(self, value: str) -> bool:
        """Parse boolean value from string.
        
        Args:
            value: String value to parse
            
        Returns:
            Boolean value
        """
        return value.lower() in ("true", "1", "yes", "on")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the configuration state.
        
        Returns:
            Configuration summary
        """
        summary = {
            "sources": {},
            "errors": [],
            "working_directory": str(self.working_directory)
        }
        
        for scope, settings_file in self._settings_files.items():
            summary["sources"][scope.value] = {
                "path": str(settings_file.path),
                "exists": settings_file.exists,
                "settings_count": len(settings_file.settings),
                "errors": settings_file.errors
            }
            
            # Collect all errors
            summary["errors"].extend(settings_file.errors)
        
        return summary