from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class TariffBase(BaseModel):
    origin: str
    destination: str
    border_crossing: Optional[str] = None
    category: Optional[str] = "Todas"
    truck_type: str = "General"
    sale_price_usd: float = Field(..., gt=0)
    estimated_carrier_cost_usd: float = Field(..., gt=0)
    is_active: bool = True

class TariffCreate(TariffBase):
    pass

class TariffUpdate(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    border_crossing: Optional[str] = None
    category: Optional[str] = None
    truck_type: Optional[str] = None
    sale_price_usd: Optional[float] = None
    estimated_carrier_cost_usd: Optional[float] = None
    is_active: Optional[bool] = None

class TariffResponse(TariffBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
