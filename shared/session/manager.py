"""Session manager backed by TinyDB."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from tinydb import Query

from shared.storage.database import get_database


class SessionManager:
    """Manage session data in the TinyDB sessions table."""

    def __init__(self, database_path: Path):
        self.database = get_database(database_path)
        self.table = self.database.table("sessions")

    def create(self, user_input: str, output_dir: str, mode: str = "yolo") -> str:
        session_id = str(uuid.uuid4())
        self.table.insert({
            "id": session_id,
            "created_at": datetime.now().isoformat(),
            "finished_at": None,
            "user_input": user_input,
            "mode": mode,
            "output_dir": output_dir,
            "status": "pending",
            "current_step": "",
            "step_history": [],
            "step_details": {},
            "project_name": None,
            "business_domain": None,
            "modules": None,
            "fields": None,
            "project_config": None,
            "project_path": None,
            "review_issues": [],
            "review_fixes": [],
            "test_errors": None,
            "retry_count": 0,
            "max_retries": 3,
            "pending_approval": None,
            "approval_required": False,
            "approval_response": None,
            "result": None,
            "error": None,
        })
        return session_id

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        record = self.table.get(Query().id == session_id)
        return dict(record) if record else None

    def update(self, session_id: str, data: Dict[str, Any]) -> None:
        self.table.update(data, Query().id == session_id)

    def list(self, limit: int = 50) -> List[Dict[str, Any]]:
        sessions = [dict(record) for record in self.table.all()]
        sessions.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return sessions[:limit]

    def delete(self, session_id: str) -> bool:
        removed = self.table.remove(Query().id == session_id)
        return bool(removed)
