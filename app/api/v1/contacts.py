from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import get_db
from app.domain.models.contact import ProspectContact
from app.domain.models.prospect import Prospect
from app.domain.schemas.contact import ContactCreate, ContactResponse
from typing import List

router = APIRouter(prefix="/contacts", tags=["Contacts"])

@router.get("/{prospect_id}", response_model=List[ContactResponse])
async def list_prospect_contacts(
    prospect_id: int,
    db: AsyncSession = Depends(get_db)
):
    query = select(ProspectContact).where(ProspectContact.prospect_id == prospect_id).order_by(ProspectContact.created_at.desc())
    res = await db.execute(query)
    contacts = res.scalars().all()
    return contacts

@router.post("/", response_model=ContactResponse)
async def create_prospect_contact(
    req: ContactCreate,
    db: AsyncSession = Depends(get_db)
):
    prospect_res = await db.execute(select(Prospect).where(Prospect.id == req.prospect_id))
    if not prospect_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Prospecto no encontrado")
        
    contact = ProspectContact(
        prospect_id=req.prospect_id,
        name=req.name,
        role_title=req.role_title,
        email=req.email,
        phone=req.phone,
        linkedin_url=req.linkedin_url,
        is_primary=req.is_primary or 0,
        notes=req.notes
    )
    
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact
