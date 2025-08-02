"""
Main CLI application entry point.

This module contains the main Typer application and command handlers
for My CLI.
"""

from typing import Optional, Dict, Any
import asyncio
from pathlib import Path
import typer
from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich.panel import Panel

from my_cli import VERSION
from my_cli.config.settings import MyCliSettings
from my_cli.core.config import MyCliConfig
from my_cli.config.hierarchical import SettingScope
from my_cli.config.env_loader import EnvFileLoader
from my_cli.core.client import create_gemini_client, AuthType, StreamEvent, GeminiError
from my_cli.core.client.turn import Message, MessageRole, MessagePart

# Create the main Typer application
app = typer.Typer(
    name="my-cli",
    help="My CLI - AI-powered command-line assistant",
    add_completion=False,
    rich_markup_mode="rich",
)

# Rich console for output
console = Console()


def version_callback(value: bool) -> None:
    """Display version information and exit."""
    if value:
        console.print(f"[bold blue]My CLI[/bold blue] version [green]{VERSION}[/green]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """
    My CLI - AI-powered command-line assistant.
    
    A Python-based CLI for AI-powered productivity tasks with enhanced
    performance and extensibility.
    """
    pass


@app.command("chat")
def chat_command(
    message: Optional[str] = typer.Argument(None, help="Message to send to AI"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="AI model to use"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Enable/disable streaming responses"),
    tools: bool = typer.Option(True, "--tools/--no-tools", help="Enable/disable AI tool usage"),
    auto_confirm: bool = typer.Option(False, "--auto-confirm", help="Auto-confirm all tool executions"),
) -> None:
    """Start a chat session with AI or send a single message."""
    
    def _run_async_chat():
        if tools:
            # Use enhanced chat with tools
            from .enhanced_chat import enhanced_chat_command
            return asyncio.run(enhanced_chat_command(
                message=message,
                model=model,
                stream=stream,
                auto_confirm_tools=auto_confirm,
                enable_tools=tools
            ))
        else:
            # Use basic chat without tools
            return asyncio.run(_async_chat_command(message, model, stream))
    
    _run_async_chat()


async def _async_chat_command(
    message: Optional[str],
    model: Optional[str],
    stream: bool,
) -> None:
    """Async implementation of chat command."""
    try:
        # Load settings
        config = MyCliConfig()
        await config.initialize()
        settings = config.settings
        
        # Determine the model to use
        target_model = model or settings.model
        
        # Check if API key is configured for the target model
        api_key = settings.get_api_key_for_model(target_model)
        if not api_key:
            model_type = "Kimi" if target_model.startswith("kimi-") else "Gemini"
            env_var = "MY_CLI_KIMI_API_KEY" if model_type == "Kimi" else "MY_CLI_API_KEY"
            console.print(f"[red]Error:[/red] No {model_type} API key configured.")
            console.print(f"[dim]Set {env_var} environment variable or use 'my-cli config --set {'kimi_api_key' if model_type == 'Kimi' else 'api_key'}=your-key'[/dim]")
            raise typer.Exit(1)
        
        # Create API client using the multi-provider factory
        from my_cli.core.client.provider_factory import create_content_generator
        
        # Prepare creation parameters
        client_params = {
            "model": target_model,
            "api_key": api_key,
            "max_tokens": settings.max_tokens,
            "temperature": settings.temperature,
        }
        
        # Add Kimi-specific parameters if it's a Kimi model
        if target_model.startswith("kimi-"):
            client_params["kimi_provider"] = settings.kimi_provider
            if settings.kimi_base_url:
                client_params["base_url"] = settings.kimi_base_url
        
        client = create_content_generator(**client_params)
        
        # Initialize client
        await client.initialize()
        
        if message:
            # Single message mode
            await _send_single_message(client, message, stream)
        else:
            # Interactive chat mode
            await _interactive_chat(client, stream)
            
    except GeminiError as e:
        console.print(f"[red]AI Error:[/red] {e}")
        if hasattr(e, 'status') and e.status == 401:
            console.print("[dim]Check your API key configuration[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


async def _send_single_message(client, message: str, stream: bool, show_user_message: bool = True) -> None:
    """Send a single message to the AI."""
    if show_user_message:
        console.print(f"[yellow]You:[/yellow] {message}")
    
    # Create message object
    messages = [Message(
        role=MessageRole.USER,
        parts=[MessagePart(text=message)]
    )]
    
    if stream:
        # Streaming response
        console.print("[blue]AI:[/blue] ", end="")
        
        try:
            response_text = ""
            async for response_chunk in client.generate_content_stream(messages):
                if response_chunk.has_content:
                    chunk_text = response_chunk.text
                    console.print(chunk_text, end="")
                    response_text += chunk_text
            
            console.print()  # New line at end
            
            # Show token usage if available (estimate for streaming)
            if response_text:
                estimated_tokens = len(response_text) // 4  # Rough estimate
                console.print(f"[dim](~{estimated_tokens} tokens)[/dim]")
                    
        except Exception as e:
            console.print(f"\n[red]Error:[/red] {e}")
    else:
        # Non-streaming response
        try:
            with console.status("[dim]Thinking...[/dim]"):
                response = await client.generate_content(messages)
            
            console.print(f"[blue]AI:[/blue] {response.text}")
            
            # Show token usage if available
            if response.usage_metadata:
                console.print(f"[dim]({response.usage_metadata.total_token_count} tokens)[/dim]")
                
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")


async def _interactive_chat(client, stream: bool) -> None:
    """Start an interactive chat session."""
    console.print("[bold green]My CLI[/bold green] - Interactive Chat")
    console.print(f"[dim]Model: {client.model}[/dim]")
    console.print(f"[dim]Provider: {client.provider.value}[/dim]")
    console.print(f"[dim]Streaming: {'enabled' if stream else 'disabled'}[/dim]")
    console.print("[dim]Type 'exit', 'quit', or press Ctrl+C to exit[/dim]")
    console.print("[dim]Type '/help' for commands[/dim]\n")
    
    session_active = True
    while session_active:
        try:
            user_input = typer.prompt("You")
            
            # Handle special commands
            if user_input.lower().strip() in ["exit", "quit", "q"]:
                console.print("[dim]Goodbye![/dim]")
                break
                
            elif user_input.lower().strip() == "/help":
                _show_chat_help()
                continue
                
            elif user_input.lower().strip() == "/stats":
                console.print("[dim]Stats not available in this version[/dim]")
                continue
                
            elif user_input.lower().strip() == "/clear":
                console.print("[dim]History clearing not available in this version[/dim]")
                continue
                
            elif user_input.lower().strip().startswith("/stream"):
                # Toggle streaming mode
                stream = not stream
                console.print(f"[dim]Streaming {'enabled' if stream else 'disabled'}[/dim]")
                continue
                
            elif user_input.strip() == "":
                continue
            
            # Send message to AI using the same logic as _send_single_message
            # Don't show user message again since typer.prompt already showed it
            await _send_single_message(client, user_input, stream, show_user_message=False)
                    
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            break


def _show_chat_help() -> None:
    """Show help for chat commands."""
    help_text = """[bold]Chat Commands:[/bold]
    
[cyan]/help[/cyan]     - Show this help message
[cyan]/stats[/cyan]    - Show conversation statistics  
[cyan]/clear[/cyan]    - Clear conversation history
[cyan]/stream[/cyan]   - Toggle streaming mode
[cyan]exit[/cyan]      - Exit the chat session

[dim]Press Ctrl+C or type 'exit' to quit[/dim]"""
    
    console.print(Panel(help_text, title="Help", border_style="blue"))


async def _show_chat_stats(client) -> None:
    """Show chat session statistics."""
    stats = client.get_client_statistics()
    session_stats = client.get_session_statistics()
    
    # Create stats table
    stats_table = Table(title="Chat Session Statistics", show_header=True, header_style="bold magenta")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")
    
    # Client stats
    stats_table.add_row("Total Requests", str(stats["client_stats"]["total_requests"]))
    stats_table.add_row("Successful Requests", str(stats["client_stats"]["successful_requests"]))
    stats_table.add_row("Failed Requests", str(stats["client_stats"]["failed_requests"]))
    stats_table.add_row("Total Tokens", str(stats["client_stats"]["total_tokens"]))
    
    # Session stats
    if session_stats:
        stats_table.add_row("Session Turns", str(session_stats["turn_count"]))
        stats_table.add_row("Session Tokens", str(session_stats["token_count"]))
        
        if "duration_minutes" in session_stats:
            duration_min = round(session_stats["duration_minutes"], 1)
            stats_table.add_row("Session Duration", f"{duration_min} min")
    
    console.print(stats_table)
    
    # Token management stats
    if "token_statistics" in stats:
        token_stats = stats["token_statistics"]
        if "manager_stats" in token_stats:
            manager_stats = token_stats["manager_stats"]
            console.print(f"\n[dim]Compressions performed: {manager_stats.get('total_compressions', 0)}[/dim]")
            console.print(f"[dim]Tokens saved: {manager_stats.get('total_tokens_saved', 0)}[/dim]")


@app.command("config")
def config_command(
    show: bool = typer.Option(False, "--show", "-s", help="Show current configuration"),
    show_sources: bool = typer.Option(False, "--sources", help="Show configuration sources"),
    set_key: Optional[str] = typer.Option(None, "--set", help="Set configuration key=value"),
    scope: str = typer.Option("user", "--scope", help="Configuration scope (user, project, system)"),
    key: Optional[str] = typer.Option(None, "--key", "-k", help="Show specific configuration key"),
    init: bool = typer.Option(False, "--init", help="Initialize configuration files"),
    reload: bool = typer.Option(False, "--reload", help="Reload configuration from all sources"),
) -> None:
    """Manage My CLI configuration with hierarchical settings."""
    
    def _run_async_config_command():
        return asyncio.run(_async_config_command(show, show_sources, set_key, scope, key, init, reload))
    
    _run_async_config_command()


async def _async_config_command(
    show: bool,
    show_sources: bool,
    set_key: Optional[str],
    scope: str,
    key: Optional[str],
    init: bool,
    reload: bool,
) -> None:
    """Async implementation of config command."""
    try:
        # Initialize config
        config = MyCliConfig()
        await config.initialize()
        
        if init:
            await _init_config_files(config)
            return
        
        if reload:
            await _reload_config(config)
            return
        
        if set_key:
            await _set_config_value(config, set_key, scope)
            return
        
        if key:
            await _show_config_key(config, key)
            return
        
        if show_sources:
            await _show_config_sources(config)
            return
        
        if show:
            await _show_current_config(config)
            return
        
        # Default: show help
        console.print("[yellow]Use one of the following options:[/yellow]")
        console.print("  --show         Show current configuration")
        console.print("  --sources      Show configuration sources and files")
        console.print("  --key <key>    Show specific configuration key")
        console.print("  --set <key=val> Set configuration value")
        console.print("  --init         Initialize configuration files")
        console.print("  --reload       Reload configuration from all sources")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


async def _show_current_config(config: MyCliConfig) -> None:
    """Show current configuration values."""
    settings = config.settings
    
    # Create configuration table
    table = Table(title="Current Configuration", show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    table.add_column("Source", style="dim")
    
    # Key configuration items
    config_items = [
        ("api_key", "Set" if settings.api_key else "Not set"),
        ("model", settings.model),
        ("theme", settings.theme),
        ("auto_confirm", str(settings.auto_confirm)),
        ("max_tokens", str(settings.max_tokens)),
        ("temperature", str(settings.temperature)),
        ("timeout", str(settings.timeout)),
        ("debug", str(settings.debug)),
        ("log_level", settings.log_level),
    ]
    
    config_loader = config.get_config_loader()
    
    for key, value in config_items:
        # Get source information
        sources = config.get_setting_sources(key)
        if sources:
            # Get highest precedence source
            source_info = "unknown"
            for scope_name in ["command_line", "environment", "system", "project", "user", "default"]:
                if scope_name in sources:
                    source_info = scope_name
                    break
        else:
            source_info = "default"
        
        table.add_row(key, value, source_info)
    
    console.print(table)


async def _show_config_sources(config: MyCliConfig) -> None:
    """Show configuration sources and their status."""
    config_loader = config.get_config_loader()
    summary = config_loader.get_config_summary()
    
    # Create sources table
    table = Table(title="Configuration Sources", show_header=True, header_style="bold magenta")
    table.add_column("Scope", style="cyan", no_wrap=True)
    table.add_column("Path", style="yellow")
    table.add_column("Exists", style="green")
    table.add_column("Settings", style="blue")
    table.add_column("Errors", style="red")
    
    # Add sources in precedence order
    precedence_order = ["default", "user", "project", "system", "environment"]
    for scope in precedence_order:
        if scope in summary["sources"]:
            source = summary["sources"][scope]
            exists = "✓" if source["exists"] else "✗"
            settings_count = str(source["settings_count"])
            errors = str(len(source["errors"])) if source["errors"] else "0"
            
            table.add_row(scope, source["path"], exists, settings_count, errors)
    
    console.print(table)
    
    # Show environment file info
    env_loader = config.get_env_loader()
    env_file = env_loader.get_loaded_file()
    env_vars_count = len(env_loader.get_loaded_vars())
    
    env_panel = Panel(
        f"Environment File: {env_file or 'None found'}\n"
        f"Variables Loaded: {env_vars_count}",
        title="Environment Configuration",
        border_style="blue"
    )
    console.print(env_panel)
    
    # Show any errors
    if summary["errors"]:
        error_panel = Panel(
            "\n".join(summary["errors"]),
            title="Configuration Errors",
            border_style="red"
        )
        console.print(error_panel)


async def _show_config_key(config: MyCliConfig, key: str) -> None:
    """Show detailed information about a specific configuration key."""
    settings = config.settings
    
    # Get current value
    if hasattr(settings, key):
        current_value = getattr(settings, key)
        console.print(f"[bold]Key:[/bold] [cyan]{key}[/cyan]")
        console.print(f"[bold]Current Value:[/bold] [green]{current_value}[/green]")
        
        # Show sources for this key
        sources = config.get_setting_sources(key)
        if sources:
            console.print(f"\n[bold]Sources (in precedence order):[/bold]")
            
            source_table = Table(show_header=True, header_style="bold magenta")
            source_table.add_column("Scope", style="cyan")
            source_table.add_column("Value", style="green")
            source_table.add_column("Path", style="yellow")
            
            # Show in precedence order
            precedence_order = ["command_line", "environment", "system", "project", "user", "default"]
            for scope in precedence_order:
                if scope in sources:
                    source = sources[scope]
                    source_table.add_row(scope, str(source["value"]), source["path"])
            
            console.print(source_table)
        else:
            console.print(f"[dim]No specific sources found for key '{key}'[/dim]")
    else:
        console.print(f"[red]Error:[/red] Key '{key}' not found in configuration")


async def _set_config_value(config: MyCliConfig, set_key: str, scope: str) -> None:
    """Set a configuration value."""
    if "=" not in set_key:
        console.print("[red]Error:[/red] Use format --set key=value")
        return
    
    key, value = set_key.split("=", 1)
    key = key.strip()
    value = value.strip()
    
    # Parse scope
    try:
        setting_scope = SettingScope(scope.lower())
    except ValueError:
        console.print(f"[red]Error:[/red] Invalid scope '{scope}'. Use: user, project, or system")
        return
    
    # Convert value to appropriate type
    converted_value = _convert_config_value(key, value)
    
    # Save the setting
    success = config.save_setting(key, converted_value, setting_scope)
    
    if success:
        console.print(f"[green]✓[/green] Set {key} = {converted_value} in {scope} scope")
        
        # Show the updated value
        config.reload_configuration()
        if hasattr(config.settings, key):
            new_value = getattr(config.settings, key)
            console.print(f"[dim]Effective value:[/dim] [green]{new_value}[/green]")
    else:
        console.print(f"[red]Error:[/red] Failed to save setting {key}")


async def _init_config_files(config: MyCliConfig) -> None:
    """Initialize configuration files."""
    console.print("[bold blue]Initializing My CLI configuration files...[/bold blue]")
    
    # Create project configuration
    project_config_dir = Path.cwd() / ".my-cli"
    project_config_dir.mkdir(exist_ok=True)
    
    project_settings_file = project_config_dir / "settings.json"
    if not project_settings_file.exists():
        default_project_config = {
            "// Project-specific settings for My CLI": None,
            "theme": "default",
            "auto_confirm": False,
            "debug": False
        }
        
        config_loader = config.get_config_loader()
        config_loader.save_settings(SettingScope.PROJECT, default_project_config)
        console.print(f"[green]✓[/green] Created project settings: {project_settings_file}")
    else:
        console.print(f"[yellow]Project settings already exist:[/yellow] {project_settings_file}")
    
    # Create example .env file
    env_loader = config.get_env_loader()
    env_file_path = project_config_dir / ".env"
    if not env_file_path.exists():
        try:
            created_env_path = env_loader.create_example_env_file(scope="project")
            console.print(f"[green]✓[/green] Created example .env file: {created_env_path}")
        except Exception as e:
            console.print(f"[red]Error creating .env file:[/red] {e}")
    else:
        console.print(f"[yellow]Example .env file already exists:[/yellow] {env_file_path}")
    
    # Create user configuration directory
    user_config_dir = Path.home() / ".config" / "my-cli"
    user_config_dir.mkdir(parents=True, exist_ok=True)
    
    user_settings_file = user_config_dir / "settings.json"
    if not user_settings_file.exists():
        default_user_config = {
            "// User-wide settings for My CLI": None,
            "theme": "default",
            "log_level": "INFO"
        }
        
        config_loader = config.get_config_loader()
        config_loader.save_settings(SettingScope.USER, default_user_config)
        console.print(f"[green]✓[/green] Created user settings: {user_settings_file}")
    else:
        console.print(f"[yellow]User settings already exist:[/yellow] {user_settings_file}")
    
    console.print("\n[bold green]Configuration initialization complete![/bold green]")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("1. Edit .my-cli/.env to set your MY_CLI_API_KEY")
    console.print("2. Use 'my-cli config --show' to view your configuration")
    console.print("3. Use 'my-cli config --set key=value' to modify settings")


async def _reload_config(config: MyCliConfig) -> None:
    """Reload configuration from all sources."""
    console.print("[dim]Reloading configuration from all sources...[/dim]")
    
    merged_config = config.reload_configuration()
    
    console.print(f"[green]✓[/green] Configuration reloaded")
    console.print(f"[dim]Loaded {len(merged_config)} configuration keys[/dim]")
    
    # Show brief summary
    summary = config.get_config_summary()
    if "hierarchical_config" in summary:
        hierarchical_summary = summary["hierarchical_config"]
        console.print(f"[dim]Sources checked: {len(hierarchical_summary['sources'])}[/dim]")


def _convert_config_value(key: str, value: str) -> Any:
    """Convert string value to appropriate type based on key."""
    # Boolean values
    if key in ["auto_confirm", "debug"]:
        return value.lower() in ("true", "1", "yes", "on")
    
    # Integer values
    if key in ["max_tokens", "timeout"]:
        try:
            return int(value)
        except ValueError:
            return value
    
    # Float values
    if key in ["temperature"]:
        try:
            return float(value)
        except ValueError:
            return value
    
    # String values (default)
    return value


@app.command("init")
def init_command(
    force: bool = typer.Option(False, "--force", "-f", help="Force initialization even if config exists"),
) -> None:
    """Initialize My CLI configuration in the current directory."""
    
    def _run_async_init_command():
        return asyncio.run(_async_init_command(force))
    
    _run_async_init_command()


async def _async_init_command(force: bool) -> None:
    """Async implementation of init command."""
    try:
        config = MyCliConfig()
        await config.initialize()
        await _init_config_files(config)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def main() -> None:
    """Entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()