"""
profile.py - Profile Management

Manages system prompts and persistent notes for codeloom sessions.
Profiles are stored in ~/.config/codeloom/profiles/
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from pathlib import Path


@dataclass
class Profile:
    """A codeloom profile with system prompt and notes."""
    name: str
    system_prompt: str = ""
    notes: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        return cls(
            name=data.get("name", "default"),
            system_prompt=data.get("system_prompt", ""),
            notes=data.get("notes", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", "")
        )


# Default profile with sensible defaults
DEFAULT_PROFILE = Profile(
    name="default",
    system_prompt="You are a helpful coding assistant. Be concise and direct.",
    notes=[]
)


class ProfileManager:
    """Manages profile storage and retrieval."""

    def __init__(self):
        self.config_dir = Path.home() / ".config" / "codeloom"
        self.profiles_dir = self.config_dir / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        self.current_profile: Optional[Profile] = None
        self._ensure_default_profile()
        self.load_profile("default")

    def _ensure_default_profile(self):
        """Create default profile if it doesn't exist."""
        default_path = self.profiles_dir / "default.json"
        if not default_path.exists():
            self._save_profile_to_file(DEFAULT_PROFILE)

    def _get_profile_path(self, name: str) -> Path:
        """Get the file path for a profile."""
        # Sanitize name for filesystem
        safe_name = "".join(c for c in name if c.isalnum() or c in "-_").lower()
        return self.profiles_dir / f"{safe_name}.json"

    def _save_profile_to_file(self, profile: Profile):
        """Save a profile to disk."""
        from datetime import datetime
        profile.updated_at = datetime.now().isoformat()
        if not profile.created_at:
            profile.created_at = profile.updated_at

        path = self._get_profile_path(profile.name)
        with open(path, "w") as f:
            json.dump(profile.to_dict(), f, indent=2)

    def load_profile(self, name: str) -> Optional[Profile]:
        """Load a profile by name."""
        path = self._get_profile_path(name)
        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = json.load(f)
                self.current_profile = Profile.from_dict(data)
                return self.current_profile
        except (json.JSONDecodeError, IOError):
            return None

    def save_profile(self) -> bool:
        """Save the current profile."""
        if not self.current_profile:
            return False
        self._save_profile_to_file(self.current_profile)
        return True

    def new_profile(self, name: str, copy_from: str = None) -> Profile:
        """Create a new profile, optionally copying from another."""
        if copy_from:
            source = self.load_profile(copy_from)
            if source:
                profile = Profile(
                    name=name,
                    system_prompt=source.system_prompt,
                    notes=source.notes.copy()
                )
            else:
                profile = Profile(name=name)
        else:
            profile = Profile(name=name)

        self._save_profile_to_file(profile)
        self.current_profile = profile
        return profile

    def delete_profile(self, name: str) -> bool:
        """Delete a profile (cannot delete 'default')."""
        if name == "default":
            return False

        path = self._get_profile_path(name)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_profiles(self) -> List[Dict]:
        """List all profiles with metadata."""
        profiles = []
        for path in self.profiles_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                    profiles.append({
                        "name": data.get("name", path.stem),
                        "system_prompt_preview": data.get("system_prompt", "")[:50],
                        "notes_count": len(data.get("notes", [])),
                        "updated_at": data.get("updated_at", "")
                    })
            except (json.JSONDecodeError, IOError):
                continue

        return sorted(profiles, key=lambda x: x["name"])

    def set_system_prompt(self, prompt: str) -> bool:
        """Set the system prompt for current profile."""
        if not self.current_profile:
            return False
        self.current_profile.system_prompt = prompt
        self.save_profile()
        return True

    def get_system_prompt(self) -> str:
        """Get the current system prompt."""
        if not self.current_profile:
            return ""
        return self.current_profile.system_prompt

    def add_note(self, note: str) -> bool:
        """Add a note to the current profile."""
        if not self.current_profile:
            return False
        self.current_profile.notes.append(note)
        self.save_profile()
        return True

    def remove_note(self, index: int) -> bool:
        """Remove a note by index (1-based)."""
        if not self.current_profile:
            return False
        idx = index - 1  # Convert to 0-based
        if 0 <= idx < len(self.current_profile.notes):
            self.current_profile.notes.pop(idx)
            self.save_profile()
            return True
        return False

    def list_notes(self) -> List[str]:
        """Get all notes for current profile."""
        if not self.current_profile:
            return []
        return self.current_profile.notes

    def clear_notes(self) -> bool:
        """Clear all notes from current profile."""
        if not self.current_profile:
            return False
        self.current_profile.notes = []
        self.save_profile()
        return True

    def get_context(self) -> str:
        """Get the full context (system prompt + notes) for AI."""
        if not self.current_profile:
            return ""

        parts = []

        if self.current_profile.system_prompt:
            parts.append(self.current_profile.system_prompt)

        if self.current_profile.notes:
            notes_text = "\n".join(f"- {note}" for note in self.current_profile.notes)
            parts.append(f"\nPersistent notes:\n{notes_text}")

        return "\n\n".join(parts)
