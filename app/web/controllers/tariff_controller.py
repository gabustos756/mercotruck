from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.auth import get_current_user_web
from app.domain.models.user import User
from app.domain.models.tariff import MercotruckTariff

from app.web.jinja import templates
router = APIRouter(prefix="/tarifas", tags=["Web Tariffs ABM"])

@router.get("/", response_class=HTMLResponse)
async def render_tariffs_abm(
    request: Request,
    current_user: User = Depends(get_current_user_web),
    db: AsyncSession = Depends(get_db)
):
    """Renders the ABM Tarifario Propio management page."""
    query = select(MercotruckTariff).order_by(MercotruckTariff.updated_at.desc())
    res = await db.execute(query)
    tariffs = res.scalars().all()
    
    return templates.TemplateResponse(
        request=request,
        name="tariffs.html",
        context={
            "user": current_user,
            "current_user": current_user,
            "tariffs": tariffs
        }
    )
