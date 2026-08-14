import math
from typing import Dict, Any, Optional

class PricingEngine:
    @staticmethod
    def calculate_trucks(gross_weight_kg: float, capacity_per_truck_kg: float = 28500.0) -> int:
        """Calcula el número de camiones requeridos con techo configurable."""
        try:
            kg = float(gross_weight_kg)
            cap = float(capacity_per_truck_kg)
            if kg <= 0 or cap <= 0:
                return 1
            return max(1, int(math.ceil(kg / cap)))
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
        competitor_price_per_truck: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Simulador Interactivo de Cotización y Análisis de Ganancia / Pérdida.
        """
        trucks = cls.calculate_trucks(gross_weight_kg, truck_capacity_kg)
        
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
            "diff_vs_competitor_pct": diff_vs_competitor
        }
