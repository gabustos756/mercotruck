import math
import statistics
from typing import Dict, Any, List, Optional


class PricingEngine:
    """
    Motor de Capacidad Real y Precio FTL (Reglas Operativas Validadas con Matías Palomino):
    1. Exclusión estricta de LTL (consolidados y camionetas dedicadas chicas).
    2. Tope físico/legal inquebrantable de 28.500 kg por semirremolque (pallets estándar: 1.000–1.250 kg).
    3. Hasta 56 bultos con peso <= 28.500 kg = 1 camión (a piso <=30 o remontado 31–56).
    4. Más de 56 bultos:
       - Si peso <= 28.500 kg -> son cajas/bolsas sueltas a piso = 1 camión.
       - Si peso > 28.500 kg -> cuadra peso legal (ceil(kg / 28.500)) con bultos (cajas <350 kg/bto vs pallets >=350 kg/bto).
    5. Filtro de cordura por camión aplicado DESPUÉS de dividir por camiones reales (rescata multi-camiones > U$S 8.000).
    """

    MAX_LEGAL_KG_PER_TRUCK = 28500.0
    # En Aduana ("Kgs. Brutos") los 24–30 pallets de madera/envases suman ~700–1.300 kg de tara sobre los 28,5 tn netos
    MAX_SINGLE_TRUCK_GROSS_KG = 29800.0
    PALLETIZED_TRUCK_GROSS_KG = 29300.0
    MAX_PALLET_UNIT_KG = 2500.0

    # Palabras clave de exclusión seca (no requieren frío aunque sean alimentos/lácteos)
    _DRY_EXCLUSIONS = (
        "EN POLVO", "LECHE EN POLVO", "SUERO EN POLVO", "DESHIDRATAD",
        "UHT", "LARGA VIDA", "CONSERVA", "ENLATAD", "ESTERILIZAD",
        "HARINA DE PESCADO", "HARINA DE CARNE", "ACEITE DE PESCADO",
    )

    _REEFER_KEYWORDS = (
        "QUESO", "MOZZARELLA", "MUZZARELLA", "MANTECA", "MANTEQUILLA",
        "YOGUR", "CREMA DE LECHE", "DULCE DE LECHE REPOSTERO REFRIG",
        "CARNE BOVINA", "CARNE VACUNA", "CARNE PORCINA", "CARNE CONGELADA",
        "CARNE ENFRIADA", "CORTE VACUNO", "CORTES BOVINOS", "POLLO CONGELADO",
        "TROZOS DE POLLO", "SALMON", "SALMÓN", "TRUCHA", "MERLUZA",
        "PESCADO CONGELADO", "FILETE DE", "CAMARON", "LANGOSTINO",
        "HELADO", "CONGELAD", "REFRIGERAD", "ENFRIAD", "FRESCO REFRIG",
        "PAPAS PREFRITAS", "FRUTILLAS CONGELADAS", "BERRIES CONGELADOS",
    )

    _IMO_KEYWORDS = (
        "PELIGROS", "INFLAMABLE", "CORROSIV", "ACIDO SULFURICO",
        "ACIDO CLORHIDRICO", "ÁCIDO SULFÚRICO", "ÁCIDO CLORHÍDRICO",
        "ACIDO NITRICO", "ÁCIDO NÍTRICO", "ACIDO FOSFORICO",
        "PEROXIDO", "PERÓXIDO", "CIANURO", "HIPOCLORITO",
        "SODA CAUSTICA LIQUIDA", "HIDROXIDO DE SODIO EN SOLUCION",
        "SOLVENTE INFLAMABLE", "EXPLOSIV", "NITRATO DE AMONIO",
        "GAS LICUADO", "GAS PROPANO", "GAS BUTANO", "MEZCLA GAS", "GLP",
        "PETROLEO CRUDO", "PETRÓLEO CRUDO", "NAFTA", "GASOLINA", "GASOIL",
        "METANOL", "TOLUENO", "XILENO", "CLASE IMO",
    )

    @classmethod
    def classify_equipment(
        cls,
        merchandise_desc: str = "",
        category: str = "",
        unit_raw: str = "",
        imo_raw: str = "",
    ) -> str:
        """Clasifica el equipo requerido en 'FRIO', 'IMO' o 'SECO'."""
        u = (unit_raw or "").strip().upper()
        imo = (imo_raw or "").strip().upper()

        # 1. Clasificación explícita desde Histórico Mercotruck
        if any(k in u for k in ("REFRIGERADO", "CONGELADO", "REEFER", "FRIO", "FRÍO", "TERMICO", "TÉRMICO")):
            return "FRIO"
        if imo in ("SI", "SÍ", "YES", "IMO", "1", "TRUE"):
            return "IMO"

        # 2. Clasificación por descripción aduanera y categoría
        desc = (merchandise_desc or "").strip().upper()
        cat = (category or "").strip()

        if desc:
            if any(k in desc for k in cls._IMO_KEYWORDS):
                return "IMO"
            is_dry_shelf = any(ex in desc for ex in cls._DRY_EXCLUSIONS)
            if not is_dry_shelf and any(k in desc for k in cls._REEFER_KEYWORDS):
                return "FRIO"

        if cat in ("Carnes y derivados", "Salmon y pesca"):
            if not any(ex in desc for ex in cls._DRY_EXCLUSIONS):
                return "FRIO"

        return "SECO"

    @classmethod
    def evaluate_ftl_shipment(
        cls,
        gross_weight_kg: float,
        bultos: int = 0,
        freight_total_usd: float = 0.0,
        fuente: str = "IMPO",
        pallet_mode: str = "AUTO",
    ) -> Dict[str, Any]:
        """
        Evalúa si un CRT/DUA corresponde a carga FTL (camión completo),
        descarta LTL/camionetas (Regla 1), calcula camiones reales (Reglas 2, 3 y 4)
        y valida el rango de flete por camión.
        """
        try:
            kg = float(gross_weight_kg or 0.0)
        except (ValueError, TypeError):
            kg = 0.0

        try:
            b = max(0, int(round(float(bultos or 0))))
        except (ValueError, TypeError):
            b = 0

        try:
            flete = float(freight_total_usd or 0.0)
        except (ValueError, TypeError):
            flete = 0.0

        fuente_u = (fuente or "IMPO").strip().upper()
        mode_u = (pallet_mode or "AUTO").strip().upper()

        # --- REGLA 1: Exclusión total de LTL (Consolidados y Camionetas) ---
        min_doc_freight = 1400.0 if fuente_u == "IMPO" else 950.0
        if kg <= 0 or flete < min_doc_freight:
            return {
                "is_ftl": False,
                "exclude_reason": "LTL_FLETE_BAJO",
                "trucks_count": 0,
                "raw_freight_per_truck_usd": 0.0,
                "stowage_type": "EXCLUIDO LTL",
                "calc_log": "Excluido por flete consolidado (LTL)",
            }

        if fuente_u == "IMPO":
            # Excepción volumétrica FTL: entre 8.500 y 14.000 kg pero ocupando bodega completa (>=22 pallets o >=500 cajas)
            is_volumetric_ftl = kg >= 8500.0 and (b >= 22 or b >= 500)
            if kg < 14000.0 and not is_volumetric_ftl:
                if (b > 0 and b < 20) or kg < 11000.0:
                    return {
                        "is_ftl": False,
                        "exclude_reason": "LTL_PESO_Y_BULTOS",
                        "trucks_count": 0,
                        "raw_freight_per_truck_usd": 0.0,
                        "stowage_type": "EXCLUIDO LTL / CAMIONETA",
                        "calc_log": "Excluido por peso/bultos de carga parcial (LTL)",
                    }
        else:
            # EXPO (Chile -> Arg): sin columna numérica de bultos, piso físico FTL de 12.000 kg
            if kg < 12000.0:
                return {
                    "is_ftl": False,
                    "exclude_reason": "LTL_EXPO_PESO_BAJO",
                    "trucks_count": 0,
                    "raw_freight_per_truck_usd": 0.0,
                    "stowage_type": "EXCLUIDO LTL EXPO",
                    "calc_log": "Excluido por peso parcial en retorno",
                }

        # --- REGLAS 2, 3 y 4: Tope 28.500 kg netos (+ tara bruta envase), Granel/Cisterna vs Pallets/Cajas ---
        max_kg = cls.MAX_LEGAL_KG_PER_TRUCK
        is_bulk_lot = (b <= 0) or ((kg / b) > cls.MAX_PALLET_UNIT_KG)

        # Un equipo completo de 24–30 pallets de 1.000 kg netos declara 28.500–29.800 Kgs. Brutos en Aduana por la tara de madera.
        # Solo es doble camión en 28,5–29,8 tn si trae 33–56 pallets livianos con flete de 2 equipos (> U$S 4.500).
        is_single_truck = (kg <= max_kg) or (
            kg <= cls.MAX_SINGLE_TRUCK_GROSS_KG
            and not (33 <= b <= 56 and flete > 4500.0)
            and flete <= 5200.0
        )

        if is_single_truck:
            trucks = 1
            if is_bulk_lot:
                lbl_bulk = "FTL PESO (28,5 tn)" if (fuente_u == "EXPO" and b <= 0) else f"FTL GRANEL / CISTERNA ({kg:,.0f} kg)"
                stowage_type = lbl_bulk
                calc_log = f"{kg:,.0f} kg ≤ 28,5 tn → <span class='cr'>1 cam</span>"
            elif b <= 30:
                kg_b = kg / b
                stowage_type = f"PALLETS A PISO ({b} plts · {kg_b:,.0f} kg/plt)"
                calc_log = f"{kg:,.0f} kg · {b} plts a piso ({kg_b:,.0f} kg/plt) → <span class='cr'>1 cam</span>"
            elif b <= 56:
                kg_b = kg / b
                stowage_type = f"PALLETS REMONTADOS ({b} plts · {kg_b:,.0f} kg/plt)"
                calc_log = f"{kg:,.0f} kg · {b} plts remontados (≤56) → <span class='cr'>1 cam</span>"
            else:
                # Regla 4a: > 56 bultos pero <= 28,5 tn netos -> Cajas / bolsas sueltas a piso = 1 camión
                kg_b = kg / b
                stowage_type = f"CAJAS SUELTAS A PISO ({b:,} btos · {kg_b:.1f} kg/bto)"
                calc_log = f"{kg:,.0f} kg · {b:,} cajas/bolsas a piso ({kg_b:.1f} kg/bto) → <span class='cr'>1 cam</span>"
        else:
            # Multi-camión: diferenciar Granel/Cisterna (múltiplos exactos de 28,5 tn) vs Pallets/Cajas (con tara de envase)
            if is_bulk_lot:
                trucks = max(2, int(math.ceil(kg / max_kg)))
                kg_cam = round(kg / trucks)
                stowage_type = f"GRANEL / CISTERNA ({trucks} eq · ~{kg_cam:,.0f} kg/cam)"
                calc_log = f"{kg:,.0f} kg granel/cisterna ÷ 28,5 tn → <span class='cr'>{trucks} cam</span> (~{kg_cam:,.0f} kg/cam)"
            elif mode_u == "CAJAS_SUELTAS":
                n_weight = max(2, int(math.ceil(kg / cls.PALLETIZED_TRUCK_GROSS_KG)))
                trucks = n_weight
                stowage_type = f"CAJAS SUELTAS MULTI ({b:,} btos)"
                calc_log = f"{kg:,.0f} kg ({b:,} cajas) ÷ 28,5 tn → <span class='cr'>{trucks} cam</span>"
            else:
                n_weight = max(2, int(math.ceil(kg / cls.PALLETIZED_TRUCK_GROSS_KG)))
                kg_per_bulto = kg / b
                if kg_per_bulto < 350.0:
                    # Cajas, bolsas, sacos o tambores chicos -> manda estrictamente el peso
                    trucks = n_weight
                    stowage_type = f"CAJAS SUELTAS MULTI ({b:,} btos · {kg_per_bulto:.1f} kg/bto)"
                    calc_log = (
                        f"{kg:,.0f} kg ({b:,} cajas de {kg_per_bulto:.1f} kg) ÷ 28,5 tn "
                        f"→ <span class='cr'>{trucks} cam</span>"
                    )
                else:
                    # Son pallets reales (350 a 2.500 kg/pallet)
                    if mode_u == "PISO_28":
                        trucks = max(n_weight, int(math.ceil(b / 28.0)))
                    elif mode_u == "REMONTADO_56":
                        trucks = max(n_weight, int(math.ceil(b / 56.0)))
                    else:
                        if kg_per_bulto >= 850.0:
                            # Pallets estándar pesados (850–1.250+ kg): van a piso (máx 30 posiciones/camión)
                            trucks = max(n_weight, int(math.ceil(b / 30.0)))
                        else:
                            # Pallets medianos/livianos (350–849 kg): admiten remontado hasta 56/camión,
                            # salvo mercadería frágil no apilable donde el flete total confirma estiba a piso.
                            n_remontado = max(n_weight, int(math.ceil(b / 56.0)))
                            n_piso = max(n_weight, int(math.ceil(b / 30.0)))
                            if (
                                n_piso > n_remontado
                                and flete > 0
                                and (flete / n_remontado) > 4600.0
                                and (flete / n_piso) >= 2100.0
                            ):
                                trucks = n_piso
                            else:
                                trucks = n_remontado

                    plts_cam = round(b / trucks, 1)
                    estiba_lbl = "remontados" if plts_cam > 30 else "a piso"
                    stowage_type = f"PALLETS MULTI ({b} plts · ~{plts_cam:g}/cam {estiba_lbl})"
                    calc_log = (
                        f"{kg:,.0f} kg · {b} plts ({kg_per_bulto:,.0f} kg/plt) "
                        f"→ <span class='cr'>{trucks} cam</span> (~{plts_cam:g} plts/cam)"
                    )

        raw_per_truck = round(flete / trucks, 2)

        # --- Filtro de cordura POR CAMIÓN (rescata CRTs multi-camión > U$S 8.000) ---
        min_truck_usd = 1100.0 if fuente_u == "IMPO" else 850.0
        max_truck_usd = 6800.0
        if raw_per_truck < min_truck_usd or raw_per_truck > max_truck_usd:
            return {
                "is_ftl": False,
                "exclude_reason": "OUTLIER_FLETE_POR_CAMION",
                "trucks_count": trucks,
                "raw_freight_per_truck_usd": raw_per_truck,
                "stowage_type": stowage_type,
                "calc_log": calc_log,
            }

        return {
            "is_ftl": True,
            "exclude_reason": None,
            "trucks_count": trucks,
            "raw_freight_per_truck_usd": raw_per_truck,
            "stowage_type": stowage_type,
            "calc_log": calc_log,
        }

    @classmethod
    def calibrate_real_freight_usd(
        cls,
        raw_freight_per_truck_usd: float,
        incoterm: str = "",
        origin_str: str = "",
        fuente: str = "IMPO",
    ) -> float:
        """
        Calibra el flete aduanero por camión hacia el valor puerta-a-puerta real pagado por el cliente.
        Validado contra los 928 CRTs propios de Mercotruck en aduana (CYS/OTRO reflejan tarifa real 1:1;
        solo cláusulas EXW/FCA/FOB de larga distancia con flete truncado a frontera reciben ajuste de tramo chileno).
        """
        raw = float(raw_freight_per_truck_usd or 0.0)
        if raw <= 0:
            return 0.0

        inc = (incoterm or "").strip().upper()
        orig = (origin_str or "").strip().upper()

        if (fuente or "IMPO").upper() == "IMPO" and inc in ("EXW", "FCA", "FOB"):
            is_short_cuyo = any(c in orig for c in ("MENDOZA", "SAN JUAN", "SAN LUIS", "LUJAN DE CUYO"))
            if not is_short_cuyo and raw < 1850.0:
                return round(min(raw + 450.0, 2450.0), 2)

        return round(raw, 2)

    @staticmethod
    def compute_robust_market_price(shipments: List[Dict[str, Any]]) -> float:
        """
        Calcula el precio real pagado representativo de un cliente usando la MEDIANA ponderada por camión
        de sus despachos FTL recientes (últimos 180 días si existen), eliminando distorsiones por estadías
        invernales aisladas o errores de tipeo aduanero.
        """
        if not shipments:
            return 0.0

        dated = [s for s in shipments if s.get("shipment_date") is not None]
        pool = shipments
        if dated:
            max_d = max(s["shipment_date"] for s in dated)
            recent = [
                s for s in dated
                if (max_d - s["shipment_date"]).days <= 180
            ]
            if recent:
                pool = recent

        expanded_truck_prices: List[float] = []
        for s in pool:
            price = float(
                s.get("estimated_real_freight_per_truck_usd")
                or s.get("freight_per_truck_usd")
                or 0.0
            )
            trucks = max(1, int(s.get("trucks_count") or 1))
            if price > 0:
                expanded_truck_prices.extend([price] * min(trucks, 10))

        if not expanded_truck_prices:
            return 0.0

        return round(float(statistics.median(expanded_truck_prices)), 2)

    @classmethod
    def select_primary_corridor_and_price(cls, shipments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Determina el Corredor Principal Operativo del cliente (mayor volumen de camiones en ventana reciente)
        y calcula la mediana FTL real pagada ESPECÍFICAMENTE en ese corredor, evitando mezclar tramos cortos
        (ej. Mendoza -> Chile) con tramos largos (ej. Córdoba/Bs.As. -> Chile).
        """
        if not shipments:
            return {
                "primary_origin": None,
                "primary_destination": None,
                "corridor_median_usd": 0.0,
                "corridors": [],
            }

        dated = [s for s in shipments if s.get("shipment_date") is not None]
        recent_pool = shipments
        if dated:
            max_d = max(s["shipment_date"] for s in dated)
            rec = [s for s in dated if (max_d - s["shipment_date"]).days <= 180]
            if rec:
                recent_pool = rec

        # Agrupar volumen reciente por origen real (nivel planta/ciudad) para elegir corredor dominante
        by_corridor: Dict[tuple, List[Dict[str, Any]]] = {}
        recent_trucks_by_corridor: Dict[tuple, int] = {}
        for s in shipments:
            orig = (s.get("real_origin_city") or s.get("origin_str") or "ORIGEN").strip()
            dest = (s.get("real_destination_city") or s.get("destination_str") or "DESTINO").strip()
            by_corridor.setdefault((orig, dest), []).append(s)

        for s in recent_pool:
            orig = (s.get("real_origin_city") or s.get("origin_str") or "ORIGEN").strip()
            dest = (s.get("real_destination_city") or s.get("destination_str") or "DESTINO").strip()
            recent_trucks_by_corridor[(orig, dest)] = recent_trucks_by_corridor.get((orig, dest), 0) + max(1, int(s.get("trucks_count") or 1))

        corridor_summaries = []
        for (orig, dest), c_ships in by_corridor.items():
            c_trucks = sum(max(1, int(x.get("trucks_count") or 1)) for x in c_ships)
            c_rec_trucks = recent_trucks_by_corridor.get((orig, dest), 0)
            c_med = cls.compute_robust_market_price(c_ships)
            prices = [
                float(x.get("estimated_real_freight_per_truck_usd") or x.get("freight_per_truck_usd") or 0.0)
                for x in c_ships
                if float(x.get("estimated_real_freight_per_truck_usd") or x.get("freight_per_truck_usd") or 0.0) > 0
            ]
            prods = [x.get("product_clean") for x in c_ships if x.get("product_clean") and x.get("product_clean") not in ("MERCADERIA GENERAL", "MERCADERÍA GENERAL")]
            top_prod = prods[0] if prods else (c_ships[0].get("category") or "Mercadería General")
            corridor_summaries.append({
                "origin": orig,
                "destination": dest,
                "trucks": c_trucks,
                "recent_trucks": c_rec_trucks,
                "docs": len(c_ships),
                "median_usd": c_med,
                "min_usd": round(min(prices), 0) if prices else 0.0,
                "max_usd": round(max(prices), 0) if prices else 0.0,
                "top_product": top_prod,
            })

        # Ordenar por camiones recientes (y en empate por camiones históricos totales)
        corridor_summaries.sort(key=lambda x: (x["recent_trucks"], x["trucks"]), reverse=True)
        best = corridor_summaries[0]
        primary_key = (best["origin"], best["destination"])
        primary_ships = by_corridor[primary_key]
        if len(primary_ships) < 2:
            same_orig = [s for s in shipments if (s.get("real_origin_city") or s.get("origin_str") or "").strip() == best["origin"]]
            if len(same_orig) >= 2:
                primary_ships = same_orig

        corridor_median = cls.compute_robust_market_price(primary_ships)
        if corridor_median <= 0:
            corridor_median = cls.compute_robust_market_price(shipments)

        for idx, cs in enumerate(corridor_summaries):
            cs["is_primary"] = (idx == 0)

        return {
            "primary_origin": best["origin"],
            "primary_destination": best["destination"],
            "corridor_median_usd": corridor_median,
            "corridors": corridor_summaries,
        }

    @staticmethod
    def calculate_trucks(
        gross_weight_kg: float,
        capacity_per_truck_kg: float = 28500.0,
        bultos: int = 0,
    ) -> int:
        """Calcula el número de camiones requeridos respetando tope 28,5 tn (+ tara envase) y cuadre de pallets."""
        try:
            kg = float(gross_weight_kg)
            cap = float(capacity_per_truck_kg)
            if kg <= 0 or cap <= 0:
                return 1
            b = max(0, int(bultos or 0))
            is_bulk = (b <= 0) or ((kg / b) > PricingEngine.MAX_PALLET_UNIT_KG)
            gross_cap = cap if is_bulk else max(cap, PricingEngine.PALLETIZED_TRUCK_GROSS_KG)
            if kg <= (cap if is_bulk else max(cap, PricingEngine.MAX_SINGLE_TRUCK_GROSS_KG)):
                return 1
            n_weight = max(2, int(math.ceil(kg / gross_cap)))
            if not is_bulk and (kg / b) >= 850.0:
                return max(n_weight, int(math.ceil(b / 30.0)))
            if not is_bulk and b > 56 and (kg / b) >= 350.0:
                return max(n_weight, int(math.ceil(b / 56.0)))
            return n_weight
        except (ValueError, TypeError):
            return 1

    @staticmethod
    def calculate_price_difference_pct(mercotruck_price: float, competitor_price: float) -> Optional[float]:
        """
        Calcula la diferencia porcentual del precio Mercotruck respecto al competidor.
        Resultado negativo (ej. -15%) indica que Mercotruck es 15% MÁS BARATO.
        """
        if not competitor_price or competitor_price <= 0:
            return None
        return round(((mercotruck_price - competitor_price) / competitor_price) * 100.0, 1)

    @classmethod
    def simulate_quote(
        cls,
        gross_weight_kg: float,
        target_sale_price_per_truck: float,
        estimated_carrier_cost_per_truck: float,
        truck_capacity_kg: float = 28500.0,
        extra_costs: float = 0.0,
        competitor_price_per_truck: Optional[float] = None,
        bultos: int = 0,
    ) -> Dict[str, Any]:
        """
        Simulador Interactivo de Cotización y Análisis de Ganancia / Pérdida.
        """
        trucks = cls.calculate_trucks(gross_weight_kg, truck_capacity_kg, bultos=bultos)

        total_revenue = round(trucks * target_sale_price_per_truck, 2)
        total_carrier_cost = round(trucks * estimated_carrier_cost_per_truck, 2)
        total_cost = round(total_carrier_cost + extra_costs, 2)

        net_profit = round(total_revenue - total_cost, 2)
        margin_pct = round((net_profit / total_revenue * 100.0), 1) if total_revenue > 0 else 0.0

        diff_vs_competitor = None
        if competitor_price_per_truck:
            diff_vs_competitor = cls.calculate_price_difference_pct(
                target_sale_price_per_truck, competitor_price_per_truck
            )

        return {
            "gross_weight_kg": gross_weight_kg,
            "truck_capacity_kg": truck_capacity_kg,
            "trucks_count": trucks,
            "target_sale_price_per_truck": target_sale_price_per_truck,
            "estimated_carrier_cost_per_truck": estimated_carrier_cost_per_truck,
            "extra_costs": extra_costs,
            "total_revenue": total_revenue,
            "total_carrier_cost": total_carrier_cost,
            "total_cost": total_cost,
            "net_profit": net_profit,
            "margin_pct": margin_pct,
            "is_profitable": net_profit > 0,
            "competitor_price_per_truck": competitor_price_per_truck,
            "diff_vs_competitor_pct": diff_vs_competitor,
        }
