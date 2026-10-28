
import numpy as np
from scipy.optimize import linprog


SECTORS = ["Domestic", "Agriculture", "Industry"]


def _validate_inputs(
    available_water,
    domestic_demand,
    agriculture_demand,
    industry_demand,
    reserve_water,
):
    """Check that water volumes are finite and non-negative."""

    values = {
        "available_water": available_water,
        "domestic_demand": domestic_demand,
        "agriculture_demand": agriculture_demand,
        "industry_demand": industry_demand,
        "reserve_water": reserve_water,
    }

    checked = {}

    for name, value in values.items():
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a valid number.")

        if not np.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative.")

        checked[name] = value

    return checked


def _prepare_inputs(
    available_water,
    domestic_demand,
    agriculture_demand,
    industry_demand,
    reserve_water,
):
    values = _validate_inputs(
        available_water,
        domestic_demand,
        agriculture_demand,
        industry_demand,
        reserve_water,
    )

    available = values["available_water"]
    reserve = min(values["reserve_water"], available)

    demands = {
        "Domestic": values["domestic_demand"],
        "Agriculture": values["agriculture_demand"],
        "Industry": values["industry_demand"],
    }

    usable = available - reserve

    return available, reserve, usable, demands


def _validate_priorities(priorities):
    if priorities is None:
        priorities = {
            "Domestic": 3.0,
            "Agriculture": 2.0,
            "Industry": 1.0,
        }

    checked = {}

    for sector in SECTORS:
        try:
            weight = float(priorities.get(sector, 1.0))
        except (TypeError, ValueError):
            raise ValueError(f"Priority for {sector} must be a number.")

        if not np.isfinite(weight) or weight < 0:
            raise ValueError(
                f"Priority for {sector} must be finite and non-negative."
            )

        checked[sector] = weight

    return checked


def _format_results(
    available, reserve, usable, demands, allocations
):
    total_demand = sum(demands.values())
    total_allocated = sum(allocations.values())

    results = {
        "Available Water (MCFT)": available,
        "Protected Reserve (MCFT)": reserve,
        "Usable Water (MCFT)": usable,
        "Total Demand (MCFT)": total_demand,
        "Total Allocated (MCFT)": total_allocated,
        "Unmet Demand (MCFT)": max(
            0.0, total_demand - total_allocated
        ),
    }

    for sector in SECTORS:
        demand = demands[sector]
        allocation = allocations[sector]

        results[f"{sector} Demand (MCFT)"] = demand
        results[f"{sector} Allocation (MCFT)"] = allocation
        results[f"{sector} Unmet (MCFT)"] = max(
            0.0, demand - allocation
        )
        results[f"{sector} Satisfaction (%)"] = (
            100.0 * allocation / demand if demand > 0 else 100.0
        )

    return results


def allocate_water(
    available_water,
    domestic_demand,
    agriculture_demand,
    industry_demand,
    reserve_water,
    priorities=None,
):
    """Baseline: satisfy sectors in descending priority order."""

    available, reserve, usable, demands = _prepare_inputs(
        available_water,
        domestic_demand,
        agriculture_demand,
        industry_demand,
        reserve_water,
    )

    weights = _validate_priorities(priorities)

    allocations = {sector: 0.0 for sector in SECTORS}
    remaining = usable

    for sector in sorted(
        SECTORS,
        key=lambda name: weights[name],
        reverse=True,
    ):
        allocation = min(demands[sector], remaining)
        allocations[sector] = allocation
        remaining = max(0.0, remaining - allocation)

    return _format_results(
        available, reserve, usable, demands, allocations
    )


def optimize_water_allocation(
    available_water,
    domestic_demand,
    agriculture_demand,
    industry_demand,
    reserve_water,
    priorities=None,
):
    """Maximize priority-weighted demand satisfaction using linear programming."""

    available, reserve, usable, demands = _prepare_inputs(
        available_water,
        domestic_demand,
        agriculture_demand,
        industry_demand,
        reserve_water,
    )

    weights = _validate_priorities(priorities)

    objective = [
        -weights[sector] / demands[sector]
        if demands[sector] > 0 else 0.0
        for sector in SECTORS
    ]

    solution = linprog(
        c=objective,
        A_ub=[[1.0, 1.0, 1.0]],
        b_ub=[usable],
        bounds=[
            (0.0, demands[sector]) for sector in SECTORS
        ],
        method="highs",
    )

    if not solution.success:
        raise RuntimeError(f"Optimization failed: {solution.message}")

    allocations = {
        sector: max(0.0, float(solution.x[i]))
        for i, sector in enumerate(SECTORS)
    }

    return _format_results(
        available, reserve, usable, demands, allocations
    )


def optimize_fair_allocation(
    available_water,
    domestic_demand,
    agriculture_demand,
    industry_demand,
    reserve_water=0,
):
    """
    Maximize the minimum satisfaction ratio across sectors with
    positive demand, then maximize total allocation without
    reducing that fairness level.
    """

    available, reserve, usable, demands = _prepare_inputs(
        available_water,
        domestic_demand,
        agriculture_demand,
        industry_demand,
        reserve_water,
    )

    demand_array = np.array(
        [demands[sector] for sector in SECTORS],
        dtype=float,
    )

    positive = demand_array > 0

    # If every sector has zero demand, there is nothing to allocate.
    if not np.any(positive):
        return {
            **{sector: 0.0 for sector in SECTORS},
            "Minimum Satisfaction (%)": 100.0,
        }

    # Variables: three allocations and minimum satisfaction ratio t.
    constraints = [[1.0, 1.0, 1.0, 0.0]]
    limits = [usable]

    for i in range(3):
        if positive[i]:
            row = [0.0, 0.0, 0.0, demand_array[i]]
            row[i] = -1.0
            constraints.append(row)
            limits.append(0.0)

    bounds = [
        (0.0, demand_array[i]) for i in range(3)
    ] + [(0.0, 1.0)]

    # Stage 1: maximize the minimum satisfaction ratio.
    first = linprog(
        c=[0.0, 0.0, 0.0, -1.0],
        A_ub=constraints,
        b_ub=limits,
        bounds=bounds,
        method="highs",
    )

    if not first.success:
        raise RuntimeError(
            f"Fairness optimization failed: {first.message}"
        )

    best_satisfaction = float(first.x[3])

    # Stage 2: maximize total allocation while preserving the
    # optimal minimum satisfaction ratio.
    second_constraints = [row[:] for row in constraints]
    second_limits = list(limits)

    second_constraints.append([
        -1.0 if positive[i] else 0.0
        for i in range(3)
    ] + [0.0])

    second_limits.append(
        -best_satisfaction * float(np.sum(demand_array[positive]))
    )

    # The fairness constraint above is replaced below with the
    # exact per-sector constraints x_i >= best_satisfaction * demand_i.
    second_constraints = [row[:] for row in constraints]
    second_limits = list(limits)

    for i in range(3):
        if positive[i]:
            row = [0.0, 0.0, 0.0, 0.0]
            row[i] = -1.0
            second_constraints.append(row)
            second_limits.append(
                -best_satisfaction * demand_array[i]
            )

    second = linprog(
        c=[-1.0, -1.0, -1.0, 0.0],
        A_ub=second_constraints,
        b_ub=second_limits,
        bounds=bounds,
        method="highs",
    )

    if not second.success:
        raise RuntimeError(
            f"Allocation optimization failed: {second.message}"
        )

    allocations = {
        sector: max(0.0, float(second.x[i]))
        for i, sector in enumerate(SECTORS)
    }

    # Calculate the achieved minimum satisfaction from allocations.
    ratios = [
        allocations[sector] / demands[sector]
        for sector in SECTORS
        if demands[sector] > 0
    ]

    return {
        **allocations,
        "Minimum Satisfaction (%)": (
            100.0 * min(ratios) if ratios else 100.0
        ),
    }
