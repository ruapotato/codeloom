"""
ui.py - Terminal UI Rendering

Lightweight terminal interface using ANSI codes.
Designed to work over SSH, on phone terminals, and low-bandwidth connections.
Minimizes TTY updates while still looking nice.
"""

import sys
import os
from typing import Optional


class Colors:
    """ANSI color codes - kept simple for compatibility."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Basic colors that work everywhere
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

    @classmethod
    def disable(cls):
        """Disable all colors (for non-tty output)."""
        for attr in dir(cls):
            if attr.isupper() and not attr.startswith('_'):
                setattr(cls, attr, "")


class UI:
    """Terminal UI handler."""

    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors and sys.stdout.isatty()
        if not self.use_colors:
            Colors.disable()

        self._last_line_was_streaming = False

    def clear_screen(self):
        """Clear the terminal screen."""
        if sys.stdout.isatty():
            print("\033[2J\033[H", end="", flush=True)

    def banner(self):
        """Print the startup banner - minimal and clean."""
        c = Colors
        print(f"\n{c.CYAN}{c.BOLD}codeloom{c.RESET} {c.DIM}v0.1{c.RESET}")
        print(f"{c.DIM}Type /help for commands, Ctrl+C to interrupt{c.RESET}")
        print()

    def prompt(self, session_name: Optional[str] = None) -> str:
        """Display the input prompt."""
        c = Colors
        if session_name:
            prefix = f"{c.DIM}[{session_name}]{c.RESET} "
        else:
            prefix = ""
        return f"{prefix}{c.GREEN}{c.BOLD}>{c.RESET} "

    def print_user_message(self, message: str):
        """Echo the user's message (already shown via input)."""
        # User input is already displayed, no need to echo
        pass

    def stream_start(self):
        """Called when AI starts streaming response."""
        c = Colors
        print(f"{c.BLUE}{c.BOLD}<{c.RESET} ", end="", flush=True)
        self._last_line_was_streaming = True

    def stream_chunk(self, text: str, is_tool_call: bool = False):
        """Print a chunk of streamed response."""
        c = Colors

        if is_tool_call:
            # Highlight tool calls
            text = f"{c.YELLOW}{text}{c.RESET}"

        # Just print directly - let the terminal handle wrapping
        print(text, end="", flush=True)

    def stream_end(self):
        """Called when AI finishes streaming."""
        if self._last_line_was_streaming:
            print()  # Ensure we end on a newline
        print()  # Blank line after response
        self._last_line_was_streaming = False

    def print_error(self, message: str):
        """Print an error message."""
        c = Colors
        print(f"{c.RED}{c.BOLD}Error:{c.RESET} {c.RED}{message}{c.RESET}")
        print()

    def print_info(self, message: str):
        """Print an info message."""
        c = Colors
        print(f"{c.DIM}{message}{c.RESET}")

    def print_success(self, message: str):
        """Print a success message."""
        c = Colors
        print(f"{c.GREEN}{message}{c.RESET}")

    def print_warning(self, message: str):
        """Print a warning message."""
        c = Colors
        print(f"{c.YELLOW}{message}{c.RESET}")

    def print_sessions_list(self, sessions: list):
        """Print a list of sessions."""
        c = Colors

        if not sessions:
            print(f"{c.DIM}No saved sessions{c.RESET}")
            return

        print(f"{c.BOLD}Recent Sessions:{c.RESET}")
        print()

        for i, s in enumerate(sessions, 1):
            # Parse date for nicer display
            updated = s.get("updated_at", "")[:16].replace("T", " ")
            msg_count = s.get("message_count", 0)
            name = s.get("name", "Unnamed")
            sid = s.get("id", "")

            print(f"  {c.CYAN}{i:2}.{c.RESET} {name}")
            print(f"      {c.DIM}ID: {sid} | {msg_count} messages | {updated}{c.RESET}")

        print()
        print(f"{c.DIM}Use /load <number> or /load <id> to load a session{c.RESET}")
        print()

    def print_session_preview(self, session_id: str, name: str, preview_lines: list):
        """Print a preview of a session."""
        c = Colors

        print(f"{c.BOLD}Session:{c.RESET} {name} ({session_id})")
        print()

        if preview_lines:
            for line in preview_lines:
                print(f"  {c.DIM}{line}{c.RESET}")
        else:
            print(f"  {c.DIM}(empty session){c.RESET}")

        print()

    def print_help(self):
        """Print help information."""
        c = Colors

        help_text = f"""
{c.BOLD}Commands:{c.RESET}

  {c.CYAN}/new{c.RESET} [name]      Start a new session
  {c.CYAN}/list{c.RESET}            List saved sessions
  {c.CYAN}/load{c.RESET} <id>       Load a session by ID or number
  {c.CYAN}/save{c.RESET}            Force save current session
  {c.CYAN}/rename{c.RESET} <name>   Rename current session
  {c.CYAN}/delete{c.RESET} <id>     Delete a session
  {c.CYAN}/history{c.RESET}         Show current session history
  {c.CYAN}/clear{c.RESET}           Clear the screen
  {c.CYAN}/help{c.RESET}            Show this help
  {c.CYAN}/quit{c.RESET}            Exit codeloom

{c.BOLD}Tips:{c.RESET}

  - Press {c.YELLOW}Ctrl+C{c.RESET} to interrupt AI response
  - Sessions auto-save after each message
  - History is preserved including full AI output

"""
        print(help_text)

    def print_history(self, messages: list, limit: int = 20):
        """Print conversation history."""
        c = Colors

        if not messages:
            print(f"{c.DIM}No messages in this session{c.RESET}")
            return

        recent = messages[-limit:] if len(messages) > limit else messages

        if len(messages) > limit:
            print(f"{c.DIM}(showing last {limit} of {len(messages)} messages){c.RESET}")
            print()

        for msg in recent:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")[:16].replace("T", " ")

            if role == "user":
                print(f"{c.GREEN}{c.BOLD}>{c.RESET} {c.DIM}[{timestamp}]{c.RESET}")
                # Indent user message
                for line in content.split("\n")[:3]:  # First 3 lines
                    print(f"  {line}")
                if content.count("\n") > 3:
                    print(f"  {c.DIM}...{c.RESET}")
            else:
                print(f"{c.BLUE}{c.BOLD}<{c.RESET} {c.DIM}[{timestamp}]{c.RESET}")
                # Truncate long responses
                preview = content[:200]
                if len(content) > 200:
                    preview += f"{c.DIM}...{c.RESET}"
                for line in preview.split("\n"):
                    print(f"  {line}")

            print()

    def interrupted(self):
        """Show interrupted message."""
        c = Colors
        print(f"\n{c.YELLOW}[Interrupted]{c.RESET}")
        print()
