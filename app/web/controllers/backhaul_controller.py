from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.auth import get_current_user_web
from app.domain.models.user import User
from app.domain.models.backhaul import BackhaulOpportunity
from app.domain.models.route import MercotruckRoute

from app.web.jinja import templates
router = APIRouter(tags=["Web Retornos Vacíos"])

@router.get("/retornos-vacios", response_class=HTMLResponse)
async def render_backhaul_marketplace(
    request: Request,
    current_user: User = Depends(get_current_user_web),
    db: AsyncSession = Depends(get_db)
):
    # Si no hay oportunidades registradas, sembrar oportunidades de ejemplo de las top rutas
    count_res = await db.execute(select(func.count(BackhaulOpportunity.id)))
    count = count_res.scalar_one()

    if count == 0:
        sample_backhauls = [
            BackhaulOpportunity(
                origin="CLP - SANTIAGO",
                destination="BUENOS AIRES",
                border_crossing="LIBERTADORES",
                available_trucks=3,
                truck_type="Sider",
                standard_price_usd=2335.0,
                discounted_backhaul_price_usd=1650.0,
                estimated_carrier_cost_usd=1200.0,
                notes="Camiones descargando en Santiago. Disponibles para retorno inmediato."
            ),
            BackhaulOpportunity(
                origin="LOS ANDES",
                destination="MENDOZA",
                border_crossing="LIBERTADORES",
                available_trucks=5,
                truck_type="Refrigerado",
                standard_price_usd=1865.0,
                discounted_backhaul_price_usd=1350.0,
                estimated_carrier_cost_usd=950.0,
                notes="Retorno de fruta chilena desocupando el jueves."
            ),
            BackhaulOpportunity(
                origin="CLP - SAN ANTONIO",
                destination="CORDOBA",
                border_crossing="LIBERTADORES",
                available_trucks=2,
                truck_type="Sider",
                standard_price_usd=2450.0,
                discounted_backhaul_price_usd=1750.0,
                estimated_carrier_cost_usd=1300.0,
                notes="Contenedores desocupados en puerto San Antonio."
            )
        ]
        db.add_all(sample_backhauls)
        await db.commit()

    query = select(BackhaulOpportunity).where(BackhaulOpportunity.is_active == True)
    res = await db.execute(query)
    opportunities = res.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="retornos_vacios.html",
        context={
            "user": current_user,
            "current_user": current_user,
            "opportunities": opportunities
        }
    )
