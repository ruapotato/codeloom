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

    def prompt(self, path: Optional[str] = None, profile: Optional[str] = None) -> str:
        """Display the input prompt with path:profile format."""
        c = Colors
        if path and profile:
            prefix = f"{c.DIM}{path}{c.RESET}:{c.CYAN}{profile}{c.RESET} "
        elif path:
            prefix = f"{c.DIM}{path}{c.RESET} "
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
{c.BOLD}Session Commands:{c.RESET}
  {c.CYAN}/new{c.RESET} [name]      Start a new session
  {c.CYAN}/list{c.RESET}            List saved sessions
  {c.CYAN}/load{c.RESET} <id>       Load a session by ID or number
  {c.CYAN}/save{c.RESET}            Force save current session
  {c.CYAN}/rename{c.RESET} <name>   Rename current session
  {c.CYAN}/delete{c.RESET} <id>     Delete a session
  {c.CYAN}/history{c.RESET}         Show current session history

{c.BOLD}Profile Commands:{c.RESET}
  {c.CYAN}/profile{c.RESET} [name]  Show current or switch to profile
  {c.CYAN}/profiles{c.RESET}        List all profiles
  {c.CYAN}/prompt{c.RESET} [text]   Show or set system prompt
  {c.CYAN}/note{c.RESET} <text>     Add a persistent note
  {c.CYAN}/notes{c.RESET}           List all notes
  {c.CYAN}/note del{c.RESET} <n>    Delete note by number
  {c.CYAN}/clearnotes{c.RESET}      Clear all notes

{c.BOLD}Other:{c.RESET}
  {c.CYAN}/clear{c.RESET}           Clear the screen
  {c.CYAN}/help{c.RESET}            Show this help
  {c.CYAN}/quit{c.RESET}            Exit codeloom

{c.BOLD}Tips:{c.RESET}
  - Press {c.YELLOW}Ctrl+C{c.RESET} to interrupt AI response
  - Sessions auto-save after each message
  - Profiles store system prompts and notes persistently
"""
        print(help_text)

    def print_profile(self, name: str, system_prompt: str, notes: list):
        """Print current profile details."""
        c = Colors
        print(f"{c.BOLD}Profile:{c.RESET} {c.CYAN}{name}{c.RESET}")
        print()
        if system_prompt:
            print(f"{c.BOLD}System Prompt:{c.RESET}")
            print(f"  {c.DIM}{system_prompt}{c.RESET}")
        else:
            print(f"{c.DIM}No system prompt set{c.RESET}")
        print()
        if notes:
            print(f"{c.BOLD}Notes:{c.RESET}")
            for i, note in enumerate(notes, 1):
                print(f"  {c.CYAN}{i}.{c.RESET} {note}")
        else:
            print(f"{c.DIM}No notes{c.RESET}")
        print()

    def print_profiles_list(self, profiles: list, current: str):
        """Print list of profiles."""
        c = Colors
        if not profiles:
            print(f"{c.DIM}No profiles{c.RESET}")
            return

        print(f"{c.BOLD}Profiles:{c.RESET}")
        print()
        for p in profiles:
            name = p.get("name", "")
            marker = f"{c.GREEN}*{c.RESET} " if name == current else "  "
            preview = p.get("system_prompt_preview", "")[:40]
            notes_count = p.get("notes_count", 0)
            print(f"{marker}{c.CYAN}{name}{c.RESET}")
            if preview:
                print(f"    {c.DIM}{preview}...{c.RESET}")
            if notes_count:
                print(f"    {c.DIM}{notes_count} notes{c.RESET}")
        print()
        print(f"{c.DIM}Use /profile <name> to switch{c.RESET}")
        print()

    def print_notes(self, notes: list):
        """Print list of notes."""
        c = Colors
        if not notes:
            print(f"{c.DIM}No notes in current profile{c.RESET}")
            print(f"{c.DIM}Use /note <text> to add a note{c.RESET}")
            return

        print(f"{c.BOLD}Notes:{c.RESET}")
        print()
        for i, note in enumerate(notes, 1):
            print(f"  {c.CYAN}{i}.{c.RESET} {note}")
        print()
        print(f"{c.DIM}Use /note del <n> to remove{c.RESET}")
        print()

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
