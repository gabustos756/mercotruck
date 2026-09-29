from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class MercotruckTariff(Base):
    """
    Tarifario Maestro de Servicios Propios por Empresa en crossTruck.
    Permite definir tarifas de venta y costos de fletero para cualquier ruta o servicio.
    """
    __tablename__ = "mercotruck_tariffs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    origin = Column(String(150), index=True, nullable=False)
    destination = Column(String(150), index=True, nullable=False)
    border_crossing = Column(String(150), index=True, nullable=True)
    category = Column(String(100), index=True, nullable=True)
    truck_type = Column(String(100), default="General", nullable=False)
    
    sale_price_usd = Column(Float, nullable=False)
    estimated_carrier_cost_usd = Column(Float, nullable=False)
    
    is_active = Column(Boolean, default=True, index=True)
    
    origin_lat = Column(Float, nullable=True)
    origin_lon = Column(Float, nullable=True)
    dest_lat = Column(Float, nullable=True)
    dest_lon = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación
    company = relationship("Company", back_populates="tariffs")
