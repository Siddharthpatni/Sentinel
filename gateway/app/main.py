"""Sentinel Gateway — FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.models import Base
from app.db.seed import seed_default_project
from app.db.session import AsyncSessionLocal, async_engine
from app.routes import anthropic_compat, openai_compat, traces, verifications


def configure_logging() -> None:
    """Set up structured logging via structlog."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(message)s",
    )
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Application lifecycle: create tables and seed on startup."""
    configure_logging()
    logger = logging.getLogger(__name__)

    # Create tables (for dev/local — production uses Alembic)
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")

    # Seed default project
    async with AsyncSessionLocal() as session:
        await seed_default_project(session)

    logger.info("Sentinel Gateway started on %s:%d", settings.gateway_host, settings.gateway_port)
    yield

    # Shutdown
    await async_engine.dispose()
    logger.info("Sentinel Gateway shutdown complete")


app = FastAPI(
    title="Sentinel Gateway",
    description="LLM observability proxy — intercepts, logs, and forwards API calls.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the dashboard to call the gateway
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(openai_compat.router)
app.include_router(anthropic_compat.router)
app.include_router(traces.router)
app.include_router(verifications.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok", "service": "sentinel-gateway"}
