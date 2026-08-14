from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.domain.models.favorite import ProspectFavorite

from app.web.jinja import templates
router = APIRouter(tags=["Web Favorites"])

@router.get("/favoritos", response_class=HTMLResponse)
async def render_favorites(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Renderiza la vista dedicada de Monitoreo de Clientes Favoritos & Alertas por Email."""
    query = select(ProspectFavorite).options(selectinload(ProspectFavorite.prospect)).where(ProspectFavorite.user_id == 1).order_by(ProspectFavorite.created_at.desc())
    res = await db.execute(query)
    favs = res.scalars().all()

    items = []
    total_monitored_trucks = 0
    total_monitored_freight = 0.0

    for f in favs:
        p = f.prospect
        if p:
            total_monitored_trucks += (p.total_trucks or 0)
            total_monitored_freight += (p.total_freight_usd or 0.0)
            items.append({
                "favorite_id": f.id,
                "id": p.id,
                "name": p.name,
                "tax_id": p.tax_id or "—",
                "fuente": p.fuente.value if hasattr(p.fuente, "value") else str(p.fuente),
                "category": p.primary_category or "Otros",
                "total_trucks": p.total_trucks,
                "avg_freight_per_truck_usd": round(p.avg_freight_per_truck_usd or 0, 2),
                "total_freight_usd": round(p.total_freight_usd or 0, 2),
                "created_at_str": f.created_at.strftime("%d/%m/%Y"),
                "status": "🟢 Monitoreando Cargas"
            })

    return templates.TemplateResponse(
        request=request,
        name="favoritos.html",
        context={
            "favorites": items,
            "total_favs": len(items),
            "total_monitored_trucks": total_monitored_trucks,
            "total_monitored_freight": f"${total_monitored_freight:,.0f}"
        }
    )
