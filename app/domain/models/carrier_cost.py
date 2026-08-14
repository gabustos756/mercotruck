from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from app.core.database import Base

class CarrierCostMatrix(Base):
    """
    Matriz de Costos Directos Estimados de Fleteros por Ruta y Tipo de Remolque.
    """
    __tablename__ = "carrier_cost_matrix"

    id = Column(Integer, primary_key=True, index=True)
    origin = Column(String(150), index=True, nullable=False)
    destination = Column(String(150), index=True, nullable=False)
    truck_type = Column(String(100), default="Sider", nullable=False) # Sider, Refrigerado, Playo, Furgon
    
    base_cost_usd = Column(Float, nullable=False)
    toll_cost_usd = Column(Float, default=0.0)
    estimated_total_cost_usd = Column(Float, nullable=False)
    
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
