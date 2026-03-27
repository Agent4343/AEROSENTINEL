from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # --- Startup ---
    # Verify database connection
    async with engine.connect() as conn:
        await conn.execute(
            __import__("sqlalchemy").text("SELECT 1")
        )

    # Connect to Redis
    app.state.redis = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    await app.state.redis.ping()

    # Connect to MQTT broker
    from app.services.mqtt_service import MQTTService

    app.state.mqtt = MQTTService(
        broker_host=settings.mqtt_broker_host,
        broker_port=settings.mqtt_broker_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
    )
    await app.state.mqtt.connect()

    yield

    # --- Shutdown ---
    await app.state.mqtt.disconnect()
    await app.state.redis.aclose()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount route modules
from app.api.routes import router as api_router  # noqa: E402

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.app_name}
