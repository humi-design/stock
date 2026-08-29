"""ROI estimation for the Humisense demo.

Produces ESTIMATES only. The output explicitly avoids claiming guaranteed
savings - figures are directional capacity estimates for demonstration.
"""
import math


def calculate(monthly_exceptions, handling_minutes, hourly_cost,
              ai_rate=70, review_minutes=3):
    """Return an estimate dict given monthly operational assumptions."""
    monthly_exceptions = max(0, int(monthly_exceptions or 0))
    handling_minutes = max(0, float(handling_minutes or 0))
    hourly_cost = max(0, float(hourly_cost or 0))
    ai_rate = max(0.0, min(100.0, float(ai_rate or 0)))
    review_minutes = max(0, float(review_minutes or 0))

    current_minutes = monthly_exceptions * handling_minutes
    automated_minutes = monthly_exceptions * (ai_rate / 100.0) * (
        handling_minutes - review_minutes)
    released_hours = automated_minutes / 60.0
    current_hours = current_minutes / 60.0

    monthly_cost_saved = released_hours * hourly_cost
    monthly_current_cost = current_hours * hourly_cost

    human_minutes = (monthly_exceptions * (1 - ai_rate / 100.0) * handling_minutes
                     + monthly_exceptions * (ai_rate / 100.0) * review_minutes)
    human_hours = human_minutes / 60.0

    return {
        "monthly_exceptions": monthly_exceptions,
        "handling_minutes": handling_minutes,
        "hourly_cost": hourly_cost,
        "ai_rate": ai_rate,
        "review_minutes": review_minutes,
        "current_manual_hours": round(current_hours, 1),
        "potential_hours_released": round(released_hours, 1),
        "monthly_operational_cost": round(monthly_current_cost, 0),
        "capacity_released": round(released_hours, 1),
        "annual_capacity": round(released_hours * 12, 1),
        "time_reduction_pct": 100.0 * (1 - review_minutes / handling_minutes)
        if handling_minutes > 0 else 0.0,
    }


def hero_estimate():
    """Numbers shown on the control center (demo estimate)."""
    return {
        "records_processed": 12842,
        "matched": 12516,
        "exceptions": 326,
        "investigated": 247,
        "awaiting_approval": 61,
        "critical": 18,
        "hours_saved": 74.5,
        "capacity_inr": 37250,
    }