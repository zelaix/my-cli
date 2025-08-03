# My CLI - Python-based Multi-Provider AI Assistant

## Project Overview

My CLI is a Python reimplementation of Google's Gemini CLI that brings agentic coding capabilities to your terminal with enhanced multi-provider support, tool integration, and autonomous behavior.

## Key Features

- **Multi-Provider AI Support**: Gemini and Kimi K2 models with automatic provider detection
- **Native Function Calling**: Direct integration with Gemini's function calling API
- **Tool Ecosystem**: Built-in tools for file operations, shell commands, and development workflows
- **Autonomous Behavior**: Proactive AI that can automatically use tools to complete complex tasks
- **Advanced Configuration**: Hierarchical settings with environment variable interpolation

## Current Implementation Status

**✅ Phase 2.1+ Complete**: Multi-provider AI client with streaming, conversation management, and error handling
**🔄 Phase 2.2 In Progress**: Autonomous agentic behavior with comprehensive system prompts and tool integration

## Project Structure

```
src/my_cli/
├── cli/                    # Frontend CLI interface
├── core/                   # Backend logic & API client
│   ├── client/            # Content generation and providers
│   ├── function_calling/  # Native function calling system
│   ├── prompts/           # System prompt management
│   └── config/            # Configuration management
├── tools/                 # Tool system and implementations
│   ├── core/             # Built-in tools (read_file, write_file, etc.)
│   ├── registry.py       # Tool registration and discovery
│   └── types.py          # Tool system types
└── utils/                # Shared utilities
```

## Development Standards

- **Testing**: Comprehensive test suite with 93+ passing tests
- **Type Safety**: Full MyPy type checking with strict mode
- **Code Quality**: Ruff linting with modern Python standards
- **Architecture**: Async-first design with dependency injection
- **Documentation**: Comprehensive docstrings and inline documentation

## Key Models and Providers

### Kimi K2 Models (Default)
- `kimi-k2-instruct` - Instruction-tuned for conversations
- `kimi-k2-base` - Base model for general use

### Gemini Models
- `gemini-2.0-flash-exp` - Latest Gemini model with function calling
- `gemini-1.5-pro` - High capability model
- `gemini-1.5-flash` - Fast response model

## Tool System

### Built-in Core Tools
- `read_file` - Read file contents with path validation
- `write_file` - Write content to files
- `edit_file` - Edit existing files with find/replace
- `list_directory` - List directory contents with filtering
- `run_shell_command` - Execute shell commands safely

### Function Calling Integration
- Native Gemini function calling with proper schema generation
- Streaming function call support
- Tool confirmation workflows for destructive operations
- Function response processing with conversation integration

## Build and Test Commands

```bash
# Development setup
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Run linting
python scripts/build.py lint

# Run type checking
python scripts/build.py typecheck

# Clean build artifacts
python scripts/build.py clean
```

## Configuration

### Environment Variables
- `MY_CLI_API_KEY` - Gemini API key
- `MY_CLI_KIMI_API_KEY` - Kimi API key  
- `MY_CLI_MODEL` - Default model (kimi-k2-instruct)
- `MY_CLI_DEBUG` - Enable debug logging
- `MY_CLI_AUTO_CONFIRM` - Auto-confirm tool executions

### Configuration Files
- `.my-cli/settings.json` - Project-specific settings
- `~/.config/my-cli/settings.json` - User settings
- `.my-cli/.env` - Environment variables

## Usage Examples

```bash
# Basic chat
my-cli chat "Hello world"

# Interactive mode with tools
my-cli chat

# Use specific model
my-cli chat "Analyze this code" --model gemini-2.0-flash-exp

# Configuration management
my-cli config --show
my-cli config --set theme=dark --scope project
```

## Development Priorities

1. **Phase 2.2a**: System prompt integration for autonomous behavior ✅ In Progress
2. **Phase 2.2b**: Enhanced tool orchestration and workflow patterns
3. **Phase 2.2c**: Advanced context integration and memory management
4. **Phase 3**: MCP protocol support and external tool integration

## Code Style

- Use async/await throughout for I/O operations
- Leverage Pydantic for data validation and settings
- Follow protocol-based design for extensibility  
- Maintain comprehensive type annotations
- Write self-documenting code with clear function names