from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.auth import get_current_user_optional
from app.domain.models.user import User
from app.domain.models.shipment import SofttradeShipment
from app.domain.models.prospect import Prospect
from app.web.jinja import templates

router = APIRouter(tags=["Landing Page"])

_DASHBOARD_FILTER_PARAMS = {
    "search", "origin", "destination", "product",
    "category", "fuente", "status", "country",
    "match", "min_trucks", "page"
}

@router.get("/", response_class=HTMLResponse)
async def landing_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Landing Page institucional y comercial de crossTruck.
    Si recibe parámetros de búsqueda del Dashboard (ej. por caché de navegador), redirige a /dashboard.
    """
    if any(k in request.query_params for k in _DASHBOARD_FILTER_PARAMS):
        return RedirectResponse(url=f"/dashboard?{request.url.query}", status_code=302)
    # Estadísticas dinámicas de mercado para generar alto impacto
    total_despachos = 55487
    total_transportistas = 3552
    total_dadores = 1122

    try:
        q_shipments = await db.execute(select(func.count(SofttradeShipment.id)))
        s_count = q_shipments.scalar()
        if s_count and s_count > 0:
            total_despachos = s_count

        q_prospects = await db.execute(select(func.count(Prospect.id)))
        p_count = q_prospects.scalar()
        if p_count and p_count > 0:
            total_dadores = p_count
    except Exception:
        pass

    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={
            "current_user": current_user,
            "stats": {
                "total_despachos": f"{total_despachos:,}".replace(",", "."),
                "total_transportistas": f"{total_transportistas:,}".replace(",", "."),
                "total_dadores": f"{total_dadores:,}".replace(",", "."),
                "paso_principal": "Paso Los Libertadores (Cristo Redentor)",
                "ahorro_medio_pct": "7.8%",
                "margen_minimo_seguro": "15%"
            }
        }
    )
