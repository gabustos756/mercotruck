from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from app.core.database import Base


class ClientMasterProfile(Base):
    """
    Padrón Maestro Fijo de Clientes, Nombres de Fantasía (Dador Mercotruck) y Plantas Verificadas.
    Permite fijar de forma permanente Razón Social Aduana <-> Nombre de Fantasía <-> Ciudad de Planta
    y tipo de equipo/estiba para garantizar 95%+ de precisión en futuras ingestas y Mesas de los Lunes.
    """
    __tablename__ = "client_master_profiles"

    id = Column(Integer, primary_key=True, index=True)
    normalized_key = Column(String(150), unique=True, index=True, nullable=False)
    tax_id = Column(String(50), index=True, nullable=True)
    legal_name = Column(String(255), nullable=False)
    trade_name = Column(String(255), index=True, nullable=True)  # Nombre de fantasía / Dador (ej. Molfino, Bunge)
    shipper_plant_name = Column(String(255), nullable=True)      # Planta exportadora / fábrica asociada

    verified_origin_city = Column(String(150), nullable=True)    # Ej. CORDOBA - TIO PUJIO
    verified_dest_city = Column(String(150), nullable=True)      # Ej. CLP - SANTIAGO

    default_equipment = Column(String(30), default="SECO", nullable=False)  # SECO, FRIO, IMO
    pallet_mode = Column(String(30), default="AUTO", nullable=False)        # AUTO, PISO_28, REMONTADO_56, CAJAS_SUELTAS

    is_human_verified = Column(Boolean, default=False, index=True, nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

