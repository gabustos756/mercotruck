from app.domain.models.user import User, UserRole
from app.domain.models.prospect import Prospect, ProspectStatus, ProspectFuente
from app.domain.models.contact import ProspectContact
from app.domain.models.shipment import SofttradeShipment
from app.domain.models.route import MercotruckRoute
from app.domain.models.tariff import MercotruckTariff
from app.domain.models.carrier_cost import CarrierCostMatrix
from app.domain.models.quote_history import QuoteHistory, QuoteStatus
from app.domain.models.backhaul import BackhaulOpportunity
from app.domain.models.interaction import CommercialInteraction
from app.domain.models.simulation import SavedQuoteSimulation
from app.domain.models.favorite import ProspectFavorite

__all__ = [
    "User",
    "UserRole",
    "Prospect",
    "ProspectStatus",
    "ProspectFuente",
    "ProspectContact",
    "SofttradeShipment",
    "MercotruckRoute",
    "MercotruckTariff",
    "CarrierCostMatrix",
    "QuoteHistory",
    "QuoteStatus",
    "BackhaulOpportunity",
    "CommercialInteraction",
    "SavedQuoteSimulation",
    "ProspectFavorite"
]
