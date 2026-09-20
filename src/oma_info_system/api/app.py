"""FastAPI application factory - the composition root for the API layer."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from oma_info_system.api.routes import health, sessions
from oma_info_system.api.routes import settings as settings_api
from oma_info_system.config import settings
from oma_info_system.platform.preview import get_preview_manager


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )

    # Preview manager startup
    preview_manager = get_preview_manager()

    @app.on_event("startup")
    async def startup():
        """Run startup tasks."""
        # Clean up any zombie processes from previous runs
        zombie_count = preview_manager.cleanup_zombie_processes()
        if zombie_count > 0:
            print(f"[Startup] Cleaned up {zombie_count} zombie preview processes")

        # Start periodic cleanup thread
        preview_manager.start_cleanup_thread()
        print("[Startup] Preview cleanup thread started")

    @app.on_event("shutdown")
    async def shutdown():
        """Run shutdown tasks."""
        # Stop cleanup thread
        preview_manager.stop_cleanup_thread()
        print("[Shutdown] Preview cleanup thread stopped")

    # Web assets ship inside the package so they resolve from an installed wheel.
    package_dir = Path(__file__).resolve().parent.parent

    static_dir = package_dir / "web" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    template_dir = package_dir / "web" / "templates"
    app.state.template_dir = template_dir

    # Register routes
    app.include_router(sessions.router, prefix="/api")
    app.include_router(health.router, prefix="/api")
    app.include_router(settings_api.router, prefix="/api")

    # HTML routes - serve static HTML files
    from fastapi.responses import HTMLResponse

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Home page."""
        template_file = app.state.template_dir / "index.html"
        if template_file.exists():
            html_content = template_file.read_text()
            return HTMLResponse(content=html_content)
        return HTMLResponse("<h1>Info System Agent</h1><p>Template not found</p>")

    @app.get("/session/{session_id}", response_class=HTMLResponse)
    async def session_page(session_id: str):
        """Session page."""
        template_file = app.state.template_dir / "session.html"
        if template_file.exists():
            html_content = template_file.read_text()
            # Replace session_id placeholder
            html_content = html_content.replace("{session_id}", session_id)
            return HTMLResponse(content=html_content)
        return HTMLResponse(f"<h1>Session {session_id} not found</h1>")

    @app.get("/magic", response_class=HTMLResponse)
    async def magic_index():
        """Standalone magic-mode home experience."""
        template_file = app.state.template_dir / "magic.html"
        if template_file.exists():
            return HTMLResponse(content=template_file.read_text())
        return HTMLResponse("<h1>Magic template not found</h1>", status_code=404)

    @app.get("/magic/session/{session_id}", response_class=HTMLResponse)
    async def magic_session_page(session_id: str):
        """Standalone magic-mode workflow experience."""
        template_file = app.state.template_dir / "magic_session.html"
        if template_file.exists():
            return HTMLResponse(content=template_file.read_text().replace("{session_id}", session_id))
        return HTMLResponse("<h1>Magic session template not found</h1>", status_code=404)

    @app.get("/api", response_class=HTMLResponse)
    async def api_docs():
        """API docs placeholder."""
        return HTMLResponse("""
        <html>
        <head><title>Info System Agent API</title></head>
        <body>
            <h1>Info System Agent API</h1>
            <ul>
                <li><a href="/api/health">Health Check</a></li>
                <li><a href="/api/config">Configuration</a></li>
                <li><a href="/api/sessions">Sessions</a></li>
            </ul>
        </body>
        </html>
        """)

    return app


# Expose app for ASGI servers: uvicorn oma_info_system.api.app:app
app = create_app()
