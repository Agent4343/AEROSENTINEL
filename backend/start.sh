#!/bin/sh
set -e

echo "=== AeroSentinel Backend Starting ==="
echo "PORT=${PORT:-8000}"
echo "DATABASE_URL is set: $([ -n "$DATABASE_URL" ] && echo 'yes' || echo 'NO - this will cause issues!')"
echo "MQTT_ENABLED=${MQTT_ENABLED:-true}"
echo "REDIS_ENABLED=${REDIS_ENABLED:-true}"
echo "========================================="

# Test Python can import the app
python -c "from app.main import app; print('App import OK')" || {
    echo "FATAL: Failed to import app. Running diagnostics..."
    python -c "from app.config import settings; print('Config OK, DB URL prefix:', settings.database_url[:30])" || echo 'Config FAILED'
    python -c "from app.db.database import engine; print('Database engine OK')" || echo 'Database engine FAILED'
    python -c "from app.models import Incident, Drone, Mission, Detection, Alert; print('Models OK')" || echo 'Models FAILED'
    python -c "from app.api.routes import router; print('Routes OK')" || echo 'Routes FAILED'
    exit 1
}

exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --loop uvloop
