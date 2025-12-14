"""
brain.py - AI Backend Abstraction

This is the ONLY file that needs to change to support a different AI platform.
Currently implements Claude Code headless mode via subprocess.
"""

import subprocess
import threading
import queue
import signal
import os
from typing import Generator, Optional, Callable
from dataclasses import dataclass


@dataclass
class StreamEvent:
    """Represents a chunk of streamed output."""
    text: str
    is_tool_call: bool = False
    is_error: bool = False
    is_done: bool = False


class ClaudeBrain:
    """
    Claude Code headless mode backend.

    To adapt for another AI:
    1. Replace this class with your implementation
    2. Keep the same interface: send() returning Generator[StreamEvent]
    3. Implement interrupt() to stop generation
    """

    def __init__(self, session_context: Optional[str] = None):
        self.process: Optional[subprocess.Popen] = None
        self._interrupted = False
        self.session_context = session_context

    def send(self, message: str, conversation_history: list = None) -> Generator[StreamEvent, None, None]:
        """
        Send a message and stream the response.

        Args:
            message: User input message
            conversation_history: Previous messages for context (optional)

        Yields:
            StreamEvent objects with response chunks
        """
        self._interrupted = False

        # Build the prompt with context if we have history
        prompt = self._build_prompt(message, conversation_history)

        # Build command
        cmd = [
            "claude",
            "-p", prompt,
            "--dangerously-skip-permissions"
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid  # Create new process group for clean interrupt
            )

            # Stream output line by line
            buffer = ""
            for char in iter(lambda: self.process.stdout.read(1), ''):
                if self._interrupted:
                    yield StreamEvent(text="\n[Interrupted]", is_done=True)
                    break

                buffer += char

                # Yield on newlines or when buffer gets long
                if char == '\n' or len(buffer) > 80:
                    # Detect tool calls (Claude outputs specific patterns)
                    is_tool = self._detect_tool_call(buffer)
                    yield StreamEvent(text=buffer, is_tool_call=is_tool)
                    buffer = ""

            # Yield any remaining buffer
            if buffer and not self._interrupted:
                yield StreamEvent(text=buffer)

            self.process.wait()

            if not self._interrupted:
                yield StreamEvent(text="", is_done=True)

        except FileNotFoundError:
            yield StreamEvent(
                text="Error: 'claude' command not found. Is Claude Code installed?",
                is_error=True,
                is_done=True
            )
        except Exception as e:
            yield StreamEvent(
                text=f"Error: {str(e)}",
                is_error=True,
                is_done=True
            )
        finally:
            self.process = None

    def interrupt(self) -> bool:
        """
        Interrupt the current generation.

        Returns:
            True if a process was interrupted, False otherwise
        """
        self._interrupted = True
        if self.process:
            try:
                # Kill the entire process group
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                return True
            except (ProcessLookupError, PermissionError):
                pass
        return False

    def _build_prompt(self, message: str, history: list = None) -> str:
        """Build prompt with conversation context."""
        if not history:
            return message

        # Build context from history
        # Format: previous exchanges to give context
        context_parts = []

        # Only include last few exchanges to avoid token limits
        recent_history = history[-6:] if len(history) > 6 else history

        for entry in recent_history:
            role = entry.get("role", "user")
            content = entry.get("content", "")

            if role == "user":
                context_parts.append(f"User: {content}")
            elif role == "assistant":
                # Truncate long responses
                if len(content) > 500:
                    content = content[:500] + "..."
                context_parts.append(f"Assistant: {content}")

        if context_parts:
            context = "\n".join(context_parts)
            return f"Previous conversation context:\n{context}\n\nCurrent message: {message}"

        return message

    def _detect_tool_call(self, text: str) -> bool:
        """Detect if output contains tool call indicators."""
        tool_indicators = [
            "Running:",
            "Reading:",
            "Writing:",
            "Searching:",
            "Executing:",
            "$ ",  # Shell command
        ]
        return any(indicator in text for indicator in tool_indicators)


# Alias for easy import
Brain = ClaudeBrain
