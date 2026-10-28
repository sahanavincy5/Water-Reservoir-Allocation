
def simulate_rainfall_scenarios(
    current_storage_mcft,
    capacity_mcft,
    reserve_water_mcft,
    expected_inflow_mcft
):
    """
    Illustrative one-period rainfall scenarios.
    All water volumes are in MCFT.
    Scenario multipliers are assumptions, not forecasts.
    """

    scenarios = {
        "Drought": 0.4,
        "Normal": 1.0,
        "Wet": 1.6
    }

    results = []

    for scenario, multiplier in scenarios.items():
        scenario_inflow = expected_inflow_mcft * multiplier

        projected_storage = min(
            capacity_mcft,
            max(0, current_storage_mcft + scenario_inflow)
        )

        usable_water = max(
            0,
            projected_storage - reserve_water_mcft
        )

        results.append({
            "Scenario": scenario,
            "Scenario Inflow (MCFT)": round(scenario_inflow, 2),
            "Projected Storage (MCFT)": round(projected_storage, 2),
            "Usable Storage (MCFT)": round(usable_water, 2)
        })

    return results
