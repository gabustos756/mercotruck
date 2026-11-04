from datetime import date
from app.domain.services.pricing_engine import PricingEngine
from app.domain.services.scoring_engine import ScoringEngine


def test_calculate_trucks():
    # 28,500 kg ceiling on bulk
    assert PricingEngine.calculate_trucks(28500, 28500) == 1
    assert PricingEngine.calculate_trucks(28501, 28500) == 2
    assert PricingEngine.calculate_trucks(57000, 28500) == 2
    assert PricingEngine.calculate_trucks(60000, 28500) == 3
    # Palletized wood tare allowance (28 pallets = 28.000 kg net + 840 kg pallet tare = 28.840 kg gross -> 1 truck)
    assert PricingEngine.calculate_trucks(28840, 28500, bultos=28) == 1


def test_matias_rule1_exclude_ltl_and_vans():
    # Fast Food Chile: 6.300 kg, 6 pallets, U$S 922 -> EXCLUIDO LTL
    res_ltl = PricingEngine.evaluate_ftl_shipment(6300, bultos=6, freight_total_usd=922, fuente="IMPO")
    assert res_ltl["is_ftl"] is False

    # Techint camioneta urgente: 278 kg, 1 bulto, U$S 2.100 -> EXCLUIDO LTL / CAMIONETA
    res_van = PricingEngine.evaluate_ftl_shipment(278, bultos=1, freight_total_usd=2100, fuente="IMPO")
    assert res_van["is_ftl"] is False

    # Excepción volumétrica válida (Cotral / envases livianos ocupando bodega entera): 11.500 kg, 1.006 cajas, U$S 2.650 -> 1 camión FTL
    res_vol = PricingEngine.evaluate_ftl_shipment(11500, bultos=1006, freight_total_usd=2650, fuente="IMPO")
    assert res_vol["is_ftl"] is True
    assert res_vol["trucks_count"] == 1


def test_matias_rules_2_3_4_real_cases():
    # Regla 2: Pallets estándar a piso (Comercial Cerrillos / Molfino: 25.500 kg, 24 pallets, U$S 3.250) -> 1 camión
    molfino = PricingEngine.evaluate_ftl_shipment(25500, bultos=24, freight_total_usd=3250, fuente="IMPO")
    assert molfino["is_ftl"] is True
    assert molfino["trucks_count"] == 1
    assert molfino["raw_freight_per_truck_usd"] == 3250.0
    assert "PISO" in molfino["stowage_type"]

    # Regla 3: 56 pallets remontados <= 28.500 kg -> 1 camión remontado
    remontado = PricingEngine.evaluate_ftl_shipment(26800, bultos=56, freight_total_usd=2700, fuente="IMPO")
    assert remontado["is_ftl"] is True
    assert remontado["trucks_count"] == 1
    assert "REMONTADOS" in remontado["stowage_type"]

    # Regla 4a: > 56 bultos PERO <= 28.500 kg -> Cajas sueltas a piso = 1 camión (S.C. Johnson: 27.720 kg, 4.816 cajas, U$S 2.300)
    sc_johnson = PricingEngine.evaluate_ftl_shipment(27720, bultos=4816, freight_total_usd=2300, fuente="IMPO")
    assert sc_johnson["is_ftl"] is True
    assert sc_johnson["trucks_count"] == 1
    assert sc_johnson["raw_freight_per_truck_usd"] == 2300.0
    assert "CAJAS SUELTAS" in sc_johnson["stowage_type"]

    # Regla 4b (cajas multi-camión): Agrocommerce / Bunge: 55.524 kg, 5.280 cajas, U$S 4.450 -> 2 camiones a U$S 2.225
    bunge = PricingEngine.evaluate_ftl_shipment(55524, bultos=5280, freight_total_usd=4450, fuente="IMPO")
    assert bunge["is_ftl"] is True
    assert bunge["trucks_count"] == 2
    assert bunge["raw_freight_per_truck_usd"] == 2225.0

    # Regla 4b (pallets multi-camión rescatado > U$S 8.000): Unilever: 81.190 kg, 84 pallets, U$S 8.463 -> 3 camiones a U$S 2.821
    unilever = PricingEngine.evaluate_ftl_shipment(81190, bultos=84, freight_total_usd=8463, fuente="IMPO")
    assert unilever["is_ftl"] is True
    assert unilever["trucks_count"] == 3
    assert unilever["raw_freight_per_truck_usd"] == 2821.0

    # Tara bruta aduanera: 28 pallets de arroz (28.840 kg Kgs. Brutos, U$S 2.850) = 1 camión (no 2)
    arroz_tara = PricingEngine.evaluate_ftl_shipment(28840, bultos=28, freight_total_usd=2850, fuente="IMPO")
    assert arroz_tara["is_ftl"] is True
    assert arroz_tara["trucks_count"] == 1
    assert arroz_tara["raw_freight_per_truck_usd"] == 2850.0

    # Doble equipo liviano en 29.120 kg: 56 pallets de fideos desde Necochea (U$S 5.800) = 2 camiones de 28 plts
    pasta_doble = PricingEngine.evaluate_ftl_shipment(29120, bultos=56, freight_total_usd=5800, fuente="IMPO")
    assert pasta_doble["is_ftl"] is True
    assert pasta_doble["trucks_count"] == 2
    assert pasta_doble["raw_freight_per_truck_usd"] == 2900.0

    # Granel / Cisterna con Bultos=1 (Bunge 166.750 kg, 1 lote granel, U$S 18.312) = 6 camiones granel (nunca "1 plts")
    bunge_granel = PricingEngine.evaluate_ftl_shipment(166750, bultos=1, freight_total_usd=18312, fuente="IMPO")
    assert bunge_granel["is_ftl"] is True
    assert bunge_granel["trucks_count"] == 6
    assert bunge_granel["raw_freight_per_truck_usd"] == 3052.0
    assert "GRANEL" in bunge_granel["stowage_type"]
    assert "plts" not in bunge_granel["stowage_type"]

    # Masterfoods 141 pallets remontados (77.227 kg, U$S 6.300) = 3 camiones a U$S 2.100 (no 5)
    masterfoods = PricingEngine.evaluate_ftl_shipment(77227, bultos=141, freight_total_usd=6300, fuente="IMPO")
    assert masterfoods["is_ftl"] is True
    assert masterfoods["trucks_count"] == 3
    assert masterfoods["raw_freight_per_truck_usd"] == 2100.0

    # Unilever 90 pallets aerosoles no apilables (62.059 kg, U$S 11.366) = 3 camiones a piso a U$S 3.788,67
    unilever_aerosol = PricingEngine.evaluate_ftl_shipment(62059, bultos=90, freight_total_usd=11366, fuente="IMPO")
    assert unilever_aerosol["is_ftl"] is True
    assert unilever_aerosol["trucks_count"] == 3
    assert round(unilever_aerosol["raw_freight_per_truck_usd"]) == 3789


def test_classify_equipment_and_median_market_price():
    assert PricingEngine.classify_equipment("QUESO MOZZARELLA CONGELADO") == "FRIO"
    assert PricingEngine.classify_equipment("LECHE EN POLVO ENTERA EN BOLSAS") == "SECO"
    assert PricingEngine.classify_equipment("PEROXIDO DE HIDROGENO CORROSIVO") == "IMO"
    assert PricingEngine.classify_equipment("GAS PROPANO LICUADO") == "IMO"
    assert PricingEngine.classify_equipment("PETROLEO CRUDO") == "IMO"
    assert PricingEngine.classify_equipment("HARINA", unit_raw="FURGON REFRIGERADO") == "FRIO"

    # Selección de corredor principal sin contaminar ruta larga ($3.070) con ruta corta Cuyo ($1.680)
    corridor = PricingEngine.select_primary_corridor_and_price([
        {"shipment_date": date(2026, 6, 20), "trucks_count": 3, "real_origin_city": "SAN LORENZO", "real_destination_city": "CLP - SANTIAGO", "estimated_real_freight_per_truck_usd": 3070.0},
        {"shipment_date": date(2026, 6, 15), "trucks_count": 3, "real_origin_city": "SAN LORENZO", "real_destination_city": "CLP - SANTIAGO", "estimated_real_freight_per_truck_usd": 3070.0},
        {"shipment_date": date(2026, 6, 10), "trucks_count": 2, "real_origin_city": "MENDOZA", "real_destination_city": "LOS ANDES", "estimated_real_freight_per_truck_usd": 1680.0},
    ])
    assert corridor["primary_origin"] == "SAN LORENZO"
    assert corridor["corridor_median_usd"] == 3070.0
    assert len(corridor["corridors"]) == 2

    # Mediana inmune a un viaje con estadía atípica ($5.900)
    med = PricingEngine.compute_robust_market_price([
        {"shipment_date": date(2026, 9, 1), "trucks_count": 1, "estimated_real_freight_per_truck_usd": 2700.0},
        {"shipment_date": date(2026, 9, 5), "trucks_count": 1, "estimated_real_freight_per_truck_usd": 2750.0},
        {"shipment_date": date(2026, 9, 10), "trucks_count": 1, "estimated_real_freight_per_truck_usd": 5900.0},
    ])
    assert med == 2750.0


def test_price_difference_pct():
    diff = PricingEngine.calculate_price_difference_pct(2500, 3000)
    assert diff == -16.7


def test_simulate_quote():
    sim = PricingEngine.simulate_quote(
        gross_weight_kg=57000,
        target_sale_price_per_truck=3000,
        estimated_carrier_cost_per_truck=2200,
        truck_capacity_kg=28500,
        extra_costs=100,
        competitor_price_per_truck=3200
    )
    assert sim["trucks_count"] == 2
    assert sim["total_revenue"] == 6000.0
    assert sim["total_carrier_cost"] == 4400.0
    assert sim["total_cost"] == 4500.0
    assert sim["net_profit"] == 1500.0
    assert sim["margin_pct"] == 25.0
    assert sim["is_profitable"] is True
    assert sim["diff_vs_competitor_pct"] == -6.2
