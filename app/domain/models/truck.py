import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class TruckType(str, enum.Enum):
    SIDER = "SIDER" # Lona / Cortina
    TERMICO = "TERMICO" # Refrigerado / Con equipo de frío
    FURGON = "FURGON" # Cerrado paquetero
    BATEA = "BATEA" # Granelero / Tolva
    CHASIS = "CHASIS" # Chasis con cabina
    PLAYO = "PLAYO" # Plataforma plana
    OTRO = "OTRO"

class TruckStatus(str, enum.Enum):
    DISPONIBLE = "DISPONIBLE"
    EN_VIAJE = "EN_VIAJE"
    EN_MANTENIMIENTO = "EN_MANTENIMIENTO"
    INACTIVO = "INACTIVO"

class CompanyTruck(Base):
    """
    Unidad de flota propia o semirremolque de la empresa cliente.
    Permite conocer la disponibilidad real para asignar cargas y optimizar retornos.
    """
    __tablename__ = "company_trucks"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    plate_number = Column(String(50), nullable=False, index=True) # Patente / Matrícula
    truck_type = Column(Enum(TruckType), default=TruckType.SIDER, nullable=False)
    brand_model = Column(String(150), nullable=True) # ej. Scania R450, Volvo FH 540
    model_year = Column(Integer, nullable=True)
    
    max_weight_kg = Column(Float, default=28000.0) # Capacidad útil estándar
    max_volume_m3 = Column(Float, default=90.0) # Metros cúbicos
    
    driver_name = Column(String(150), nullable=True)
    driver_phone = Column(String(50), nullable=True)
    
    status = Column(Enum(TruckStatus), default=TruckStatus.DISPONIBLE, nullable=False, index=True)
    current_city = Column(String(150), nullable=True) # Ubicación actual de la unidad
    notes = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación
    company = relationship("Company", back_populates="trucks")
