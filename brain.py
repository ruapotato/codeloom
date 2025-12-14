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
import json
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

        # Build command with streaming JSON output for live feedback
        cmd = [
            "claude",
            "-p", prompt,
            "--dangerously-skip-permissions",
            "--verbose",
            "--output-format", "stream-json"
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

            # Stream JSON events line by line
            for line in self.process.stdout:
                if self._interrupted:
                    yield StreamEvent(text="\n[Interrupted]", is_done=True)
                    break

                line = line.strip()
                if not line:
                    continue

                # Parse streaming JSON event
                try:
                    event = json.loads(line)
                    for stream_event in self._parse_stream_event(event):
                        yield stream_event
                except json.JSONDecodeError:
                    # Non-JSON output, display as-is
                    yield StreamEvent(text=line + "\n")

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

    def _parse_stream_event(self, event: dict) -> Generator[StreamEvent, None, None]:
        """Parse a streaming JSON event from Claude Code."""
        event_type = event.get("type", "")

        if event_type == "assistant":
            # Assistant text message (complete)
            message = event.get("message", {})
            content = message.get("content", [])
            for block in content:
                block_type = block.get("type")
                if block_type == "text":
                    text = block.get("text", "")
                    if text:
                        yield StreamEvent(text=text + "\n")
                elif block_type == "tool_use":
                    # Tool use within assistant message
                    tool_name = block.get("name", "tool")
                    tool_input = block.get("input", {})
                    yield from self._format_tool_use(tool_name, tool_input)

        elif event_type == "content_block_start":
            # Start of a content block
            content_block = event.get("content_block", {})
            block_type = content_block.get("type", "")
            if block_type == "tool_use":
                tool_name = content_block.get("name", "tool")
                yield StreamEvent(text=f"\n⚙ {tool_name}\n", is_tool_call=True)

        elif event_type == "content_block_delta":
            # Streaming delta
            delta = event.get("delta", {})
            delta_type = delta.get("type", "")
            if delta_type == "text_delta":
                text = delta.get("text", "")
                if text:
                    yield StreamEvent(text=text)
            elif delta_type == "input_json_delta":
                # Tool input being streamed - could show partial input
                pass

        elif event_type == "content_block_stop":
            # End of a content block - add newline
            yield StreamEvent(text="\n")

        elif event_type == "tool_use":
            # Tool is being called (standalone event)
            tool_name = event.get("tool", event.get("name", "tool"))
            tool_input = event.get("input", {})
            yield from self._format_tool_use(tool_name, tool_input)

        elif event_type == "tool_result":
            # Tool execution result (standalone)
            content = event.get("content", "")
            if content:
                # Format tool output - truncate if very long
                if len(content) > 2000:
                    content = content[:2000] + "\n... (truncated)"
                yield StreamEvent(text=f"{content}\n", is_tool_call=True)

        elif event_type == "user":
            # User message containing tool results
            message = event.get("message", {})
            content = message.get("content", [])
            for block in content:
                if block.get("type") == "tool_result":
                    result_content = block.get("content", "")
                    if result_content:
                        # Format tool result - truncate if very long
                        if len(result_content) > 2000:
                            result_content = result_content[:2000] + "\n... (truncated)"
                        yield StreamEvent(text=f"→ {result_content}\n", is_tool_call=True)

        elif event_type == "system":
            # System message (e.g., tool execution info)
            message = event.get("message", "")
            subtype = event.get("subtype", "")
            if message:
                yield StreamEvent(text=f"{message}\n", is_tool_call=(subtype == "tool_use"))

        elif event_type == "result":
            # Final result - this contains the complete response
            result = event.get("result", "")
            subtype = event.get("subtype", "")
            # Don't re-output if we already streamed it
            if subtype == "success":
                pass  # Already streamed above
            elif result and isinstance(result, str):
                yield StreamEvent(text=result + "\n")

        else:
            # Unknown event type - show it for debugging
            if event_type and event_type not in ("message_start", "message_delta", "message_stop"):
                yield StreamEvent(text=f"[{event_type}] {json.dumps(event)[:200]}\n", is_tool_call=True)

    def _format_tool_use(self, tool_name: str, tool_input: dict) -> Generator[StreamEvent, None, None]:
        """Format a tool use event for display."""
        if tool_name == "Write":
            file_path = tool_input.get("file_path", "")
            content = tool_input.get("content", "")
            lines = content.count('\n') + 1 if content else 0
            yield StreamEvent(text=f"📝 Writing {file_path} ({lines} lines)\n", is_tool_call=True)
        elif tool_name == "Edit":
            file_path = tool_input.get("file_path", "")
            old = tool_input.get("old_string", "")[:50]
            yield StreamEvent(text=f"✏️  Editing {file_path}\n", is_tool_call=True)
        elif tool_name == "Bash":
            cmd = tool_input.get("command", "")
            yield StreamEvent(text=f"$ {cmd}\n", is_tool_call=True)
        elif tool_name == "Read":
            file_path = tool_input.get("file_path", "")
            yield StreamEvent(text=f"📖 Reading {file_path}\n", is_tool_call=True)
        elif tool_name == "Glob":
            pattern = tool_input.get("pattern", "")
            yield StreamEvent(text=f"🔍 Glob {pattern}\n", is_tool_call=True)
        elif tool_name == "Grep":
            pattern = tool_input.get("pattern", "")
            yield StreamEvent(text=f"🔍 Grep {pattern}\n", is_tool_call=True)
        else:
            yield StreamEvent(text=f"⚙ {tool_name}\n", is_tool_call=True)

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
