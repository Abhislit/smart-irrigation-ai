"""Smoke tests: data contract, alias mapping, sane predictions, no regression.

    ./run.sh src/test_smoke.py
"""
import json
import unittest

from common import FEATURES, REPORT_DIR, TARGET
from predict import normalise, predict


class ProjectTest(unittest.TestCase):
    def test_target_never_in_features(self):
        self.assertNotIn(TARGET, FEATURES)

    def test_sensor_aliases(self):
        self.assertEqual(normalise({"soil_moisture": 20}), {"Soil_Moisture": 20})
        self.assertEqual(normalise({"Soil_Moisture": 20}), {"Soil_Moisture": 20})
        self.assertEqual(normalise({"garbage": 1}), {})

    def test_prediction_is_well_formed(self):
        out = predict({"soil_moisture": 25, "temperature_c": 30})
        self.assertIn(out["need"], {"Low", "Medium", "High"})
        self.assertAlmostEqual(sum(out["probabilities"].values()), 1.0, places=2)
        self.assertTrue(out["advice"])

    def test_dry_hot_soil_is_not_low_need(self):
        out = predict({"soil_moisture": 8, "temperature_c": 42, "rainfall_mm": 1})
        self.assertNotEqual(out["need"], "Low")

    def test_wet_soil_is_low_need(self):
        out = predict({"soil_moisture": 65, "temperature_c": 20, "rainfall_mm": 2000})
        self.assertEqual(out["need"], "Low")

    def test_model_beats_baselines(self):
        m = json.loads((REPORT_DIR / "metrics.json").read_text())
        self.assertGreater(m["rf_accuracy"], m["baseline_majority_accuracy"])
        self.assertGreater(m["rf_macro_f1"], m["logreg_macro_f1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
