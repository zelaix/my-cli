"""
Enhanced .env file loading system for My CLI.

This module provides enhanced .env file loading with hierarchical search,
similar to the original Gemini CLI's environment loading system.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class EnvFileLoader:
    """
    Enhanced .env file loader with hierarchical search.
    
    Search order (stops at first file found):
    1. Current directory: .my-cli/.env → .env
    2. Parent directories (up to git root or home): .my-cli/.env → .env  
    3. Home directory: ~/.my-cli/.env → ~/.env
    """
    
    CONFIG_DIR_NAME = ".my-cli"
    ENV_FILE_NAME = ".env"
    
    def __init__(self, working_directory: Optional[Path] = None):
        """Initialize env file loader.
        
        Args:
            working_directory: Starting directory for search
        """
        self.working_directory = Path(working_directory or Path.cwd()).resolve()
        self._loaded_file: Optional[Path] = None
        self._loaded_vars: Dict[str, str] = {}
    
    def load_env_file(self) -> Optional[Path]:
        """Load environment variables from .env file.
        
        Returns:
            Path to loaded .env file or None if none found
        """
        env_file_path = self._find_env_file()
        
        if env_file_path:
            try:
                # Load the .env file
                load_dotenv(env_file_path, override=False, verbose=True)
                
                # Store loaded file info
                self._loaded_file = env_file_path
                self._load_env_vars_from_file(env_file_path)
                
                logger.info(f"Loaded environment variables from: {env_file_path}")
                return env_file_path
                
            except Exception as e:
                logger.error(f"Error loading .env file {env_file_path}: {e}")
        else:
            logger.debug("No .env file found in search path")
        
        return None
    
    def get_loaded_file(self) -> Optional[Path]:
        """Get path to the loaded .env file.
        
        Returns:
            Path to loaded file or None
        """
        return self._loaded_file
    
    def get_loaded_vars(self) -> Dict[str, str]: 
        """Get variables loaded from .env file.
        
        Returns:
            Dictionary of loaded environment variables
        """
        return self._loaded_vars.copy()
    
    def _find_env_file(self) -> Optional[Path]:
        """Find the first .env file in the search hierarchy.
        
        Returns:
            Path to .env file or None if not found
        """
        # Start from working directory and search upward
        current_dir = self.working_directory
        
        while current_dir != current_dir.parent:
            # Check for .my-cli/.env first (preferred)
            my_cli_env = current_dir / self.CONFIG_DIR_NAME / self.ENV_FILE_NAME
            if my_cli_env.exists() and my_cli_env.is_file():
                return my_cli_env
            
            # Check for .env in current directory
            env_file = current_dir / self.ENV_FILE_NAME
            if env_file.exists() and env_file.is_file():
                return env_file
            
            # Stop at git repository root or home directory
            if self._should_stop_search(current_dir):
                break
                
            current_dir = current_dir.parent
        
        # Final fallback: check home directory
        home_dir = Path.home()
        
        # Check ~/.my-cli/.env first
        home_my_cli_env = home_dir / self.CONFIG_DIR_NAME / self.ENV_FILE_NAME
        if home_my_cli_env.exists() and home_my_cli_env.is_file():
            return home_my_cli_env
        
        # Check ~/.env
        home_env = home_dir / self.ENV_FILE_NAME
        if home_env.exists() and home_env.is_file():
            return home_env
        
        return None
    
    def _should_stop_search(self, directory: Path) -> bool:
        """Check if search should stop at this directory.
        
        Args:
            directory: Directory to check
            
        Returns:
            True if search should stop
        """
        # Stop at Git repository root
        if (directory / ".git").exists():
            return True
        
        # Stop at home directory
        if directory == Path.home():
            return True
        
        return False
    
    def _load_env_vars_from_file(self, env_file_path: Path) -> None:
        """Load environment variables from file into internal storage.
        
        Args:
            env_file_path: Path to .env file
        """
        try:
            with open(env_file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse KEY=value format
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        self._loaded_vars[key] = value
                    else:
                        logger.warning(f"Invalid line in {env_file_path}:{line_num}: {line}")
        
        except Exception as e:
            logger.error(f"Error reading .env file {env_file_path}: {e}")
    
    def create_example_env_file(self, target_dir: Optional[Path] = None, scope: str = "project") -> Path:
        """Create an example .env file.
        
        Args:
            target_dir: Directory to create file in (default: working directory)
            scope: Scope of the .env file ('project' or 'user')
            
        Returns:
            Path to created example file
        """
        if target_dir is None:
            if scope == "user":
                target_dir = Path.home() / self.CONFIG_DIR_NAME
            else:
                target_dir = self.working_directory / self.CONFIG_DIR_NAME
        
        # Ensure directory exists
        target_dir.mkdir(parents=True, exist_ok=True)
        
        env_file_path = target_dir / self.ENV_FILE_NAME
        
        # Example content
        example_content = '''# My CLI Configuration
# This file contains environment variables for My CLI configuration.
# Lines starting with # are comments and will be ignored.

# Required: Your AI API key
MY_CLI_API_KEY=your-api-key-here

# Optional: Model configuration
MY_CLI_MODEL=gemini-2.0-flash-exp
MY_CLI_TEMPERATURE=0.7
MY_CLI_MAX_TOKENS=8192

# Optional: UI configuration  
MY_CLI_THEME=default
MY_CLI_AUTO_CONFIRM=false

# Optional: Debug settings
MY_CLI_DEBUG=false
MY_CLI_LOG_LEVEL=INFO

# Optional: Timeout settings
MY_CLI_TIMEOUT=30
'''
        
        try:
            with open(env_file_path, 'w', encoding='utf-8') as f:
                f.write(example_content)
            
            logger.info(f"Created example .env file: {env_file_path}")
            return env_file_path
            
        except Exception as e:
            logger.error(f"Error creating example .env file: {e}")
            raise
    
    def get_search_paths(self) -> list[Path]:
        """Get list of all paths that would be searched for .env files.
        
        Returns:
            List of search paths in order
        """
        search_paths = []
        
        # Search upward from working directory
        current_dir = self.working_directory
        
        while current_dir != current_dir.parent:
            # Add .my-cli/.env path
            search_paths.append(current_dir / self.CONFIG_DIR_NAME / self.ENV_FILE_NAME)
            
            # Add .env path
            search_paths.append(current_dir / self.ENV_FILE_NAME)
            
            # Stop at git repository root or home directory
            if self._should_stop_search(current_dir):
                break
                
            current_dir = current_dir.parent
        
        # Add home directory paths
        home_dir = Path.home()
        search_paths.append(home_dir / self.CONFIG_DIR_NAME / self.ENV_FILE_NAME)
        search_paths.append(home_dir / self.ENV_FILE_NAME)
        
        return search_paths


def load_env_with_hierarchy(working_directory: Optional[Path] = None) -> Optional[Path]:
    """Convenience function to load .env file with hierarchical search.
    
    Args:
        working_directory: Starting directory for search
        
    Returns:
        Path to loaded .env file or None
    """
    loader = EnvFileLoader(working_directory)
    return loader.load_env_file()


def create_example_env(target_dir: Optional[Path] = None, scope: str = "project") -> Path:
    """Convenience function to create example .env file.
    
    Args:
        target_dir: Directory to create file in
        scope: Scope of the .env file
        
    Returns:
        Path to created example file
    """
    loader = EnvFileLoader()
    return loader.create_example_env_file(target_dir, scope)