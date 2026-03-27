from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Application
    app_name: str = "AeroSentinel"
    app_version: str = "0.1.0"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    allowed_origins: list[str] = ["http://localhost:3000"]

    # Database (PostgreSQL + TimescaleDB)
    database_url: str = Field(
        default="postgresql+asyncpg://aerosentinel:aerosentinel@localhost:5432/aerosentinel",
        alias="DATABASE_URL",
    )
    db_pool_size: int = 20
    db_max_overflow: int = 10

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )

    # MQTT (EMQX)
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_broker_ws_port: int = 8083
    mqtt_username: str = "aerosentinel"
    mqtt_password: str = "aerosentinel"
    mqtt_client_id: str = "aerosentinel-backend"

    # S3 / MinIO object storage
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "aerosentinel"
    s3_region: str = "us-east-1"

    # AI / ONNX Runtime model paths
    ai_detection_model_path: str = "models/detection/yolov8_emergency.onnx"
    ai_classification_model_path: str = "models/classification/incident_classifier.onnx"
    ai_segmentation_model_path: str = "models/segmentation/damage_segmentation.onnx"
    ai_confidence_threshold: float = 0.45
    ai_use_gpu: bool = False

    # DJI Cloud API
    dji_app_id: str = ""
    dji_app_key: str = ""
    dji_app_license: str = ""


settings = Settings()
