"""
session.py - Session and History Management

Handles saving/loading sessions with full conversation history,
including all AI output (not just messages like Claude Code does).
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class Message:
    """A single message in the conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Session:
    """A conversation session with full history."""
    id: str
    name: str
    created_at: str
    updated_at: str
    messages: List[Message]
    working_directory: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "working_directory": self.working_directory,
            "messages": [asdict(m) for m in self.messages]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        messages = [Message(**m) for m in data.get("messages", [])]
        return cls(
            id=data["id"],
            name=data["name"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            working_directory=data.get("working_directory", os.getcwd()),
            messages=messages
        )


class SessionManager:
    """Manages session persistence and listing."""

    def __init__(self, sessions_dir: Optional[str] = None):
        if sessions_dir:
            self.sessions_dir = Path(sessions_dir)
        else:
            # Default to ~/.config/codeloom/sessions
            config_dir = Path.home() / ".config" / "codeloom"
            self.sessions_dir = config_dir / "sessions"

        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.current_session: Optional[Session] = None

    def new_session(self, name: Optional[str] = None) -> Session:
        """Create a new session."""
        now = datetime.now()
        session_id = now.strftime("%Y%m%d_%H%M%S")

        if not name:
            name = now.strftime("%Y-%m-%d %H:%M")

        self.current_session = Session(
            id=session_id,
            name=name,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            messages=[],
            working_directory=os.getcwd()
        )

        self._save_current()
        return self.current_session

    def load_session(self, session_id: str) -> Optional[Session]:
        """Load a session by ID."""
        session_file = self.sessions_dir / f"{session_id}.json"

        if not session_file.exists():
            return None

        try:
            with open(session_file, "r") as f:
                data = json.load(f)
            self.current_session = Session.from_dict(data)
            return self.current_session
        except (json.JSONDecodeError, KeyError) as e:
            return None

    def save_session(self) -> bool:
        """Save the current session."""
        return self._save_current()

    def _save_current(self) -> bool:
        """Internal save method."""
        if not self.current_session:
            return False

        self.current_session.updated_at = datetime.now().isoformat()
        session_file = self.sessions_dir / f"{self.current_session.id}.json"

        try:
            with open(session_file, "w") as f:
                json.dump(self.current_session.to_dict(), f, indent=2)
            return True
        except IOError:
            return False

    def add_message(self, role: str, content: str, metadata: Dict = None) -> None:
        """Add a message to the current session."""
        if not self.current_session:
            self.new_session()

        msg = Message(
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            metadata=metadata
        )
        self.current_session.messages.append(msg)
        self._save_current()  # Auto-save after each message

    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history in simple format for the AI."""
        if not self.current_session:
            return []

        return [
            {"role": m.role, "content": m.content}
            for m in self.current_session.messages
        ]

    def list_sessions(self, limit: int = 20) -> List[Dict[str, str]]:
        """List recent sessions."""
        sessions = []

        for session_file in sorted(self.sessions_dir.glob("*.json"), reverse=True):
            if len(sessions) >= limit:
                break

            try:
                with open(session_file, "r") as f:
                    data = json.load(f)
                sessions.append({
                    "id": data["id"],
                    "name": data["name"],
                    "updated_at": data["updated_at"],
                    "message_count": len(data.get("messages", []))
                })
            except (json.JSONDecodeError, KeyError):
                continue

        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        session_file = self.sessions_dir / f"{session_id}.json"

        if session_file.exists():
            try:
                session_file.unlink()
                if self.current_session and self.current_session.id == session_id:
                    self.current_session = None
                return True
            except IOError:
                pass

        return False

    def rename_session(self, new_name: str) -> bool:
        """Rename the current session."""
        if not self.current_session:
            return False

        self.current_session.name = new_name
        return self._save_current()

    def get_session_preview(self, session_id: str, lines: int = 5) -> List[str]:
        """Get a preview of a session's recent messages."""
        session_file = self.sessions_dir / f"{session_id}.json"

        if not session_file.exists():
            return []

        try:
            with open(session_file, "r") as f:
                data = json.load(f)

            messages = data.get("messages", [])
            preview = []

            for msg in messages[-lines:]:
                role = msg.get("role", "?")
                content = msg.get("content", "")[:60]
                if len(msg.get("content", "")) > 60:
                    content += "..."
                prefix = ">" if role == "user" else "<"
                preview.append(f"{prefix} {content}")

            return preview
        except (json.JSONDecodeError, KeyError):
            return []
