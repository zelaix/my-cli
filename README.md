# My CLI - Preview Release v0.1.0

A Python-based agentic AI coding assistant powered by Kimi K2 models.

## 🚀 What is My CLI?

My CLI is an **intelligent command-line coding assistant** that brings the power of AI directly to your terminal. Unlike traditional AI chat tools, My CLI features:

- **⚡ Agentic Tool Execution**: AI can autonomously read files, search codebases, browse the web, and execute commands
- **🔍 Advanced Search**: Pattern matching and file discovery capabilities for efficient codebase exploration
- **🤖 Specialized Subagents**: Automatic delegation to expert AI specialists for code review and debugging
- **🌑 Powered by Kimi K2**: This preview version uses Moonshot AI's Kimi K2 models, known for their advanced agentic intelligence.

## ✨ Implemented Features

### 🛠️ **Core Tool System**
- **File Operations**: `read_file`, `write_file`, `edit_file`, `list_directory` with intelligent file handling
- **Shell Integration**: Safe command execution with confirmation workflows
- **Advanced Search**: `grep` for pattern matching in files, `glob` for file discovery with complex patterns
- **Web Tools**: `web_search` for real-time information, `web_fetch` for content analysis

### 💬 **Intelligent Conversation**
- **Multi-Step Workflows**: AI automatically chains tool calls to complete complex tasks
- **Cross-Turn Memory**: Maintains conversation context in interactive mode
- **Streaming Responses**: Real-time AI responses with live tool execution feedback
- **Rich Terminal Interface**: Beautiful output formatting and progress indicators

### 🤖 **Specialized Subagents**
- **Code Review Specialist**: Automatically triggered for security analysis, code quality assessment, and best practices validation
- **Debug Specialist**: Systematic debugging methodology with root cause analysis and targeted fix recommendations
- **Transparent Delegation**: Clear indication when specialists are handling your tasks

## 📦 Installation & Configuration

### Prerequisites
- Python 3.8 or higher
- Kimi API key from [Moonshot AI](https://platform.moonshot.cn)

### Installation

```bash
# Clone the repository
git clone https://github.com/zelaix/my-cli.git
cd my-cli

# Install the package in development mode
conda create -n my-cli python=3.9
conda activate my-cli
pip install -r requirements.txt
pip install -e ".[dev]"

# Verify installation
my-cli --version
```

### Configuration

#### 1. Set up your Kimi API key
```bash
# Option 1: Environment variable (recommended)
export MY_CLI_KIMI_API_KEY="your-kimi-api-key-here"

# Option 2: Configuration file
my-cli config --init
my-cli config --set kimi_api_key="your-kimi-api-key-here" --scope user
```

#### 2. Optional: Configure web search (for web tools)
```bash
# Set up web search APIs (choose one or more)
export SERPER_API_KEY="your-serper-key"      # Default search engine
```

#### 3. Verify configuration
```bash
my-cli config --show
```

### Model Configuration

```bash
# Available Kimi K2 models
MY_CLI_MODEL=kimi-k2-instruct  # Default
MY_CLI_MODEL=kimi-k2-base      # Alternative

# Check current model
my-cli config --key model
```

## 🎯 Example Use Cases

### 1. **Basic Chat**
```bash
# Simple conversation
my-cli chat "Hello! What can you do?"

# Interactive mode
my-cli chat
# Then type your questions interactively
```

### 2. **File Operations**
```bash
# Ask AI to read and explain a file
my-cli chat "Read the README.md file and summarize its contents"

# Create a new file with AI assistance
my-cli chat "Write a Python file that calculates fibonacci numbers"
```

### 3. **Codebase Exploration**
```bash
# Find specific patterns in code
my-cli chat "Find all TODO comments in the entire codebase"

# Discover files with specific patterns
my-cli chat "List all Python test files in the project"

# Complex search operations
my-cli chat "Find all functions that use the 'typer' library and show me their implementations"
```

### 4. **Web Integration**
```bash
# Stay updated on technology
my-cli chat "Search for the best practices for using kimi k2 and summarize them"

# Analyze web content
my-cli chat "Fetch the content from https://docs.python.org/3/tutorial/ and explain the key concepts"
```

### 5. **Multi-Step Workflows**
```bash
# Comprehensive codebase analysis
my-cli chat "Analyze this entire Python project: find the main entry points, identify potential security issues, and suggest improvements"
```

### 6. **Subagent Specialization**
```bash
# Trigger Code Review Specialist
my-cli chat "Review the code of subagents for security vulnerabilities"
# Output: 🤖 Using code-reviewer specialist...

# Trigger Debug Specialist  
my-cli chat "Debug this error: ModuleNotFoundError: No module named 'torch'"
# Output: 🤖 Using debug-specialist specialist...
```

### 7. **Interactive Development Session**
```bash
# Start interactive mode
my-cli chat

# Example conversation flow:
You: "Read the app.py file"
AI: [Reads and shows file contents]

You: "What security issues do you see?"
AI: [Provides detailed security analysis]

You: "Fix the most critical issue"
AI: [Implements fix with explanation]
```

## ⚠️ Current Limitations

### **Subagent System**
- **Fixed Specialists**: Only 2 hardcoded subagents (code-reviewer, debug-specialist)
- **Pattern-Based Matching**: Uses simple regex patterns for task delegation
- **No Custom Subagents**: Cannot create or configure custom specialist agents
- **No Multi-Agent Collaboration**: Subagents work independently, no chaining

### **Context Management**
- **No Auto-Summarization**: When context limit is reached, conversation may be truncated
- **Session-Only Memory**: Cross-turn memory only works within single interactive session
- **No Persistent History**: Conversation history is lost when session ends
- **Limited Context Awareness**: No long-term project context retention

### **Model Support**
- **Kimi K2 Only**: Preview version limited to Kimi models (kimi-k2-instruct, kimi-k2-base)
- **Single Provider**: No multi-provider support in this release
- **API Dependency**: Requires stable internet connection and valid API keys

### **Tool System**
- **No MCP Integration**: Cannot connect to external Model Context Protocol servers
- **Limited Git Support**: Basic file operations only, no advanced version control features
- **No Plugin System**: Cannot add custom tools dynamically
- **Web Search Dependency**: Web tools require third-party API keys for best results

### **Error Handling**
- **Basic Recovery**: Limited error recovery and retry mechanisms
- **API Rate Limits**: May hit rate limits with intensive usage
- **Network Dependencies**: Web tools fail gracefully but provide limited offline functionality

### **Performance**
- **No Caching**: Repeated operations don't benefit from caching
- **Sequential Processing**: Tool calls executed sequentially, not in parallel
- **Memory Usage**: Large files or long conversations may consume significant memory

## 🔧 Troubleshooting

### Common Issues

**1. "API key not found" error**
```bash
# Make sure your API key is set
export MY_CLI_KIMI_API_KEY="your-actual-api-key"
my-cli config --show  # Verify key is loaded
```

**2. Web search not working**
```bash
# Web search requires additional API keys
export SERPER_API_KEY="your-serper-key"  # Recommended
# Or set up alternative providers (see configuration section)
```

**3. Interactive mode commands**
```bash
# In interactive mode, use these commands:
/help     # Show available commands
/stats    # View conversation statistics
/clear    # Clear conversation history
/stream   # Toggle streaming mode
/exit     # Exit interactive mode
```

## 🚀 What's Next?

This preview release demonstrates the core agentic capabilities with specialized subagents. Future releases will include:

- **More Specialists**: Data analysis, testing, documentation specialists
- **Custom Subagents**: User-configurable specialist agents
- **Persistent Memory**: Cross-session conversation and project context
- **Advanced Tool Ecosystem**: MCP integration, Git workflows, IDE integration
- **Multi-Provider Support**: Additional AI model providers and fallback systems
- **Performance Optimizations**: Caching, parallel processing, and efficiency improvements

## 📄 License

MIT License - See LICENSE file for details.

---

**Happy coding with your AI assistant! 🤖✨**