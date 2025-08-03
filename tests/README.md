# Test Suite Organization

This directory contains the comprehensive test suite for My CLI, organized by test type and scope.

## Directory Structure

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── test_tools.py       # Tool system tests
│   ├── test_container.py   # Dependency injection tests
│   ├── test_settings.py    # Configuration system tests
│   └── ...
├── integration/             # Integration tests for complete workflows
│   ├── test_function_calling.py           # Single-step function calling
│   ├── test_multi_step_function_calling.py # Multi-step agentic workflows
│   └── test_native_gemini_function_calling.py
├── debug/                   # Debug utilities and tools
│   └── debug_conversation_history.py      # Conversation analysis tool
└── fixtures/                # Test fixtures and mock data
```

## Test Categories

### Unit Tests (`unit/`)
Test individual components in isolation:
- **Tool System**: Protocol validation, parameter handling
- **Configuration**: Hierarchical settings, environment variables
- **Service Layer**: File discovery, Git operations
- **Dependency Injection**: Container management, service scopes

### Integration Tests (`integration/`)
Test complete workflows and system interactions:
- **Function Calling**: AI → Tool execution → Response processing
- **Multi-step Workflows**: Complex task orchestration
- **Provider Integration**: Gemini API, streaming, authentication

### Debug Tools (`debug/`)
Utilities for debugging and analysis:
- **Conversation History**: Debug function call/response matching
- **API Analysis**: Trace conversation flow and event sequences

## Running Tests

### All Tests
```bash
# Run complete test suite
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=my_cli
```

### Specific Test Categories
```bash
# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests only  
python -m pytest tests/integration/ -v

# Specific test file
python -m pytest tests/integration/test_function_calling.py -v
```

### Function Calling Tests (Manual)
```bash
# Single-step function calling
MY_CLI_API_KEY=your-key python tests/integration/test_function_calling.py

# Multi-step agentic workflows  
MY_CLI_API_KEY=your-key python tests/integration/test_multi_step_function_calling.py

# Enable debug output
MY_CLI_DEBUG=1 MY_CLI_API_KEY=your-key python tests/integration/test_multi_step_function_calling.py
```

## Test Status

- ✅ **Unit Tests**: 50+ tests covering core components
- ✅ **Integration Tests**: Phase 2.1 complete, function calling working
- ✅ **Function Calling**: Single-step and multi-step workflows validated
- ✅ **Multi-step Agentic**: Complete orchestration pipeline working

## Key Test Features

- **Clean Output**: Tests show essential information by default
- **Debug Mode**: Use `MY_CLI_DEBUG=1` for detailed logging
- **Real API Testing**: Integration tests use actual Gemini API
- **Comprehensive Coverage**: From unit components to end-to-end workflows