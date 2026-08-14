from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class BackhaulOpportunity(Base):
    """
    Oportunidades de Retornos Vacíos (Camiones que retornan desocupados).
    Permite ofrecer tarifas con descuento de retorno conservando alto margen neto.
    """
    __tablename__ = "backhaul_opportunities"

    id = Column(Integer, primary_key=True, index=True)
    origin = Column(String(150), nullable=False, index=True)
    destination = Column(String(150), nullable=False, index=True)
    border_crossing = Column(String(100), default="LIBERTADORES")
    
    available_trucks = Column(Integer, default=1, nullable=False)
    available_date = Column(Date, default=date.today, nullable=False)
    truck_type = Column(String(100), default="Sider")
    
    standard_price_usd = Column(Float, nullable=False)
    discounted_backhaul_price_usd = Column(Float, nullable=False) # Tarifa especial de retorno
    estimated_carrier_cost_usd = Column(Float, nullable=False)
    
    is_active = Column(Boolean, default=True, index=True)
    notes = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
