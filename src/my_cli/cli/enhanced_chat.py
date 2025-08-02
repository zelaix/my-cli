"""Enhanced chat commands with AI-Tool integration."""

import asyncio
import logging
from typing import Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ..core.config import MyCliConfig
from ..core.client.provider_factory import create_content_generator
from ..core.client import GeminiError
from ..tools.registry import ToolRegistry
from ..core.function_calling import (
    ConversationOrchestrator,
    create_confirmation_handler
)
from ..config.settings import MyCliSettings

console = Console()
logger = logging.getLogger(__name__)



async def enhanced_chat_command(
    message: Optional[str] = None,
    model: Optional[str] = None,
    stream: bool = True,
    auto_confirm_tools: bool = False,
    enable_tools: bool = True
) -> None:
    """
    Enhanced chat command with AI-Tool integration.
    
    Args:
        message: Message to send to AI (None for interactive mode)
        model: AI model to use
        stream: Whether to use streaming responses
        auto_confirm_tools: Whether to auto-confirm tool executions
        enable_tools: Whether to enable tool usage
    """
    try:
        # Load configuration
        config = MyCliConfig()
        await config.initialize()
        settings = config.settings
        
        # Determine model
        target_model = model or settings.model
        
        # Check API key
        api_key = settings.get_api_key_for_model(target_model)
        if not api_key:
            model_type = "Kimi" if target_model.startswith("kimi-") else "Gemini"
            env_var = "MY_CLI_KIMI_API_KEY" if model_type == "Kimi" else "MY_CLI_API_KEY"
            console.print(f"[red]Error:[/red] No {model_type} API key configured.")
            console.print(f"[dim]Set {env_var} environment variable or use config commands[/dim]")
            raise typer.Exit(1)
        
        # Create content generator
        client_params = {
            "model": target_model,
            "api_key": api_key,
            "max_tokens": settings.max_tokens,
            "temperature": settings.temperature,
        }
        
        if target_model.startswith("kimi-"):
            client_params["kimi_provider"] = settings.kimi_provider
            if settings.kimi_base_url:
                client_params["base_url"] = settings.kimi_base_url
        
        client = create_content_generator(**client_params)
        await client.initialize()
        
        # Initialize tool system if enabled
        orchestrator = None
        if enable_tools:
            # Create tool registry and discover tools
            tool_registry = ToolRegistry()
            discovered = await tool_registry.discover_builtin_tools(config)
            
            if discovered > 0:
                console.print(f"[dim]🔧 Loaded {discovered} tools[/dim]")
                
                # Generate function schemas and set tools on client
                if target_model.startswith("gemini-"):
                    # Use Gemini-compatible schema generator
                    from ..core.function_calling.gemini_schema_generator import generate_all_gemini_function_schemas
                    schemas = generate_all_gemini_function_schemas(tool_registry)
                else:
                    # Use general schema generator
                    from ..core.function_calling import generate_all_function_schemas
                    schemas = generate_all_function_schemas(tool_registry)
                
                # Convert schemas to tools format expected by the AI client
                tools = [{"functionDeclarations": schemas}] if schemas else []
                client.set_tools(tools)
                
                # Create confirmation handler
                confirmation_handler = create_confirmation_handler(
                    auto_confirm=auto_confirm_tools
                )
                
                # Create conversation orchestrator
                orchestrator = ConversationOrchestrator(
                    content_generator=client,
                    tool_registry=tool_registry,
                    config=config,
                    confirmation_handler=confirmation_handler.confirm_tool_execution,
                    output_handler=lambda text: console.print(text, end="")
                )
            else:
                console.print("[yellow]Warning:[/yellow] No tools available")
                enable_tools = False
        
        if message:
            # Single message mode
            await _send_enhanced_message(
                orchestrator or client,
                message,
                stream,
                auto_confirm_tools,
                enable_tools
            )
        else:
            # Interactive mode
            await _interactive_enhanced_chat(
                orchestrator or client,
                stream,
                auto_confirm_tools,
                enable_tools
            )
    
    except GeminiError as e:
        console.print(f"[red]AI Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.exception("Unexpected error in enhanced chat")
        raise typer.Exit(1)


async def _send_enhanced_message(
    orchestrator_or_client,
    message: str,
    stream: bool,
    auto_confirm_tools: bool,
    enable_tools: bool,
    show_user_message: bool = True
) -> None:
    """Send a single message with tool support."""
    if show_user_message:
        console.print(f"[yellow]You:[/yellow] {message}")
    
    if enable_tools and hasattr(orchestrator_or_client, 'send_message'):
        # Use orchestrator for tool-enabled conversation
        if stream:
            # Print AI prefix before streaming starts (with newline to separate from user prompt)
            console.print("\n[blue]AI:[/blue] ", end="")
        
        turn = await orchestrator_or_client.send_message(
            message,
            stream=stream,
            auto_confirm_tools=auto_confirm_tools
        )
        
        if stream:
            # Add consistent newline after streaming response
            # Check if response already ends with newline to avoid double newlines
            response_text = turn.final_ai_response or ""
            if response_text and not response_text.endswith('\n'):
                console.print("\n")  # Add newline if response doesn't have one
            else:
                console.print()  # Just print empty line for consistent spacing
        
        # Show final AI response only for non-streaming mode
        # (In streaming mode, orchestrator already printed response via output_handler)
        if turn.final_ai_response and not stream:
            console.print(f"[blue]AI:[/blue] {turn.final_ai_response}\n")
        
        # Show conversation stats if tools were used
        if turn.function_calls:
            stats = orchestrator_or_client.get_conversation_stats()
            console.print(f"\n[dim]Tools used: {len(turn.function_calls)}, Total tools available: {stats['available_tools']}[/dim]")
    
    else:
        # Use regular client without tools
        from ..cli.app import _send_single_message
        await _send_single_message(orchestrator_or_client, message, stream, show_user_message=False)


async def _interactive_enhanced_chat(
    orchestrator_or_client,
    stream: bool,
    auto_confirm_tools: bool,
    enable_tools: bool
) -> None:
    """Interactive chat with tool support."""
    # Show header
    console.print("[bold green]My CLI[/bold green] - Enhanced Interactive Chat")
    
    if hasattr(orchestrator_or_client, 'content_generator'):
        client = orchestrator_or_client.content_generator
        console.print(f"[dim]Model: {client.model}[/dim]")
        console.print(f"[dim]Provider: {client.provider.value}[/dim]")
    else:
        console.print(f"[dim]Model: {orchestrator_or_client.model}[/dim]")
        console.print(f"[dim]Provider: {orchestrator_or_client.provider.value}[/dim]")
    
    console.print(f"[dim]Streaming: {'enabled' if stream else 'disabled'}[/dim]")
    console.print(f"[dim]Tools: {'enabled' if enable_tools else 'disabled'}[/dim]")
    console.print(f"[dim]Auto-confirm tools: {'yes' if auto_confirm_tools else 'no'}[/dim]")
    console.print("[dim]Type 'exit', 'quit', or press Ctrl+C to exit[/dim]")
    console.print("[dim]Type '/help' for commands[/dim]\n")
    
    while True:
        try:
            user_input = typer.prompt("You")
            
            # Handle special commands
            if user_input.lower().strip() in ["exit", "quit", "q"]:
                console.print("[dim]Goodbye![/dim]")
                break
            
            elif user_input.lower().strip() == "/help":
                _show_enhanced_chat_help(enable_tools)
                continue
            
            elif user_input.lower().strip() == "/stats":
                if enable_tools and hasattr(orchestrator_or_client, 'get_conversation_stats'):
                    stats = orchestrator_or_client.get_conversation_stats()
                    _show_conversation_stats(stats)
                else:
                    console.print("[dim]Stats not available in this mode[/dim]")
                continue
            
            elif user_input.lower().strip() == "/clear":
                if enable_tools and hasattr(orchestrator_or_client, 'clear_conversation_history'):
                    orchestrator_or_client.clear_conversation_history()
                    console.print("[dim]Conversation history cleared[/dim]")
                else:
                    console.print("[dim]History clearing not available in this mode[/dim]")
                continue
            
            elif user_input.lower().strip().startswith("/stream"):
                stream = not stream
                console.print(f"[dim]Streaming {'enabled' if stream else 'disabled'}[/dim]")
                continue
            
            elif user_input.lower().strip().startswith("/tools"):
                if enable_tools:
                    auto_confirm_tools = not auto_confirm_tools
                    console.print(f"[dim]Auto-confirm tools {'enabled' if auto_confirm_tools else 'disabled'}[/dim]")
                else:
                    console.print("[dim]Tools are not enabled in this session[/dim]")
                continue
            
            elif user_input.strip() == "":
                continue
            
            # Send message
            await _send_enhanced_message(
                orchestrator_or_client,
                user_input,
                stream,
                auto_confirm_tools,
                enable_tools,
                show_user_message=False  # Interactive mode already shows "You:" prompt
            )
        
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"\n[red]Error:[/red] {e}")
            logger.exception("Error in interactive chat")


def _show_enhanced_chat_help(enable_tools: bool) -> None:
    """Show help for enhanced chat commands."""
    help_text = "[bold]Enhanced Chat Commands:[/bold]\n\n"
    help_text += "[cyan]/help[/cyan]     - Show this help message\n"
    help_text += "[cyan]/stats[/cyan]    - Show conversation statistics\n"
    help_text += "[cyan]/clear[/cyan]    - Clear conversation history\n"
    help_text += "[cyan]/stream[/cyan]   - Toggle streaming mode\n"
    
    if enable_tools:
        help_text += "[cyan]/tools[/cyan]    - Toggle auto-confirm tools\n"
    
    help_text += "[cyan]exit[/cyan]      - Exit the chat session\n"
    
    panel = Panel(
        help_text,
        title="Help",
        title_align="left",
        border_style="cyan"
    )
    console.print(panel)


def _show_conversation_stats(stats: dict) -> None:
    """Show conversation statistics."""
    from rich.table import Table
    
    table = Table(show_header=False, box=None)
    table.add_row("[bold]Total Turns:[/bold]", str(stats.get('total_turns', 0)))
    table.add_row("[bold]Turns with Tools:[/bold]", str(stats.get('turns_with_tools', 0)))
    table.add_row("[bold]Total Tool Calls:[/bold]", str(stats.get('total_tool_calls', 0)))
    table.add_row("[bold]Successful Tool Calls:[/bold]", str(stats.get('successful_tool_calls', 0)))
    table.add_row("[bold]Available Tools:[/bold]", str(stats.get('available_tools', 0)))
    
    panel = Panel(
        table,
        title="📊 Conversation Statistics",
        title_align="left",
        border_style="green"
    )
    console.print(panel)
