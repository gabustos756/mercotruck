from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional

from app.core.database import get_db
from app.domain.models.quote_history import QuoteHistory, QuoteStatus
from app.domain.models.prospect import Prospect

router = APIRouter(prefix="/quotes", tags=["Quote History"])

class QuoteCreateRequest(BaseModel):
    prospect_id: int
    route_name: str
    strategy_type: str = "RECOMENDADA" # AGRESIVA, RECOMENDADA, MAX_MARGIN, CUSTOM, BACKHAUL
    trucks_count: int = Field(default=1, ge=1)
    quoted_price_per_truck_usd: float = Field(..., gt=0)
    competitor_price_per_truck_usd: Optional[float] = None
    estimated_carrier_cost_per_truck_usd: float = Field(..., gt=0)
    
    # Extras & Upselling
    has_insurance: bool = False
    insurance_cost_usd: float = 0.0
    has_priority_customs: bool = False
    priority_customs_cost_usd: float = 0.0
    has_refrigerated: bool = False
    refrigerated_cost_usd: float = 0.0
    is_backhaul: bool = False
    
    customer_savings_total_usd: float = Field(default=0.0)
    notes: Optional[str] = None

class QuoteStatusUpdateRequest(BaseModel):
    status: QuoteStatus
    loss_reason: Optional[str] = None

class QuoteNegotiateRequest(BaseModel):
    quoted_price_per_truck_usd: float = Field(..., gt=0)
    status: QuoteStatus
    notes: Optional[str] = None
    loss_reason: Optional[str] = None

@router.post("/")
async def create_quote(
    req: QuoteCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Registra una cotización enviada al cliente en la base de datos."""
    prospect_res = await db.execute(select(Prospect).where(Prospect.id == req.prospect_id))
    prospect = prospect_res.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospecto no encontrado")
        
    unit_base = req.quoted_price_per_truck_usd + req.insurance_cost_usd + req.priority_customs_cost_usd + req.refrigerated_cost_usd
    total_quoted = round(unit_base * req.trucks_count, 2)
    total_cost = round(req.estimated_carrier_cost_per_truck_usd * req.trucks_count, 2)
    total_profit = round(total_quoted - total_cost, 2)
    margin_pct = round((total_profit / total_quoted * 100.0), 1) if total_quoted > 0 else 0.0
    
    quote = QuoteHistory(
        prospect_id=req.prospect_id,
        user_id=1, # Default Admin User
        route_name=req.route_name,
        strategy_type=req.strategy_type,
        trucks_count=req.trucks_count,
        quoted_price_per_truck_usd=req.quoted_price_per_truck_usd,
        competitor_price_per_truck_usd=req.competitor_price_per_truck_usd,
        estimated_carrier_cost_per_truck_usd=req.estimated_carrier_cost_per_truck_usd,
        has_insurance=req.has_insurance,
        insurance_cost_usd=req.insurance_cost_usd,
        has_priority_customs=req.has_priority_customs,
        priority_customs_cost_usd=req.priority_customs_cost_usd,
        has_refrigerated=req.has_refrigerated,
        refrigerated_cost_usd=req.refrigerated_cost_usd,
        is_backhaul=req.is_backhaul,
        total_quoted_usd=total_quoted,
        total_estimated_profit_usd=total_profit,
        margin_pct=margin_pct,
        customer_savings_total_usd=req.customer_savings_total_usd,
        status=QuoteStatus.ENVIADA,
        notes=req.notes
    )
    
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    
    return {"status": "success", "quote_id": quote.id, "message": "Cotización emitida y registrada exitosamente"}

@router.put("/{quote_id}/status")
async def update_quote_status(
    quote_id: int,
    req: QuoteStatusUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Actualiza el estado comercial de una cotización en el Pipeline CRM."""
    res = await db.execute(select(QuoteHistory).where(QuoteHistory.id == quote_id))
    quote = res.scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    quote.status = req.status
    if req.loss_reason:
        quote.loss_reason = req.loss_reason
    quote.updated_at = datetime.utcnow()
        
    await db.commit()
    return {"status": "success", "quote_id": quote.id, "new_status": quote.status.value}

@router.put("/{quote_id}/negotiate")
async def negotiate_quote(
    quote_id: int,
    req: QuoteNegotiateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Re-negocia tarifa, margen, notas y estado comercial en vivo desde el CRM."""
    res = await db.execute(select(QuoteHistory).where(QuoteHistory.id == quote_id))
    quote = res.scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    cost = quote.estimated_carrier_cost_per_truck_usd
    total_quoted = round(req.quoted_price_per_truck_usd * quote.trucks_count, 2)
    total_cost = round(cost * quote.trucks_count, 2)
    total_profit = round(total_quoted - total_cost, 2)
    margin_pct = round((total_profit / total_quoted * 100.0), 1) if total_quoted > 0 else 0.0

    quote.quoted_price_per_truck_usd = req.quoted_price_per_truck_usd
    quote.total_quoted_usd = total_quoted
    quote.total_estimated_profit_usd = total_profit
    quote.margin_pct = margin_pct
    quote.status = req.status
    quote.updated_at = datetime.utcnow()

    if quote.competitor_price_per_truck_usd:
        quote.customer_savings_total_usd = max(0.0, (quote.competitor_price_per_truck_usd - req.quoted_price_per_truck_usd) * quote.trucks_count)

    if req.notes:
        existing_notes = quote.notes or ""
        timestamp = datetime.utcnow().strftime("%d/%m/%Y %H:%M")
        quote.notes = f"[{timestamp}] {req.notes}\n" + existing_notes

    if req.loss_reason:
        quote.loss_reason = req.loss_reason

    await db.commit()
    return {"status": "success", "quote_id": quote.id, "new_margin_pct": margin_pct, "new_status": quote.status.value}

@router.get("/{prospect_id}")
async def list_prospect_quotes(
    prospect_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Obtiene el historial de cotizaciones emitidas a un prospecto."""
    query = select(QuoteHistory).where(QuoteHistory.prospect_id == prospect_id).order_by(QuoteHistory.created_at.desc())
    res = await db.execute(query)
    quotes = res.scalars().all()
    return quotes
