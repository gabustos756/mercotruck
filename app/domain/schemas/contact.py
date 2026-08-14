from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class ContactBase(BaseModel):
    name: str
    role_title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_primary: Optional[int] = 0
    notes: Optional[str] = None

class ContactCreate(ContactBase):
    prospect_id: int

class ContactResponse(ContactBase):
    id: int
    prospect_id: int
    created_at: datetime

    class Config:
        from_attributes = True
