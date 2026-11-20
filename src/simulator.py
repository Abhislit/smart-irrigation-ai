"""Water-balance history generator.

Backfills per-minute readings so the 15-minute regressor can be trained and the
dashboard demonstrated before real sensor logs exist. Deterministic.
"""

import math
import random
from datetime import datetime, timedelta

from store import init_db, insert_reading

START_MOISTURE = 42.0
IRRIGATION_TRIGGER = 28.0
IRRIGATION_ADD = 26.0


def backfill(db_path: str, days: int = 14) -> int:
    init_db(db_path)
    rng = random.Random(42)
    end = datetime.now().replace(second=0, microsecond=0)
    start = end - timedelta(days=days, minutes=-1)
    moisture = START_MOISTURE
    minutes_since_irrigation = 90.0
    rows = []
    t = start

    while t <= end:
        hour = t.hour + t.minute / 60.0
        temp = 24.0 + 9.0 * math.sin((hour - 8) / 24 * 2 * math.pi) + rng.uniform(-0.8, 0.8)
        humidity = 62.0 - 22.0 * math.sin((hour - 8) / 24 * 2 * math.pi) + rng.uniform(-1.5, 1.5)

        # evapotranspiration: hotter and drier air pulls the pot down faster
        et = 0.018 + max(0.0, temp - 25.0) * 0.0022 + max(0.0, 55.0 - humidity) * 0.0006
        moisture = max(8.0, moisture - et * rng.uniform(0.8, 1.2))
        minutes_since_irrigation += 1.0

        pump = 0
        if moisture < IRRIGATION_TRIGGER and minutes_since_irrigation > 45:
            moisture = min(52.0, moisture + IRRIGATION_ADD * rng.uniform(0.85, 1.15))
            minutes_since_irrigation = 0.0
            pump = 1

        rows.append(
            {
                "ts": t.isoformat(),
                "moisture": round(moisture, 2),
                "temp": round(temp, 2),
                "humidity": round(humidity, 2),
                "pump": pump,
                "minutes_since_irrigation": round(minutes_since_irrigation, 2),
                "source": "simulated",
            }
        )
        t += timedelta(minutes=1)

    for row in rows:
        insert_reading(db_path, row)
    return len(rows)
