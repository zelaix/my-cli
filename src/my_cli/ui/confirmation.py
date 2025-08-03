"""CLI confirmation interface for tool execution approval."""

import sys
import difflib
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm

from ..tools.types import (
    ToolCallConfirmationDetails,
    ToolConfirmationOutcome,
    ToolExecuteConfirmationDetails,
    ToolEditConfirmationDetails
)


class ConfirmationInterface:
    """CLI interface for tool execution confirmation."""
    
    def __init__(self):
        self.console = Console()
    
    def show_confirmation_dialog(
        self, 
        confirmation_details: ToolCallConfirmationDetails
    ) -> ToolConfirmationOutcome:
        """Show confirmation dialog and get user decision."""
        self.console.print()  # Add spacing
        
        if confirmation_details.type == "exec":
            return self._show_exec_confirmation(confirmation_details)
        elif confirmation_details.type == "edit":
            return self._show_edit_confirmation(confirmation_details)
        elif confirmation_details.type == "write":
            return self._show_write_confirmation(confirmation_details)
        else:
            return self._show_generic_confirmation(confirmation_details)
    
    def _show_exec_confirmation(
        self, 
        details: ToolCallConfirmationDetails
    ) -> ToolConfirmationOutcome:
        """Show confirmation for shell command execution."""
        # Display the command
        self.console.print(Panel(
            Text(details.command or "", style="cyan bold"),
            title="🔧 Shell Command",
            border_style="yellow"
        ))
        
        if details.description:
            self.console.print(f"[dim]{details.description}[/dim]")
        
        # Show options
        self.console.print("\n[bold]Options:[/bold]")
        self.console.print("  [green]1.[/green] Yes, allow once")
        self.console.print("  [green]2.[/green] Yes, allow always")
        self.console.print("  [red]3.[/red] No, cancel (default)")
        
        choice = Prompt.ask(
            "\nAllow execution?",
            choices=["1", "2", "3", "y", "n", ""],
            default="3"
        )
        
        if choice in ["1", "y"]:
            return ToolConfirmationOutcome.PROCEED_ONCE
        elif choice == "2":
            return ToolConfirmationOutcome.PROCEED_ALWAYS
        else:
            return ToolConfirmationOutcome.CANCEL
    
    def _show_edit_confirmation(
        self, 
        details: ToolCallConfirmationDetails
    ) -> ToolConfirmationOutcome:
        """Show confirmation for file editing."""
        # Display file info
        file_name = getattr(details, 'file_name', None) or details.file_path or "file"
        self.console.print(Panel(
            Text(file_name, style="cyan bold"),
            title="📝 File Edit",
            border_style="yellow"
        ))
        
        # Show diff if available
        if details.file_diff:
            self._show_diff(details.file_diff)
        elif details.original_content and details.new_content:
            self._show_content_diff(
                details.original_content, 
                details.new_content, 
                file_name
            )
        
        # Show options
        self.console.print("\n[bold]Options:[/bold]")
        self.console.print("  [green]1.[/green] Yes, apply changes")
        self.console.print("  [green]2.[/green] Yes, always allow edits")
        self.console.print("  [red]3.[/red] No, cancel (default)")
        
        choice = Prompt.ask(
            "\nApply this change?",
            choices=["1", "2", "3", "y", "n", ""],
            default="3"
        )
        
        if choice in ["1", "y"]:
            return ToolConfirmationOutcome.PROCEED_ONCE
        elif choice == "2":
            return ToolConfirmationOutcome.PROCEED_ALWAYS
        else:
            return ToolConfirmationOutcome.CANCEL
    
    def _show_write_confirmation(
        self, 
        details: ToolCallConfirmationDetails
    ) -> ToolConfirmationOutcome:
        """Show confirmation for file writing."""
        file_path = details.file_path or "file"
        self.console.print(Panel(
            Text(file_path, style="cyan bold"),
            title="💾 File Write",
            border_style="yellow"
        ))
        
        if details.description:
            self.console.print(f"[dim]{details.description}[/dim]")
        
        # Show preview of content if available
        if details.new_content:
            preview = details.new_content[:500]
            if len(details.new_content) > 500:
                preview += "\n... [truncated]"
            
            self.console.print(Panel(
                Syntax(preview, "text", theme="monokai", line_numbers=True),
                title="Content Preview",
                border_style="blue"
            ))
        
        # Show options
        self.console.print("\n[bold]Options:[/bold]")
        self.console.print("  [green]1.[/green] Yes, write file")
        self.console.print("  [green]2.[/green] Yes, always allow writes")
        self.console.print("  [red]3.[/red] No, cancel (default)")
        
        choice = Prompt.ask(
            "\nWrite this file?",
            choices=["1", "2", "3", "y", "n", ""],
            default="3"
        )
        
        if choice in ["1", "y"]:
            return ToolConfirmationOutcome.PROCEED_ONCE
        elif choice == "2":
            return ToolConfirmationOutcome.PROCEED_ALWAYS
        else:
            return ToolConfirmationOutcome.CANCEL
    
    def _show_generic_confirmation(
        self, 
        details: ToolCallConfirmationDetails
    ) -> ToolConfirmationOutcome:
        """Show generic confirmation dialog."""
        self.console.print(Panel(
            Text(details.title or "Tool Execution", style="cyan bold"),
            border_style="yellow"
        ))
        
        if details.description:
            self.console.print(f"[dim]{details.description}[/dim]")
        
        if details.urls:
            self.console.print(f"\n[bold]URLs to access:[/bold]")
            for url in details.urls:
                self.console.print(f"  • {url}")
        
        # Show options
        self.console.print("\n[bold]Options:[/bold]")
        self.console.print("  [green]1.[/green] Yes, allow once")
        self.console.print("  [green]2.[/green] Yes, allow always")
        self.console.print("  [red]3.[/red] No, cancel (default)")
        
        choice = Prompt.ask(
            "\nProceed with this operation?",
            choices=["1", "2", "3", "y", "n", ""],
            default="3"
        )
        
        if choice in ["1", "y"]:
            return ToolConfirmationOutcome.PROCEED_ONCE
        elif choice == "2":
            return ToolConfirmationOutcome.PROCEED_ALWAYS
        else:
            return ToolConfirmationOutcome.CANCEL
    
    def _show_diff(self, diff_content: str) -> None:
        """Display diff content with syntax highlighting."""
        self.console.print(Panel(
            Syntax(diff_content, "diff", theme="monokai", line_numbers=False),
            title="Changes",
            border_style="blue"
        ))
    
    def _show_content_diff(
        self, 
        original: str, 
        new: str, 
        filename: str = "file"
    ) -> None:
        """Generate and show diff between original and new content."""
        diff_lines = list(difflib.unified_diff(
            original.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"{filename} (current)",
            tofile=f"{filename} (proposed)",
            lineterm=""
        ))
        
        if diff_lines:
            diff_content = "".join(diff_lines)
            self._show_diff(diff_content)
    
    def show_cancellation_message(self) -> None:
        """Show message when user cancels operation."""
        self.console.print("\n[red]❌ Operation cancelled by user[/red]")
    
    def show_approval_message(self, outcome: ToolConfirmationOutcome) -> None:
        """Show message when user approves operation."""
        if outcome == ToolConfirmationOutcome.PROCEED_ONCE:
            self.console.print("\n[green]✅ Approved for this execution[/green]")
        elif outcome == ToolConfirmationOutcome.PROCEED_ALWAYS:
            self.console.print("\n[green]✅ Approved and remembered for future executions[/green]")