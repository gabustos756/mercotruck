from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.domain.models.demo_request import DemoRequest, DemoStatus

router = APIRouter(prefix="/demos", tags=["Demo Requests"])

class DemoRequestCreate(BaseModel):
    company_name: str
    contact_name: str
    email: str
    phone: str
    fleet_size: Optional[str] = "1-10"
    corridor_interest: Optional[str] = "Argentina - Chile"
    notes: Optional[str] = None

@router.post("/request", status_code=status.HTTP_201_CREATED)
async def submit_demo_request(
    data: DemoRequestCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint público consumido por la landing page de crossTruck
    para registrar una solicitud de demostración comercial.
    """
    req = DemoRequest(
        company_name=data.company_name.strip(),
        contact_name=data.contact_name.strip(),
        email=data.email.strip().lower(),
        phone=data.phone.strip(),
        fleet_size=data.fleet_size,
        corridor_interest=data.corridor_interest,
        notes=data.notes,
        status=DemoStatus.NUEVO
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    
    return {
        "success": True,
        "message": "Solicitud de demostración recibida con éxito. Un especialista de crossTruck se comunicará a la brevedad.",
        "request_id": req.id
    }
