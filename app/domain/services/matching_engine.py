import math
import statistics
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional

from app.domain.services.geo_service import (
    haversine_matrix,
    pasos_coinciden,
    check_mendoza_transit_disclaimer,
    check_camionera_mendocina_disclaimer,
)


class MatchingEngine:
    """
    Motor de emparejamiento geoespacial y de tipo de equipo ('Peras con Peras': SECO vs FRIO vs IMO)
    para evaluar ventajas competitivas reales de tarifas Mercotruck.
    """
    DIAS_RECIENTE = 90

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distancia esférica rápida en km entre dos coordenadas escalares."""
        r = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
        return 2.0 * r * math.asin(min(1.0, math.sqrt(a)))

    @classmethod
    def match_shipment_to_routes(
        cls,
        shipment_origin_lat: Optional[float],
        shipment_origin_lon: Optional[float],
        shipment_dest_lat: Optional[float],
        shipment_dest_lon: Optional[float],
        shipment_border_crossing: str,
        routes: List[Dict[str, Any]],
        radio_exacto_km: float = 50.0,
        radio_cercano_km: float = 100.0,
        ref_date: Optional[date] = None,
        shipment_equipment: str = "SECO",
    ) -> Dict[str, Any]:
        """Alias retrocompatible para emparejamiento con rutas históricas únicamente."""
        return cls.match_shipment_to_routes_and_tariffs(
            shipment_origin_lat=shipment_origin_lat,
            shipment_origin_lon=shipment_origin_lon,
            shipment_dest_lat=shipment_dest_lat,
            shipment_dest_lon=shipment_dest_lon,
            shipment_border_crossing=shipment_border_crossing,
            shipment_category="Todas",
            routes=routes,
            tariffs=[],
            radio_exacto_km=radio_exacto_km,
            radio_cercano_km=radio_cercano_km,
            ref_date=ref_date,
            shipment_equipment=shipment_equipment,
        )

    @classmethod
    def match_shipment_to_routes_and_tariffs(
        cls,
        shipment_origin_lat: Optional[float],
        shipment_origin_lon: Optional[float],
        shipment_dest_lat: Optional[float],
        shipment_dest_lon: Optional[float],
        shipment_border_crossing: str,
        shipment_category: str,
        routes: List[Dict[str, Any]],
        tariffs: List[Dict[str, Any]],
        radio_exacto_km: float = 50.0,
        radio_cercano_km: float = 100.0,
        ref_date: Optional[date] = None,
        shipment_equipment: str = "SECO",
    ) -> Dict[str, Any]:
        """
        Calcula la mejor tarifa o ruta coincidente exigiendo compatibilidad estricta de equipo
        (SECO solo contra SECO, FRIO solo contra FRIO, IMO solo contra IMO) y mediana reciente.
        """
        today = ref_date or date.today()
        limite_90d = today - timedelta(days=cls.DIAS_RECIENTE)
        target_eq = (shipment_equipment or "SECO").strip().upper()

        # 1. Intentar match con rutas históricas del mismo tipo de equipo
        matched_routes = []
        if shipment_origin_lat is not None and shipment_dest_lat is not None and routes:
            for r in routes:
                if r.get("origin_lat") is None or r.get("dest_lat") is None:
                    continue

                route_eq = (r.get("equipment_type") or "SECO").strip().upper()
                if route_eq != target_eq:
                    continue

                d_orig = float(haversine_matrix(
                    shipment_origin_lat, shipment_origin_lon,
                    r["origin_lat"], r["origin_lon"]
                ))

                d_dest = float(haversine_matrix(
                    shipment_dest_lat, shipment_dest_lon,
                    r["dest_lat"], r["dest_lon"]
                ))

                is_exact = d_orig <= radio_exacto_km and d_dest <= radio_exacto_km
                # Para evitar falsos matches lejanos donde solo coincide Santiago como destino,
                # exigimos que ambos extremos estén dentro de un corredor regional coherente (<= 250 km).
                is_near = (
                    (d_orig <= radio_cercano_km and d_dest <= 250.0)
                    or (d_dest <= radio_cercano_km and d_orig <= 250.0)
                )

                if is_exact or is_near:
                    trip_d = r.get("trip_date")
                    if isinstance(trip_d, str):
                        try:
                            trip_d = datetime.strptime(trip_d, "%Y-%m-%d").date()
                        except ValueError:
                            trip_d = None

                    is_recent = trip_d >= limite_90d if (trip_d and isinstance(trip_d, date)) else False

                    # Score points calculation (1 to 7)
                    score_pts = 0
                    if d_orig <= radio_exacto_km:
                        score_pts += 2
                    elif d_orig <= radio_cercano_km:
                        score_pts += 1

                    if d_dest <= radio_exacto_km:
                        score_pts += 2
                    elif d_dest <= radio_cercano_km:
                        score_pts += 1

                    if (
                        shipment_border_crossing
                        and r.get("border_crossing")
                        and (
                            shipment_border_crossing.upper() in r.get("border_crossing", "").upper()
                            or r.get("border_crossing", "").upper() in shipment_border_crossing.upper()
                        )
                    ):
                        score_pts += 1

                    if is_recent:
                        score_pts += 1

                    r_cat = r.get("category") or r.get("merchandise") or ""
                    if shipment_category and r_cat and shipment_category.upper() in r_cat.upper():
                        score_pts += 1

                    score_pts = min(7, max(1, score_pts))

                    matched_routes.append({
                        "route": r,
                        "match_type": "EXACTO" if is_exact else "CERCANO",
                        "score": score_pts,
                        "dist_total": d_orig + d_dest,
                        "is_recent": is_recent,
                        "trip_date": trip_d,
                        "sale_price_usd": r.get("sale_price_usd", 0.0),
                        "cost_price_usd": r.get("cost_price_usd", 0.0),
                        "ruta_orig": r.get("origin", "Mendoza"),
                        "ruta_dest": r.get("destination", "Santiago"),
                        "ruta_paso": r.get("border_crossing", "LIBERTADORES"),
                        "ruta_merc": r.get("merchandise") or r.get("category") or target_eq,
                        "equipment_type": route_eq,
                    })

        if matched_routes:
            matched_routes.sort(
                key=lambda x: (not x["is_recent"], x["match_type"] != "EXACTO", -x["score"], x["dist_total"])
            )
            best = matched_routes[0]

            # Mediana de rutas del mismo nivel (exacto/cercano y reciente) para blindar tarifa propia
            same_tier = [
                m for m in matched_routes
                if m["match_type"] == best["match_type"]
                and m["is_recent"] == best["is_recent"]
                and m["sale_price_usd"] > 0
            ][:15]
            median_sale = (
                round(float(statistics.median([m["sale_price_usd"] for m in same_tier])), 2)
                if same_tier else best["sale_price_usd"]
            )
            valid_costs = [m["cost_price_usd"] for m in same_tier if m["cost_price_usd"] > 0]
            median_cost = (
                round(float(statistics.median(valid_costs)), 2)
                if valid_costs else best["cost_price_usd"]
            )

            final_score = best["score"]
            score_dots = [i < final_score for i in range(7)]

            return {
                "source": "RECIENTE_90D" if best["is_recent"] else "HISTORICO_GENERAL",
                "is_recent_90d": best["is_recent"],
                "match_type": best["match_type"],
                "score": final_score,
                "score_dots": score_dots,
                "sale_price_usd": median_sale,
                "cost_price_usd": median_cost,
                "ruta_orig": best.get("ruta_orig"),
                "ruta_dest": best.get("ruta_dest"),
                "ruta_paso": best.get("ruta_paso"),
                "ruta_merc": best.get("ruta_merc"),
                "equipment_type": best.get("equipment_type", target_eq),
                "route_info": best["route"],
                "best_route": best["route"],
            }

        # 2. Intentar match con Tarifario Maestro (MercotruckTariff) del mismo equipo
        if shipment_origin_lat is not None and shipment_dest_lat is not None and tariffs:
            matched_tariffs = []
            for t in tariffs:
                if t.get("origin_lat") is None or t.get("dest_lat") is None:
                    continue

                t_eq = (t.get("equipment_type") or "SECO").strip().upper()
                if t_eq != target_eq:
                    continue

                d_orig = float(haversine_matrix(
                    shipment_origin_lat, shipment_origin_lon,
                    t["origin_lat"], t["origin_lon"]
                ))
                d_dest = float(haversine_matrix(
                    shipment_dest_lat, shipment_dest_lon,
                    t["dest_lat"], t["dest_lon"]
                ))

                if d_orig <= radio_cercano_km and d_dest <= radio_cercano_km:
                    is_exact = d_orig <= radio_exacto_km and d_dest <= radio_exacto_km
                    score_pts = 6 if is_exact else 4
                    matched_tariffs.append({
                        "tariff": t,
                        "dist_total": d_orig + d_dest,
                        "score": score_pts,
                        "sale_price_usd": t.get("sale_price_usd", 0.0),
                        "cost_price_usd": t.get("estimated_carrier_cost_usd", 0.0),
                        "ruta_orig": t.get("origin", "Mendoza"),
                        "ruta_dest": t.get("destination", "Santiago"),
                        "ruta_paso": t.get("border_crossing", "LIBERTADORES"),
                        "ruta_merc": t.get("category", "General"),
                        "equipment_type": t_eq,
                    })

            if matched_tariffs:
                matched_tariffs.sort(key=lambda x: (-x["score"], x["dist_total"]))
                best_t = matched_tariffs[0]
                final_score = best_t["score"]
                score_dots = [i < final_score for i in range(7)]
                return {
                    "source": "TARIFARIO_PROPIO",
                    "is_recent_90d": False,
                    "match_type": "EXACTO" if final_score >= 5 else "CERCANO",
                    "score": final_score,
                    "score_dots": score_dots,
                    "sale_price_usd": best_t["sale_price_usd"],
                    "cost_price_usd": best_t["cost_price_usd"],
                    "ruta_orig": best_t.get("ruta_orig"),
                    "ruta_dest": best_t.get("ruta_dest"),
                    "ruta_paso": best_t.get("ruta_paso"),
                    "ruta_merc": best_t.get("ruta_merc"),
                    "equipment_type": best_t.get("equipment_type", target_eq),
                    "tariff_info": best_t["tariff"],
                    "best_route": best_t["tariff"],
                }

        score_dots = [False] * 7
        return {
            "source": "SIN_MATCH",
            "is_recent_90d": False,
            "match_type": "CERCANO",
            "score": 2,
            "score_dots": score_dots,
            "sale_price_usd": None,
            "cost_price_usd": None,
            "ruta_orig": "—",
            "ruta_dest": "—",
            "ruta_paso": "—",
            "ruta_merc": "—",
            "equipment_type": target_eq,
            "best_route": None,
        }
