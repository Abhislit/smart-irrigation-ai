"""15-minute soil-moisture regressor.

Features come only from information available at time t. The target is the
moisture reading 15 rows (15 minutes) later, so the split must be chronological.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

LOOKBACK = 30
HORIZON = 15
BUNDLE_PATH = Path(__file__).resolve().parent.parent / "models" / "forecast.joblib"

FEATURES = [
    "moisture_lag0",
    "moisture_lag5",
    "moisture_lag10",
    "moisture_lag15",
    "moisture_lag30",
    "slope15",
    "slope30",
    "temp",
    "humidity",
    "hour_sin",
    "hour_cos",
    "minutes_since_irrigation",
    "pump",
]


def build_features(rows: list[dict], with_target: bool = True):
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").reset_index(drop=True)

    m = df["moisture"].astype(float)
    out = {"moisture_lag0": m}
    for lag in (5, 10, 15, 30):
        out[f"moisture_lag{lag}"] = m.shift(lag)
    out["slope15"] = (m - m.shift(15)) / 15.0
    out["slope30"] = (m - m.shift(30)) / 30.0
    out["temp"] = df["temp"].astype(float)
    out["humidity"] = df["humidity"].astype(float)
    hour = df["ts"].dt.hour + df["ts"].dt.minute / 60.0
    out["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    out["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    out["minutes_since_irrigation"] = df["minutes_since_irrigation"].astype(float)
    out["pump"] = df["pump"].astype(float)

    X = pd.DataFrame(out)
    X = X.dropna(subset=FEATURES)
    y = None
    if with_target:
        # Model the 15-minute CHANGE, not the absolute level: absolute targets
        # regress to the mean of the wet/dry cycle and lose to persistence.
        target = (m.shift(-HORIZON) - m).rename("target")
        valid = X.index.intersection(target.dropna().index)
        X, y = X.loc[valid].reset_index(drop=True), target.loc[valid].reset_index(drop=True)
    return X.reset_index(drop=True), y


def train(rows: list[dict]) -> dict:
    X, y = build_features(rows)
    split = int(len(X) * 0.7)

    rf = RandomForestRegressor(
        n_estimators=300, min_samples_leaf=5, n_jobs=-1, random_state=42
    )
    rf.fit(X.iloc[:split], y.iloc[:split])

    ridge = make_pipeline(StandardScaler(), Ridge()).fit(X.iloc[:split], y.iloc[:split])
    delta = rf.predict(X.iloc[split:])

    bundle = {
        "model": rf,
        "mae": float(mean_absolute_error(y.iloc[split:], delta)),
        "r2": float(r2_score(y.iloc[split:], delta)),
        "persistence_mae": float(mean_absolute_error(y.iloc[split:], np.zeros(len(delta)))),
        "ridge_mae": float(mean_absolute_error(y.iloc[split:], ridge.predict(X.iloc[split:]))),
        "importances": {
            name: round(float(imp), 4) for name, imp in zip(FEATURES, rf.feature_importances_)
        },
        "trained_rows": int(len(X)),
    }
    BUNDLE_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(bundle, BUNDLE_PATH)
    return bundle


def decide(prediction: float, current: float, minutes_since: float, mode: str = "AUTO") -> dict:
    """Recommendation only. The ESP32 enforces the hard limits independently."""
    if mode != "AUTO":
        return {"action": "HOLD", "duration_s": 0, "why": "MANUAL mode: no automatic command."}
    if current <= 15:
        return {"action": "HOLD", "duration_s": 0, "why": "Soil already too dry for a safe burst."}
    if minutes_since <= 45:
        return {"action": "HOLD", "duration_s": 0, "why": "Irrigated less than 45 minutes ago."}
    if prediction >= 30:
        return {"action": "HOLD", "duration_s": 0, "why": "Forecast stays above the 30% threshold."}
    return {
        "action": "BURST",
        "duration_s": 40,
        "why": f"Forecast {prediction:.1f}% in 15 min is below 30%: irrigate 40 s.",
    }


def predict(bundle: dict, rows: list[dict], mode: str = "AUTO") -> dict:
    X, _ = build_features(rows, with_target=False)
    latest_row = X.iloc[[-1]]
    model = bundle["model"]
    value = float(latest_row["moisture_lag0"].iloc[0]) + float(model.predict(latest_row)[0])
    spread = float(np.std([tree.predict(latest_row.to_numpy())[0] for tree in model.estimators_]))
    last = rows[-1]
    decision = decide(value, float(last["moisture"]), float(last["minutes_since_irrigation"]), mode)
    return {
        "moisture_15min": round(value, 2),
        "spread": round(spread, 3),
        "mae": bundle["mae"],
        "r2": bundle["r2"],
        "decision": decision["action"],
        "duration_s": decision["duration_s"],
        "why": decision["why"],
    }
