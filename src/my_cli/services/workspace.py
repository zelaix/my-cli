"""
Workspace context service for My CLI.

This module provides workspace management and context services,
mirroring the functionality of the original Gemini CLI's WorkspaceContext.
"""

import asyncio
import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Set
import logging
from dataclasses import dataclass, asdict
from enum import Enum

from .file_discovery import FileDiscoveryService, FileFilteringOptions
from .git_service import GitService

logger = logging.getLogger(__name__)


class ProjectType(Enum):
    """Types of projects that can be detected."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    CPP = "cpp"
    CSHARP = "csharp"
    PHP = "php"
    RUBY = "ruby"
    UNKNOWN = "unknown"


@dataclass
class ProjectInfo:
    """Information about a detected project."""
    type: ProjectType
    name: str
    root_path: str
    config_files: List[str]
    main_files: List[str]
    dependencies: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class WorkspaceStats:
    """Statistics about the workspace."""
    total_files: int
    code_files: int
    total_size: int
    project_types: List[ProjectType]
    git_status: Optional[str]


class WorkspaceContext:
    """Service for managing workspace context and project detection."""
    
    # Project detection patterns
    PROJECT_PATTERNS = {
        ProjectType.PYTHON: {
            'config_files': [
                'pyproject.toml', 'setup.py', 'requirements.txt', 
                'Pipfile', 'poetry.lock', 'environment.yml'
            ],
            'main_files': ['main.py', 'app.py', '__init__.py'],
            'extensions': ['.py', '.pyx', '.pyi']
        },
        ProjectType.JAVASCRIPT: {
            'config_files': [
                'package.json', 'package-lock.json', 'yarn.lock',
                'webpack.config.js', 'rollup.config.js'
            ],
            'main_files': ['index.js', 'main.js', 'app.js'],
            'extensions': ['.js', '.jsx', '.mjs']
        },
        ProjectType.TYPESCRIPT: {
            'config_files': [
                'tsconfig.json', 'package.json', 'yarn.lock',
                'webpack.config.ts', 'vite.config.ts'
            ],
            'main_files': ['index.ts', 'main.ts', 'app.ts'],
            'extensions': ['.ts', '.tsx', '.d.ts']
        },
        ProjectType.JAVA: {
            'config_files': [
                'pom.xml', 'build.gradle', 'build.gradle.kts',
                'settings.gradle', 'maven.xml'
            ],
            'main_files': ['Main.java', 'Application.java'],
            'extensions': ['.java', '.kt', '.scala']
        },
        ProjectType.GO: {
            'config_files': ['go.mod', 'go.sum', 'Gopkg.toml'],
            'main_files': ['main.go'],
            'extensions': ['.go']
        },
        ProjectType.RUST: {
            'config_files': ['Cargo.toml', 'Cargo.lock'],
            'main_files': ['main.rs', 'lib.rs'],
            'extensions': ['.rs']
        },
        ProjectType.CPP: {
            'config_files': [
                'CMakeLists.txt', 'Makefile', 'configure.ac',
                'meson.build', 'conanfile.txt'
            ],
            'main_files': ['main.cpp', 'main.c', 'main.cc'],
            'extensions': ['.cpp', '.c', '.cc', '.h', '.hpp']
        },
        ProjectType.CSHARP: {
            'config_files': [
                '*.csproj', '*.sln', 'Directory.Build.props',
                'nuget.config', 'global.json'
            ],
            'main_files': ['Program.cs', 'Main.cs'],
            'extensions': ['.cs', '.vb', '.fs']
        },
        ProjectType.PHP: {
            'config_files': ['composer.json', 'composer.lock'],
            'main_files': ['index.php', 'app.php'],
            'extensions': ['.php', '.phtml']
        },
        ProjectType.RUBY: {
            'config_files': ['Gemfile', 'Gemfile.lock', 'Rakefile'],
            'main_files': ['main.rb', 'app.rb'],
            'extensions': ['.rb', '.rake']
        }
    }
    
    def __init__(
        self,
        root_directory: str,
        include_directories: Optional[List[str]] = None
    ):
        """Initialize workspace context.
        
        Args:
            root_directory: Root directory of the workspace
            include_directories: Additional directories to include
        """
        self.root_directory = Path(root_directory).resolve()
        self.include_directories = [
            Path(d).resolve() for d in (include_directories or [])
        ]
        
        # Services
        self.file_service = FileDiscoveryService(str(self.root_directory))
        self.git_service = GitService(str(self.root_directory))
        
        # Cached data
        self._projects: Optional[List[ProjectInfo]] = None
        self._workspace_stats: Optional[WorkspaceStats] = None
        self._context_cache: Dict[str, Any] = {}
    
    async def initialize(self) -> None:
        """Initialize the workspace context."""
        await self.git_service.initialize()
        await self._detect_projects()
    
    async def get_projects(self, force_refresh: bool = False) -> List[ProjectInfo]:
        """Get detected projects in the workspace.
        
        Args:
            force_refresh: Force re-detection of projects
            
        Returns:
            List of detected projects
        """
        if self._projects is None or force_refresh:
            await self._detect_projects()
        return self._projects or []
    
    async def get_workspace_stats(self, force_refresh: bool = False) -> WorkspaceStats:
        """Get workspace statistics.
        
        Args:
            force_refresh: Force recalculation of stats
            
        Returns:
            Workspace statistics
        """
        if self._workspace_stats is None or force_refresh:
            await self._calculate_workspace_stats()
        return self._workspace_stats or WorkspaceStats(
            total_files=0,
            code_files=0,
            total_size=0,
            project_types=[],
            git_status=None
        )
    
    async def get_context_summary(self) -> Dict[str, Any]:
        """Get a summary of workspace context for AI consumption.
        
        Returns:
            Dictionary with workspace context information
        """
        projects = await self.get_projects()
        stats = await self.get_workspace_stats()
        
        context = {
            'workspace_root': str(self.root_directory),
            'is_git_repository': self.git_service.is_git_repository,
            'current_branch': await self.git_service.get_current_branch() if self.git_service.is_git_repository else None,
            'projects': [project.to_dict() for project in projects],
            'statistics': {
                'total_files': stats.total_files,
                'code_files': stats.code_files,
                'project_types': [pt.value for pt in stats.project_types]
            }
        }
        
        # Add Git status if available
        if self.git_service.is_git_repository:
            git_status = await self.git_service.get_status()
            if git_status:
                context['git_changes'] = {
                    'modified': len([s for s in git_status if s.is_modified]),
                    'added': len([s for s in git_status if s.is_added]),
                    'deleted': len([s for s in git_status if s.is_deleted]),
                    'untracked': len([s for s in git_status if s.is_untracked])
                }
        
        return context
    
    async def find_relevant_files(
        self,
        query: str,
        max_files: int = 20
    ) -> List[Path]:
        """Find files relevant to a query.
        
        Args:
            query: Search query
            max_files: Maximum number of files to return
            
        Returns:
            List of relevant file paths
        """
        # Simple implementation - can be enhanced with semantic search
        patterns = [
            f"*{query}*",
            f"*{query.lower()}*",
            f"*{query.upper()}*"
        ]
        
        relevant_files = []
        for pattern in patterns:
            files = await self.file_service.find_files_by_pattern(
                pattern, max_files=max_files - len(relevant_files)
            )
            relevant_files.extend(files)
            if len(relevant_files) >= max_files:
                break
        
        return relevant_files[:max_files]
    
    async def get_project_context(self, project_type: Optional[ProjectType] = None) -> Dict[str, Any]:
        """Get context specific to a project type.
        
        Args:
            project_type: Specific project type to get context for
            
        Returns:
            Project-specific context information
        """
        projects = await self.get_projects()
        
        if project_type:
            target_projects = [p for p in projects if p.type == project_type]
        else:
            target_projects = projects
        
        if not target_projects:
            return {}
        
        # Get the primary project (first one found)
        project = target_projects[0]
        
        context = {
            'project': project.to_dict(),
            'config_files': [],
            'main_files': [],
            'recent_changes': []
        }
        
        # Load config files content
        for config_file in project.config_files:
            config_path = Path(project.root_path) / config_file
            if config_path.exists():
                content = await self.file_service.get_file_content(config_path)
                if content:
                    context['config_files'].append({
                        'path': config_file,
                        'content': content[:1000]  # Limit content size
                    })
        
        # Get recent Git changes if available
        if self.git_service.is_git_repository:
            recent_commits = await self.git_service.get_log(max_count=5)
            context['recent_changes'] = [
                {
                    'hash': commit.short_hash,
                    'message': commit.message,
                    'date': commit.date
                }
                for commit in recent_commits
            ]
        
        return context
    
    async def _detect_projects(self) -> None:
        """Detect projects in the workspace."""
        projects = []
        
        # Check root directory
        project = await self._detect_project_in_directory(self.root_directory)
        if project:
            projects.append(project)
        
        # Check subdirectories for additional projects
        try:
            for item in self.root_directory.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    subproject = await self._detect_project_in_directory(item)
                    if subproject and subproject.root_path != str(self.root_directory):
                        projects.append(subproject)
        except Exception as e:
            logger.error(f"Error scanning subdirectories: {e}")
        
        self._projects = projects
    
    async def _detect_project_in_directory(self, directory: Path) -> Optional[ProjectInfo]:
        """Detect project type in a specific directory.
        
        Args:
            directory: Directory to analyze
            
        Returns:
            ProjectInfo if project detected, None otherwise
        """
        try:
            files = list(directory.iterdir())
            file_names = {f.name.lower() for f in files if f.is_file()}
            
            # Try to detect project type based on config files
            for project_type, patterns in self.PROJECT_PATTERNS.items():
                config_files = patterns['config_files']
                
                # Check for exact matches and glob patterns
                found_configs = []
                for config in config_files:
                    if '*' in config:
                        # Handle glob patterns
                        import fnmatch
                        matching = [f for f in file_names if fnmatch.fnmatch(f, config.lower())]
                        found_configs.extend(matching)
                    elif config.lower() in file_names:
                        found_configs.append(config)
                
                if found_configs:
                    # Found config files for this project type
                    main_files = [
                        f for f in patterns['main_files']
                        if f.lower() in file_names
                    ]
                    
                    # Try to extract project name
                    project_name = await self._extract_project_name(
                        directory, project_type, found_configs
                    )
                    
                    return ProjectInfo(
                        type=project_type,
                        name=project_name or directory.name,
                        root_path=str(directory),
                        config_files=found_configs,
                        main_files=main_files,
                        dependencies=await self._extract_dependencies(
                            directory, project_type, found_configs
                        )
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting project in {directory}: {e}")
            return None
    
    async def _extract_project_name(
        self,
        directory: Path,
        project_type: ProjectType,
        config_files: List[str]
    ) -> Optional[str]:
        """Extract project name from config files.
        
        Args:
            directory: Project directory
            project_type: Detected project type
            config_files: Found config files
            
        Returns:
            Project name if found
        """
        try:
            if project_type == ProjectType.PYTHON:
                # Try pyproject.toml first, then setup.py
                for config_file in ['pyproject.toml', 'setup.py']:
                    if config_file in config_files:
                        config_path = directory / config_file
                        content = await self.file_service.get_file_content(config_path)
                        if content and config_file == 'pyproject.toml':
                            # Parse TOML for project name
                            lines = content.split('\n')
                            for line in lines:
                                if line.strip().startswith('name'):
                                    parts = line.split('=', 1)
                                    if len(parts) == 2:
                                        return parts[1].strip().strip('"\'')
                        break
            
            elif project_type in [ProjectType.JAVASCRIPT, ProjectType.TYPESCRIPT]:
                # Try package.json
                if 'package.json' in config_files:
                    config_path = directory / 'package.json'
                    content = await self.file_service.get_file_content(config_path)
                    if content:
                        try:
                            import json
                            data = json.loads(content)
                            return data.get('name')
                        except json.JSONDecodeError:
                            pass
            
            elif project_type == ProjectType.RUST:
                # Try Cargo.toml
                if 'Cargo.toml' in config_files:
                    config_path = directory / 'Cargo.toml'
                    content = await self.file_service.get_file_content(config_path)
                    if content:
                        lines = content.split('\n')
                        for line in lines:
                            if line.strip().startswith('name'):
                                parts = line.split('=', 1)
                                if len(parts) == 2:
                                    return parts[1].strip().strip('"\'')
            
            # Default to directory name
            return directory.name
            
        except Exception as e:
            logger.error(f"Error extracting project name: {e}")
            return directory.name
    
    async def _extract_dependencies(
        self,
        directory: Path,
        project_type: ProjectType,
        config_files: List[str]
    ) -> Dict[str, Any]:
        """Extract project dependencies from config files.
        
        Args:
            directory: Project directory
            project_type: Detected project type
            config_files: Found config files
            
        Returns:
            Dictionary of dependencies
        """
        dependencies = {}
        
        try:
            if project_type in [ProjectType.JAVASCRIPT, ProjectType.TYPESCRIPT]:
                if 'package.json' in config_files:
                    config_path = directory / 'package.json'
                    content = await self.file_service.get_file_content(config_path)
                    if content:
                        try:
                            data = json.loads(content)
                            dependencies.update(data.get('dependencies', {}))
                            dependencies.update(data.get('devDependencies', {}))
                        except json.JSONDecodeError:
                            pass
            
            # Add more dependency extraction logic for other project types
            
        except Exception as e:
            logger.error(f"Error extracting dependencies: {e}")
        
        return dependencies
    
    async def _calculate_workspace_stats(self) -> None:
        """Calculate workspace statistics."""
        try:
            files = await self.file_service.discover_files(max_files=50000)
            
            total_files = len(files)
            code_files = 0
            total_size = 0
            
            for file_path in files:
                try:
                    stat = file_path.stat()
                    total_size += stat.st_size
                    
                    if file_path.suffix.lower() in self.file_service.CODE_EXTENSIONS:
                        code_files += 1
                except Exception:
                    continue
            
            projects = await self.get_projects()
            project_types = list(set(p.type for p in projects))
            
            git_status = None
            if self.git_service.is_git_repository:
                branch = await self.git_service.get_current_branch()
                is_clean = await self.git_service.is_clean_working_tree()
                git_status = f"{branch} ({'clean' if is_clean else 'modified'})"
            
            self._workspace_stats = WorkspaceStats(
                total_files=total_files,
                code_files=code_files,
                total_size=total_size,
                project_types=project_types,
                git_status=git_status
            )
            
        except Exception as e:
            logger.error(f"Error calculating workspace stats: {e}")
            self._workspace_stats = WorkspaceStats(
                total_files=0,
                code_files=0,
                total_size=0,
                project_types=[],
                git_status=None
            )