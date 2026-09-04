from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.auth import get_current_user_web
from app.domain.models.user import User

from app.web.jinja import templates
router = APIRouter(prefix="/rutas-frecuentes", tags=["Web Analytics Corredores"])

@router.get("/", response_class=HTMLResponse)
async def render_top_routes(
    request: Request,
    current_user: User = Depends(get_current_user_web),
    db: AsyncSession = Depends(get_db)
):
    """Renders top commercial trade corridors analytics view."""
    # Top Routes Query
    query_routes = text("""
        SELECT 
            origin_str, 
            destination_str, 
            border_crossing,
            fuente,
            COUNT(*) as total_envios,
            SUM(trucks_count) as total_camiones,
            SUM(freight_usd) as flete_total_usd,
            AVG(freight_per_truck_usd) as flete_promedio_camion
        FROM softtrade_shipments
        WHERE origin_str IS NOT NULL AND destination_str IS NOT NULL
        GROUP BY origin_str, destination_str, border_crossing, fuente
        ORDER BY total_camiones DESC
        LIMIT 20;
    """)
    res_routes = await db.execute(query_routes)
    routes = res_routes.mappings().all()

    # Top Origins Query
    query_origins = text("""
        SELECT 
            origin_str, 
            COUNT(*) as total_envios,
            SUM(trucks_count) as total_camiones,
            SUM(freight_usd) as flete_total_usd
        FROM softtrade_shipments
        WHERE origin_str IS NOT NULL
        GROUP BY origin_str
        ORDER BY total_camiones DESC
        LIMIT 10;
    """)
    res_origins = await db.execute(query_origins)
    origins = res_origins.mappings().all()

    # Top Borders Query
    query_borders = text("""
        SELECT 
            border_crossing, 
            COUNT(*) as total_envios,
            SUM(trucks_count) as total_camiones,
            SUM(freight_usd) as flete_total_usd
        FROM softtrade_shipments
        WHERE border_crossing IS NOT NULL AND border_crossing != ''
        GROUP BY border_crossing
        ORDER BY total_camiones DESC
        LIMIT 10;
    """)
    res_borders = await db.execute(query_borders)
    borders = res_borders.mappings().all()

    return templates.TemplateResponse(
        request=request,
        name="top_routes.html",
        context={
            "user": current_user,
            "current_user": current_user,
            "routes": routes,
            "origins": origins,
            "borders": borders
        }
    )
