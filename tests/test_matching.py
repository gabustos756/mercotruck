from app.domain.services.geo_service import get_coords, resolver_origen_impo
from app.domain.services.matching_engine import MatchingEngine


def test_get_coords_and_interior_customs():
    lat, lon = get_coords("CORDOBA")
    assert lat is not None and lon is not None
    assert round(lat, 2) == -31.42

    # Aduana 093 Villa María & 015 Colón incorporadas al nomenclador
    assert resolver_origen_impo("LOS LIBERTADORES", "", "093123456") == "VILLA MARÍA"
    assert resolver_origen_impo("OTROS ARGENTINA", "", "015987654") == "COLÓN"
    vm_lat, vm_lon = get_coords("VILLA MARIA")
    assert vm_lat is not None and round(vm_lat, 2) == -32.41


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


def test_strict_equipment_matching_peras_con_peras():
    """Un despacho de FRIO jamás debe cruzarse contra un semirremolque SECO más barato."""
    routes = [
        {
            "id": 10,
            "origin": "CORDOBA - TIO PUJIO",
            "destination": "CLP - SANTIAGO",
            "border_crossing": "LIBERTADORES",
            "equipment_type": "SECO",
            "origin_lat": -32.309,
            "origin_lon": -63.320,
            "dest_lat": -33.459,
            "dest_lon": -70.648,
            "sale_price_usd": 2250,
            "cost_price_usd": 1900,
        },
        {
            "id": 20,
            "origin": "CORDOBA - TIO PUJIO",
            "destination": "CLP - SANTIAGO",
            "border_crossing": "LIBERTADORES",
            "equipment_type": "FRIO",
            "origin_lat": -32.309,
            "origin_lon": -63.320,
            "dest_lat": -33.459,
            "dest_lon": -70.648,
            "sale_price_usd": 3050,
            "cost_price_usd": 2550,
        },
    ]

    match_frio = MatchingEngine.match_shipment_to_routes(
        shipment_origin_lat=-32.309,
        shipment_origin_lon=-63.320,
        shipment_dest_lat=-33.459,
        shipment_dest_lon=-70.648,
        shipment_border_crossing="LIBERTADORES",
        routes=routes,
        shipment_equipment="FRIO",
    )
    assert match_frio["sale_price_usd"] == 3050
    assert match_frio["best_route"]["id"] == 20


def test_tarifario_activo_priority_over_historico_and_border_guard():
    """El Tarifario Activo (Octubre - Actualidad) tiene Prioridad #1 sobre rutas históricas y respeta Paso Fronterizo."""
    chac_lat, chac_lon = get_coords("ARG - BUENOS AIRES - CHACABUCO")
    scl_lat, scl_lon = get_coords("CL - REGIÓN METROPOLITANA - SANTIAGO")
    pilar_cba_lat, _ = get_coords("ARG - CÓRDOBA - PILAR")
    pilar_ba_lat, _ = get_coords("ARG - BUENOS AIRES - PILAR")

    # Pilar (Córdoba) != Pilar (Buenos Aires) y Chacabuco != CABA
    assert round(pilar_cba_lat, 2) == -31.68
    assert round(pilar_ba_lat, 2) == -34.46
    assert round(chac_lat, 2) == -34.64

    old_routes = [
        {
            "id": 99,
            "origin": "BUENOS AIRES - CHACABUCO",
            "destination": "CLP - SANTIAGO",
            "border_crossing": "LIBERTADORES",
            "equipment_type": "SECO",
            "origin_lat": chac_lat,
            "origin_lon": chac_lon,
            "dest_lat": scl_lat,
            "dest_lon": scl_lon,
            "sale_price_usd": 2400.0,
            "cost_price_usd": 2000.0,
            "trip_date": "2026-10-15",
        }
    ]
    active_tariffs = [
        {
            "id": 1,
            "origin": "BUENOS AIRES - CHACABUCO",
            "destination": "CL - SANTIAGO",
            "border_crossing": "PINO HACHADO",
            "category": "Cereales y harinas",
            "equipment_type": "SECO",
            "sale_price_usd": 5300.0,
            "estimated_carrier_cost_usd": 4505.0,
            "origin_lat": chac_lat,
            "origin_lon": chac_lon,
            "dest_lat": scl_lat,
            "dest_lon": scl_lon,
        },
        {
            "id": 2,
            "origin": "BUENOS AIRES - CHACABUCO",
            "destination": "CL - SANTIAGO",
            "border_crossing": "LIBERTADORES",
            "category": "Cereales y harinas",
            "equipment_type": "SECO",
            "sale_price_usd": 3200.0,
            "estimated_carrier_cost_usd": 2720.0,
            "origin_lat": chac_lat,
            "origin_lon": chac_lon,
            "dest_lat": scl_lat,
            "dest_lon": scl_lon,
        },
    ]

    res = MatchingEngine.match_shipment_to_routes_and_tariffs(
        shipment_origin_lat=chac_lat,
        shipment_origin_lon=chac_lon,
        shipment_dest_lat=scl_lat,
        shipment_dest_lon=scl_lon,
        shipment_border_crossing="LOS LIBERTADORES",
        shipment_category="Cereales y harinas",
        routes=old_routes,
        tariffs=active_tariffs,
        shipment_equipment="SECO",
    )
    assert res["source"] == "TARIFARIO_PROPIO"
    assert res["match_type"] == "EXACTO"
    assert res["sale_price_usd"] == 3200.0
    assert res["ruta_paso"] == "LIBERTADORES"
