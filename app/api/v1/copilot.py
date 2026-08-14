from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.domain.models.prospect import Prospect
from app.domain.services.copilot_engine import CopilotEngine

router = APIRouter(prefix="/copilot", tags=["AI Copilot Decision Engine"])

@router.get("/advice/{prospect_id}")
async def get_copilot_advice(
    prospect_id: int,
    competitor_price: Optional[float] = Query(None),
    carrier_cost: Optional[float] = Query(None),
    trucks: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Obtiene asesoramiento comercial y estrategias de precio del AI Copilot."""
    query = select(Prospect).where(Prospect.id == prospect_id)
    res = await db.execute(query)
    prospect = res.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospecto no encontrado")
        
    comp_price = competitor_price or prospect.avg_freight_per_truck_usd or 2500.0
    cost_price = carrier_cost or (comp_price * 0.80)
    truck_count = trucks or prospect.total_trucks or 1
    
    advice = CopilotEngine.generate_advice(
        prospect_name=prospect.name,
        total_trucks=truck_count,
        competitor_price_per_truck=comp_price,
        estimated_carrier_cost_per_truck=cost_price,
        category=prospect.primary_category or "General"
    )
    
    return advice
