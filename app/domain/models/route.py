from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text
from app.core.database import Base

class MercotruckRoute(Base):
    __tablename__ = "mercotruck_routes"

    id = Column(Integer, primary_key=True, index=True)
    trip_date = Column(Date, index=True, nullable=True)
    origin = Column(String(150), index=True, nullable=False)
    destination = Column(String(150), index=True, nullable=False)
    border_crossing = Column(String(150), index=True, nullable=True)
    
    client_name = Column(String(255), index=True, nullable=True)
    shipper_name = Column(String(255), nullable=True)
    carrier_name = Column(String(255), nullable=True)
    merchandise = Column(String(255), index=True, nullable=True)
    
    sale_price_usd = Column(Float, default=0.0)
    cost_price_usd = Column(Float, default=0.0)
    gross_margin_usd = Column(Float, default=0.0)
    gross_margin_pct = Column(Float, default=0.0)
    
    commercial_name = Column(String(150), nullable=True)
    customer_name = Column(String(150), nullable=True)
    status = Column(String(100), index=True, nullable=True) # e.g. EMBARQUE CONFIRMADO
    
    origin_lat = Column(Float, nullable=True)
    origin_lon = Column(Float, nullable=True)
    dest_lat = Column(Float, nullable=True)
    dest_lon = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
