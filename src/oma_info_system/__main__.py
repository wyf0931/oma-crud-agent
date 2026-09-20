"""CLI entry point for the Info System Agent server."""

import sys

import uvicorn

from oma_info_system.api.app import create_app
from oma_info_system.config import settings


def main() -> int:
    """Validate configuration and run the API server."""
    settings.ensure_directories()

    missing = [
        name
        for name, value in {
            "OPENAI_API_KEY": settings.OPENAI_API_KEY,
            "OPENAI_BASE_URL": settings.OPENAI_BASE_URL,
            "OPENAI_MODEL": settings.OPENAI_MODEL,
        }.items()
        if not value
    ]
    if missing:
        print(f"Missing required configuration: {', '.join(missing)}")
        print("Set it in a .env file or the process environment.")
        return 1

    print(
        "\n"
        "    Info System Agent\n"
        f"      Version:   {settings.APP_VERSION}\n"
        f"      LLM model: {settings.OPENAI_MODEL}\n"
        f"      Server:    http://{settings.HOST}:{settings.PORT}\n"
    )

    uvicorn.run(create_app(), host=settings.HOST, port=settings.PORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
