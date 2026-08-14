from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.core.database import Base

class CommercialInteraction(Base):
    __tablename__ = "commercial_interactions"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    interaction_type = Column(String(50), nullable=False) # LLAMADA, EMAIL, REUNION, COTIZACION
    notes = Column(Text, nullable=False)
    next_action_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    prospect = relationship("Prospect", back_populates="interactions")
    user = relationship("User", back_populates="interactions")
