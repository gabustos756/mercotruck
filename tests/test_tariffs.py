from app.domain.services.matching_engine import MatchingEngine

def test_matching_with_tariff_fallback():
    routes = [] # Sin viajes históricos
    
    tariffs = [{
        "id": 10,
        "origin": "MENDOZA",
        "destination": "CLP - SANTIAGO",
        "border_crossing": "LIBERTADORES",
        "category": "Todas",
        "sale_price_usd": 2400.0,
        "estimated_carrier_cost_usd": 1900.0,
        "origin_lat": -32.890,
        "origin_lon": -68.845,
        "dest_lat": -33.459,
        "dest_lon": -70.648
    }]
    
    match = MatchingEngine.match_shipment_to_routes_and_tariffs(
        shipment_origin_lat=-32.890,
        shipment_origin_lon=-68.845,
        shipment_dest_lat=-33.459,
        shipment_dest_lon=-70.648,
        shipment_border_crossing="LIBERTADORES",
        shipment_category="Frutas y verduras",
        routes=routes,
        tariffs=tariffs
    )
    
    assert match["source"] == "TARIFARIO_PROPIO"
    assert match["sale_price_usd"] == 2400.0
    assert match["cost_price_usd"] == 1900.0
    assert match["match_type"] == "EXACTO"
