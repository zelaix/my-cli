"""Rich UI for tool execution confirmations."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax
from rich.prompt import Confirm, Prompt
from typing import Optional, Dict, Any

from ...tools.types import (
    ToolCallConfirmationDetails,
    ToolConfirmationOutcome,
    ToolExecuteConfirmationDetails,
    ToolEditConfirmationDetails
)

console = Console()


class ToolConfirmationUI:
    """Rich UI for handling tool execution confirmations."""
    
    def __init__(self, auto_confirm: bool = False):
        """
        Initialize confirmation UI.
        
        Args:
            auto_confirm: Whether to automatically confirm all tools
        """
        self.auto_confirm = auto_confirm
        self.always_allow_tools = set()  # Tools that user chose "always allow"
    
    def confirm_tool_execution(
        self,
        confirmation_details: ToolCallConfirmationDetails
    ) -> ToolConfirmationOutcome:
        """
        Handle tool execution confirmation with rich UI.
        
        Args:
            confirmation_details: Details about the tool execution
            
        Returns:
            User's confirmation choice
        """
        if self.auto_confirm:
            return ToolConfirmationOutcome.PROCEED_ONCE
        
        # Check if tool is in always-allow list
        tool_key = self._get_tool_key(confirmation_details)
        if tool_key in self.always_allow_tools:
            return ToolConfirmationOutcome.PROCEED_ONCE
        
        # Show confirmation UI based on tool type
        if isinstance(confirmation_details, ToolExecuteConfirmationDetails):
            return self._confirm_shell_execution(confirmation_details)
        elif isinstance(confirmation_details, ToolEditConfirmationDetails):
            return self._confirm_file_edit(confirmation_details)
        else:
            return self._confirm_generic_tool(confirmation_details)
    
    def _confirm_shell_execution(
        self,
        details: ToolExecuteConfirmationDetails
    ) -> ToolConfirmationOutcome:
        """Confirm shell command execution."""
        # Create confirmation panel
        command = details.command or "<unknown command>"
        root_command = details.root_command or "<unknown>"
        
        # Create table with command details
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_row("[bold]Command:[/bold]", f"[cyan]{command}[/cyan]")
        table.add_row("[bold]Root Command:[/bold]", f"[yellow]{root_command}[/yellow]")
        
        if details.description:
            table.add_row("[bold]Description:[/bold]", details.description)
        
        panel = Panel(
            table,
            title="💻 Shell Command Confirmation",
            title_align="left",
            border_style="yellow"
        )
        
        console.print(panel)
        
        # Show warning for potentially dangerous commands
        if self._is_potentially_dangerous_command(command):
            console.print(
                "⚠️  [bold red]Warning:[/bold red] This command may modify your system!",
                style="red"
            )
        
        return self._get_user_choice("shell command")
    
    def _confirm_file_edit(
        self,
        details: ToolEditConfirmationDetails
    ) -> ToolConfirmationOutcome:
        """Confirm file edit operation."""
        file_path = details.file_path or "<unknown file>"
        file_name = details.file_name or file_path
        
        # Create table with file details
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_row("[bold]File:[/bold]", f"[cyan]{file_name}[/cyan]")
        table.add_row("[bold]Path:[/bold]", f"[dim]{file_path}[/dim]")
        
        if details.description:
            table.add_row("[bold]Operation:[/bold]", details.description)
        
        # Show diff if available
        if details.file_diff:
            table.add_row("[bold]Changes:[/bold]", "See diff below")
        
        panel = Panel(
            table,
            title="✏️  File Edit Confirmation",
            title_align="left",
            border_style="blue"
        )
        
        console.print(panel)
        
        # Show diff preview
        if details.file_diff:
            console.print("\n[bold]Diff Preview:[/bold]")
            try:
                diff_syntax = Syntax(
                    details.file_diff,
                    "diff",
                    theme="monokai",
                    line_numbers=False,
                    word_wrap=True
                )
                console.print(diff_syntax)
            except Exception:
                # Fallback to plain text
                console.print(details.file_diff)
        
        return self._get_user_choice("file edit")
    
    def _confirm_generic_tool(
        self,
        details: ToolCallConfirmationDetails
    ) -> ToolConfirmationOutcome:
        """Confirm generic tool execution."""
        # Create table with tool details
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_row("[bold]Type:[/bold]", details.type or "unknown")
        
        if details.description:
            table.add_row("[bold]Operation:[/bold]", details.description)
        
        if details.file_path:
            table.add_row("[bold]File:[/bold]", f"[cyan]{details.file_path}[/cyan]")
        
        if details.urls:
            table.add_row("[bold]URLs:[/bold]", ", ".join(details.urls))
        
        panel = Panel(
            table,
            title="🔧 Tool Execution Confirmation",
            title_align="left",
            border_style="green"
        )
        
        console.print(panel)
        
        return self._get_user_choice("tool execution")
    
    def _get_user_choice(self, operation_type: str) -> ToolConfirmationOutcome:
        """Get user's confirmation choice."""
        console.print("\n[bold]Choose an action:[/bold]")
        console.print("[green]y[/green] - Proceed once")
        console.print("[yellow]a[/yellow] - Proceed and always allow this tool")
        console.print("[red]n[/red] - Cancel")
        
        while True:
            try:
                choice = Prompt.ask(
                    f"Confirm {operation_type}",
                    choices=["y", "a", "n", "yes", "always", "no"],
                    default="n",
                    show_choices=False
                ).lower()
                
                if choice in ["y", "yes"]:
                    return ToolConfirmationOutcome.PROCEED_ONCE
                elif choice in ["a", "always"]:
                    return ToolConfirmationOutcome.PROCEED_ALWAYS_TOOL
                elif choice in ["n", "no"]:
                    return ToolConfirmationOutcome.CANCEL
                else:
                    console.print("[red]Invalid choice. Please select y/a/n[/red]")
            
            except KeyboardInterrupt:
                console.print("\n[dim]Cancelled by user[/dim]")
                return ToolConfirmationOutcome.CANCEL
            except EOFError:
                console.print("\n[dim]Cancelled by user[/dim]")
                return ToolConfirmationOutcome.CANCEL
    
    def _get_tool_key(self, details: ToolCallConfirmationDetails) -> str:
        """Get a unique key for the tool for always-allow tracking."""
        if isinstance(details, ToolExecuteConfirmationDetails):
            return f"shell:{details.root_command}"
        elif isinstance(details, ToolEditConfirmationDetails):
            return f"edit:{details.file_name or 'unknown'}"
        else:
            return f"{details.type}:generic"
    
    def _is_potentially_dangerous_command(self, command: str) -> bool:
        """Check if a command is potentially dangerous."""
        dangerous_patterns = [
            "rm ", "rmdir", "del ", "format", "fdisk", "mkfs",
            "dd ", "sudo ", "su ", "chmod +x", "chown",
            "shutdown", "reboot", "halt", "init 0", "init 6",
            "kill ", "killall", "pkill", "> /dev/", ">/dev/"
        ]
        
        command_lower = command.lower()
        return any(pattern in command_lower for pattern in dangerous_patterns)
    
    def update_always_allow(self, outcome: ToolConfirmationOutcome, tool_key: str) -> None:
        """Update always-allow list based on user choice."""
        if outcome == ToolConfirmationOutcome.PROCEED_ALWAYS_TOOL:
            self.always_allow_tools.add(tool_key)
    
    def show_execution_progress(self, tool_name: str, status: str) -> None:
        """Show tool execution progress."""
        status_icons = {
            "validating": "🔍",
            "scheduled": "⏱️",
            "executing": "⚙️",
            "success": "✅",
            "error": "❌",
            "cancelled": "❌"
        }
        
        icon = status_icons.get(status, "🔧")
        console.print(f"{icon} {tool_name}: {status}")
    
    def show_tool_summary(
        self,
        total: int,
        successful: int,
        failed: int,
        cancelled: int
    ) -> None:
        """Show tool execution summary."""
        if total == 0:
            return
        
        table = Table(show_header=False, box=None)
        table.add_row("[bold]Total:[/bold]", str(total))
        table.add_row("[bold green]Successful:[/bold green]", str(successful))
        
        if failed > 0:
            table.add_row("[bold red]Failed:[/bold red]", str(failed))
        
        if cancelled > 0:
            table.add_row("[bold yellow]Cancelled:[/bold yellow]", str(cancelled))
        
        panel = Panel(
            table,
            title="📊 Tool Execution Summary",
            title_align="left",
            border_style="cyan"
        )
        
        console.print(panel)


def create_confirmation_handler(auto_confirm: bool = False) -> ToolConfirmationUI:
    """Create a confirmation handler for tool executions."""
    return ToolConfirmationUI(auto_confirm=auto_confirm)
