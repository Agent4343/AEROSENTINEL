from fastapi import APIRouter

from app.api.routes.incidents import router as incidents_router
from app.api.routes.drones import router as drones_router
from app.api.routes.missions import router as missions_router
from app.api.routes.detections import router as detections_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.websocket import router as websocket_router
from app.api.routes.simulator import router as simulator_router

router = APIRouter()

router.include_router(incidents_router)
router.include_router(drones_router)
router.include_router(missions_router)
router.include_router(detections_router)
router.include_router(alerts_router)
router.include_router(websocket_router)
router.include_router(simulator_router)
