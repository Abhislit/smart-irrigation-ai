"""Tests for the realtime irrigation pipeline.

Run: ./run.sh -m unittest discover -s src -p test_project.py
"""
import os
import sqlite3
import tempfile
import unittest

from model import build_features, predict, train
from simulator import backfill
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
        self.assertEqual(float(y.iloc[0] - X.iloc[0]["moisture_lag0"]), 15.0)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
