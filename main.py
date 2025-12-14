#!/usr/bin/env python3
"""
codeloom - A lightweight Claude Code terminal interface

Designed to work on phones, over SSH, and anywhere a heavy TUI won't.
Full session history, live streaming, and interrupt support.
"""

import sys
import os
import re
import signal
import readline  # Enables line editing and history in input()
from typing import Optional

from brain import Brain
from session import SessionManager
from profile import ProfileManager
from process import ProcessManager
from ui import UI


class Codeloom:
    """Main application class."""

    def __init__(self):
        self.ui = UI()
        self.session_mgr = SessionManager()
        self.profile_mgr = ProfileManager()
        self.process_mgr = ProcessManager()
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
        profile = self.profile_mgr.current_profile
        self.ui.print_info(f"Session: {session.name} | Profile: {profile.name}")
        print()

        while self.running:
            try:
                # Check for pending process callbacks
                self._check_process_callbacks()

                # Get shortened path for prompt
                cwd = os.getcwd()
                home = os.path.expanduser("~")
                if cwd.startswith(home):
                    display_path = "~" + cwd[len(home):]
                else:
                    display_path = cwd

                profile_name = self.profile_mgr.current_profile.name if self.profile_mgr.current_profile else "default"
                prompt = self.ui.prompt(display_path, profile_name)
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

        # Get profile context (system prompt + notes)
        profile_context = self.profile_mgr.get_context()

        # Add process info to context
        process_context = self._get_process_context()
        if process_context:
            if profile_context:
                profile_context += "\n\n" + process_context
            else:
                profile_context = process_context

        # Start streaming
        self.ui.stream_start()

        response_text = ""
        try:
            for event in self.brain.send(message, history, profile_context):
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

        # Check for background process requests in response
        self._parse_background_requests(response_text)

    def _get_process_context(self) -> str:
        """Get process-related context for Claude."""
        parts = []

        # Running processes
        running_summary = self.process_mgr.get_running_summary()
        if running_summary:
            parts.append(running_summary)

        # Instructions for background processes
        bg_instructions = """To run a long-running command in the background (like a server, build, or test):
Output: [BACKGROUND] your-command-here
The command will run in background and you'll be called back with results when it completes."""
        parts.append(bg_instructions)

        return "\n\n".join(parts)

    def _check_process_callbacks(self):
        """Check for completed background processes that need Claude review."""
        pending = self.process_mgr.get_pending_callbacks()
        for proc in pending:
            self.ui.print_info(f"Background process [{proc.id}] finished. Sending to Claude for review...")
            print()

            # Generate callback message
            callback_msg = self.process_mgr.get_callback_message(proc)

            # Mark as reviewed before sending to avoid loops
            self.process_mgr.mark_reviewed(proc.id)

            # Send to Claude
            self._send_message(callback_msg)

    def _parse_background_requests(self, response_text: str):
        """
        Parse Claude's response for background process requests.

        Looks for patterns like:
        [BACKGROUND] command here
        [BG] command here
        """
        # Pattern: [BACKGROUND] or [BG] followed by command
        patterns = [
            r'\[BACKGROUND\]\s*(.+?)(?:\n|$)',
            r'\[BG\]\s*(.+?)(?:\n|$)',
            r'`\[BACKGROUND\]\s*(.+?)`',
            r'`\[BG\]\s*(.+?)`',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            for cmd in matches:
                cmd = cmd.strip()
                if cmd:
                    self.ui.print_info(f"Starting background process: {cmd[:50]}...")
                    proc = self.process_mgr.run(cmd, callback=True)
                    self.ui.print_success(f"Started [{proc.id}] - will notify when complete")
                    print()

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

        # Profile commands
        elif cmd == "profile":
            if not args:
                # Show current profile
                p = self.profile_mgr.current_profile
                self.ui.print_profile(p.name, p.system_prompt, p.notes)
            else:
                # Switch to profile
                profile = self.profile_mgr.load_profile(args)
                if profile:
                    self.ui.print_success(f"Switched to profile: {profile.name}")
                else:
                    # Create new profile
                    profile = self.profile_mgr.new_profile(args)
                    self.ui.print_success(f"Created new profile: {profile.name}")

        elif cmd == "profiles":
            profiles = self.profile_mgr.list_profiles()
            self.ui.print_profiles_list(profiles, self.profile_mgr.current_profile.name)

        elif cmd == "prompt":
            if not args:
                # Show current prompt
                prompt = self.profile_mgr.get_system_prompt()
                if prompt:
                    self.ui.print_info(f"System prompt:\n{prompt}")
                else:
                    self.ui.print_info("No system prompt set")
            else:
                # Set new prompt
                self.profile_mgr.set_system_prompt(args)
                self.ui.print_success("System prompt updated")

        elif cmd == "note":
            if not args:
                self.ui.print_error("Usage: /note <text> to add, /notes to list, /note del <n> to remove")
            elif args.startswith("del "):
                try:
                    idx = int(args[4:].strip())
                    if self.profile_mgr.remove_note(idx):
                        self.ui.print_success(f"Removed note {idx}")
                    else:
                        self.ui.print_error(f"Invalid note number: {idx}")
                except ValueError:
                    self.ui.print_error("Usage: /note del <number>")
            else:
                self.profile_mgr.add_note(args)
                self.ui.print_success("Note added")

        elif cmd == "notes":
            notes = self.profile_mgr.list_notes()
            self.ui.print_notes(notes)

        elif cmd == "clearnotes":
            self.profile_mgr.clear_notes()
            self.ui.print_success("All notes cleared")

        # Process commands
        elif cmd == "run":
            if not args:
                self.ui.print_error("Usage: /run <command>")
                return
            proc = self.process_mgr.run(args)
            self.ui.print_success(f"Started [{proc.id}]: {args[:50]}")

        elif cmd == "ps":
            processes = self.process_mgr.list_processes(include_finished=(args != "-r"))
            self.ui.print_processes(processes)

        elif cmd == "output" or cmd == "out":
            if not args:
                self.ui.print_error("Usage: /output <process_id> [lines]")
                return
            parts = args.split()
            proc_id = parts[0]
            lines = int(parts[1]) if len(parts) > 1 else 50
            output = self.process_mgr.get_output(proc_id, tail=lines)
            if output:
                self.ui.print_process_output(proc_id, output)
            else:
                self.ui.print_error(f"Process not found: {proc_id}")

        elif cmd == "kill":
            if not args:
                self.ui.print_error("Usage: /kill <process_id>")
                return
            if self.process_mgr.kill(args):
                self.ui.print_success(f"Killed process: {args}")
            else:
                self.ui.print_error(f"Could not kill process: {args}")

        elif cmd == "pclean":
            count = self.process_mgr.cleanup()
            self.ui.print_success(f"Cleaned up {count} finished processes")

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
