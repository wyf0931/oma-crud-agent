"""Process-wide dependencies shared by the API routes."""

from oma_info_system.config import settings
from oma_info_system.platform.preview import PreviewManager, get_preview_manager
from oma_info_system.platform.sessions import SessionManager

session_manager = SessionManager(settings.DATABASE_FILE)
preview_manager: PreviewManager = get_preview_manager()
