"""
Entry point for running My CLI as a module.

This allows users to run the CLI using:
    python -m my_cli [command] [options]
"""

from my_cli.cli.app import main

if __name__ == "__main__":
    main()