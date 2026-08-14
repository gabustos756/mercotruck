from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional

from app.domain.services.geo_service import haversine_matrix, pasos_coinciden, check_mendoza_transit_disclaimer, check_camionera_mendocina_disclaimer

class MatchingEngine:
    """
    Motor de emparejamiento geoespacial y evaluación de ventajas competitivas para fletes Mercotruck.
    """
    DIAS_RECIENTE = 90

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
        ref_date: Optional[date] = None
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
            ref_date=ref_date
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
        ref_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Calcula la mejor tarifa o ruta coincidente evaluando reciencia de 90 días.
        Prioridad 1: Viajes en los últimos 90 días en MercotruckRoute.
        Prioridad 2: Histórico general en MercotruckRoute.
        Prioridad 3: Tarifario Maestro Propio MercotruckTariff.
        """
        today = ref_date or date.today()
        limite_90d = today - timedelta(days=cls.DIAS_RECIENTE)

        # 1. Intentar match con rutas históricas
        matched_routes = []
        if shipment_origin_lat is not None and shipment_dest_lat is not None and routes:
            for r in routes:
                if r.get("origin_lat") is None or r.get("dest_lat") is None:
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
                is_near = d_orig <= radio_cercano_km or d_dest <= radio_cercano_km

                if is_exact or is_near:
                    trip_d = r.get("trip_date")
                    if isinstance(trip_d, str):
                        try:
                            trip_d = datetime.strptime(trip_d, "%Y-%m-%d").date()
                        except ValueError:
                            trip_d = None

                    is_recent = trip_d >= limite_90d if (trip_d and isinstance(trip_d, date)) else False

                    matched_routes.append({
                        "route": r,
                        "match_type": "EXACTO" if is_exact else "CERCANO",
                        "score": 5 if is_exact else 3,
                        "dist_total": d_orig + d_dest,
                        "is_recent": is_recent,
                        "trip_date": trip_d,
                        "sale_price_usd": r.get("sale_price_usd", 0.0),
                        "cost_price_usd": r.get("cost_price_usd", 0.0)
                    })

        if matched_routes:
            matched_routes.sort(key=lambda x: (not x["is_recent"], x["match_type"] != "EXACTO", x["dist_total"]))
            best = matched_routes[0]

            recent_sales = [m["sale_price_usd"] for m in matched_routes if m["is_recent"] and m["sale_price_usd"] > 0]
            avg_recent = round(sum(recent_sales) / len(recent_sales), 2) if recent_sales else best["sale_price_usd"]

            return {
                "source": "RECIENTE_90D" if best["is_recent"] else "HISTORICO_GENERAL",
                "is_recent_90d": best["is_recent"],
                "match_type": best["match_type"],
                "score": best["score"],
                "sale_price_usd": avg_recent if best["is_recent"] else best["sale_price_usd"],
                "cost_price_usd": best["cost_price_usd"],
                "route_info": best["route"],
                "best_route": best["route"]
            }

        # 2. Intentar match con Tarifario Maestro (MercotruckTariff)
        if shipment_origin_lat is not None and shipment_dest_lat is not None and tariffs:
            matched_tariffs = []
            for t in tariffs:
                if t.get("origin_lat") is None or t.get("dest_lat") is None:
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
                    matched_tariffs.append({
                        "tariff": t,
                        "dist_total": d_orig + d_dest,
                        "sale_price_usd": t.get("sale_price_usd", 0.0),
                        "cost_price_usd": t.get("estimated_carrier_cost_usd", 0.0)
                    })

            if matched_tariffs:
                matched_tariffs.sort(key=lambda x: x["dist_total"])
                best_t = matched_tariffs[0]
                return {
                    "source": "TARIFARIO_PROPIO",
                    "is_recent_90d": False,
                    "match_type": "EXACTO",
                    "score": 4,
                    "sale_price_usd": best_t["sale_price_usd"],
                    "cost_price_usd": best_t["cost_price_usd"],
                    "tariff_info": best_t["tariff"],
                    "best_route": best_t["tariff"]
                }

        return {
            "source": "SIN_MATCH",
            "is_recent_90d": False,
            "match_type": "NINGUNO",
            "score": 0,
            "sale_price_usd": None,
            "cost_price_usd": None,
            "best_route": None
        }
