"""Open-Meteo current weather with a disk cache. No API key, no extra sensor."""

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "weather.json"
TTL_SECONDS = 15 * 60

# Mumbai by default; edit LAT/LON for your farm.
LAT, LON = 19.0760, 72.8777


def _fetch() -> dict:
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
        "&current=temperature_2m,relative_humidity_2m"
    )
    with urllib.request.urlopen(url, timeout=6) as response:
        payload = json.load(response)["current"]
    return {
        "temperature": round(float(payload["temperature_2m"]), 2),
        "humidity": round(float(payload["relative_humidity_2m"]), 2),
        "stale": False,
        "fetched_at": time.time(),
    }


def current_weather(cache_path=None, fetch=None) -> dict:
    path = Path(cache_path) if cache_path else CACHE_PATH
    fetch = fetch or _fetch
    cached = {}
    if path.exists():
        try:
            cached = json.loads(path.read_text())
        except (ValueError, OSError):
            cached = {}

    fresh = cached.get("fetched_at", 0) + TTL_SECONDS > time.time()
    if fresh:
        return cached

    try:
        result = fetch()
    except Exception:
        result = {
            "temperature": cached.get("temperature", 25.0),
            "humidity": cached.get("humidity", 55.0),
            "stale": True,
            "fetched_at": cached.get("fetched_at", 0),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result))
    return result
