from __future__ import annotations


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def calculate_landslide_risk(slope_degrees, rainfall_mm, seismic_index) -> float:
    """Return a normalized landslide risk score between 0.0 and 1.0.

    Weighted formula using normalized components:
    - Rainfall: 45%
    - Slope: 35%
    - Seismic: 20%
    """
    slope = float(slope_degrees)
    rainfall = float(rainfall_mm)
    seismic = float(seismic_index)

    slope_norm = _clamp((slope - 10.0) / (60.0 - 10.0))
    rainfall_norm = _clamp(rainfall / 300.0)
    seismic_norm = _clamp(seismic / 3.0)

    risk_score = (
        0.45 * rainfall_norm +
        0.35 * slope_norm +
        0.20 * seismic_norm
    )

    return round(_clamp(risk_score), 4)


def evaluate_cascade_hazard(landslide_risk, distance_to_town_km, river_proximity_meters=100):
    """Evaluate downstream cascade hazard and flood response.

    The rule explicitly states river_blocked should be True when risk > 0.65.
    The wave arrival is estimated based on distance and risk severity.
    """
    risk = _clamp(float(landslide_risk))
    distance_km = max(0.0, float(distance_to_town_km))

    river_blocked = risk > 0.65
    wave_arrival_mins = None

    if river_blocked:
        estimated_travel = max(8, int((distance_km * 7.5) * (1.0 - (risk * 0.25))))
        wave_arrival_mins = max(5, min(120, estimated_travel))
        flood_warning = (
            "🚨 FLASH FLOOD WARNING: Landslide dam is likely blocking the river and "
            "a downstream surge could reach settlements within minutes. Evacuate "
            "villages immediately and dispatch emergency response teams to notified "
            "zones."
        )
    else:
        flood_warning = (
            "✅ River channel remains stable. No cascading flood wave is expected "
            "under the current conditions."
        )

    return {
        "river_blocked": river_blocked,
        "wave_arrival_mins": wave_arrival_mins,
        "flood_warning": flood_warning,
    }


if __name__ == "__main__":
    sample_risk = calculate_landslide_risk(42, 180, 1.8)
    sample_hazard = evaluate_cascade_hazard(sample_risk, 18, river_proximity_meters=100)
    print(f"Risk score: {sample_risk}")
    print(f"Hazard result: {sample_hazard}"
          )
