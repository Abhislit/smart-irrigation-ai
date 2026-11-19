"""Shared data contract for training, prediction and the API.

The feature list lives here only, so the target can never leak into X.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "raw" / "irrigation_prediction.csv"
MODEL_PATH = ROOT / "models" / "irrigation_rf.joblib"
DEFAULTS_PATH = ROOT / "models" / "defaults.json"
REPORT_DIR = ROOT / "reports"

TARGET = "Irrigation_Need"
CLASSES = ["Low", "Medium", "High"]

CATEGORICAL = [
    "Soil_Type",
    "Crop_Type",
    "Crop_Growth_Stage",
    "Season",
    "Irrigation_Type",
    "Water_Source",
    "Mulching_Used",
    "Region",
]
NUMERIC = [
    "Soil_pH",
    "Soil_Moisture",
    "Organic_Carbon",
    "Electrical_Conductivity",
    "Temperature_C",
    "Humidity",
    "Rainfall_mm",
    "Sunlight_Hours",
    "Wind_Speed_kmh",
    "Field_Area_hectare",
    "Previous_Irrigation_mm",
]
FEATURES = CATEGORICAL + NUMERIC


def load_raw() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH)


def features(df: pd.DataFrame) -> pd.DataFrame:
    return df[FEATURES]


def defaults(df: pd.DataFrame) -> dict:
    """Median/mode per column: what an ESP32 that only has a moisture probe fills in."""
    out = {}
    for col in CATEGORICAL:
        out[col] = df[col].mode().iloc[0]
    for col in NUMERIC:
        out[col] = float(df[col].median())
    return out
