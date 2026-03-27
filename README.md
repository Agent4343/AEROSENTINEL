# AeroSentinel

**AI-Powered Emergency Response Drone Coordination Platform**

DJI Enterprise Drone Onboard AI Challenge 2026 | Cloud Algorithm Track | Industry: Emergency Response

---

## Overview

AeroSentinel is a cloud-based AI platform that transforms DJI enterprise drone fleets into coordinated emergency response systems. It combines DJI Cloud API integration with server-side computer vision and intelligent mission orchestration to enable faster detection, assessment, and response to emergency incidents.

### Target Use Cases
- Wildfire perimeter mapping
- Flood extent assessment
- Search-and-rescue operations
- Structural damage inspection after natural disasters
- Hazmat incident perimeter monitoring

## Architecture

```
Edge Layer          Protocol Layer       Cloud Backend           Operator UI
-----------         --------------       -------------           -----------
DJI Dock 3          MQTT (EMQX)         Mission Engine          React Dashboard
Matrice 4D/4TD      HTTPS                AI Pipeline             Mapbox GL Map
Matrice 4E/4T       WebSocket            Alert Engine            Real-time Panels
DJI Pilot 2         RTMP/WebRTC          Data Stores             Fleet Management
```

### Core Services

| Service | Description |
|---------|-------------|
| **Mission Engine** | Generates search patterns (expanding square, parallel track, sector) as DJI WPML waylines, dispatches via MQTT |
| **AI Pipeline** | YOLOv8 ONNX inference with geo-referencing, supports real-time frame processing and batch analysis |
| **Alert Engine** | Configurable triage rules, spatiotemporal deduplication, severity escalation, automated dispatch triggers |
| **Telemetry Service** | Ingests DJI OSD telemetry via MQTT, maintains in-memory cache, publishes to Redis for WebSocket fan-out |
| **MQTT Service** | Full DJI Cloud API MQTT integration with auto-reconnect, topic routing, and command publishing |

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend API | Python / FastAPI (async) |
| MQTT Broker | EMQX 5.x |
| AI Inference | ONNX Runtime (YOLOv8) |
| Database | PostgreSQL + TimescaleDB |
| Cache / Pub-Sub | Redis 7.x |
| Object Storage | MinIO (S3-compatible) |
| Frontend | React 18 + Mapbox GL JS + Tailwind CSS |
| Deployment | Docker Compose |

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Mapbox access token (for the map UI)

### Setup

```bash
# Clone the repository
git clone https://github.com/agent4343/aerosentinel.git
cd aerosentinel

# Copy environment configuration
cp .env.example .env
# Edit .env with your settings (Mapbox token, passwords, etc.)

# Start all services
docker compose up -d

# The services will be available at:
# - Frontend:        http://localhost:3000
# - Backend API:     http://localhost:8000
# - API Docs:        http://localhost:8000/docs
# - EMQX Dashboard:  http://localhost:18083
# - MinIO Console:   http://localhost:9001
```

### Development Setup

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm start
```

## API Endpoints

### Incidents
- `POST /api/v1/incidents` - Create incident
- `GET /api/v1/incidents` - List incidents (filter by status, type)
- `GET /api/v1/incidents/{id}` - Get incident details
- `PUT /api/v1/incidents/{id}` - Update incident
- `DELETE /api/v1/incidents/{id}` - Delete incident

### Drones
- `GET /api/v1/drones` - List fleet
- `GET /api/v1/drones/{serial}` - Drone detail + latest telemetry
- `POST /api/v1/drones/{serial}/command` - Send command

### Missions
- `POST /api/v1/missions` - Create mission
- `GET /api/v1/missions` - List missions
- `POST /api/v1/missions/{id}/execute` - Start mission
- `POST /api/v1/missions/{id}/pause` - Pause mission
- `POST /api/v1/missions/{id}/resume` - Resume mission

### Detections
- `GET /api/v1/detections` - List detections (filter by mission, category, severity)
- `GET /api/v1/detections/stats` - Aggregated statistics

### Alerts
- `GET /api/v1/alerts` - List alerts
- `GET /api/v1/alerts/active` - Unacknowledged alerts
- `POST /api/v1/alerts/{id}/acknowledge` - Acknowledge alert

### WebSocket
- `ws://localhost:8000/ws/live` - Real-time telemetry, detections, and alerts

## Project Structure

```
aerosentinel/
├── .env.example                    # Environment configuration template
├── docker-compose.yml              # Full stack orchestration
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini                 # Database migration config
│   ├── alembic/env.py              # Async Alembic setup
│   └── app/
│       ├── main.py                 # FastAPI application entry point
│       ├── config.py               # Pydantic settings
│       ├── db/database.py          # SQLAlchemy async engine
│       ├── models/                 # SQLAlchemy ORM models
│       │   ├── incident.py         # Incident with type/status/severity enums
│       │   ├── drone.py            # Drone + DroneTelemetry (TimescaleDB)
│       │   ├── mission.py          # Mission with wayline data (JSONB)
│       │   ├── detection.py        # AI detection with geo-coordinates
│       │   └── alert.py            # Triage alerts with acknowledgement
│       ├── api/routes/             # FastAPI route modules
│       │   ├── incidents.py        # Incident CRUD
│       │   ├── drones.py           # Fleet management
│       │   ├── missions.py         # Mission lifecycle
│       │   ├── detections.py       # Detection queries + stats
│       │   ├── alerts.py           # Alert management
│       │   └── websocket.py        # Real-time WebSocket feed
│       ├── services/               # Business logic services
│       │   ├── mqtt_service.py     # DJI Cloud API MQTT client
│       │   ├── mission_engine.py   # Search patterns + WPML dispatch
│       │   ├── ai_pipeline.py      # ONNX YOLOv8 inference
│       │   ├── alert_engine.py     # Triage rules + deduplication
│       │   └── telemetry_service.py # OSD ingestion + Redis fan-out
│       └── core/                   # Shared utilities
│           ├── geo.py              # Haversine, search patterns, pixel-to-geo
│           └── wpml.py             # DJI WPML XML generation
└── frontend/
    ├── Dockerfile                  # Multi-stage build with nginx
    ├── package.json
    ├── tailwind.config.js          # Emergency ops-center theme
    └── src/
        ├── App.jsx                 # Sidebar navigation layout
        ├── index.css               # Dark theme base styles
        └── components/
            ├── Dashboard/Dashboard.jsx  # Main ops dashboard
            ├── Map/DroneMap.jsx         # Mapbox GL with 7 layers
            └── Fleet/FleetPanel.jsx     # Fleet management panel
```

## DJI Cloud API Integration

| Feature | Protocol | Usage |
|---------|----------|-------|
| Device Telemetry (OSD) | MQTT `thing/product/{sn}/osd` | Real-time fleet position on live map |
| Wayline Management | MQTT `flighttask_prepare/execute` | Automated search pattern dispatch |
| Live Streaming | RTMP / WebRTC | Video feed for real-time AI detection |
| Media Upload | HTTPS + S3 | Post-flight batch analysis |
| Live Flight Controls | MQTT DRC | Operator override during incidents |
| Health Management | MQTT HMS | Fleet readiness monitoring |

## License

This project is developed for the DJI Enterprise Drone Onboard AI Challenge 2026.

- YOLOv8: AGPL-3.0 (Ultralytics)
- SAM 2: Apache 2.0 (Meta)
- EMQX: Apache 2.0
- FastAPI: MIT
