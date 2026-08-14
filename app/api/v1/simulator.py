from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.domain.models.prospect import Prospect
from app.domain.models.simulation import SavedQuoteSimulation
from app.domain.schemas.simulator import SimulationRequest, SimulationResponse
from app.domain.services.pricing_engine import PricingEngine

router = APIRouter(prefix="/simulator", tags=["Simulator"])

@router.post("/calculate", response_model=SimulationResponse)
async def calculate_simulation(req: SimulationRequest):
    """Calcula en tiempo real el escenario de ganancia/pérdida sin guardar."""
    sim = PricingEngine.simulate_quote(
        gross_weight_kg=req.gross_weight_kg,
        target_sale_price_per_truck=req.target_sale_price_per_truck,
        estimated_carrier_cost_per_truck=req.estimated_carrier_cost_per_truck,
        truck_capacity_kg=req.truck_capacity_kg,
        extra_costs=req.extra_costs,
        competitor_price_per_truck=req.competitor_price_per_truck
    )
    
    sim["prospect_id"] = req.prospect_id
    return sim

@router.post("/save", response_model=dict)
async def save_simulation(
    req: SimulationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Guarda una cotización calculada en el historial del prospecto."""
    query = select(Prospect).where(Prospect.id == req.prospect_id)
    res = await db.execute(query)
    prospect = res.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospecto no encontrado")
        
    calc = PricingEngine.simulate_quote(
        gross_weight_kg=req.gross_weight_kg,
        target_sale_price_per_truck=req.target_sale_price_per_truck,
        estimated_carrier_cost_per_truck=req.estimated_carrier_cost_per_truck,
        truck_capacity_kg=req.truck_capacity_kg,
        extra_costs=req.extra_costs,
        competitor_price_per_truck=req.competitor_price_per_truck
    )
    
    saved_obj = SavedQuoteSimulation(
        prospect_id=req.prospect_id,
        user_id=1, # Default user (Admin)
        route_name=req.route_name or "Cotización Personalizada",
        truck_capacity_kg=req.truck_capacity_kg,
        trucks_count=calc["trucks_count"],
        target_sale_price_usd=req.target_sale_price_per_truck,
        estimated_carrier_cost_usd=req.estimated_carrier_cost_per_truck,
        extra_costs_usd=req.extra_costs,
        total_revenue_usd=calc["total_revenue"],
        total_cost_usd=calc["total_cost"],
        net_profit_usd=calc["net_profit"],
        margin_pct=calc["margin_pct"],
        competitor_price_usd=req.competitor_price_per_truck,
        notes=req.notes
    )
    
    db.add(saved_obj)
    await db.commit()
    await db.refresh(saved_obj)
    
    return {"status": "success", "simulation_id": saved_obj.id, "message": "Cotización guardada exitosamente"}
