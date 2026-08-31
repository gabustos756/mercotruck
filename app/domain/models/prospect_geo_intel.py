from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from app.core.database import Base

class ProspectGeoIntel(Base):
    __tablename__ = "prospect_geo_intel"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), index=True, nullable=False)
    country = Column(String(50), index=True, nullable=False, default="CHILE")
    
    formatted_address = Column(Text, nullable=True)
    city = Column(String(150), index=True, nullable=True)
    state = Column(String(150), nullable=True)
    country_code = Column(String(10), nullable=True)
    
    phone = Column(String(100), nullable=True)
    website = Column(String(255), nullable=True)
    google_maps_url = Column(Text, nullable=True)
    google_rating = Column(Float, nullable=True)
    user_ratings_total = Column(Integer, nullable=True)
    
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    
    place_id = Column(String(255), nullable=True)
    source = Column(String(50), default="GOOGLE_PLACES")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
