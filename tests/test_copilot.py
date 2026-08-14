from app.domain.services.copilot_engine import CopilotEngine

def test_copilot_advice_generation():
    advice = CopilotEngine.generate_advice(
        prospect_name="CARTOCOR CHILE S.A.",
        total_trucks=5,
        competitor_price_per_truck=3000.0,
        estimated_carrier_cost_per_truck=2000.0,
        category="Papel y cartón"
    )
    
    assert advice["prospect_name"] == "CARTOCOR CHILE S.A."
    assert advice["total_trucks"] == 5
    assert advice["floor_price_usd"] == 2353.0 # 2000 / 0.85
    
    # Check 3 strategies
    strats = advice["strategies"]
    assert "AGRESIVA" in strats
    assert "RECOMENDADA" in strats
    assert "MAX_MARGIN" in strats
    
    assert strats["AGRESIVA"]["price_per_truck"] == 2700.0 # -10% vs 3000
    assert strats["RECOMENDADA"]["price_per_truck"] == 2850.0 # -5% vs 3000
    assert strats["MAX_MARGIN"]["price_per_truck"] == 3060.0 # +2% vs 3000
    
    assert strats["RECOMENDADA"]["total_customer_savings"] == 750.0 # 150 * 5 trucks
    assert "CARTOCOR CHILE S.A." in advice["pitch_argument"]
