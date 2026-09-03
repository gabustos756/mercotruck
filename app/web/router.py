from fastapi import APIRouter
from app.web.controllers.dashboard_controller import router as dashboard_router
from app.web.controllers.prospect_controller import router as prospect_router
from app.web.controllers.tariff_controller import router as tariff_router
from app.web.controllers.analytics_controller import router as analytics_router
from app.web.controllers.escenarios_controller import router as escenarios_router
from app.web.controllers.backhaul_controller import router as backhaul_router
from app.web.controllers.crm_controller import router as crm_router
from app.web.controllers.favorites_controller import router as favorites_router
from app.web.controllers.presentation_controller import router as presentation_router

web_router = APIRouter()
web_router.include_router(dashboard_router)
web_router.include_router(prospect_router)
web_router.include_router(tariff_router)
web_router.include_router(analytics_router)
web_router.include_router(escenarios_router)
web_router.include_router(backhaul_router)
web_router.include_router(crm_router)
web_router.include_router(favorites_router)
web_router.include_router(presentation_router)
