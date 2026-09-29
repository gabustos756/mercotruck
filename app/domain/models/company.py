import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class PlanTier(str, enum.Enum):
    TRIAL = "TRIAL"
    STARTER = "STARTER"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"

class SubscriptionStatus(str, enum.Enum):
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"

class Company(Base):
    """
    Entidad Tenant / Empresa Transportista o Logística en crossTruck.
    Permite el aislamiento de tarifas, flota, rutas y usuarios por cliente.
    """
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True) # Nombre comercial (ej. Mercotruck Logistics, Andesmar Cargas)
    business_name = Column(String(255), nullable=True) # Razón social oficial
    cuit_rut = Column(String(50), nullable=True, index=True) # Identificador fiscal
    country = Column(String(100), default="Argentina", nullable=False)
    
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    
    plan_tier = Column(Enum(PlanTier), default=PlanTier.PRO, nullable=False)
    subscription_status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)
    
    max_trucks = Column(Integer, default=50)
    max_users = Column(Integer, default=5)
    
    logo_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    trucks = relationship("CompanyTruck", back_populates="company", cascade="all, delete-orphan")
    tariffs = relationship("MercotruckTariff", back_populates="company")
    quotes = relationship("QuoteHistory", back_populates="company")
