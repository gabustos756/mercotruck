from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class SimulationRequest(BaseModel):
    prospect_id: int
    gross_weight_kg: float = Field(..., gt=0)
    target_sale_price_per_truck: float = Field(..., gt=0)
    estimated_carrier_cost_per_truck: float = Field(..., gt=0)
    truck_capacity_kg: float = Field(default=28500.0, gt=0)
    extra_costs: float = Field(default=0.0, ge=0)
    competitor_price_per_truck: Optional[float] = None
    route_name: Optional[str] = "Cotización Personalizada"
    notes: Optional[str] = None

class SimulationResponse(BaseModel):
    id: Optional[int] = None
    prospect_id: int
    gross_weight_kg: float
    truck_capacity_kg: float
    trucks_count: int
    target_sale_price_per_truck: float
    estimated_carrier_cost_per_truck: float
    extra_costs: float
    total_revenue: float
    total_carrier_cost: float
    total_cost: float
    net_profit: float
    margin_pct: float
    is_profitable: bool
    competitor_price_per_truck: Optional[float] = None
    diff_vs_competitor_pct: Optional[float] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
