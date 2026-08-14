import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base

class QuoteStatus(str, enum.Enum):
    ENVIADA = "ENVIADA"
    NEGOCIANDO = "NEGOCIANDO"
    GANADA = "GANADA"
    PERDIDA = "PERDIDA"
    DISCARDED = "DISCARDED"

class QuoteHistory(Base):
    """
    Historial de Cotizaciones Emitidas a Clientes y Pipeline CRM de Conversión.
    """
    __tablename__ = "quote_history"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    route_name = Column(String(255), nullable=False)
    strategy_type = Column(String(50), default="RECOMENDADA") # AGRESIVA, RECOMENDADA, MAX_MARGIN, CUSTOM, BACKHAUL
    trucks_count = Column(Integer, default=1)
    
    quoted_price_per_truck_usd = Column(Float, nullable=False)
    competitor_price_per_truck_usd = Column(Float, nullable=True)
    estimated_carrier_cost_per_truck_usd = Column(Float, nullable=False)
    
    # Extras & Upselling
    has_insurance = Column(Boolean, default=False)
    insurance_cost_usd = Column(Float, default=0.0)
    has_priority_customs = Column(Boolean, default=False)
    priority_customs_cost_usd = Column(Float, default=0.0)
    has_refrigerated = Column(Boolean, default=False)
    refrigerated_cost_usd = Column(Float, default=0.0)
    is_backhaul = Column(Boolean, default=False)
    
    total_quoted_usd = Column(Float, nullable=False)
    total_estimated_profit_usd = Column(Float, nullable=False)
    margin_pct = Column(Float, nullable=False)
    customer_savings_total_usd = Column(Float, default=0.0)
    
    status = Column(Enum(QuoteStatus), default=QuoteStatus.ENVIADA, index=True)
    loss_reason = Column(String(255), nullable=True) # Precio, Tiempo Tránsito, Disponibilidad
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    prospect = relationship("Prospect")
    user = relationship("User")
