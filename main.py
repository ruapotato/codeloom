#!/usr/bin/env python3
"""
codeloom - A lightweight Claude Code terminal interface

Designed to work on phones, over SSH, and anywhere a heavy TUI won't.
Full session history, live streaming, and interrupt support.
"""

import sys
import signal
import readline  # Enables line editing and history in input()
from typing import Optional

from brain import Brain
from session import SessionManager
from ui import UI


class Codeloom:
    """Main application class."""

    def __init__(self):
        self.ui = UI()
        self.session_mgr = SessionManager()
        self.brain = Brain()
        self.running = True
        self._setup_signals()

    def _setup_signals(self):
        """Setup signal handlers for clean interrupt."""
        signal.signal(signal.SIGINT, self._handle_interrupt)

    def _handle_interrupt(self, signum, frame):
        """Handle Ctrl+C - interrupt AI or exit."""
        if self.brain.interrupt():
            self.ui.interrupted()
        else:
            # No active generation, treat as exit request
            print()
            self.ui.print_info("Press Ctrl+C again or type /quit to exit")

    def run(self, initial_session: Optional[str] = None):
        """Main application loop."""
        self.ui.banner()

        # Load or create session
        if initial_session:
            if not self.session_mgr.load_session(initial_session):
                self.ui.print_error(f"Session '{initial_session}' not found")
                self.session_mgr.new_session()
        else:
            # Start new session by default
            self.session_mgr.new_session()

        session = self.session_mgr.current_session
        self.ui.print_info(f"Session: {session.name} ({session.id})")
        print()

        while self.running:
            try:
                prompt = self.ui.prompt(self.session_mgr.current_session.name)
                user_input = input(prompt).strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                    continue

                # Regular message - send to AI
                self._send_message(user_input)

            except EOFError:
                # Ctrl+D
                print()
                self.running = False
            except KeyboardInterrupt:
                # Already handled by signal, but catch here too
                print()
                continue

        self._cleanup()

    def _send_message(self, message: str):
        """Send a message to the AI and stream the response."""
        # Save user message
        self.session_mgr.add_message("user", message)

        # Get conversation history for context
        history = self.session_mgr.get_history()[:-1]  # Exclude current message

        # Start streaming
        self.ui.stream_start()

        response_text = ""
        try:
            for event in self.brain.send(message, history):
                if event.is_error:
                    self.ui.print_error(event.text)
                    return

                if event.is_done:
                    break

                response_text += event.text
                self.ui.stream_chunk(event.text, event.is_tool_call)

        except KeyboardInterrupt:
            self.brain.interrupt()
            self.ui.interrupted()
            response_text += "\n[Interrupted]"

        finally:
            self.ui.stream_end()

        # Save AI response
        if response_text.strip():
            self.session_mgr.add_message("assistant", response_text.strip())

    def _handle_command(self, command: str):
        """Handle slash commands."""
        parts = command[1:].split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("quit", "exit", "q"):
            self.running = False

        elif cmd == "help":
            self.ui.print_help()

        elif cmd == "clear":
            self.ui.clear_screen()

        elif cmd == "new":
            name = args if args else None
            session = self.session_mgr.new_session(name)
            self.ui.print_success(f"New session: {session.name}")

        elif cmd == "list":
            sessions = self.session_mgr.list_sessions()
            self.ui.print_sessions_list(sessions)

        elif cmd == "load":
            if not args:
                self.ui.print_error("Usage: /load <session_id or number>")
                return

            # Check if it's a number (from /list)
            try:
                idx = int(args)
                sessions = self.session_mgr.list_sessions()
                if 1 <= idx <= len(sessions):
                    args = sessions[idx - 1]["id"]
                else:
                    self.ui.print_error(f"Invalid session number: {idx}")
                    return
            except ValueError:
                pass  # Not a number, use as ID

            session = self.session_mgr.load_session(args)
            if session:
                self.ui.print_success(f"Loaded: {session.name}")
                # Show preview
                preview = self.session_mgr.get_session_preview(args)
                if preview:
                    print()
                    for line in preview[-3:]:
                        self.ui.print_info(f"  {line}")
                    print()
            else:
                self.ui.print_error(f"Session not found: {args}")

        elif cmd == "save":
            if self.session_mgr.save_session():
                self.ui.print_success("Session saved")
            else:
                self.ui.print_error("Failed to save session")

        elif cmd == "rename":
            if not args:
                self.ui.print_error("Usage: /rename <new name>")
                return
            if self.session_mgr.rename_session(args):
                self.ui.print_success(f"Renamed to: {args}")
            else:
                self.ui.print_error("Failed to rename session")

        elif cmd == "delete":
            if not args:
                self.ui.print_error("Usage: /delete <session_id>")
                return
            if self.session_mgr.delete_session(args):
                self.ui.print_success(f"Deleted session: {args}")
            else:
                self.ui.print_error(f"Session not found: {args}")

        elif cmd == "history":
            messages = [
                {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                for m in (self.session_mgr.current_session.messages if self.session_mgr.current_session else [])
            ]
            self.ui.print_history(messages)

        else:
            self.ui.print_error(f"Unknown command: /{cmd}")
            self.ui.print_info("Type /help for available commands")

    def _cleanup(self):
        """Cleanup before exit."""
        self.session_mgr.save_session()
        self.ui.print_info("Goodbye!")


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="codeloom - Lightweight Claude Code terminal interface"
    )
    parser.add_argument(
        "-s", "--session",
        help="Load a specific session by ID"
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List available sessions and exit"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )

    args = parser.parse_args()

    if args.list:
        mgr = SessionManager()
        ui = UI(use_colors=not args.no_color)
        sessions = mgr.list_sessions()
        ui.print_sessions_list(sessions)
        return

    app = Codeloom()
    if args.no_color:
        from ui import Colors
        Colors.disable()

    app.run(initial_session=args.session)


if __name__ == "__main__":
    main()
