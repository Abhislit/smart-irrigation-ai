"""Predict irrigation need for one field record.

    ./run.sh src/predict.py                       # median field
    ./run.sh src/predict.py --json '{"Soil_Moisture": 18, "Temperature_C": 34}'
    echo '{"soil_moisture": 18}' | ./run.sh src/predict.py
"""
import argparse
import json
import sys

import joblib
import pandas as pd

from common import DEFAULTS_PATH, FEATURES, MODEL_PATH

ADVICE = {
    "Low": "No irrigation needed; re-check in ~24 h.",
    "Medium": "Irrigate about half the normal dose; re-check in ~12 h.",
    "High": "Irrigate now.",
}

# What a real probe sends -> what the model expects.
SENSOR_ALIASES = {
    "soil_moisture": "Soil_Moisture",
    "temperature_c": "Temperature_C",
    "humidity": "Humidity",
    "rainfall_mm": "Rainfall_mm",
    "soil_ph": "Soil_pH",
}


def normalise(payload: dict) -> dict:
    """Map sensor-style keys to model columns; drop anything unknown."""
    out = {}
    for key, value in payload.items():
        column = SENSOR_ALIASES.get(key.lower(), key)
        if column in FEATURES:
            out[column] = value
    return out


def predict(payload: dict, model=None, base: dict | None = None) -> dict:
    model = model if model is not None else joblib.load(MODEL_PATH)
    base = base if base is not None else json.loads(DEFAULTS_PATH.read_text())

    row = {**base, **normalise(payload)}
    proba = model.predict_proba(pd.DataFrame([row])[FEATURES])[0]
    best = int(proba.argmax())
    need = str(model.classes_[best])
    return {
        "need": need,
        "confidence": round(float(proba[best]), 3),
        "advice": ADVICE[need],
        "probabilities": {str(c): round(float(p), 3) for c, p in zip(model.classes_, proba)},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="field record as JSON; omit to read stdin or use medians")
    args = ap.parse_args()

    if args.json:
        payload = json.loads(args.json)
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
    else:
        payload = {}

    print(json.dumps(predict(payload), indent=2))


if __name__ == "__main__":
    main()
