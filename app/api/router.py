from fastapi import APIRouter
from app.api.v1.prospects import router as prospects_router
from app.api.v1.simulator import router as simulator_router
from app.api.v1.contacts import router as contacts_router
from app.api.v1.etl import router as etl_router
from app.api.v1.tariffs import router as tariffs_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.copilot import router as copilot_router
from app.api.v1.quotes import router as quotes_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(prospects_router)
api_router.include_router(simulator_router)
api_router.include_router(contacts_router)
api_router.include_router(etl_router)
api_router.include_router(tariffs_router)
api_router.include_router(analytics_router)
api_router.include_router(copilot_router)
api_router.include_router(quotes_router)
