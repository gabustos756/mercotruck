import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Date, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class ProspectStatus(str, enum.Enum):
    PROSPECT = "PROSPECT"
    CONTACTED = "CONTACTED"
    IN_NEGOTIATION = "IN_NEGOTIATION"
    WON = "WON"
    LOST = "LOST"
    DISCARDED = "DISCARDED"

class ProspectFuente(str, enum.Enum):
    IMPO = "IMPO"
    EXPO = "EXPO"
    BOTH = "BOTH"

class Prospect(Base):
    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    tax_id = Column(String(50), index=True, nullable=True) # RUT / CUIT
    fuente = Column(Enum(ProspectFuente), default=ProspectFuente.IMPO, nullable=False)
    primary_category = Column(String(100), index=True, nullable=True)
    
    total_shipments = Column(Integer, default=0)
    total_trucks = Column(Integer, default=0)
    total_freight_usd = Column(Float, default=0.0)
    avg_freight_per_truck_usd = Column(Float, default=0.0)
    last_shipment_date = Column(Date, nullable=True)
    
    status = Column(Enum(ProspectStatus), default=ProspectStatus.PROSPECT, index=True)
    assigned_commercial_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assigned_commercial = relationship("User", back_populates="prospects")
    contacts = relationship("ProspectContact", back_populates="prospect", cascade="all, delete-orphan")
    shipments = relationship("SofttradeShipment", back_populates="prospect", cascade="all, delete-orphan")
    interactions = relationship("CommercialInteraction", back_populates="prospect", cascade="all, delete-orphan")
    simulations = relationship("SavedQuoteSimulation", back_populates="prospect", cascade="all, delete-orphan")
