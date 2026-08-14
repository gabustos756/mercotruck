from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.domain.models.prospect import Prospect

from app.web.jinja import templates
router = APIRouter(tags=["Web Escenarios"])

@router.get("/escenarios", response_class=HTMLResponse)
async def render_escenarios(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Renderiza la vista de Escenarios de Cotización con desgloses instantáneos."""
    query = select(Prospect).order_by(Prospect.total_trucks.desc())
    res = await db.execute(query)
    all_prospects = res.scalars().all()

    prospects_json = [
        {
            "id": p.id,
            "name": p.name,
            "tax_id": p.tax_id or "—",
            "total_shipments": p.total_shipments,
            "total_trucks": p.total_trucks,
            "avg_freight_per_truck_usd": round(p.avg_freight_per_truck_usd or 2500, 2),
            "total_freight_usd": round(p.total_freight_usd or 0, 2),
            "category": p.primary_category or "Otros",
            "fuente": p.fuente.value if hasattr(p.fuente, "value") else str(p.fuente)
        }
        for p in all_prospects
    ]

    top_10 = prospects_json[:10]

    return templates.TemplateResponse("escenarios.html", {
        "request": request,
        "prospects_json": prospects_json,
        "top_10": top_10
    })
