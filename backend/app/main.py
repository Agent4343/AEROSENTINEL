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
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # --- Startup ---
    # Database: try to connect with retries
    db_ok = False
    import asyncio

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
        logger.error("Database unavailable after 5 attempts — starting without DB")
    else:
        # Auto-create tables if they don't exist (for Railway fresh deploys)
        # Import all models so Base.metadata has them registered
        import app.models  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created")

    # Connect to Redis (optional — degrades gracefully)
    if settings.redis_enabled:
        try:
            app.state.redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            await app.state.redis.ping()
            logger.info("Redis connected")
        except Exception:
            logger.warning("Redis unavailable — real-time features disabled")
            app.state.redis = None
    else:
        app.state.redis = None

    # Connect to MQTT broker (optional — degrades gracefully)
    if settings.mqtt_enabled:
        try:
            from app.services.mqtt_service import MQTTService

            app.state.mqtt = MQTTService(
                broker_host=settings.mqtt_broker_host,
                broker_port=settings.mqtt_broker_port,
                username=settings.mqtt_username,
                password=settings.mqtt_password,
            )
            await app.state.mqtt.connect()
            logger.info("MQTT connected")
        except Exception:
            logger.warning("MQTT unavailable — drone communication disabled")
            app.state.mqtt = None
    else:
        app.state.mqtt = None

    app.state.db_ok = db_ok

    yield

    # --- Shutdown ---
    if getattr(app.state, "mqtt", None) is not None:
        await app.state.mqtt.disconnect()
    if getattr(app.state, "redis", None) is not None:
        await app.state.redis.aclose()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount route modules
from app.api.routes import router as api_router  # noqa: E402

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "database": getattr(app.state, "db_ok", False),
        "redis": getattr(app.state, "redis", None) is not None,
        "mqtt": getattr(app.state, "mqtt", None) is not None,
    }
