import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db.database import engine, Base

logger = logging.getLogger("aerosentinel")

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level if hasattr(settings, "log_level") else "INFO"),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    # --- Startup ---
    # Database: try to connect with retries
    db_ok = False
    import asyncio
    # Import all models so Base.metadata has them registered
    from app.models import Incident, Drone, Mission, Detection, Alert  # noqa: F401

    for attempt in range(1, 6):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_ok = True
            logger.info("Database connected")
            break
        except Exception as exc:
            logger.warning("Database connection attempt %d/5 failed: %s", attempt, exc)
            if attempt < 5:
                await asyncio.sleep(2 * attempt)

    if not db_ok:
        logger.error("Database unavailable after 5 attempts \u2014 starting without DB")
    else:
        # Auto-create tables if they don't exist (for Railway fresh deploys)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created")

    # Connect to Redis (optional \u2014 degrades gracefully)
    if settings.redis_enabled:
        try:
            application.state.redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            await application.state.redis.ping()
            logger.info("Redis connected")
        except Exception:
            logger.warning("Redis unavailable \u2014 real-time features disabled")
            application.state.redis = None
    else:
        application.state.redis = None

    # Connect to MQTT broker (optional \u2014 degrades gracefully)
    if settings.mqtt_enabled:
        try:
            from app.services.mqtt_service import MQTTService

            application.state.mqtt = MQTTService(
                broker_host=settings.mqtt_broker_host,
                broker_port=settings.mqtt_broker_port,
                username=settings.mqtt_username,
                password=settings.mqtt_password,
            )
            await application.state.mqtt.connect()
            logger.info("MQTT connected")
        except Exception:
            logger.warning("MQTT unavailable \u2014 drone communication disabled")
            application.state.mqtt = None
    else:
        application.state.mqtt = None

    application.state.db_ok = db_ok

    yield

    # --- Shutdown ---
    if getattr(application.state, "mqtt", None) is not None:
        await application.state.mqtt.disconnect()
    if getattr(application.state, "redis", None) is not None:
        await application.state.redis.aclose()
    await engine.dispose()


fastapi_app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount route modules
from app.api.routes import router as api_router  # noqa: E402

fastapi_app.include_router(api_router, prefix="/api/v1")


@fastapi_app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "database": getattr(fastapi_app.state, "db_ok", False),
        "redis": getattr(fastapi_app.state, "redis", None) is not None,
        "mqtt": getattr(fastapi_app.state, "mqtt", None) is not None,
    }


# Alias for uvicorn: `uvicorn app.main:app`
app = fastapi_app
