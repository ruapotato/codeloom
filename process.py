"""
process.py - Background Process Management

Manages long-running background processes that persist across Claude calls.
Processes are tracked with output captured for later review.
"""

import os
import json
import subprocess
import signal
import threading
import time
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
from pathlib import Path
from datetime import datetime


@dataclass
class ProcessInfo:
    """Information about a tracked process."""
    id: str
    pid: int
    command: str
    started_at: str
    status: str  # running, completed, failed, killed
    exit_code: Optional[int] = None
    cwd: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProcessInfo":
        return cls(
            id=data.get("id", ""),
            pid=data.get("pid", 0),
            command=data.get("command", ""),
            started_at=data.get("started_at", ""),
            status=data.get("status", "unknown"),
            exit_code=data.get("exit_code"),
            cwd=data.get("cwd", "")
        )


class ProcessManager:
    """Manages background processes with persistent tracking."""

    def __init__(self):
        self.config_dir = Path.home() / ".config" / "codeloom"
        self.process_dir = self.config_dir / "processes"
        self.process_dir.mkdir(parents=True, exist_ok=True)

        self.processes: Dict[str, ProcessInfo] = {}
        self._output_threads: Dict[str, threading.Thread] = {}
        self._load_processes()
        self._check_running()

    def _load_processes(self):
        """Load process info from disk."""
        index_file = self.process_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file) as f:
                    data = json.load(f)
                    for proc_data in data.get("processes", []):
                        proc = ProcessInfo.from_dict(proc_data)
                        self.processes[proc.id] = proc
            except (json.JSONDecodeError, IOError):
                pass

    def _save_processes(self):
        """Save process info to disk."""
        index_file = self.process_dir / "index.json"
        data = {
            "processes": [p.to_dict() for p in self.processes.values()]
        }
        with open(index_file, "w") as f:
            json.dump(data, f, indent=2)

    def _check_running(self):
        """Check if tracked processes are still running."""
        for proc_id, proc in list(self.processes.items()):
            if proc.status == "running":
                if not self._is_running(proc.pid):
                    # Process has finished
                    proc.status = "completed"
                    # Try to get exit code from output file
                    self._save_processes()

    def _is_running(self, pid: int) -> bool:
        """Check if a process is still running."""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def _generate_id(self) -> str:
        """Generate a short unique ID for a process."""
        import random
        import string
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    def _get_output_file(self, proc_id: str) -> Path:
        """Get the output file path for a process."""
        return self.process_dir / f"{proc_id}.log"

    def run(self, command: str, name: Optional[str] = None) -> ProcessInfo:
        """
        Run a command in the background.

        Args:
            command: The shell command to run
            name: Optional name/ID for the process

        Returns:
            ProcessInfo for the started process
        """
        proc_id = name if name else self._generate_id()

        # Ensure unique ID
        if proc_id in self.processes:
            base_id = proc_id
            counter = 1
            while proc_id in self.processes:
                proc_id = f"{base_id}_{counter}"
                counter += 1

        output_file = self._get_output_file(proc_id)
        cwd = os.getcwd()

        # Start the process
        with open(output_file, "w") as f:
            f.write(f"$ {command}\n")
            f.write(f"Started: {datetime.now().isoformat()}\n")
            f.write(f"CWD: {cwd}\n")
            f.write("-" * 40 + "\n")

        # Run with output redirection
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            preexec_fn=os.setsid  # New process group
        )

        proc_info = ProcessInfo(
            id=proc_id,
            pid=process.pid,
            command=command,
            started_at=datetime.now().isoformat(),
            status="running",
            cwd=cwd
        )

        self.processes[proc_id] = proc_info
        self._save_processes()

        # Start output capture thread
        thread = threading.Thread(
            target=self._capture_output,
            args=(proc_id, process, output_file),
            daemon=True
        )
        thread.start()
        self._output_threads[proc_id] = thread

        return proc_info

    def _capture_output(self, proc_id: str, process: subprocess.Popen, output_file: Path):
        """Capture process output to file."""
        try:
            with open(output_file, "a") as f:
                for line in process.stdout:
                    f.write(line)
                    f.flush()

            process.wait()

            # Update status
            if proc_id in self.processes:
                proc = self.processes[proc_id]
                proc.exit_code = process.returncode
                proc.status = "completed" if process.returncode == 0 else "failed"
                self._save_processes()

                # Write exit info
                with open(output_file, "a") as f:
                    f.write("-" * 40 + "\n")
                    f.write(f"Exited: {datetime.now().isoformat()}\n")
                    f.write(f"Exit code: {process.returncode}\n")

        except Exception as e:
            with open(output_file, "a") as f:
                f.write(f"\nError capturing output: {e}\n")

    def get_output(self, proc_id: str, tail: int = 50) -> Optional[str]:
        """
        Get the output of a process.

        Args:
            proc_id: Process ID
            tail: Number of lines from end (0 for all)

        Returns:
            Output string or None if not found
        """
        output_file = self._get_output_file(proc_id)
        if not output_file.exists():
            return None

        try:
            with open(output_file) as f:
                lines = f.readlines()
                if tail > 0 and len(lines) > tail:
                    return "".join(lines[-tail:])
                return "".join(lines)
        except IOError:
            return None

    def get_status(self, proc_id: str) -> Optional[ProcessInfo]:
        """Get the status of a process."""
        if proc_id not in self.processes:
            return None

        proc = self.processes[proc_id]

        # Update status if needed
        if proc.status == "running":
            if not self._is_running(proc.pid):
                proc.status = "completed"
                self._save_processes()

        return proc

    def kill(self, proc_id: str) -> bool:
        """
        Kill a running process.

        Returns:
            True if killed, False if not found or already dead
        """
        if proc_id not in self.processes:
            return False

        proc = self.processes[proc_id]

        if proc.status != "running":
            return False

        try:
            # Kill the entire process group
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.status = "killed"
            self._save_processes()

            # Write to output
            output_file = self._get_output_file(proc_id)
            with open(output_file, "a") as f:
                f.write("-" * 40 + "\n")
                f.write(f"Killed: {datetime.now().isoformat()}\n")

            return True
        except (ProcessLookupError, PermissionError):
            proc.status = "completed"
            self._save_processes()
            return False

    def list_processes(self, include_finished: bool = True) -> List[ProcessInfo]:
        """
        List all tracked processes.

        Args:
            include_finished: Include completed/failed/killed processes

        Returns:
            List of ProcessInfo
        """
        self._check_running()

        if include_finished:
            return list(self.processes.values())
        else:
            return [p for p in self.processes.values() if p.status == "running"]

    def cleanup(self, keep_running: bool = True) -> int:
        """
        Remove finished processes from tracking.

        Args:
            keep_running: Keep running processes

        Returns:
            Number of processes removed
        """
        to_remove = []
        for proc_id, proc in self.processes.items():
            if proc.status != "running" or not keep_running:
                to_remove.append(proc_id)

        for proc_id in to_remove:
            del self.processes[proc_id]
            # Optionally remove output file
            output_file = self._get_output_file(proc_id)
            if output_file.exists():
                output_file.unlink()

        self._save_processes()
        return len(to_remove)

    def get_running_summary(self) -> str:
        """Get a summary of running processes for AI context."""
        running = [p for p in self.processes.values() if p.status == "running"]
        if not running:
            return ""

        lines = ["Background processes running:"]
        for proc in running:
            lines.append(f"  [{proc.id}] {proc.command[:50]}")

        return "\n".join(lines)
