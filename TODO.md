# Kimi K2 Tool Calling Implementation Plan

## Overview
Implement complete tool calling support for Kimi K2 models while maintaining full backward compatibility with existing Gemini implementation.

## Key API Differences

### Gemini API (Current)
- Uses native `functionDeclarations` format: `[{"functionDeclarations": [...]}]`
- Function calls in response use `function_call` with `name` and `args`
- Integrated into Google's generative AI SDK

### Kimi API (To Implement)
- Uses OpenAI-compatible `tools` format: `[{"type": "function", "function": {...}}]`
- Function calls in response use `tool_calls` with `finish_reason='tool_calls'`
- Supports manual parsing with special markers: `<|tool_calls_section_begin|>`, etc.
- Tool responses use `role='tool'` messages

## Implementation Tasks

### Phase 1: Core Schema Generation ✅ COMPLETE
- ✅ Create `src/my_cli/core/function_calling/kimi_schema_generator.py`
  - Convert internal tool schemas to OpenAI-compatible format
  - Generate `{"type": "function", "function": {...}}` structures
  - Handle parameter validation and type conversion

- ✅ Update `src/my_cli/core/function_calling/gemini_schema_generator.py`
  - Add `format_tools_for_provider()` function
  - Support both Gemini and Kimi formats
  - Maintain backward compatibility

### Phase 2: Enhanced Function Call Parsing ✅ COMPLETE
- ✅ Update `src/my_cli/core/function_calling/function_parser.py`
  - Add support for OpenAI-style `tool_calls` parsing
  - Implement manual parsing for Kimi special markers
  - Handle `finish_reason='tool_calls'` detection
  - Support both Gemini and Kimi response formats

### Phase 3: Kimi Content Generator Enhancement ✅ COMPLETE
- ✅ Update `src/my_cli/core/client/kimi_generator.py`
  - Add `tools` parameter support to request creation
  - Implement tool-aware response handling
  - Add streaming support for tool calls
  - Handle `role='tool'` messages for tool responses

### Phase 4: Provider-Agnostic Orchestrator ✅ COMPLETE
- ✅ Update `src/my_cli/core/function_calling/agentic_orchestrator.py`
  - Auto-detect provider and use appropriate schema format
  - Handle different response formats in agentic loop
  - Ensure tool result formatting works for both providers
  - Maintain unified tool execution flow

### Phase 5: Response Processing Updates ✅ COMPLETE
- ✅ Update `src/my_cli/core/function_calling/function_response_converter.py`
  - Handle both Gemini and Kimi response formats
  - Support `role='tool'` message format for Kimi
  - Ensure conversation history works with both providers
  - Handle tool result feedback loop for both APIs

### Phase 6: Integration and Testing ✅ COMPLETE
- ✅ Create integration tests for Kimi tool calling
- ✅ Test multi-step tool workflows with Kimi models
- ✅ Verify seamless provider switching
- ✅ Test all core tools (read_file, write_file, etc.) with Kimi
- ✅ Validate conversation history and context management

## Technical Implementation Details

### Tool Schema Conversion
```python
# Gemini Format (current)
{
    "functionDeclarations": [
        {
            "name": "read_file",
            "description": "Read file contents",
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
    ]
}

# Kimi Format (to implement)
[
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents",
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
    }
]
```

### Response Format Handling
```python
# Gemini Response
{
    "candidates": [{
        "content": {
            "parts": [{
                "function_call": {
                    "name": "read_file",
                    "args": {"file_path": "/path/to/file"}
                }
            }]
        }
    }]
}

# Kimi Response
{
    "choices": [{
        "message": {
            "tool_calls": [{
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": '{"file_path": "/path/to/file"}'
                }
            }]
        },
        "finish_reason": "tool_calls"
    }]
}
```

## Success Criteria
- ✅ All core tools work with Kimi K2 models
- ✅ Multi-step agentic workflows function correctly
- ✅ Seamless switching between Gemini and Kimi models
- ✅ Full backward compatibility maintained
- ✅ Streaming tool execution works for both providers
- ✅ Conversation history and context management unified
- ✅ Error handling and retry logic works for both APIs

## Notes
- Provider detection is automatic based on model name (`gemini-*` vs `kimi-*`)
- Tool registry and execution remain provider-agnostic
- Same tools work with both providers without modification
- Configuration system already supports both providers