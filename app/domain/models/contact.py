from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class ProspectContact(Base):
    __tablename__ = "prospect_contacts"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    role_title = Column(String(100), nullable=True) # e.g. Gerente de Logística, Comercio Exterior
    email = Column(String(255), nullable=True)
    phone = Column(String(100), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    is_primary = Column(Integer, default=0) # 1 for primary contact
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    prospect = relationship("Prospect", back_populates="contacts")
