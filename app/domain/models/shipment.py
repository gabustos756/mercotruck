from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class SofttradeShipment(Base):
    __tablename__ = "softtrade_shipments"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True)
    fuente = Column(String(10), nullable=False, index=True) # IMPO or EXPO
    document_id = Column(String(100), index=True, nullable=False) # Documento / DUA
    item = Column(String(50), nullable=True)
    shipment_date = Column(Date, index=True, nullable=True)
    
    customs_sach_code = Column(String(50), nullable=True)
    customs_office = Column(String(100), index=True, nullable=True) # Aduana
    origin_str = Column(String(150), index=True, nullable=True)
    destination_str = Column(String(150), index=True, nullable=True)
    border_crossing = Column(String(150), index=True, nullable=True) # Puerto Embarque/Desembarque
    
    carrier_name = Column(String(255), index=True, nullable=True)
    gross_weight_kg = Column(Float, default=0.0)
    trucks_count = Column(Integer, default=1)
    
    freight_usd = Column(Float, default=0.0)
    freight_per_truck_usd = Column(Float, default=0.0)
    fob_usd = Column(Float, default=0.0)
    cif_usd = Column(Float, default=0.0)
    
    merchandise_desc = Column(Text, nullable=True)
    product_clean = Column(String(200), index=True, nullable=True)
    category = Column(String(100), index=True, nullable=True)
    
    # Enriched Route Inference & Commercial Entity Fields
    real_origin_city = Column(String(150), index=True, nullable=True)
    real_destination_city = Column(String(150), index=True, nullable=True)
    customs_office_code = Column(String(100), nullable=True)
    shipper_name = Column(String(255), index=True, nullable=True)
    consignee_name = Column(String(255), index=True, nullable=True)
    geo_inference_level = Column(String(50), nullable=True) # HISTORIC_MATCH, MERCHANDISE_RULE, GOOGLE_INTEL, RAW_CUSTOMS

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    prospect = relationship("Prospect", back_populates="shipments")
