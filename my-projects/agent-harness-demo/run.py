#!/usr/bin/env python3
"""
Agent Harness Demo — Interactive CLI
=====================================

A debuggable agent harness to demonstrate the Agent = Model + Harness pattern.

Usage:
    python run.py                      # Normal mode (INFO level)
    python run.py --debug              # Show tool call details
    python run.py --trace              # Show everything including raw API
    python run.py --max-steps 5        # Limit loop iterations

Commands (type during session):
    q, exit, quit    — Exit the session (auto-saves transcript)
    :stats            — Show session statistics
    :save [filename]  — Save transcript manually
    :debug, :trace    — Change log level at runtime

Examples:
    python run.py --debug
    s01 >> Create a file hello.py that prints "Hello, Agent!"
    s01 >> What files are in the current directory?
    s01 >> Read the contents of hello.py
    s01 >> q

Setup:
    1. pip install anthropic python-dotenv
    2. Copy parent .env or create .env with ANTHROPIC_API_KEY / MODEL_ID
    3. python run.py
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Ensure we can import agent_harness even when run directly
_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from agent_harness.logger import DebugLogger, Level
from agent_harness.tools import TOOLS, TOOL_HANDLERS
from agent_harness.session import Session
from agent_harness.core import agent_loop

# ── Optional: readline for better REPL ──────────────────────
try:
    import readline
    readline.parse_and_bind('set bind-tty-special-chars off')
    readline.parse_and_bind('set input-meta on')
    readline.parse_and_bind('set output-meta on')
    readline.parse_and_bind('set convert-meta off')
except ImportError:
    pass


def load_config():
    """Load API configuration from .env files (project-local first, then parent)."""
    # Try importing dotenv
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("[ERROR] python-dotenv not installed. Run: pip install python-dotenv")
        sys.exit(1)

    # Search for .env: local first, then parent (learn-claude-code)
    env_paths = [
        _here / ".env",
        _here.parent / "learn-claude-code" / ".env",
        _here.parent / ".env",
    ]

    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            break
    else:
        print("[WARN] No .env file found. Using environment variables.")

    # Validate required config
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("MODEL_ID", "claude-sonnet-4-6")
    base_url = os.getenv("ANTHROPIC_BASE_URL")

    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY not set.")
        print("  Create a .env file with:")
        print("    ANTHROPIC_API_KEY=sk-ant-xxx")
        print("    MODEL_ID=claude-sonnet-4-6")
        sys.exit(1)

    return api_key, model, base_url


def create_client(api_key: str, base_url: str | None):
    """Create the Anthropic client."""
    try:
        from anthropic import Anthropic
    except ImportError:
        print("[ERROR] anthropic not installed. Run: pip install anthropic")
        sys.exit(1)

    if base_url:
        # For Anthropic-compatible providers (DeepSeek, MiniMax, etc.)
        return Anthropic(base_url=base_url, api_key=api_key)
    else:
        return Anthropic(api_key=api_key)


def print_welcome(logger: DebugLogger, model: str, log_level: Level):
    """Print the welcome banner."""
    logger.banner("Agent Harness Demo")
    print(f"  Model:      {model}")
    print(f"  Log level:  {log_level}")
    print(f"  Tools:      {', '.join(TOOL_HANDLERS.keys())} ({len(TOOL_HANDLERS)} total)")
    print(f"  Workspace:  {Path.cwd()}")
    print()
    print(f"  Type a task and press Enter. The agent will use tools to complete it.")
    print(f"  Commands:  :stats  :save  :debug  :trace  :info  q/exit")
    print()


def handle_meta_command(cmd: str, logger: DebugLogger, session: Session) -> bool:
    """
    Handle meta-commands (starting with ':' or 'q').
    Returns True if the REPL should continue, False to exit.
    """
    cmd_lower = cmd.strip().lower()

    # Exit commands
    if cmd_lower in ("q", "exit", "quit"):
        return False

    # :stats — show session summary
    if cmd_lower == ":stats":
        print(session.summary())
        return True

    # :save — manual save
    if cmd_lower.startswith(":save"):
        parts = cmd.split(maxsplit=1)
        filename = parts[1] if len(parts) > 1 else None
        path = session.save(filename)
        print(f"  ✅ Transcript saved: {path}")
        return True

    # :debug — switch to DEBUG level
    if cmd_lower == ":debug":
        logger.set_level("DEBUG")
        print(f"  🔍 Log level: DEBUG")
        return True

    # :trace — switch to TRACE level
    if cmd_lower == ":trace":
        logger.set_level("TRACE")
        print(f"  🔬 Log level: TRACE")
        return True

    # :info — switch back to INFO level
    if cmd_lower == ":info":
        logger.set_level("INFO")
        print(f"  📋 Log level: INFO")
        return True

    # :help — show commands
    if cmd_lower in (":help", ":h"):
        print("  Commands:")
        print("    q, exit, quit  — Exit (auto-saves transcript)")
        print("    :stats          — Show session statistics")
        print("    :save [name]    — Save transcript to file")
        print("    :debug          — Show tool call details")
        print("    :trace          — Show raw API responses")
        print("    :info           — Show only step markers")
        print("    :help           — This message")
        return True

    print(f"  Unknown command: {cmd}. Type :help for available commands.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Agent Harness Demo — a debuggable agent loop"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Show tool call details and token usage"
    )
    parser.add_argument(
        "--trace", action="store_true",
        help="Show everything including raw API responses"
    )
    parser.add_argument(
        "--max-steps", type=int, default=30,
        help="Maximum loop iterations (default: 30)"
    )
    args = parser.parse_args()

    # Determine log level
    if args.trace:
        log_level: Level = "TRACE"
    elif args.debug:
        log_level: Level = "DEBUG"
    else:
        log_level: Level = "INFO"

    # Initialize
    logger = DebugLogger(level=log_level)
    session = Session(save_dir=str(_here / "transcripts"))

    # Load config and create client
    api_key, model, base_url = load_config()
    client = create_client(api_key, base_url)

    # System prompt
    system_prompt = (
        f"You are a coding agent working in directory '{Path.cwd()}'.\n"
        f"You have access to these tools: {', '.join(TOOL_HANDLERS.keys())}.\n"
        f"Rules:\n"
        f"1. Use tools to complete the task — don't just explain.\n"
        f"2. Read files before editing them.\n"
        f"3. After creating or editing files, verify your work.\n"
        f"4. When the task is done, state clearly what you accomplished.\n"
        f"5. If a tool fails, try a different approach.\n"
        f"6. Stay within the workspace directory — don't navigate outside."
    )

    # Welcome
    print_welcome(logger, model, log_level)

    # ── REPL ──────────────────────────────────────────────
    history = []

    while True:
        try:
            query = input("\033[36mharness >> \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break

        if not query:
            continue

        # Handle meta-commands
        if query.startswith(":") or query.lower() in ("q", "exit", "quit"):
            should_continue = handle_meta_command(query, logger, session)
            if not should_continue:
                break
            continue

        # Record user query
        session.add_user_query(query)

        # Add user message to history
        history.append({"role": "user", "content": query})

        # ── Run the agent loop ──────────────────────────
        try:
            agent_loop(
                messages=history,
                client=client,
                model=model,
                system_prompt=system_prompt,
                logger=logger,
                session=session,
                max_steps=args.max_steps,
            )
        except KeyboardInterrupt:
            logger.warn("Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Agent loop crashed: {e}")
            continue

        # Print the model's final text response
        if history:
            last_msg = history[-1]
            if last_msg["role"] == "assistant":
                content = last_msg["content"]
                if isinstance(content, list):
                    for block in content:
                        if hasattr(block, "type") and block.type == "text":
                            print(f"\n\033[1m{block.text}\033[0m")
                elif isinstance(content, str):
                    print(f"\n\033[1m{content}\033[0m")

        print()

    # ── Exit: save transcript ────────────────────────────
    saved_path = session.save()
    print(f"\n📝 Transcript auto-saved: {saved_path}")
    print(session.summary())
    print("\n👋 Goodbye!\n")


if __name__ == "__main__":
    main()
