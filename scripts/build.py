#!/usr/bin/env python3
"""
Build script for My CLI.

This script handles building, testing, and packaging the project.
Equivalent to the build.js script in the original Node.js version.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def run_command(command: List[str], cwd: Optional[Path] = None) -> int:
    """Run a command and return its exit code."""
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command, cwd=cwd)
    return result.returncode


def build_package() -> int:
    """Build the package for distribution."""
    print("🏗️  Building My CLI...")
    
    # Run linting
    print("\n📋 Running linter...")
    if run_command(["ruff", "check", "src/", "tests/"]) != 0:
        print("❌ Linting failed")
        return 1
    
    # Run formatting check
    print("\n🎨 Checking formatting...")
    if run_command(["ruff", "format", "--check", "src/", "tests/"]) != 0:
        print("❌ Formatting check failed")
        return 1
    
    # Run type checking
    print("\n🔍 Running type checker...")
    if run_command(["mypy", "src/"]) != 0:
        print("❌ Type checking failed")
        return 1
    
    # Run tests
    print("\n🧪 Running tests...")
    if run_command(["pytest", "tests/"]) != 0:
        print("❌ Tests failed")
        return 1
    
    # Build package
    print("\n📦 Building package...")
    if run_command(["python", "-m", "build"]) != 0:
        print("❌ Package build failed")  
        return 1
    
    print("\n✅ Build completed successfully!")
    return 0


def clean() -> int:
    """Clean build artifacts."""
    print("🧹 Cleaning build artifacts...")
    
    artifacts = [
        "build/",
        "dist/", 
        "*.egg-info/",
        "__pycache__/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        "htmlcov/",
    ]
    
    for pattern in artifacts:
        if "*" in pattern:
            # Use shell globbing for wildcard patterns
            subprocess.run(f"rm -rf {pattern}", shell=True)
        else:
            path = Path(pattern)
            if path.exists():
                subprocess.run(["rm", "-rf", str(path)])
    
    print("✅ Clean completed!")
    return 0


def test() -> int:
    """Run tests with coverage."""
    print("🧪 Running tests with coverage...")
    return run_command([
        "pytest", 
        "tests/",
        "--cov=gemini_cli",
        "--cov-report=term-missing",
        "--cov-report=html"
    ])


def lint() -> int:
    """Run linting and formatting."""
    print("📋 Running linter and formatter...")
    
    # Run linter with auto-fix
    result = run_command(["ruff", "check", "--fix", "src/", "tests/"])
    if result != 0:
        return result
    
    # Run formatter
    return run_command(["ruff", "format", "src/", "tests/"])


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/build.py [build|clean|test|lint]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "build":
        sys.exit(build_package())
    elif command == "clean":
        sys.exit(clean())
    elif command == "test":
        sys.exit(test())
    elif command == "lint":
        sys.exit(lint())
    else:
        print(f"Unknown command: {command}")
        print("Available commands: build, clean, test, lint")
        sys.exit(1)


if __name__ == "__main__":
    main()