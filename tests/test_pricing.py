from app.domain.services.pricing_engine import PricingEngine
from app.domain.services.scoring_engine import ScoringEngine

def test_calculate_trucks():
    # 28,500 kg ceiling
    assert PricingEngine.calculate_trucks(28500, 28500) == 1
    assert PricingEngine.calculate_trucks(28501, 28500) == 2
    assert PricingEngine.calculate_trucks(57000, 28500) == 2
    assert PricingEngine.calculate_trucks(60000, 28500) == 3

def test_price_difference_pct():
    # Mercotruck is $2500, Competitor is $3000 -> 16.7% cheaper (-16.7%)
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
