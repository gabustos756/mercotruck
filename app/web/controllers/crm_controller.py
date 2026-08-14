from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.core.database import get_db
from app.domain.models.quote_history import QuoteHistory, QuoteStatus

from app.web.jinja import templates
router = APIRouter(tags=["Web Pipeline CRM"])

def get_status_str(val):
    if hasattr(val, "value"):
        return str(val.value)
    return str(val)

@router.get("/pipeline-crm", response_class=HTMLResponse)
async def render_pipeline_crm(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Renderiza el Módulo de Embudo Comercial CRM & Asistente de Negociación."""
    query = select(QuoteHistory).options(selectinload(QuoteHistory.prospect)).order_by(QuoteHistory.created_at.desc())
    res = await db.execute(query)
    quotes = res.scalars().all()

    # Formatear datos extendidos de negociación para la plantilla
    formatted_quotes = []
    for q in quotes:
        cost = q.estimated_carrier_cost_per_truck_usd or 2000.0
        floor_price = round(cost / 0.85, 2) # Piso 15% margen
        max_price = round(cost / 0.75, 2)   # Techo 25% margen

        updated_str = q.updated_at.strftime("%d/%m/%Y %H:%M") if q.updated_at else q.created_at.strftime("%d/%m/%Y %H:%M")

        formatted_quotes.append({
            "id": q.id,
            "prospect_id": q.prospect_id,
            "prospect_name": q.prospect.name if q.prospect else "Cliente",
            "tax_id": q.prospect.tax_id if q.prospect else "—",
            "route_name": q.route_name,
            "strategy_type": q.strategy_type,
            "trucks_count": q.trucks_count,
            "quoted_price_per_truck_usd": round(q.quoted_price_per_truck_usd, 2),
            "competitor_price_per_truck_usd": round(q.competitor_price_per_truck_usd, 2) if q.competitor_price_per_truck_usd else None,
            "carrier_cost_usd": round(cost, 2),
            "floor_price_usd": floor_price,
            "max_price_usd": max_price,
            "total_quoted_usd": round(q.total_quoted_usd, 2),
            "total_profit_usd": round(q.total_estimated_profit_usd, 2),
            "margin_pct": q.margin_pct,
            "customer_savings_total_usd": round(q.customer_savings_total_usd or 0, 2),
            "has_insurance": q.has_insurance,
            "has_priority_customs": q.has_priority_customs,
            "has_refrigerated": q.has_refrigerated,
            "is_backhaul": q.is_backhaul,
            "status": get_status_str(q.status),
            "loss_reason": q.loss_reason,
            "notes": q.notes or "",
            "updated_str": updated_str
        })

    pipeline = {
        "ENVIADA": [q for q in formatted_quotes if q["status"] == "ENVIADA"],
        "NEGOCIANDO": [q for q in formatted_quotes if q["status"] == "NEGOCIANDO"],
        "GANADA": [q for q in formatted_quotes if q["status"] == "GANADA"],
        "PERDIDA": [q for q in formatted_quotes if q["status"] == "PERDIDA"]
    }

    total_pipeline_usd = sum(q["total_quoted_usd"] for q in formatted_quotes if q["status"] in ("ENVIADA", "NEGOCIANDO"))
    total_ganado_usd = sum(q["total_quoted_usd"] for q in formatted_quotes if q["status"] == "GANADA")

    return templates.TemplateResponse(
        request=request,
        name="pipeline_crm.html",
        context={
            "pipeline": pipeline,
            "total_quotes": len(formatted_quotes),
            "total_pipeline_usd": f"${total_pipeline_usd:,.0f}",
            "total_ganado_usd": f"${total_ganado_usd:,.0f}"
        }
    )
