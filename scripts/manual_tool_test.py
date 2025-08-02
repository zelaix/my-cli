#!/usr/bin/env python3
"""Manual test of individual tools."""

import asyncio
from pathlib import Path
from src.my_cli.tools.registry import ToolRegistry
from src.my_cli.core.config import MyCliConfig

class NoAbortSignal:
    """Simple abort signal that never aborts."""
    def is_aborted(self):
        return False
    
    def is_set(self):
        return False

async def test_read_file():
    print("🔧 Testing read_file tool")
    config = MyCliConfig()
    await config.initialize()
    
    tool_registry = ToolRegistry()
    await tool_registry.discover_builtin_tools(config)
    
    read_file_tool = tool_registry.get_tool("read_file")
    if read_file_tool:
        try:
            # Test reading README.md
            result = await read_file_tool.execute({
                "absolute_path": str(Path.cwd() / "README.md")
            }, NoAbortSignal())
            print("✅ read_file tool works!")
            print(f"First 200 chars: {result.llm_content[:200]}...")
        except Exception as e:
            print(f"❌ read_file failed: {e}")
    else:
        print("❌ read_file tool not found")

async def test_list_directory():
    print("\n🔧 Testing list_directory tool")
    config = MyCliConfig()
    await config.initialize()
    
    tool_registry = ToolRegistry()
    await tool_registry.discover_builtin_tools(config)
    
    list_dir_tool = tool_registry.get_tool("list_directory")
    if list_dir_tool:
        try:
            result = await list_dir_tool.execute({
                "path": str(Path.cwd())
            }, NoAbortSignal())
            print("✅ list_directory tool works!")
            print(f"Directory listing preview: {result.llm_content[:300]}...")
        except Exception as e:
            print(f"❌ list_directory failed: {e}")
    else:
        print("❌ list_directory tool not found")

async def test_run_shell_command():
    print("\n🔧 Testing run_shell_command tool")
    config = MyCliConfig()
    await config.initialize()
    
    tool_registry = ToolRegistry()
    await tool_registry.discover_builtin_tools(config)
    
    shell_tool = tool_registry.get_tool("run_shell_command")
    if shell_tool:
        try:
            result = await shell_tool.execute({
                "command": "echo 'Hello from shell tool!'",
                "description": "Test echo command"
            }, NoAbortSignal())
            print("✅ run_shell_command tool works!")
            print(f"Output: {result.llm_content}")
        except Exception as e:
            print(f"❌ run_shell_command failed: {e}")
    else:
        print("❌ run_shell_command tool not found")

async def test_write_file():
    print("\n🔧 Testing write_file tool")
    config = MyCliConfig()
    await config.initialize()
    
    tool_registry = ToolRegistry()
    await tool_registry.discover_builtin_tools(config)
    
    write_tool = tool_registry.get_tool("write_file")
    if write_tool:
        try:
            test_file = Path.cwd() / "test_write.txt"
            result = await write_tool.execute({
                "absolute_path": str(test_file),
                "content": "Hello from write_file tool!\nThis is a test file."
            }, NoAbortSignal())
            print("✅ write_file tool works!")
            print(f"Result: {result.llm_content}")
            
            # Clean up
            if test_file.exists():
                test_file.unlink()
                print("🧹 Cleaned up test file")
                
        except Exception as e:
            print(f"❌ write_file failed: {e}")
    else:
        print("❌ write_file tool not found")

async def test_edit_file():
    print("\n🔧 Testing edit_file tool")
    config = MyCliConfig()
    await config.initialize()
    
    tool_registry = ToolRegistry()
    await tool_registry.discover_builtin_tools(config)
    
    # First create a test file
    test_file = Path.cwd() / "test_edit.txt"
    test_file.write_text("Hello World\nThis is a test file.")
    
    edit_tool = tool_registry.get_tool("edit_file")
    if edit_tool:
        try:
            result = await edit_tool.execute({
                "absolute_path": str(test_file),
                "old_str": "Hello World",
                "new_str": "Hello Universe"
            }, NoAbortSignal())
            print("✅ edit_file tool works!")
            print(f"Result: {result.llm_content}")
            
            # Check the edit worked
            new_content = test_file.read_text()
            print(f"File content after edit: {new_content}")
            
            # Clean up
            test_file.unlink()
            print("🧹 Cleaned up test file")
            
        except Exception as e:
            print(f"❌ edit_file failed: {e}")
            # Clean up on error
            if test_file.exists():
                test_file.unlink()
    else:
        print("❌ edit_file tool not found")

async def main():
    print("🚀 Manual Tool Testing")
    print("Testing each tool directly without AI interaction\n")
    
    await test_read_file()
    await test_list_directory()
    await test_run_shell_command()
    await test_write_file()
    await test_edit_file()
    
    print("\n🎉 Manual tool testing completed!")

if __name__ == "__main__":
    asyncio.run(main())