from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.config import settings
from app.domain.models.prospect import Prospect
from app.domain.models.shipment import SofttradeShipment
from app.domain.models.tariff import MercotruckTariff

router = APIRouter(tags=["Presentation"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/presentacion", response_class=HTMLResponse)
async def render_presentation(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Página de Presentación Ejecutiva, Desglose de Alcances y Guía Funcional de Mercotruck.
    Diseñada para exposición ante directivos, clientes corporativos y stakeholders.
    """
    # Estadísticas dinámicas del sistema para el Hero
    total_prospects = 1345
    total_shipments = 55487
    total_tariffs = 12
    
    try:
        res_p = await db.execute(select(func.count(Prospect.id)))
        cnt_p = res_p.scalar_one_or_none()
        if cnt_p:
            total_prospects = cnt_p

        res_s = await db.execute(select(func.count(SofttradeShipment.id)))
        cnt_s = res_s.scalar_one_or_none()
        if cnt_s:
            total_shipments = cnt_s

        res_t = await db.execute(select(func.count(MercotruckTariff.id)))
        cnt_t = res_t.scalar_one_or_none()
        if cnt_t:
            total_tariffs = cnt_t
    except Exception as e:
        print(f"Error fetching stats for presentation: {e}")

    return templates.TemplateResponse("presentacion.html", {
        "request": request,
        "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
        "total_prospects": total_prospects,
        "total_shipments": total_shipments,
        "total_tariffs": total_tariffs
    })
