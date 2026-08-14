from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base

class ProspectFavorite(Base):
    __tablename__ = "prospect_favorites"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, default=1)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    prospect = relationship("Prospect", lazy="joined")

    __table_args__ = (
        UniqueConstraint('prospect_id', 'user_id', name='uix_prospect_user_fav'),
    )
