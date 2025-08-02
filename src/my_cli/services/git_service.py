"""
Git service for My CLI.

This module provides Git operations and repository management,
mirroring the functionality of the original Gemini CLI's GitService.
"""

import asyncio
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class GitOperationError(Exception):
    """Exception raised for Git operation errors."""
    pass


@dataclass
class GitFileStatus:
    """Represents the status of a file in Git."""
    path: str
    status: str  # 'M', 'A', 'D', 'R', 'C', '??', etc.
    staged: bool
    
    @property
    def is_modified(self) -> bool:
        return self.status in ('M', 'MM')
    
    @property
    def is_added(self) -> bool:
        return self.status in ('A', 'AM')
    
    @property
    def is_deleted(self) -> bool:
        return self.status in ('D', 'AD')
    
    @property
    def is_untracked(self) -> bool:
        return self.status == '??'


@dataclass
class GitCommitInfo:
    """Information about a Git commit."""
    hash: str
    short_hash: str
    message: str
    author: str
    date: str
    
    
class GitService:
    """Service for Git operations."""
    
    def __init__(self, repository_path: str):
        """Initialize Git service.
        
        Args:
            repository_path: Path to Git repository
        """
        self.repository_path = Path(repository_path).resolve()
        self._is_git_repo: Optional[bool] = None
        self._git_root: Optional[Path] = None
    
    async def initialize(self) -> None:
        """Initialize the Git service and verify repository."""
        try:
            # Check if this is a Git repository
            result = await self._run_git_command(['rev-parse', '--is-inside-work-tree'])
            self._is_git_repo = result.returncode == 0
            
            if self._is_git_repo:
                # Get repository root
                result = await self._run_git_command(['rev-parse', '--show-toplevel'])
                if result.returncode == 0:
                    self._git_root = Path(result.stdout.strip()).resolve()
                else:
                    self._git_root = self.repository_path
                    
        except Exception as e:
            logger.error(f"Error initializing Git service: {e}")
            self._is_git_repo = False
    
    @property
    def is_git_repository(self) -> bool:
        """Check if the current directory is a Git repository."""
        return self._is_git_repo or False
    
    @property
    def git_root(self) -> Optional[Path]:
        """Get the Git repository root path."""
        return self._git_root
    
    async def get_status(self) -> List[GitFileStatus]:
        """Get Git status of files.
        
        Returns:
            List of file statuses
        """
        if not self.is_git_repository:
            return []
        
        try:
            result = await self._run_git_command(['status', '--porcelain=v1'])
            if result.returncode != 0:
                return []
            
            statuses = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                    
                # Parse porcelain format
                # Format: XY filename
                # X = staged status, Y = unstaged status
                index_status = line[0] if len(line) > 0 else ' '
                worktree_status = line[1] if len(line) > 1 else ' '
                filename = line[3:] if len(line) > 3 else ''
                
                # Combine statuses
                if index_status != ' ' and worktree_status != ' ':
                    status = index_status + worktree_status
                elif index_status != ' ':
                    status = index_status
                elif worktree_status != ' ':
                    status = worktree_status
                else:
                    status = '??'
                
                statuses.append(GitFileStatus(
                    path=filename,
                    status=status,
                    staged=index_status != ' '
                ))
            
            return statuses
            
        except Exception as e:
            logger.error(f"Error getting Git status: {e}")
            return []
    
    async def get_diff(
        self,
        staged: bool = True,
        file_path: Optional[str] = None
    ) -> str:
        """Get Git diff output.
        
        Args:
            staged: Get staged changes if True, unstaged if False
            file_path: Specific file to diff (optional)
            
        Returns:
            Diff output as string
        """
        if not self.is_git_repository:
            return ""
        
        try:
            cmd = ['diff']
            if staged:
                cmd.append('--cached')
            if file_path:
                cmd.append('--')
                cmd.append(file_path)
            
            result = await self._run_git_command(cmd)
            if result.returncode == 0:
                return result.stdout
            else:
                logger.warning(f"Git diff failed: {result.stderr}")
                return ""
                
        except Exception as e:
            logger.error(f"Error getting Git diff: {e}")
            return ""
    
    async def get_log(
        self,
        max_count: int = 10,
        format_string: str = "format:%H|%h|%s|%an|%ad",
        date_format: str = "short"
    ) -> List[GitCommitInfo]:
        """Get Git commit log.
        
        Args:
            max_count: Maximum number of commits to retrieve
            format_string: Git log format string
            date_format: Date format for commits
            
        Returns:
            List of commit information
        """
        if not self.is_git_repository:
            return []
        
        try:
            cmd = [
                'log',
                f'--max-count={max_count}',
                f'--pretty={format_string}',
                f'--date={date_format}'
            ]
            
            result = await self._run_git_command(cmd)
            if result.returncode != 0:
                return []
            
            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                    
                parts = line.split('|', 4)
                if len(parts) >= 5:
                    commits.append(GitCommitInfo(
                        hash=parts[0],
                        short_hash=parts[1],
                        message=parts[2],
                        author=parts[3],
                        date=parts[4]
                    ))
            
            return commits
            
        except Exception as e:
            logger.error(f"Error getting Git log: {e}")
            return []
    
    async def add_files(self, file_paths: List[str]) -> bool:
        """Add files to Git staging area.
        
        Args:
            file_paths: List of file paths to add
            
        Returns:
            True if successful
        """
        if not self.is_git_repository:
            return False
        
        try:
            cmd = ['add'] + file_paths
            result = await self._run_git_command(cmd)
            
            if result.returncode == 0:
                logger.info(f"Added {len(file_paths)} file(s) to staging area")
                return True
            else:
                logger.error(f"Failed to add files: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error adding files to Git: {e}")
            return False
    
    async def commit(
        self,
        message: str,
        amend: bool = False,
        author: Optional[str] = None
    ) -> bool:
        """Create a Git commit.
        
        Args:
            message: Commit message
            amend: Whether to amend the last commit
            author: Author string (optional)
            
        Returns:
            True if successful
        """
        if not self.is_git_repository:
            return False
        
        try:
            cmd = ['commit', '-m', message]
            if amend:
                cmd.append('--amend')
            if author:
                cmd.extend(['--author', author])
            
            result = await self._run_git_command(cmd)
            
            if result.returncode == 0:
                logger.info(f"Created commit: {message[:50]}...")
                return True
            else:
                logger.error(f"Failed to create commit: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating Git commit: {e}")
            return False
    
    async def get_current_branch(self) -> Optional[str]:
        """Get the current Git branch name.
        
        Returns:
            Current branch name or None if error
        """
        if not self.is_git_repository:
            return None
        
        try:
            result = await self._run_git_command(['branch', '--show-current'])
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting current branch: {e}")
            return None
    
    async def get_remote_url(self, remote: str = 'origin') -> Optional[str]:
        """Get remote repository URL.
        
        Args:
            remote: Remote name (default: origin)
            
        Returns:
            Remote URL or None if not found
        """
        if not self.is_git_repository:
            return None
        
        try:
            result = await self._run_git_command(['remote', 'get-url', remote])
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting remote URL: {e}")
            return None
    
    async def is_clean_working_tree(self) -> bool:
        """Check if working tree is clean (no uncommitted changes).
        
        Returns:
            True if working tree is clean
        """
        if not self.is_git_repository:
            return True
        
        try:
            result = await self._run_git_command(['status', '--porcelain'])
            return result.returncode == 0 and not result.stdout.strip()
            
        except Exception as e:
            logger.error(f"Error checking working tree status: {e}")
            return False
    
    async def get_file_at_commit(
        self,
        file_path: str,
        commit_hash: str = 'HEAD'
    ) -> Optional[str]:
        """Get file content at a specific commit.
        
        Args:
            file_path: Path to file
            commit_hash: Commit hash (default: HEAD)
            
        Returns:
            File content or None if error
        """
        if not self.is_git_repository:
            return None
        
        try:
            result = await self._run_git_command(['show', f'{commit_hash}:{file_path}'])
            if result.returncode == 0:
                return result.stdout
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting file at commit: {e}")
            return None
    
    async def _run_git_command(
        self,
        args: List[str],
        cwd: Optional[Path] = None
    ) -> subprocess.CompletedProcess:
        """Run a Git command asynchronously.
        
        Args:
            args: Git command arguments
            cwd: Working directory (default: repository path)
            
        Returns:
            Completed process result
            
        Raises:
            GitOperationError: If Git command fails
        """
        if cwd is None:
            cwd = self.repository_path
        
        try:
            process = await asyncio.create_subprocess_exec(
                'git', *args,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            result = subprocess.CompletedProcess(
                args=['git'] + args,
                returncode=process.returncode,
                stdout=stdout.decode('utf-8', errors='ignore'),
                stderr=stderr.decode('utf-8', errors='ignore')
            )
            
            return result
            
        except Exception as e:
            raise GitOperationError(f"Failed to run git command {args}: {e}")
    
    async def create_checkpoint(self, message: str) -> bool:
        """Create a checkpoint commit if there are changes.
        
        Args:
            message: Checkpoint commit message
            
        Returns:
            True if checkpoint was created
        """
        if not self.is_git_repository:
            return False
        
        try:
            # Check if there are any changes
            if await self.is_clean_working_tree():
                return False
            
            # Stage all changes
            result = await self._run_git_command(['add', '-A'])
            if result.returncode != 0:
                logger.error(f"Failed to stage changes for checkpoint: {result.stderr}")
                return False
            
            # Create checkpoint commit
            return await self.commit(f"[CHECKPOINT] {message}")
            
        except Exception as e:
            logger.error(f"Error creating checkpoint: {e}")
            return False