"""
Main CLI entry point for Grivredr
Provides access to all commands and features
"""

import sys
import asyncio
from typing import Optional


def print_banner():
    """Print application banner"""
    banner = """
╔══════════════════════════════════════════════════════════╗
║                                                            ║
║        Grivredr - AI Web Scraper Generator                    ║
║                                                            ║
║  Train web scrapers using AI in minutes, not hours        ║
║                                                            ║
╚══════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_help():
    """Print help information"""
    help_text = """
Usage: grivredr [COMMAND] [OPTIONS]

Commands:
  tui           Launch interactive Terminal UI (recommended)
  train          Train a new portal scraper (CLI mode)
  fill           Fill a grievance form using generated scraper
  record         Record human actions for training
  --help, -h     Show this help message

Examples:
  grivredr tui                              # Launch interactive UI
  grivredr train my_portal --district ranchi  # Train specific portal
  grivredr fill --scraper outputs/scrapers/   # Fill form

For more information, visit: https://github.com/yourusername/grivredr
"""
    print(help_text)


async def launch_tui():
    """Launch the interactive TUI"""
    try:
        from cli.tui import main as tui_main

        await tui_main()
    except ImportError as e:
        print(f"Error: {e}")
        print("\nPlease install rich package: pip install rich")
        sys.exit(1)


async def train_cli(args: list):
    """Run training CLI"""
    try:
        from cli.train_cli import main as train_main

        await train_main(args)
    except ImportError:
        print("Error: train_cli module not found")
        sys.exit(1)


async def fill_cli(args: list):
    """Run fill CLI"""
    try:
        from cli.fill_cli import main as fill_main

        await fill_main(args)
    except ImportError:
        print("Error: fill_cli module not found")
        sys.exit(1)


async def record_cli(args: list):
    """Run record CLI"""
    try:
        from cli.record_cli import main as record_main

        await record_main(args)
    except ImportError:
        print("Error: record_cli module not found")
        sys.exit(1)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Grivredr - AI-Powered Web Scraper Generator", add_help=False
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="tui",
        help="Command to run (tui, train, fill, record)",
    )
    parser.add_argument(
        "args", nargs=argparse.REMAINDER, help="Additional arguments for the command"
    )

    # Parse arguments
    args = parser.parse_args()

    print_banner()

    # Route to appropriate command
    if args.command == "tui":
        asyncio.run(launch_tui())
    elif args.command == "train":
        asyncio.run(train_cli(args.args))
    elif args.command == "fill":
        asyncio.run(fill_cli(args.args))
    elif args.command == "record":
        asyncio.run(record_cli(args.args))
    elif args.command in ["--help", "-h"]:
        print_help()
    else:
        print(f"Unknown command: {args.command}")
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
