"""Tests for the realtime irrigation pipeline.

Run: ./run.sh -m unittest discover -s src -p test_project.py
"""
import os
import sqlite3
from datetime import datetime, timedelta
import tempfile
import unittest

from model import build_features, decide, predict, train
from simulator import backfill
from state import compute_state
from weather import current_weather
from store import count, init_db, insert_reading, latest, read_window


class StoreTest(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(self.db)

    def tearDown(self):
        if os.path.exists(self.db):
            os.remove(self.db)

    def test_init_creates_readings_table(self):
        init_db(self.db)
        with sqlite3.connect(self.db) as con:
            cols = [r[1] for r in con.execute("PRAGMA table_info(readings)")]
        self.assertEqual(
            cols,
            ["ts", "moisture", "temp", "humidity", "pump", "minutes_since_irrigation", "source"],
        )

    def test_insert_and_latest_round_trip(self):
        init_db(self.db)
        row = {
            "ts": "2026-11-20T10:00:00",
            "moisture": 28.5,
            "temp": 31.2,
            "humidity": 45.0,
            "pump": 1,
            "minutes_since_irrigation": 12.0,
            "source": "esp32",
        }
        insert_reading(self.db, row)
        got = latest(self.db)
        self.assertEqual(got["moisture"], 28.5)
        self.assertEqual(got["source"], "esp32")
        self.assertEqual(got["pump"], 1)

    def test_read_window_returns_newest_last_and_is_bounded(self):
        init_db(self.db)
        for i in range(8):
            insert_reading(
                self.db,
                {
                    "ts": f"2026-11-20T10:{i:02d}:00",
                    "moisture": float(i),
                    "temp": 25.0,
                    "humidity": 50.0,
                    "pump": 0,
                    "minutes_since_irrigation": float(i),
                    "source": "simulated",
                },
            )
        rows = read_window(self.db, 5)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[-1]["ts"], "2026-11-20T10:07:00")
        self.assertEqual(rows[0]["moisture"], 3.0)

    def test_backfill_creates_two_weeks_of_minute_data(self):
        init_db(self.db)
        n = backfill(self.db, days=14)
        self.assertGreaterEqual(n, 20000)
        self.assertEqual(count(self.db), n)
        self.assertEqual(latest(self.db)["source"], "simulated")


class ModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, cls.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(cls.db)
        backfill(cls.db, days=14)
        cls.rows = read_window(cls.db, 4000)

    @classmethod
    def tearDownClass(cls):
        os.remove(cls.db)

    def test_target_is_never_a_feature(self):
        X, _ = build_features(self.rows)
        self.assertNotIn("target", X.columns)
        self.assertFalse(any(c.startswith("target") for c in X.columns))

    def test_windows_containing_irrigation_are_excluded(self):
        rows = []
        for i in range(60):
            rows.append(
                {
                    "ts": f"2026-11-20T00:{i:02d}:00",
                    "moisture": 40.0 - i * 0.1,
                    "temp": 25.0,
                    "humidity": 50.0,
                    "pump": 1 if i == 35 else 0,
                    "minutes_since_irrigation": float(i),
                    "source": "simulated",
                }
            )
        X, y = build_features(rows)
        # 15 rows have both lags and a target; 5 of them water in the window.
        self.assertEqual(len(X), 10)
        self.assertEqual(len(y), 10)

    def test_target_is_exactly_15_rows_ahead(self):
        rows = [
            {
                "ts": f"2026-11-20T00:{i // 60:02d}:{i % 60:02d}" if i < 3600 else f"t{i}",
                "moisture": float(i),
                "temp": 25.0,
                "humidity": 50.0,
                "pump": 0,
                "minutes_since_irrigation": float(i),
                "source": "simulated",
            }
            for i in range(60)
        ]
        X, y = build_features(rows)
        self.assertEqual(float(y.iloc[0]), 15.0)

    def test_random_forest_beats_persistence_baseline(self):
        bundle = train(self.rows)
        self.assertLess(bundle["mae"], bundle["persistence_mae"])
        self.assertGreater(bundle["r2"], 0.0)

    def test_predict_drydown_returns_falling_forecast_and_spread(self):
        bundle = train(self.rows)
        out = predict(bundle, self.rows[-60:])
        self.assertLess(out["moisture_15min"], self.rows[-1]["moisture"])
        self.assertGreaterEqual(out["spread"], 0.0)
        self.assertIn("decision", out)
        self.assertTrue(out["why"])


def sample_rows(n, age_minutes=0):
    now = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=age_minutes)
    return [
        {
            "ts": (now - timedelta(minutes=n - 1 - i)).isoformat(),
            "moisture": 30.0,
            "temp": 26.0,
            "humidity": 55.0,
            "pump": 0,
            "minutes_since_irrigation": float(60 + i),
            "source": "esp32",
        }
        for i in range(n)
    ]


class StateTest(unittest.TestCase):
    def test_no_rows_is_no_data(self):
        self.assertEqual(compute_state({})["primary"], "NO_DATA")

    def test_few_rows_is_collecting(self):
        out = compute_state({"rows": sample_rows(50), "has_model": True})
        self.assertEqual(out["primary"], "COLLECTING")

    def test_ten_minute_old_reading_raises_sensor_stale(self):
        out = compute_state({"rows": sample_rows(300, age_minutes=10), "has_model": True})
        self.assertIn("SENSOR_STALE", out["warnings"])
        self.assertEqual(out["primary"], "PREDICTING")

    def test_stale_weather_warning_does_not_change_primary(self):
        ctx = {
            "rows": sample_rows(300),
            "has_model": True,
            "weather": {"stale": True},
        }
        out = compute_state(ctx)
        self.assertIn("WEATHER_STALE", out["warnings"])
        self.assertEqual(out["primary"], "PREDICTING")

    def test_unacknowledged_command_reports_unknown_pump(self):
        out = compute_state(
            {
                "rows": sample_rows(300),
                "has_model": True,
                "last_command_id": "c1",
                "ack_command_id": None,
            }
        )
        self.assertEqual(out["pump_state"], "UNKNOWN")

    def test_acknowledged_command_uses_device_report(self):
        out = compute_state(
            {
                "rows": sample_rows(300),
                "has_model": True,
                "last_command_id": "c1",
                "ack_command_id": "c1",
                "reported_pump": 1,
            }
        )
        self.assertEqual(out["pump_state"], "ON")


class WeatherTest(unittest.TestCase):
    def test_failed_fetch_returns_last_cached_values_and_stale_flag(self):
        fd, cache = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(cache, "w") as fh:
            fh.write('{"temperature": 29.0, "humidity": 51.0, "stale": false}')

        def boom():
            raise OSError("offline")

        weather = current_weather(cache, fetch=boom)
        self.assertEqual(weather["temperature"], 29.0)
        self.assertTrue(weather["stale"])
        os.remove(cache)


class DecisionTest(unittest.TestCase):
    def test_burst_when_forecast_below_threshold(self):
        out = decide(28.5, 31.0, 60.0)
        self.assertEqual(out["action"], "BURST")
        self.assertEqual(out["duration_s"], 40)

    def test_hold_when_soil_already_too_dry(self):
        self.assertEqual(decide(20.0, 12.0, 90.0)["action"], "HOLD")

    def test_hold_inside_45_minute_gap(self):
        self.assertEqual(decide(20.0, 31.0, 20.0)["action"], "HOLD")

    def test_manual_mode_never_issues_automatic_command(self):
        self.assertEqual(decide(20.0, 31.0, 90.0, mode="MANUAL")["action"], "HOLD")

    def test_safety_lock_blocks_automatic_command(self):
        self.assertEqual(decide(20.0, 31.0, 90.0, safety_lock=True)["action"], "HOLD")


class FirmwareTest(unittest.TestCase):
    def test_firmware_contains_local_safety_limits(self):
        from pathlib import Path

        sketch = Path(__file__).resolve().parent.parent / "firmware" / "esp32_realtime.ino"
        source = sketch.read_text()
        for token in (
            "MAX_BURST_MS = 60000",
            "MIN_GAP_MS = 45UL * 60000UL",
            "pumpStopAt",
            "lastCommandId",
            "duration_s > 60",
        ):
            self.assertIn(token, source)


class EndToEndTest(unittest.TestCase):
    def test_backfill_to_acknowledged_command(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(self.db)
        try:
            backfill(self.db, days=14)
            rows = read_window(self.db, 5000)
            X, y = build_features(rows)
            self.assertNotIn("target", X.columns)
            self.assertEqual(y.name, "target")
            bundle = train(rows)
            self.assertLess(bundle["mae"], bundle["persistence_mae"])

            ctx = {"rows": rows, "has_model": True, "weather": {"stale": False}, "mode": "AUTO"}
            self.assertEqual(compute_state(ctx)["primary"], "PREDICTING")

            # A dry reading arrives from the probe at the current minute.
            insert_reading(
                self.db,
                {**rows[-1], "moisture": 22.0, "pump": 0,
                 "minutes_since_irrigation": 90.0, "source": "esp32"},
            )
            rows = read_window(self.db, 5000)
            self.assertEqual(latest(self.db)["source"], "esp32")
            out = predict(bundle, rows, "AUTO")
            self.assertLess(out["moisture_15min"], 30.0)
            self.assertEqual(out["decision"], "BURST")
            self.assertLessEqual(out["duration_s"], 60)

            command = {"id": "e2e-1", "duration_s": out["duration_s"]}
            pending = {**ctx, "rows": rows, "last_command_id": command["id"], "ack_command_id": None}
            self.assertEqual(compute_state(pending)["pump_state"], "UNKNOWN")
            acked = {**pending, "ack_command_id": command["id"]}
            self.assertEqual(compute_state(acked)["pump_state"], "OFF")

            # Inside the 45-minute gap the same dry forecast must not command.
            insert_reading(
                self.db,
                {
                    **rows[-1],
                    "ts": (datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=1)).isoformat(),
                    "moisture": 22.0,
                    "pump": 0,
                    "minutes_since_irrigation": 20.0,
                    "source": "esp32",
                },
            )
            gapped = predict(bundle, read_window(self.db, 5000), "AUTO")
            self.assertEqual(gapped["decision"], "HOLD")
            self.assertEqual(gapped["duration_s"], 0)
        finally:
            os.remove(self.db)


if __name__ == "__main__":
    unittest.main(verbosity=2)
