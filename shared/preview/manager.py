"""Preview process state management module.

This module provides a state machine for managing preview processes with automatic
timeout cleanup and zombie process detection.
"""

import json
import os
import signal
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Literal
from dataclasses import dataclass, asdict


# Preview states
PreviewState = Literal["new", "preview", "timeout", "stopped", "destroyed"]

# State transitions:
# new → preview: when preview starts
# preview → timeout: after 30min of inactivity
# preview → stopped: when user clicks stop
# timeout → destroyed: after cleanup
# stopped → preview: when user clicks preview again
# any → destroyed: when project/session deleted


@dataclass
class PreviewRecord:
    """Record for a single preview process."""
    project_id: str                    # Session/project ID
    project_path: str                 # Absolute path to generated project
    pid: int                            # Process ID
    port: int                           # Port number
    state: PreviewState                # Current state
    created_at: str                     # ISO timestamp when record created
    started_at: Optional[str] = None   # ISO timestamp when process started
    stopped_at: Optional[str] = None   # ISO timestamp when process stopped
    timeout_at: Optional[str] = None  # ISO timestamp when will timeout
    last_activity: Optional[str] = None  # ISO timestamp of last user interaction

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PreviewRecord":
        """Create from dict."""
        return cls(**data)


class PreviewManager:
    """Manages preview process lifecycle with automatic cleanup."""

    def __init__(self, storage_path: str, timeout_minutes: int = 30):
        """Initialize the preview manager.

        Args:
            storage_path: Path to the JSON file storing preview records
            timeout_minutes: Minutes before a preview is considered timed out
        """
        self.storage_path = Path(storage_path)
        self.timeout_minutes = timeout_minutes
        self.timeout_delta = timedelta(minutes=timeout_minutes)

        # Ensure storage directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing records
        self._records: Dict[str, PreviewRecord] = {}
        self._load()

        # Cleanup thread control
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()

    def _load(self) -> None:
        """Load records from JSON file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    for record_id, record_data in data.items():
                        self._records[record_id] = PreviewRecord.from_dict(record_data)
            except (json.JSONDecodeError, KeyError):
                # File corrupted, start fresh
                self._records = {}

    def _save(self) -> None:
        """Save records to JSON file."""
        cleaned_records: Dict[str, PreviewRecord] = self._cleanup_records()
        data = {
            record_id: record.to_dict()
            for record_id, record in cleaned_records.items()
        }
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _cleanup_records(self) -> Dict[str, PreviewRecord]:
        """Remove records for destroyed projects older than 1 hour."""
        cutoff = datetime.now() - timedelta(hours=1)
        return {
            rid: r
            for rid, r in self._records.items()
            if r.state != "destroyed" or
            (r.state == "destroyed" and
             datetime.fromisoformat(r.stopped_at or r.created_at) >= cutoff)
        }

    def start_preview(
        self,
        project_id: str,
        project_path: str,
        port: int,
        process: subprocess.Popen
    ) -> PreviewRecord:
        """Start a new preview process.

        Args:
            project_id: Session/project ID
            project_path: Path to generated project
            port: Port number
            process: Subprocess.Popen object

        Returns:
            PreviewRecord: The created record
        """
        now = datetime.now().isoformat()
        timeout_at = (datetime.now() + self.timeout_delta).isoformat()

        record = PreviewRecord(
            project_id=project_id,
            project_path=project_path,
            pid=process.pid,
            port=port,
            state="preview",
            created_at=now,
            started_at=now,
            timeout_at=timeout_at,
            last_activity=now
        )

        self._records[project_id] = record
        self._save()
        return record

    def stop_preview(self, project_id: str) -> None:
        """Stop a preview process by ID.

        Args:
            project_id: Project/session ID
        """
        if project_id not in self._records:
            return

        record = self._records[project_id]
        if record.state in ["preview", "timeout"]:
            # Kill the process
            try:
                os.kill(record.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass  # Process already dead

        record.state = "stopped"
        record.stopped_at = datetime.now().isoformat()
        self._save()

    def get_record(self, project_id: str) -> Optional[PreviewRecord]:
        """Get preview record by project ID.

        Args:
            project_id: Project/session ID

        Returns:
            PreviewRecord if exists, else None
        """
        return self._records.get(project_id)

    def get_all_records(self) -> Dict[str, PreviewRecord]:
        """Get all preview records."""
        return self._records.copy()

    def destroy_record(self, project_id: str) -> None:
        """Mark a preview record as destroyed (kept for history, won't be cleaned up).

        Args:
            project_id: Project/session ID
        """
        if project_id in self._records:
            self._records[project_id].state = "destroyed"
            if not self._records[project_id].stopped_at:
                self._records[project_id].stopped_at = datetime.now().isoformat()
            self._save()

    def delete_record(self, project_id: str) -> None:
        """Delete a preview record permanently.

        Args:
            project_id: Project_id
        """
        if project_id in self._records:
            del self._records[project_id]
            self._save()

    def cleanup_timeout_processes(self) -> int:
        """Find and clean up timed-out preview processes.

        Returns:
            Number of processes cleaned up
        """
        now = datetime.now()
        cleaned = 0

        for record in self._records.values():
            if record.state not in ["preview", "timeout"]:
                continue

            # Check if process is still alive
            try:
                os.kill(record.pid, 0)  # Check process existence
            except ProcessLookupError:
                # Process dead, mark as stopped
                record.state = "stopped"
                record.stopped_at = now.isoformat()
                self._save()
                continue

            # Check timeout
            timeout_at = record.timeout_at
            if timeout_at and now >= datetime.fromisoformat(timeout_at):
                # Timeout reached
                try:
                    os.kill(record.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass  # Already dead

                record.state = "timeout"
                record.stopped_at = now.isoformat()
                cleaned += 1

        if cleaned > 0:
            self._save()

        return cleaned

    def cleanup_zombie_processes(self) -> int:
        """Find and clean up processes marked as 'preview' but actually dead.

        Returns:
            Number of zombie processes cleaned
        """
        now = datetime.now()
        cleaned = 0

        for record in self._records.values():
            if record.state != "preview":
                continue

            # Check if process is actually dead
            try:
                os.kill(record.pid, 0)
            except ProcessLookupError:
                # Process is dead
                record.state = "stopped"
                record.stopped_at = now.isoformat()
                cleaned += 1

        if cleaned > 0:
            self._save()

        return cleaned

    def start_cleanup_thread(
        self,
        interval_seconds: int = 300  # 5 minutes
    ) -> threading.Thread:
        """Start background cleanup thread.

        Args:
            interval_seconds: Check interval in seconds

        Returns:
            The cleanup thread
        """
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return self._cleanup_thread

        def cleanup_loop():
            while not self._stop_cleanup.is_set():
                try:
                    # Clean timeouts
                    timeout_cleaned = self.cleanup_timeout_processes()
                    # Clean zombies
                    zombie_cleaned = self.cleanup_zombie_processes()

                    if timeout_cleaned > 0 or zombie_cleaned > 0:
                        print(f"[PreviewManager] Cleaned {timeout_cleaned} timed out, {zombie_cleaned} zombie processes")
                except Exception as e:
                    print(f"[PreviewManager] Cleanup error: {e}")

                # Wait for next interval or stop signal
                self._stop_cleanup.wait(interval_seconds)

        self._cleanup_thread = threading.Thread(
            target=cleanup_loop,
            daemon=True,
            name="preview_cleanup"
        )
        self._cleanup_thread.start()
        return self._cleanup_thread

    def stop_cleanup_thread(self) -> None:
        """Stop the cleanup thread gracefully."""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._stop_cleanup.set()
            self._cleanup_thread.join(timeout=5)
            self._cleanup_thread = None


# Global singleton instance
_preview_manager: Optional[PreviewManager] = None


def get_preview_manager() -> PreviewManager:
    """Get or create the global preview manager singleton."""
    global _preview_manager
    if _preview_manager is None:
        # Import settings to get config dir
        import sys
        from pathlib import Path as PathLib
        # Add project root to path if not already
        project_root = PathLib(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from backend.core.config import settings

        storage_path = settings.PREVIEW_STATE_FILE
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        _preview_manager = PreviewManager(
            storage_path=str(storage_path),
            timeout_minutes=30
        )
    return _preview_manager


def reset_preview_manager() -> None:
    """Reset the global preview manager (for testing)."""
    global _preview_manager
    _preview_manager = None
