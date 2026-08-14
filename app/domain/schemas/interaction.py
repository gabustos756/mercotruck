from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class InteractionCreate(BaseModel):
    prospect_id: int
    interaction_type: str # LLAMADA, EMAIL, REUNION, COTIZACION
    notes: str
    next_action_date: Optional[date] = None

class InteractionResponse(BaseModel):
    id: int
    prospect_id: int
    user_id: int
    interaction_type: str
    notes: str
    next_action_date: Optional[date] = None
    created_at: datetime
    user_name: Optional[str] = None

    class Config:
        from_attributes = True
