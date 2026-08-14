from typing import Dict, Any, Optional, List

class CopilotEngine:
    """
    Motor Inteligente de Ayuda en la Toma de Decisiones Comerciales (AI Copilot).
    Proporciona tácticas de negociación, piso mínimo permitido y 3 escenarios de cotización.
    """
    
    MIN_CORPORATE_MARGIN_PCT = 15.0 # Margen piso mínimo permitido
    
    @classmethod
    def generate_advice(
        cls,
        prospect_name: str,
        total_trucks: int,
        competitor_price_per_truck: float,
        estimated_carrier_cost_per_truck: float,
        mercotruck_hist_price_per_truck: Optional[float] = None,
        category: str = "General"
    ) -> Dict[str, Any]:
        
        comp_price = float(competitor_price_per_truck or 0.0)
        cost_price = float(estimated_carrier_cost_per_truck or 0.0)
        
        if comp_price <= 0:
            comp_price = mercotruck_hist_price_per_truck or (cost_price * 1.25)
            
        if cost_price <= 0:
            cost_price = comp_price * 0.80
            
        # 1. Piso Mínimo Innegociable (Piso de Margen Mínimo 15%)
        floor_price_usd = round(cost_price / (1.0 - (cls.MIN_CORPORATE_MARGIN_PCT / 100.0)), 0)
        
        # 2. Generar 3 Escenarios de Cotización
        # A. Escenario Agresivo (-10% vs Competencia)
        price_agresivo = max(floor_price_usd, round(comp_price * 0.90, 0))
        renta_agresiva = round(price_agresivo - cost_price, 0)
        margin_agresivo = round((renta_agresiva / price_agresivo * 100.0), 1) if price_agresivo > 0 else 0
        ahorro_agresivo = round(comp_price - price_agresivo, 0)
        
        # B. Escenario Recomendado (-5% vs Competencia)
        price_recomendado = max(floor_price_usd, round(comp_price * 0.95, 0))
        renta_recomendada = round(price_recomendado - cost_price, 0)
        margin_recomendado = round((renta_recomendada / price_recomendado * 100.0), 1) if price_recomendado > 0 else 0
        ahorro_recomendado = round(comp_price - price_recomendado, 0)

        # C. Escenario Max-Margin (Mismo precio competencia o +2%)
        price_max_margin = round(comp_price * 1.02, 0) if comp_price > cost_price * 1.3 else round(comp_price, 0)
        renta_max = round(price_max_margin - cost_price, 0)
        margin_max = round((renta_max / price_max_margin * 100.0), 1) if price_max_margin > 0 else 0

        # 3. Argumentos Comerciales Cuantitativos
        trucks = max(1, total_trucks)
        total_ahorro_rec = ahorro_recomendado * trucks
        
        pitch_argument = (
          f"Ofrecer a {prospect_name} una tarifa de ${price_recomendado:,.0f} U$S por camión. "
          f"Le genera un ahorro directo de ${ahorro_recomendado:,.0f} U$S por viaje "
          f"(${total_ahorro_rec:,.0f} U$S total en los {trucks} camiones del lote)."
        )
        
        warning_alert = (
          f"Atención: El piso mínimo permitido es ${floor_price_usd:,.0f} U$S por camión. "
          f"Por debajo de ese monto la renta cae del {cls.MIN_CORPORATE_MARGIN_PCT}% corporativo."
        )

        tactical_insights = [
            f"El prospecto {prospect_name} opera en el rubro {category} con un volumen de {trucks} camiones.",
            f"La competencia le está cobrando actualmente ${comp_price:,.0f} U$S/camión.",
            f"El costo directo estimado del fletero para Mercotruck es ${cost_price:,.0f} U$S/camión.",
            f"En el escenario recomendado (Margen {margin_recomendado}%), Mercotruck gana ${renta_recomendada:,.0f} U$S por camión."
        ]

        return {
            "prospect_name": prospect_name,
            "total_trucks": trucks,
            "category": category,
            "competitor_price_usd": comp_price,
            "estimated_carrier_cost_usd": cost_price,
            "floor_price_usd": floor_price_usd,
            "min_margin_pct": cls.MIN_CORPORATE_MARGIN_PCT,
            "strategies": {
                "AGRESIVA": {
                    "price_per_truck": price_agresivo,
                    "profit_per_truck": renta_agresiva,
                    "margin_pct": margin_agresivo,
                    "customer_savings_per_truck": ahorro_agresivo,
                    "total_customer_savings": ahorro_agresivo * trucks,
                    "description": "Descuento agresivo (-10%) para asegurar el cierre inmediato del cliente."
                },
                "RECOMENDADA": {
                    "price_per_truck": price_recomendado,
                    "profit_per_truck": renta_recomendada,
                    "margin_pct": margin_recomendado,
                    "customer_savings_per_truck": ahorro_recomendado,
                    "total_customer_savings": total_ahorro_rec,
                    "description": "Equilibrio óptimo: Ahorro del 5% para el cliente y renta saludable de Mercotruck."
                },
                "MAX_MARGIN": {
                    "price_per_truck": price_max_margin,
                    "profit_per_truck": renta_max,
                    "margin_pct": margin_max,
                    "customer_savings_per_truck": 0.0,
                    "total_customer_savings": 0.0,
                    "description": "Máxima rentabilidad para momentos de alta demanda o escasa disponibilidad de camiones."
                }
            },
            "pitch_argument": pitch_argument,
            "warning_alert": warning_alert,
            "tactical_insights": tactical_insights
        }
