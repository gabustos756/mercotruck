from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class SavedQuoteSimulation(Base):
    __tablename__ = "saved_quote_simulations"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    route_name = Column(String(255), nullable=False)
    truck_capacity_kg = Column(Float, default=28500.0)
    trucks_count = Column(Integer, default=1)
    
    target_sale_price_usd = Column(Float, nullable=False)
    estimated_carrier_cost_usd = Column(Float, nullable=False)
    extra_costs_usd = Column(Float, default=0.0)
    
    total_revenue_usd = Column(Float, nullable=False)
    total_cost_usd = Column(Float, nullable=False)
    net_profit_usd = Column(Float, nullable=False)
    margin_pct = Column(Float, nullable=False)
    
    competitor_price_usd = Column(Float, nullable=True)
    mercotruck_hist_price_usd = Column(Float, nullable=True)
    
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    prospect = relationship("Prospect", back_populates="simulations")
    user = relationship("User", back_populates="simulations")
