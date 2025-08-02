"""Shell tool implementation with command allowlist and confirmation workflows."""

import asyncio
import os
import subprocess
import signal
import time
from typing import Dict, Any, List, Optional, Set, Union

from ..base import ModifyingTool
from ..types import (
    Icon,
    ToolLocation,
    ToolResult,
    ToolCallConfirmationDetails,
    ToolExecuteConfirmationDetails,
    ToolConfirmationOutcome
)
# Avoid circular import


class ShellToolParams:
    """Parameters for the Shell tool."""
    command: str
    description: Optional[str] = None
    directory: Optional[str] = None


class ShellTool(ModifyingTool):
    """Tool for executing shell commands with safety confirmation."""
    
    # Commands that are generally safe and don't need confirmation
    SAFE_COMMANDS = {
        'ls', 'dir', 'pwd', 'whoami', 'date', 'echo', 'cat', 'head', 'tail',
        'grep', 'find', 'which', 'where', 'type', 'ps', 'top', 'df', 'du',
        'free', 'uname', 'id', 'groups', 'env', 'printenv', 'history'
    }
    
    # Commands that should never be allowed
    DANGEROUS_COMMANDS = {
        'rm', 'rmdir', 'del', 'format', 'fdisk', 'mkfs', 'dd', 'shred',
        'halt', 'shutdown', 'reboot', 'poweroff', 'init', 'telinit',
        'kill', 'killall', 'pkill', 'sudo', 'su', 'chmod', 'chown',
        'passwd', 'usermod', 'userdel', 'groupdel'
    }
    
    def __init__(self, config: Optional[Any] = None):
        schema = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of what the command does"
                },
                "directory": {
                    "type": "string",
                    "description": "Optional: Directory to run the command in (relative to project root)"
                }
            },
            "required": ["command"]
        }
        
        super().__init__(
            name="run_shell_command",
            display_name="Shell Command",
            description="Executes a shell command. Commands are run in a subprocess with output capture. Use with caution for system-modifying operations.",
            icon=Icon.TERMINAL,
            schema=schema,
            config=config
        )
        self.can_update_output = True  # Support live output
        
        # Track allowed commands to avoid repeated confirmations
        self.allowlist: Set[str] = set()
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate Shell tool parameters."""
        command = params.get("command")
        if not command or not command.strip():
            return "command parameter is required and cannot be empty"
        
        # Check for dangerous commands
        command_root = self._get_command_root(command.strip())
        if command_root in self.DANGEROUS_COMMANDS:
            return f"Command '{command_root}' is not allowed for security reasons"
        
        # Validate directory if provided
        directory = params.get("directory")
        if directory:
            if os.path.isabs(directory):
                return "directory must be relative to project root, not absolute"
            
            # Check if directory exists (relative to current working directory or project root)
            work_dir = os.getcwd()
            if self.config and hasattr(self.config, 'project_root'):
                work_dir = getattr(self.config, 'project_root', work_dir)
            
            full_dir_path = os.path.join(work_dir, directory)
            if not os.path.exists(full_dir_path):
                return f"Directory does not exist: {directory}"
            
            if not os.path.isdir(full_dir_path):
                return f"Path is not a directory: {directory}"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get description of what this command will do."""
        command = params.get("command", "<unknown>")
        description = params.get("description")
        directory = params.get("directory")
        
        desc = f"Execute: `{command}`"
        
        if directory:
            desc += f" (in {directory})"
        
        if description:
            desc += f" - {description}"
        
        return desc
    
    def tool_locations(self, params: Dict[str, Any]) -> List[ToolLocation]:
        """Shell commands don't have specific file locations."""
        directory = params.get("directory")
        if directory:
            work_dir = os.getcwd()
            if self.config and hasattr(self.config, 'project_root'):
                work_dir = getattr(self.config, 'project_root', work_dir)
            full_path = os.path.join(work_dir, directory)
            return [ToolLocation(path=full_path)]
        return []
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        abort_signal: asyncio.Event
    ) -> Union[ToolCallConfirmationDetails, bool]:
        """Check if command needs user confirmation."""
        validation_error = self.validate_tool_params(params)
        if validation_error:
            return False  # Will fail in execute, no need to confirm
        
        command = params["command"].strip()
        command_root = self._get_command_root(command)
        
        # Skip confirmation for safe commands or already approved commands
        if command_root in self.SAFE_COMMANDS or command_root in self.allowlist:
            return False
        
        # Create confirmation details
        confirmation = ToolExecuteConfirmationDetails(
            title="Confirm Shell Command",
            description=f"Execute shell command: {command}",
            command=command,
            root_command=command_root,
            on_confirm=self._handle_confirmation
        )
        
        return confirmation
    
    def _handle_confirmation(self, outcome: ToolConfirmationOutcome) -> None:
        """Handle confirmation outcome."""
        if outcome == ToolConfirmationOutcome.PROCEED_ALWAYS:
            # Add command root to allowlist
            command = getattr(self, '_current_command', None)
            if command:
                command_root = self._get_command_root(command)
                self.allowlist.add(command_root)
    
    async def execute(
        self,
        params: Dict[str, Any],
        abort_signal: asyncio.Event,
        update_callback: Optional[callable] = None
    ) -> ToolResult:
        """Execute the shell command."""
        # Validate parameters
        validation_error = self.validate_tool_params(params)
        if validation_error:
            return self.create_result(
                llm_content=f"Error: {validation_error}",
                return_display=validation_error,
                success=False,
                error=validation_error
            )
        
        command = params["command"].strip()
        directory = params.get("directory")
        
        # Store current command for confirmation handler
        self._current_command = command
        
        # Determine working directory
        work_dir = os.getcwd()
        if self.config and hasattr(self.config, 'project_root'):
            work_dir = getattr(self.config, 'project_root', work_dir)
        
        if directory:
            work_dir = os.path.join(work_dir, directory)
        
        try:
            # Check for abort before starting
            if abort_signal.is_set():
                return self.create_result(
                    llm_content="Command was cancelled before execution",
                    return_display="Command cancelled",
                    success=False,
                    error="Operation cancelled"
                )
            
            start_time = time.time()
            
            # Create subprocess
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=work_dir,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            stdout_lines = []
            stderr_lines = []
            
            # Read output with live updates
            while process.poll() is None:
                # Check for abort signal
                if abort_signal.is_set():
                    # Terminate the process
                    if os.name != 'nt':
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    else:
                        process.terminate()
                    
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        if os.name != 'nt':
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        else:
                            process.kill()
                    
                    return self.create_result(
                        llm_content="Command was cancelled during execution",
                        return_display="Command cancelled",
                        success=False,
                        error="Operation cancelled"
                    )
                
                # Read available output
                try:
                    stdout_line = process.stdout.readline()
                    if stdout_line:
                        stdout_lines.append(stdout_line)
                        if update_callback:
                            current_output = ''.join(stdout_lines + stderr_lines)
                            update_callback(current_output)
                    
                    stderr_line = process.stderr.readline()
                    if stderr_line:
                        stderr_lines.append(stderr_line)
                        if update_callback:
                            current_output = ''.join(stdout_lines + stderr_lines)
                            update_callback(current_output)
                
                except Exception:
                    # Handle any reading errors
                    break
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
            
            # Get final output
            remaining_stdout, remaining_stderr = process.communicate()
            if remaining_stdout:
                stdout_lines.append(remaining_stdout)
            if remaining_stderr:
                stderr_lines.append(remaining_stderr)
            
            end_time = time.time()
            duration = end_time - start_time
            
            stdout_content = ''.join(stdout_lines).strip()
            stderr_content = ''.join(stderr_lines).strip()
            exit_code = process.returncode
            
            # Create result
            success = exit_code == 0
            
            # Format output for LLM
            llm_content_parts = [
                f"Command: {command}",
                f"Directory: {directory or '(project root)'}",
                f"Exit Code: {exit_code}",
                f"Duration: {duration:.2f}s"
            ]
            
            if stdout_content:
                llm_content_parts.append(f"Stdout:\n{stdout_content}")
            else:
                llm_content_parts.append("Stdout: (empty)")
            
            if stderr_content:
                llm_content_parts.append(f"Stderr:\n{stderr_content}")
            else:
                llm_content_parts.append("Stderr: (empty)")
            
            llm_content = "\n\n".join(llm_content_parts)
            
            # Format display for user
            if success and stdout_content:
                display_content = stdout_content
            elif not success:
                display_content = f"**Command failed (exit code {exit_code})**\n\n"
                if stderr_content:
                    display_content += f"Error output:\n```\n{stderr_content}\n```"
                if stdout_content:
                    display_content += f"\n\nStandard output:\n```\n{stdout_content}\n```"
            else:
                display_content = "Command completed successfully (no output)"
            
            return self.create_result(
                llm_content=llm_content,
                return_display=display_content,
                success=success,
                error=stderr_content if not success else None
            )
        
        except Exception as e:
            error_msg = f"Error executing command: {str(e)}"
            return self.create_result(
                llm_content=error_msg,
                return_display=error_msg,
                success=False,
                error=str(e)
            )
        finally:
            # Clean up
            if hasattr(self, '_current_command'):
                delattr(self, '_current_command')
    
    def _get_command_root(self, command: str) -> str:
        """Extract the root command from a command string."""
        # Handle shell operators and pipes
        command = command.split('|')[0].split(';')[0].split('&&')[0].split('||')[0]
        command = command.strip()
        
        # Extract the first word (the actual command)
        parts = command.split()
        if parts:
            return parts[0]
        
        return command
