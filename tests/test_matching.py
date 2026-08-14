from app.domain.services.geo_service import get_coords, haversine_matrix
from app.domain.services.matching_engine import MatchingEngine

def test_get_coords():
    lat, lon = get_coords("CORDOBA")
    assert lat is not None and lon is not None
    assert round(lat, 2) == -31.42

def test_matching_exact():
    routes = [{
        "id": 1,
        "origin": "CORDOBA",
        "destination": "CLP - SANTIAGO",
        "border_crossing": "LIBERTADORES",
        "origin_lat": -31.417,
        "origin_lon": -64.183,
        "dest_lat": -33.459,
        "dest_lon": -70.648,
        "sale_price_usd": 2800
    }]
    
    match = MatchingEngine.match_shipment_to_routes(
        shipment_origin_lat=-31.417,
        shipment_origin_lon=-64.183,
        shipment_dest_lat=-33.459,
        shipment_dest_lon=-70.648,
        shipment_border_crossing="LIBERTADORES",
        routes=routes
    )
    
    assert match["match_type"] == "EXACTO"
    assert match["score"] >= 4
    assert match["best_route"]["id"] == 1
