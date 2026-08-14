from typing import Optional

class ScoringEngine:
    @staticmethod
    def calculate_opportunity_score(
        total_trucks: int,
        diff_pct: Optional[float],
        match_type: str,
        days_since_last_shipment: Optional[int] = None,
        min_desired_margin_pct: float = 10.0
    ) -> float:
        """
        Score = total_camiones × factor_precio × factor_recencia × factor_match
        """
        if total_trucks <= 0:
            return 0.0

        # Factor Precio / Competitividad
        if diff_pct is None:
            fp = 0.8
        elif diff_pct <= -20.0:
            fp = 1.5  # Gran ventaja comercial (> 20% más barato que competencia)
        elif diff_pct <= 0.0:
            fp = 1.2  # Ventaja moderada (más barato o igual)
        elif diff_pct <= 10.0:
            fp = 0.9  # Casi par
        else:
            fp = 0.6  # En desventaja de precio pero negociable

        # Factor Reciencia
        if days_since_last_shipment is None:
            fr = 0.8
        elif days_since_last_shipment <= 60:
            fr = 1.3  # Muy activo recientemente
        elif days_since_last_shipment <= 120:
            fr = 1.0
        else:
            fr = 0.7  # Poco activo recientemente

        # Factor Match Geográfico
        fm = 1.0 if match_type == "EXACTO" else 0.7

        score = round(total_trucks * fp * fr * fm, 1)
        return score
