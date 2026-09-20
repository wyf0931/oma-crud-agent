"""Request models for the session API."""

from typing import Literal

from pydantic import BaseModel


class SessionCreate(BaseModel):
    """Request model for creating a session."""

    user_input: str
    mode: Literal["yolo", "hitl"] = "yolo"
    output_dir: str | None = None


class SessionApproval(BaseModel):
    """Request model for approving a step."""

    approval_response: str
