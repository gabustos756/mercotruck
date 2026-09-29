import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, Text
from app.core.database import Base

class DemoStatus(str, enum.Enum):
    NUEVO = "NUEVO"
    CONTACTADO = "CONTACTADO"
    DEMO_AGENDADA = "DEMO_AGENDADA"
    CONVERTIDO = "CONVERTIDO"
    DESCARTADO = "DESCARTADO"

class DemoRequest(Base):
    """
    Solicitudes de demostración comercial recibidas desde la landing page institucional de crossTruck.
    Permite al Superadmin contactar al prospecto y crear su empresa en 1 clic.
    """
    __tablename__ = "demo_requests"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(200), nullable=False, index=True)
    contact_name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=False)
    
    fleet_size = Column(String(50), nullable=True) # ej. 1-10, 11-50, 50+ camiones
    corridor_interest = Column(String(200), nullable=True) # ej. Argentina - Chile, Mercosur
    notes = Column(Text, nullable=True)
    
    status = Column(Enum(DemoStatus), default=DemoStatus.NUEVO, nullable=False, index=True)
    assigned_admin = Column(String(150), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
