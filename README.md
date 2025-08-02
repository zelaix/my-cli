# My CLI

A Python-based AI command-line assistant inspired by Google's [Gemini CLI](https://github.com/google-gemini/gemini-cli), bringing the power of AI directly to your terminal with enhanced performance and extensibility.

## Project Status

🎉 **Phase 2.1 Complete - Gemini API Client Ready** 🎉

The project has successfully completed Phase 2.1 with a fully functional Gemini API client featuring streaming responses, conversation management, token handling, and comprehensive error handling - all integrated into a working CLI!

### Completed Work
- ✅ Architecture analysis of original TypeScript Gemini CLI
- ✅ Dependency review and Python equivalents identified
- ✅ Core functionality mapping completed
- ✅ Integration test requirements analyzed
- ✅ Comprehensive implementation roadmap created
- ✅ **Phase 1.1**: Project structure and dependencies setup
- ✅ **Phase 1.2**: Core architecture implementation  
- ✅ **Phase 1.3**: Hierarchical configuration system
- ✅ **Phase 2.1**: Gemini API Client with streaming & conversation management
- ✅ Python package structure with proper module organization
- ✅ Modern Python tooling configuration (Ruff, MyPy, Pytest)
- ✅ **Working CLI framework** with Typer and Rich
- ✅ **Hierarchical configuration system** with JSON comments and .env support
- ✅ **Environment variable interpolation** (${VAR} syntax support)
- ✅ **Advanced CLI commands** for configuration management
- ✅ **Real AI integration** with Google Gemini API
- ✅ **Streaming responses** with real-time chat
- ✅ **Conversation management** with turn tracking and statistics
- ✅ **Token counting and compression** for efficient API usage
- ✅ **Retry logic** with exponential backoff and model fallback
- ✅ **Complete test suite** (93+ tests passing)
- ✅ Development workflow and build scripts
- ✅ **Package installation** via pip

### Current Status
- 📋 **Phase**: 2.1 - Gemini API Client ✅ **COMPLETE**
- 🎯 **Next Step**: Implement Tool Execution System (Phase 2.2)
- 📅 **Estimated Timeline**: 20 weeks remaining for full implementation  
- 🏗️ **Implementation**: Complete AI integration with streaming, conversation management, and advanced configuration system

### Quick Start

#### Installation
```bash
# Clone and setup the project
git clone <repository-url>
cd my-cli

# Install the package
pip install -e ".[dev]"
```

#### Basic Usage
```bash
# Check version and help
my-cli --version
my-cli --help

# Initialize configuration files
my-cli config --init

# View current configuration
my-cli config --show

# View configuration sources and hierarchy  
my-cli config --sources

# Set configuration values
my-cli config --set theme=dark --scope project
my-cli config --set debug=true --scope user

# View specific configuration key with source tracing
my-cli config --key theme

# Chat with AI (requires API key)
MY_CLI_API_KEY=your-key my-cli chat "Hello world"
MY_CLI_API_KEY=your-key my-cli chat  # Interactive mode

# Try streaming vs non-streaming
my-cli chat "Tell me about Python" --stream
my-cli chat "Tell me about Python" --no-stream

# Use different models
my-cli chat "Hello" --model gemini-1.5-pro
```

#### Development
```bash
# Run tests
python scripts/build.py test

# Run linting
python scripts/build.py lint

# Clean build artifacts
python scripts/build.py clean
```

## What is My CLI?

My CLI is a command-line AI workflow tool that connects to your tools, understands your code, and accelerates your workflows using AI models. With My CLI you can:

- Query and edit large codebases within Gemini's 1M token context window
- Generate new apps from PDFs or sketches using multimodal capabilities
- Automate operational tasks like querying pull requests or handling complex rebases
- Use tools and MCP servers to connect new capabilities
- Ground queries with Google Search integration

## Why Python?

Our Python implementation aims to provide:

- **Better Performance**: Faster startup times and more efficient resource usage
- **Enhanced Extensibility**: Robust plugin system leveraging Python's ecosystem
- **Improved Developer Experience**: More intuitive APIs and better debugging
- **Cross-Platform Compatibility**: Better support across different operating systems
- **Rich Ecosystem**: Access to Python's vast library ecosystem for AI/ML tools

## Implementation Roadmap

### Phase 1: Foundation & Core Infrastructure (Weeks 1-3)
**Status**: ✅ COMPLETE

#### 1.1 Project Structure & Dependencies ✅ COMPLETE
- **Tech Stack Selection**:
  - ✅ `typer` for CLI framework
  - ✅ `rich` for terminal UI and formatting
  - ✅ `asyncio` for async operations
  - ✅ `pydantic` for data validation and settings
  - ✅ `httpx` for HTTP client
  - ✅ `google-generativeai` for Gemini API integration
- **Project Structure**: ✅ Complete modular package structure created
- **Development Tools**: ✅ Ruff, MyPy, Pytest, pre-commit configured
- **Build System**: ✅ Modern Python packaging with Hatch
- **Basic CLI**: ✅ Working CLI entry point with commands

#### 1.2 Core Architecture ✅ COMPLETE
- ✅ **Modular package structure** created:
  ```
  src/my_cli/
  ├── cli/          # Frontend CLI interface
  ├── core/         # Backend logic & API client  
  ├── tools/        # Tool system
  ├── config/       # Configuration management
  ├── services/     # Service layer
  ├── prompts/      # Prompt management
  └── utils/        # Shared utilities
  ```
- ✅ **Base tool system** with protocols and abstract classes
- ✅ **API client interface** and implementations (Gemini integration ready)
- ✅ **Service layer** (FileDiscovery, Git, Workspace management)
- ✅ **Registry system** for tools and prompts
- ✅ **Dependency injection container** for service management
- ✅ **Enhanced configuration system** with hierarchical settings
- ✅ **Comprehensive test suite** for all core components

**Phase 1.2 Architecture Summary:**
- **Tool System**: Complete protocol-based tool framework with base classes for read-only and modifying tools, automatic parameter validation, and execution confirmation system
- **API Client**: Modular API client architecture with support for multiple authentication types, streaming responses, and conversation management
- **Service Layer**: Comprehensive service architecture including file discovery with Git/ignore pattern support, Git operations, and workspace context management
- **Registry Systems**: Dynamic tool and prompt registration with filtering, source tracking, and runtime discovery capabilities
- **Dependency Injection**: Full IoC container with singleton, transient, and scoped service lifetimes
- **Configuration**: Hierarchical configuration system integrating environment variables, project settings, and global configuration
- **Testing**: 50+ unit tests covering all core components with fixtures and mocking

#### 1.3 Configuration System ✅ COMPLETE
- ✅ **Hierarchical configuration system** with 6-layer precedence (default → user → project → system → environment → command-line)
- ✅ **JSON with comments support** using `commentjson` library
- ✅ **Enhanced .env file loading** with hierarchical search (`.my-cli/.env` → `.env` → `~/.my-cli/.env` → `~/.env`)
- ✅ **Environment variable interpolation** (`$VAR_NAME` and `${VAR_NAME}` syntax)
- ✅ **Deep merging** of configuration dictionaries across sources
- ✅ **Platform-specific system settings** (Linux, macOS, Windows paths)
- ✅ **Complete settings management commands**:
  - `my-cli config --show` - Display current configuration with sources
  - `my-cli config --sources` - Show all configuration files and status
  - `my-cli config --key <key>` - Show detailed info about specific setting
  - `my-cli config --set key=value --scope <scope>` - Set configuration values
  - `my-cli config --init` - Initialize configuration files
  - `my-cli config --reload` - Reload configuration from all sources
- ✅ **Rich CLI interface** with beautiful tables and error handling
- ✅ **Configuration validation and type safety** with automatic type conversion
- ✅ **API key management** with secure masking and environment variable support

### Phase 2: Core API Integration (Weeks 4-8)
**Status**: 🎯 **Phase 2.1 COMPLETE** → Phase 2.2 In Progress

#### 2.1 Gemini API Client ✅ COMPLETE
- ✅ **Event-driven streaming system** - Complete streaming architecture with comprehensive event types
- ✅ **Turn management system** - Sophisticated conversation turn handling with state management
- ✅ **Exponential backoff retry logic** - Intelligent retry system with jitter and model fallback
- ✅ **Multiple authentication methods** - API key, OAuth, Application Default Credentials, Service Account, Vertex AI
- ✅ **Token counting and compression** - Advanced token management with multiple compression strategies
- ✅ **Structured error handling** - Comprehensive error classification with user-friendly messages
- ✅ **Main GeminiClient orchestrator** - Complete client coordinating all components
- ✅ **CLI integration** - Full integration with interactive and streaming chat commands

#### 2.2 Tool Execution System 🔄 NEXT
- Implement tool execution pipeline with confirmation workflows
- Add tool result processing and integration with conversation flow
- Create tool execution hooks and event handling
- Implement tool parameter validation and safety checks

#### 2.3 Enhanced Conversation Features 🔄 Planned
- Implement chat history persistence and memory
- Add advanced conversation compression strategies
- Create context window management with smart truncation
- Port core system prompts and dynamic prompt construction

### Phase 3: Tool System (Weeks 9-12)
**Status**: 🔄 Foundation Complete → Implementation Needed

#### 3.1 Tool Framework ✅ COMPLETE
- ✅ **Base Tool class and interface** - Complete protocol-based framework
- ✅ **Tool registration system** - Dynamic discovery and registration
- ✅ **Parameter validation** - Pydantic-based validation with JSON schemas
- 🔄 **Tool execution pipeline** - Needs integration with Phase 2.1 client

#### 3.2 Core Tools Implementation 🔄 NEXT
- **File System Tools**: `read_file`, `read_many_files`, `write_file`, `edit_file`, `ls`, `glob`
- **Search Tools**: `grep`, `web_search`, `web_fetch`
- **Shell Integration**: `shell` with safety confirmations

#### 3.3 Tool Safety & Confirmation 🔄 Planned
- Implement user confirmation system
- Add tool execution previews
- Create safety checks for destructive operations
- Add sandbox execution support

### Phase 4: CLI Interface & UX (Weeks 11-14)
**Status**: 🔄 Planned

#### 4.1 Terminal Interface
- Create interactive CLI with `rich` console
- Implement command history and autocomplete
- Add keyboard shortcuts and vim mode
- Create loading indicators and progress bars

#### 4.2 Message Display System
- Implement markdown rendering
- Add syntax highlighting for code
- Create diff visualization
- Add message threading and organization

#### 4.3 Theme System
- Port existing themes (Dracula, GitHub, etc.)
- Create theme configuration system
- Add custom color scheme support
- Implement dynamic theme switching

### Phase 5: Advanced Features (Weeks 15-18)
**Status**: 🔄 Planned

#### 5.1 MCP Integration
- Implement MCP protocol support
- Create MCP server discovery and connection
- Add OAuth flow for MCP services
- Port Google Auth provider

#### 5.2 Memory System
- Implement conversation memory management
- Add memory export/import functionality
- Create memory compression and summarization
- Add memory search and retrieval

#### 5.3 Workspace Context
- Implement project detection (git, package files)
- Add .my-cli-ignore support
- Create workspace file discovery
- Add IDE integration hooks

### Phase 6: Extended Capabilities (Weeks 19-22)
**Status**: 🔄 Planned

#### 6.1 Multimodal Support
- Add image input support
- Implement file upload handling
- Create media processing pipeline
- Add document parsing (PDF, etc.)

#### 6.2 Background Operations
- Implement async task management
- Add background file monitoring
- Create proactive assistance features
- Add scheduled operations

#### 6.3 Extensibility
- Create plugin system architecture
- Add custom tool registration
- Implement external tool integration
- Create API for third-party extensions

### Phase 7: Performance & Production (Weeks 23-26)
**Status**: 🔄 Planned

#### 7.1 Performance Optimization
- Implement intelligent caching
- Add request batching and optimization
- Create efficient file handling
- Optimize memory usage

#### 7.2 Testing & Quality
- Port integration test suite
- Add comprehensive unit tests
- Create performance benchmarks
- Implement error handling and reporting

#### 7.3 Distribution & Deployment
- Create PyPI packaging
- Add installation scripts
- Implement auto-update system
- Create documentation and tutorials

## Key Implementation Considerations

### Tool System Design
- Use Python's `inspect` module for dynamic tool discovery
- Leverage `pydantic` for robust parameter validation
- Implement async/await throughout for performance

### Configuration Management
- Use `pydantic-settings` for type-safe configuration
- Support both environment variables and config files
- Implement hierarchical configuration (global → project → local)

### Security & Safety
- Implement comprehensive input validation
- Add execution sandboxing capabilities
- Create detailed permission systems
- Maintain audit logs for sensitive operations

### Performance Targets
- Sub-second startup time
- Real-time streaming responses
- Efficient memory usage for large codebases
- Responsive UI even with heavy operations

## Success Metrics

- **Functional Parity**: All core features from TypeScript version
- **Performance**: Comparable or better response times
- **User Experience**: Seamless migration path for existing users
- **Extensibility**: Plugin system for community contributions
- **Maintenance**: Clean, testable, well-documented codebase

## Current Functionality

### ✅ Working Commands

| Command | Status | Description |
|---------|--------|--------------|
| `my-cli --version` | ✅ Working | Show version information |
| `my-cli --help` | ✅ Working | Display help with rich formatting |
| `my-cli config --show` | ✅ Working | Display current configuration with sources |
| `my-cli config --sources` | ✅ Working | Show all configuration files and status |
| `my-cli config --key <key>` | ✅ Working | Show detailed info about specific setting |
| `my-cli config --set key=value --scope <scope>` | ✅ Working | Set configuration values in specific scope |
| `my-cli config --init` | ✅ Working | Initialize configuration files (.my-cli/settings.json, .env, etc.) |
| `my-cli config --reload` | ✅ Working | Reload configuration from all sources |
| `my-cli init` | ✅ Working | Initialize project configuration (calls config --init) |
| `my-cli chat "message"` | ✅ Working | Single message mode with streaming support |
| `my-cli chat "message" --no-stream` | ✅ Working | Single message mode without streaming |
| `my-cli chat "message" --model <model>` | ✅ Working | Single message with specific model |
| `my-cli chat` | ✅ Working | Interactive chat mode with commands (/help, /stats, /clear, /stream) |
| `python -m my_cli` | ✅ Working | Module execution |

### ✅ Core Architecture & AI Integration (Phase 2.1 Complete)

| Component | Status | Description |
|-----------|--------|-------------|
| **Tool System** | ✅ Complete | Protocol-based framework with base classes |
| **Gemini API Client** | ✅ Complete | Full streaming integration with Google Gemini API |
| **Event-driven Streaming** | ✅ Complete | Real-time streaming responses with comprehensive event types |
| **Turn Management** | ✅ Complete | Conversation turn handling with state management and statistics |
| **Token Management** | ✅ Complete | Token counting, compression strategies, and limit enforcement |
| **Retry Logic** | ✅ Complete | Exponential backoff with jitter and model fallback |
| **Error Handling** | ✅ Complete | Structured error classification with user-friendly messages |
| **Authentication** | ✅ Complete | Multiple auth methods (API key, OAuth, ADC, Service Account, Vertex AI) |
| **Service Layer** | ✅ Complete | File discovery, Git operations, workspace context |
| **Registry Systems** | ✅ Complete | Dynamic tool and prompt registration |
| **Dependency Injection** | ✅ Complete | IoC container with multiple scopes |
| **Hierarchical Configuration** | ✅ Complete | 6-layer precedence system with JSON comments and .env support |
| **Environment Variable Interpolation** | ✅ Complete | `$VAR` and `${VAR}` syntax support in config files |
| **Settings Management Commands** | ✅ Complete | Full CLI interface for configuration management |
| **Interactive Chat Interface** | ✅ Complete | Rich terminal interface with streaming, statistics, and chat commands |
| **Testing Framework** | ✅ Complete | 93+ tests passing, comprehensive coverage |

### ✅ Configuration System Features

#### **Hierarchical Configuration Sources** (in precedence order)
1. **Command-line arguments** (highest precedence)
2. **Environment variables** (from .env files or shell)
3. **System settings** (`/etc/my-cli/settings.json` or platform equivalent)
4. **Project settings** (`.my-cli/settings.json` in project directory)
5. **User settings** (`~/.config/my-cli/settings.json`)
6. **Default values** (lowest precedence)

#### **Configuration File Locations**
- **Project**: `.my-cli/settings.json` (JSON with comments)
- **Project Environment**: `.my-cli/.env` 
- **User**: `~/.config/my-cli/settings.json`
- **User Environment**: `~/.my-cli/.env` or `~/.env`
- **System**: `/etc/my-cli/settings.json` (Linux), `/Library/Application Support/my-cli/settings.json` (macOS)

#### **Environment Variables**

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MY_CLI_API_KEY` | None | AI API key (required for chat) |
| `MY_CLI_MODEL` | `gemini-2.0-flash-exp` | AI model to use |
| `MY_CLI_THEME` | `default` | Color theme |
| `MY_CLI_AUTO_CONFIRM` | `false` | Auto-confirm tool executions |
| `MY_CLI_MAX_TOKENS` | `8192` | Maximum response tokens |
| `MY_CLI_TEMPERATURE` | `0.7` | Response creativity (0.0-1.0) |
| `MY_CLI_TIMEOUT` | `30` | Request timeout in seconds |
| `MY_CLI_DEBUG` | `false` | Enable debug logging |
| `MY_CLI_LOG_LEVEL` | `INFO` | Logging level |

### ✅ Phase 2.1 AI Features (Working Now!)

- ✅ **Real AI Integration**: Complete Google Gemini API integration with streaming
- ✅ **Conversation Management**: Turn tracking, statistics, and session management  
- ✅ **Token Management**: Smart counting, compression, and limit enforcement
- ✅ **Error Handling**: Comprehensive retry logic and user-friendly error messages
- ✅ **Authentication**: Multiple authentication methods with secure API key handling
- ✅ **Interactive Chat**: Rich terminal interface with real-time streaming responses

### 🔄 Coming Features (Phase 2.2+)

- **Tool Integration**: File operations, shell commands, web tools with AI conversation flow
- **Enhanced Memory**: Persistent conversation history and smart context management
- **MCP Integration**: Model Context Protocol support for extended capabilities

## Testing

### Test Suite Status: ✅ 93+ Tests Passing (Phase 2.1 Complete)

```bash
# Run all tests
python -m pytest tests/unit/ -v
python -m pytest tests/test_phase_2_1_integration.py -v

# Run specific test suites
python -m pytest tests/unit/test_tools.py -v
python -m pytest tests/unit/test_container.py -v
python -m pytest tests/unit/test_prompt_registry.py -v

# Run Phase 2.1 integration tests
python -m pytest tests/test_phase_2_1_integration.py::TestStreamingSystem -v
python -m pytest tests/test_phase_2_1_integration.py::TestTokenManagement -v
python -m pytest tests/test_phase_2_1_integration.py::TestGeminiClientIntegration -v

# Test coverage (Enhanced - Phase 2.1 complete)
python -m pytest tests/ --cov=my_cli
```

### Manual Testing Examples

```bash
# Test basic commands
my-cli --version
my-cli --help
my-cli config --show

# Test configuration system
my-cli config --init                    # Initialize config files
my-cli config --show                    # View current config
my-cli config --sources                 # View all sources
my-cli config --set theme=dark --scope project  # Set project setting
my-cli config --key theme               # View specific key with sources

# Test with environment variables  
MY_CLI_API_KEY=test-key my-cli config --show
MY_CLI_MODEL=custom-model MY_CLI_THEME=dracula my-cli config --show

# Test environment variable interpolation
echo 'MY_CLI_THEME=${HOME}/themes/custom' >> .my-cli/.env
my-cli config --key theme

# Test real AI chat functionality  
MY_CLI_API_KEY=your-api-key my-cli chat "Hello world"

# Test streaming vs non-streaming
MY_CLI_API_KEY=your-api-key my-cli chat "Tell me about Python" --stream
MY_CLI_API_KEY=your-api-key my-cli chat "Tell me about Python" --no-stream

# Test interactive mode with commands
MY_CLI_API_KEY=your-api-key my-cli chat
# In interactive mode, try:
# /help - Show available commands
# /stats - View conversation statistics  
# /clear - Clear conversation history
# /stream - Toggle streaming mode

# Test core architecture components
python -c "
from my_cli.core.config import MyCliConfig
from my_cli.tools.registry import ToolRegistry
from my_cli.prompts.registry import PromptRegistry
import asyncio

async def test():
    config = MyCliConfig()
    await config.initialize()
    print('✓ Core architecture initialized')
    
    tools = ToolRegistry()
    prompts = PromptRegistry()
    print(f'✓ Registries: {len(tools.get_all_tools())} tools, {len(prompts.get_all_prompts())} prompts')

asyncio.run(test())
"
```

## Contributing

The project now has a working foundation and welcomes contributions! The CLI is functional and ready for Phase 2 development.

### Development Setup
```bash
# Clone and install
git clone <repository-url>
cd my-cli
pip install -e ".[dev]"

# Run pre-commit hooks
pre-commit install

# Verify setup
my-cli --version
python scripts/build.py test
```

### Contribution Areas
- 🔥 **Phase 2.2**: Tool execution system integration (high priority)
- 🛠️ **Tool System**: File and shell operations implementation
- 🧠 **Memory System**: Persistent conversation history
- 🎨 **UI/UX**: Enhanced terminal interface with markdown rendering
- 📚 **Documentation**: Usage examples and tutorials
- 🧪 **Testing**: Integration tests for tool execution
- 🔌 **MCP Integration**: Model Context Protocol support

## License

This project will be licensed under the Apache 2.0 License, maintaining compatibility with the original Gemini CLI project.

## Acknowledgments

This project is inspired by and aims to maintain compatibility with Google's [Gemini CLI](https://github.com/google-gemini/gemini-cli). We thank the Google Gemini team for their excellent work on the original implementation.