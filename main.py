"""Main application entrypoint for AI-ROI."""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI

from api.routes import router as api_router
from config.settings import Settings


def setup_logging(settings: Settings) -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    load_dotenv()
    settings = Settings.from_env()
    setup_logging(settings)

    app = FastAPI(title=settings.app_name)
    app.include_router(api_router, prefix="/v1")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
