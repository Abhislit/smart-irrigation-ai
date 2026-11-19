"""Visible AI state machine. One primary state plus concurrent warning pills."""

from datetime import datetime

STALE_AFTER_MINUTES = 5


def compute_state(ctx: dict) -> dict:
    rows = ctx.get("rows") or []
    if not rows:
        return {"primary": "NO_DATA", "warnings": [], "pump_state": "OFF", "age_minutes": None}

    try:
        last_ts = datetime.fromisoformat(rows[-1]["ts"])
        age = (datetime.now() - last_ts).total_seconds() / 60.0
    except (ValueError, KeyError):
        age = 10_000.0

    if ctx.get("training"):
        primary = "TRAINING"
    elif len(rows) < 200 or not ctx.get("has_model", False):
        primary = "COLLECTING"
    else:
        primary = "PREDICTING" if ctx.get("has_prediction", True) else "READY"

    warnings = []
    if age > STALE_AFTER_MINUTES:
        warnings.append("SENSOR_STALE")
    if (ctx.get("weather") or {}).get("stale"):
        warnings.append("WEATHER_STALE")
    if ctx.get("rows_since_train", 0) > 200:
        warnings.append("MODEL_STALE")
    if ctx.get("safety_lock"):
        warnings.append("SAFETY_LOCK")
    if ctx.get("mode") == "MANUAL":
        warnings.append("MANUAL_OVERRIDE")

    reported = ctx.get("reported_pump", 0)
    pump_state = "UNKNOWN" if ctx.get("last_command_id") and ctx.get("ack_command_id") != ctx.get("last_command_id") else ("ON" if reported else "OFF")

    return {
        "primary": primary,
        "warnings": warnings,
        "pump_state": pump_state,
        "age_minutes": round(age, 1),
    }
