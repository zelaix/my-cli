# My CLI

A Python-based AI command-line assistant inspired by Google's [Gemini CLI](https://github.com/google-gemini/gemini-cli), bringing the power of AI directly to your terminal with enhanced performance, multi-provider support, and extensibility.

## Project Status

🎉 **Phase 2.1+ Complete - Multi-Provider AI Assistant Ready** 🎉

The project has successfully completed Phase 2.1 with a fully functional multi-provider AI client featuring **Gemini AND Kimi K2 model support**, streaming responses, conversation management, token handling, and comprehensive error handling - all integrated into a working CLI!

### Completed Work
- ✅ Architecture analysis of original TypeScript Gemini CLI
- ✅ Dependency review and Python equivalents identified
- ✅ Core functionality mapping completed
- ✅ Integration test requirements analyzed
- ✅ Comprehensive implementation roadmap created
- ✅ **Phase 1.1**: Project structure and dependencies setup
- ✅ **Phase 1.2**: Core architecture implementation  
- ✅ **Phase 1.3**: Hierarchical configuration system
- ✅ **Phase 2.1**: Multi-Provider AI Client with streaming & conversation management
- ✅ **Multi-Provider Support**: Gemini AND Kimi K2 models with provider auto-detection
- ✅ Python package structure with proper module organization
- ✅ Modern Python tooling configuration (Ruff, MyPy, Pytest)
- ✅ **Working CLI framework** with Typer and Rich
- ✅ **Hierarchical configuration system** with JSON comments and .env support
- ✅ **Environment variable interpolation** (${VAR} syntax support)
- ✅ **Advanced CLI commands** for configuration management
- ✅ **Real AI integration** with Google Gemini AND Kimi K2 APIs
- ✅ **Streaming responses** with real-time chat for all providers
- ✅ **Conversation management** with turn tracking and statistics
- ✅ **Token counting and compression** for efficient API usage
- ✅ **Retry logic** with exponential backoff and model fallback
- ✅ **Complete test suite** (93+ tests passing)
- ✅ Development workflow and build scripts
- ✅ **Package installation** via pip

### Current Status
- 📋 **Phase**: 2.1+ - Multi-Provider AI Client ✅ **COMPLETE**
- 🌟 **Unique Feature**: **Multi-Provider Support** (Gemini + Kimi K2) - Beyond original Gemini CLI
- 🎯 **Next Step**: Implement Tool Execution System (Phase 2.2) - Agentic Capabilities
- 📅 **Goal**: Full agentic coding assistant with comprehensive tool ecosystem
- 🏗️ **Current**: Production-ready multi-provider chat assistant with advanced configuration

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

# Use different models (Gemini)
my-cli chat "Hello" --model gemini-1.5-pro
my-cli chat "Hello" --model gemini-2.0-flash-exp

# Use Kimi K2 models (NEW!)
MY_CLI_KIMI_API_KEY=your-kimi-key my-cli chat "Hello" --model kimi-k2-instruct
MY_CLI_KIMI_API_KEY=your-kimi-key my-cli chat "Hello" --model kimi-k2-base
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

My CLI is a Python-based **multi-provider agentic coding assistant** that brings AI-powered development workflows to your terminal. Building upon Google's Gemini CLI foundation, we've created an enhanced Python reimplementation with **unique multi-provider support**.

### 🚀 **Current Capabilities**
- **Multi-Provider AI Support**: Choose between Gemini and Kimi K2 models based on your needs
- **Real-time Streaming Chat**: Interactive conversations with AI assistants
- **Advanced Configuration**: Hierarchical settings with environment variable interpolation
- **Production-Ready**: Robust error handling, retry logic, and comprehensive testing

### 🎯 **Final Goal: Full Agentic Coding Assistant**
- **File Operations**: Read, write, and edit code files with AI guidance
- **Shell Integration**: Execute commands and build processes safely
- **Codebase Analysis**: Understand large projects within extended context windows
- **Automated Workflows**: Handle complex development tasks like refactoring, testing, and deployment
- **Tool Ecosystem**: Extensible plugin system for custom development tools
- **Web Integration**: Search documentation and fetch external resources
- **Memory System**: Persistent project context and conversation history
- **MCP Protocol**: Connect to external services and tools

### 🌟 **Why My CLI?**
- **Enhanced Multi-Provider Support**: Use Gemini for creativity, Kimi K2 for long context analysis
- **Python Ecosystem**: Access to rich ML/AI libraries and better extensibility
- **Modern Architecture**: Clean, async-first design with comprehensive testing
- **Developer Experience**: Intuitive APIs, better debugging, and rich terminal interface

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

#### 2.2 Core Tool System Implementation 🔄 NEXT
- **Built-in Core Tools**: Implement essential tools (`read_file`, `write_file`, `list_directory`, `shell`, `edit_file`)
- **AI-Tool Integration**: Connect tool execution with conversation flow - AI can request and execute tools
- **Confirmation Workflows**: Safe execution with user approval for destructive operations
- **Tool Result Processing**: Feed tool results back into AI conversation context
- **Execution Pipeline**: Orchestrate tool calls within conversation turns
- **Parameter Validation**: Robust input validation and error handling

#### 2.3 Enhanced Conversation Features 🔄 Planned
- Implement chat history persistence and memory
- Add advanced conversation compression strategies
- Create context window management with smart truncation
- Port core system prompts and dynamic prompt construction

### Phase 3: Advanced Tool Ecosystem (Weeks 9-12)
**Status**: 🔄 Core Foundation Ready → Ecosystem Expansion

#### 3.1 MCP Integration 🔄 NEXT
- **MCP Protocol Support**: Implement Model Context Protocol client
- **External Tool Servers**: Connect to MCP servers for extended capabilities
- **Server Discovery**: Automatic discovery and connection to MCP services
- **OAuth Integration**: Secure authentication for remote MCP servers

#### 3.2 Advanced Tools Implementation 🔄 Planned
- **Web Integration**: `web_search`, `web_fetch` for research and documentation
- **Advanced File Operations**: `grep`, `glob`, multi-file processing, batch operations
- **Git Integration**: Version control operations and project management
- **Search Tools**: Advanced search and filtering capabilities

#### 3.3 Tool Discovery & Safety 🔄 Planned
- **Dynamic Tool Registration**: Command-based and MCP-based tool discovery
- **Advanced Safety System**: Sandbox execution, permission systems
- **Tool Filtering**: Include/exclude lists, trust management
- **Custom Tool Support**: Framework for external tool development

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

### Phase 5: Extended Capabilities (Weeks 15-18)
**Status**: 🔄 Planned

#### 5.1 Memory System
- Implement conversation memory management
- Add memory export/import functionality
- Create memory compression and summarization
- Add memory search and retrieval

#### 5.2 Workspace Context
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
| `MY_CLI_API_KEY` | None | Gemini API key (for Gemini models) |
| `MY_CLI_KIMI_API_KEY` | None | Kimi API key (for Kimi K2 models) |
| `MY_CLI_MODEL` | `kimi-k2-instruct` | Default AI model to use |
| `MY_CLI_KIMI_PROVIDER` | `moonshot` | Kimi API provider (moonshot, deepinfra, etc.) |
| `MY_CLI_THEME` | `default` | Color theme |
| `MY_CLI_AUTO_CONFIRM` | `false` | Auto-confirm tool executions |
| `MY_CLI_MAX_TOKENS` | `8192` | Maximum response tokens |
| `MY_CLI_TEMPERATURE` | `0.7` | Response creativity (0.0-1.0) |
| `MY_CLI_TIMEOUT` | `30` | Request timeout in seconds |
| `MY_CLI_DEBUG` | `false` | Enable debug logging |
| `MY_CLI_LOG_LEVEL` | `INFO` | Logging level |

#### **Supported Models**

**Kimi K2 Models:**
- `kimi-k2-instruct` (default) - Instruction-tuned for conversations
- `kimi-k2-base` - Base model for general use

**Gemini Models:**
- `gemini-2.0-flash-exp` - Latest Gemini model
- `gemini-1.5-pro` - High capability model
- `gemini-1.5-flash` - Fast response model

**Kimi Providers:**
- `moonshot` (default) - Moonshot AI provider
- `deepinfra` - DeepInfra platform
- `together` - Together AI
- `fireworks` - Fireworks AI
- `groq` - Groq platform
- `openrouter` - OpenRouter

### ✅ Phase 2.1+ AI Features (Working Now!)

- ✅ **Multi-Provider AI Integration**: Complete Google Gemini AND Kimi K2 API integration with streaming
- ✅ **Provider Auto-Detection**: Automatic routing based on model names (gemini-* → Gemini, kimi-* → Kimi)
- ✅ **Conversation Management**: Turn tracking, statistics, and session management across all providers
- ✅ **Token Management**: Smart counting, compression, and limit enforcement for all models
- ✅ **Error Handling**: Comprehensive retry logic and provider-specific error messages
- ✅ **Authentication**: Multiple authentication methods with secure API key handling per provider
- ✅ **Interactive Chat**: Rich terminal interface with real-time streaming responses for all models
- ✅ **Model Flexibility**: Switch between providers/models without restart or reconfiguration

### 🔄 Coming Features (Phase 2.2+) - Road to Agentic Assistant

**Phase 2.2 - Core Tool System Implementation (Next Priority)**
- **Built-in Core Tools**: Essential tools for file operations and shell commands
- **AI-Tool Integration**: AI can request and execute tools with conversation flow integration
- **Confirmation Workflows**: Safe execution with user approval for destructive operations
- **Tool Result Processing**: Feed tool results back into AI conversation context

**Phase 3 - Advanced Tool Ecosystem**
- **MCP Integration**: Model Context Protocol support for external tool servers
- **Advanced Tools**: Web search, multi-file operations, Git integration
- **Tool Discovery**: Dynamic registration and external tool development
- **Advanced Safety**: Sandbox execution, permission systems, trust management

**Phase 4+ - Extended Capabilities** 
- **Memory System**: Persistent conversation history and project context
- **Multimodal Support**: Image analysis, document parsing, visual understanding
- **Automated Workflows**: Complex development task orchestration
- **Enhanced UX**: Rich terminal interface, themes, and advanced features

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

# Test real AI chat functionality with Gemini
MY_CLI_API_KEY=your-gemini-key my-cli chat "Hello world"

# Test Kimi K2 models
MY_CLI_KIMI_API_KEY=your-kimi-key my-cli chat "Hello world" --model kimi-k2-instruct

# Test streaming vs non-streaming (works with all models)
MY_CLI_API_KEY=your-key my-cli chat "Tell me about Python" --stream
MY_CLI_KIMI_API_KEY=your-kimi-key my-cli chat "Tell me about Python" --no-stream --model kimi-k2-instruct

# Test interactive mode with commands (works with all models)
MY_CLI_API_KEY=your-key my-cli chat
MY_CLI_KIMI_API_KEY=your-kimi-key my-cli chat --model kimi-k2-instruct
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

**🔥 HIGH PRIORITY - Core Agentic Capabilities (Phase 2.2)**
- **Built-in Core Tools**: Implement `read_file`, `write_file`, `list_directory`, `shell`, `edit_file`
- **AI-Tool Integration**: Connect AI conversation flow with tool execution system
- **Tool Safety**: User confirmation workflows and execution previews
- **Result Processing**: Feed tool results back into AI conversation context

**🛠️ MEDIUM PRIORITY - Tool Ecosystem (Phase 3)**
- **MCP Integration**: Model Context Protocol support for external tool servers
- **Advanced Tools**: Web search, multi-file operations, Git integration
- **Tool Discovery**: Dynamic registration and external tool development
- **Advanced Safety**: Sandbox execution, permission systems, trust management

**🧪 SUPPORT & QUALITY**
- **Testing**: Integration tests for tool execution and multi-provider scenarios
- **Documentation**: Usage examples, tutorials, and API reference
- **Performance**: Optimization for large codebases and long conversations

**🔌 EXTENDED CAPABILITIES (Phase 4+)**
- **Memory System**: Persistent conversation history and project context
- **Enhanced UX**: Markdown rendering, syntax highlighting, rich terminal interface
- **Multimodal**: Image and document processing capabilities

## License

This project will be licensed under the Apache 2.0 License, maintaining compatibility with the original Gemini CLI project.

## Acknowledgments

This project is inspired by and aims to enhance upon Google's [Gemini CLI](https://github.com/google-gemini/gemini-cli). We thank the Google Gemini team for their excellent work on the original implementation. 

**Key Enhancements Over Original:**
- **Multi-Provider Support**: Added Kimi K2 model integration alongside Gemini
- **Python Ecosystem**: Modern Python architecture with rich AI/ML library access  
- **Enhanced Configuration**: 6-layer hierarchical configuration with environment interpolation
- **Improved Error Handling**: Provider-specific error classification and recovery
- **Advanced Testing**: Comprehensive test suite with 93+ passing tests

Our goal is to create the most capable and extensible agentic coding assistant while honoring the vision and architecture of the original Gemini CLI.