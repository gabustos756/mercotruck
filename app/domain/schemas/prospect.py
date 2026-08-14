from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from app.domain.models.prospect import ProspectStatus, ProspectFuente

class ProspectBase(BaseModel):
    name: str
    tax_id: Optional[str] = None
    fuente: ProspectFuente
    primary_category: Optional[str] = None
    status: ProspectStatus = ProspectStatus.PROSPECT

class ProspectCreate(ProspectBase):
    pass

class ProspectUpdate(BaseModel):
    status: Optional[ProspectStatus] = None
    assigned_commercial_id: Optional[int] = None
    notes: Optional[str] = None

class ProspectResponse(ProspectBase):
    id: int
    total_shipments: int
    total_trucks: int
    total_freight_usd: float
    avg_freight_per_truck_usd: float
    last_shipment_date: Optional[date] = None
    assigned_commercial_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ProspectFilterParams(BaseModel):
    search: Optional[str] = None
    category: Optional[str] = None
    fuente: Optional[str] = None
    status: Optional[str] = None
    min_trucks: Optional[int] = Field(default=1)
    min_margin_pct: Optional[float] = Field(default=0.0)
    max_diff_pct: Optional[float] = Field(default=100.0)
    truck_capacity_kg: Optional[float] = Field(default=28500.0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
