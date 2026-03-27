from pydantic_settings import BaseSettings
from pydantic import Field, model_validator


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Application
    app_name: str = "AeroSentinel"
    app_version: str = "0.1.0"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    allowed_origins: list[str] = ["http://localhost:3000"]
    port: int = Field(default=8000, alias="PORT")

    # Database (PostgreSQL)
    # Railway provides DATABASE_URL as postgres:// — we convert to asyncpg
    database_url: str = Field(
        default="postgresql+asyncpg://aerosentinel:aerosentinel@localhost:5432/aerosentinel",
        alias="DATABASE_URL",
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Redis (Railway provides REDIS_URL)
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )
    redis_enabled: bool = True

    # MQTT (EMQX) — optional, can be disabled for Railway deployments without MQTT
    mqtt_enabled: bool = True
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_broker_ws_port: int = 8083
    mqtt_username: str = "aerosentinel"
    mqtt_password: str = "aerosentinel"
    mqtt_client_id: str = "aerosentinel-backend"

    # S3-compatible object storage (MinIO, AWS S3, Cloudflare R2)
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "aerosentinel"
    s3_region: str = "us-east-1"

    # AI / ONNX Runtime model paths
    ai_detection_model_path: str = "models/detection/yolov8_emergency.onnx"
    ai_confidence_threshold: float = 0.45
    ai_use_gpu: bool = False

    # DJI Cloud API
    dji_app_id: str = ""
    dji_app_key: str = ""
    dji_app_license: str = ""

    @model_validator(mode="after")
    def _fix_database_url(self) -> "Settings":
        """Railway gives postgres:// URLs — convert to asyncpg format."""
        url = self.database_url
        if url.startswith("postgres://"):
            self.database_url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            self.database_url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self


settings = Settings()
