# Irrigation Need Advisory — Random Forest + ESP32

Predicts whether a field needs **no / half / full irrigation** from soil, crop and
weather attributes, and drives a pump from that prediction through an ESP32.

Runs on plain Python + scikit-learn. No cloud, no GPU, no API keys.

---

## Read this first: what the dataset is

The data is `miadul/irrigation-water-requirement-prediction-dataset` (10,000 rows,
20 columns). It is **machine-generated, not measured** — that is not an opinion,
it is what `src/probe_dataset.py` shows:

| Signal | Measurement |
|---|---|
| No time axis | zero timestamp/date columns |
| Unit incoherence | `Rainfall_mm` spans 0.38–2499.69 *per row* — annual rainfall as an instantaneous reading |
| Classes overlap completely | `High`-need rows have `Soil_Moisture` 8.0–64.2; `Low`-need 8.0–65.0 |
| Saturates by depth 6–8 | depth-6 forest: 98.5% accuracy / 0.973 macro-F1; deeper trees get **worse** |
| Broken semantics | rows with `Irrigation_Type = Rainfed` still carry an `Irrigation_Need` |

**Consequence, stated honestly:** 99% accuracy here measures the generator, not
agronomic skill. Use it as a decision-support classifier and pipeline, never as
evidence that the model would work in a real field. The report must say this.

Also: this file cannot train a *time-series* moisture forecast (`t+30 min`).
There is no `t`. That needs your own per-minute sensor log.

---

## Measured results

Held-out 20% (2,000 rows), hyperparameters chosen by 5-fold CV on the training
split only; the test split was scored once.

| Model | Accuracy | Macro-F1 |
|---|---|---|
| Majority class ("always Low") | 0.5865 | — |
| Logistic regression | 0.7845 | 0.6838 |
| **Random Forest** (depth 8, leaf 10) | **0.9905** | **0.9839** |
| RF 5-fold CV on train | — | 0.9679 ± 0.0178 |

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Low | 0.989 | 0.998 | 0.994 | 1173 |
| Medium | 0.996 | 0.979 | 0.987 | 760 |
| High | 0.957 | 0.985 | 0.971 | 67 |

The rare class (3.4% of rows) is handled with `class_weight="balanced_subsample"`;
without it, `High` recall collapses. Charts: `reports/confusion_matrix.png`,
`reports/feature_importance.png`.

---

## Quickstart

```sh
pip install --target ./.deps -r requirements.txt   # already done in this folder

./run.sh src/train.py            # ~90 s: CV search, metrics, charts, model
./run.sh src/test_smoke.py       # 6 checks
./run.sh src/probe_dataset.py    # the dataset audit above
./run.sh src/api.py              # http://localhost:8000
```

`run.sh` only puts `./.deps` on `PYTHONPATH` — this machine has no `python3-venv`.

```sh
./run.sh src/predict.py --json '{"Soil_Moisture": 14, "Temperature_C": 39}'
echo '{"soil_moisture": 18}' | ./run.sh src/predict.py
```

---

## Layout

```
data/raw/irrigation_prediction.csv   the Kaggle file, untouched
src/common.py                        feature contract (target can never leak in)
src/train.py                         CV search, evaluation, export
src/predict.py                       pure predict() + CLI
src/api.py                           stdlib HTTP demo + ESP32 endpoint
src/probe_dataset.py                 dataset audit
src/test_smoke.py                    contract + sanity tests
firmware/esp32_irrigation.ino        probe -> API -> pump, with local safety
models/                              trained pipeline + field defaults
reports/                             metrics.json + charts
```

`models/defaults.json` holds the median/mode of every column, so the ESP32 only
has to send `soil_moisture`; the other 18 fields are filled in.

---

## HTTP API

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/` | — | form UI |
| GET | `/health` | — | `{"status":"ok"}` |
| POST | `/predict` | any subset of the 19 fields | `need`, `confidence`, `advice`, `probabilities` |
| POST | `/sensor` | `{"soil_moisture": 22.5}` | same (sensor-key aliases accepted) |

```sh
curl -X POST localhost:8000/sensor -d '{"soil_moisture":22.5,"temperature_c":31.2}'
# {"need":"Medium","confidence":0.54,"advice":"Irrigate about half the normal dose; ..."}
```

Malformed JSON returns 400. Unknown keys are ignored.

---

## ESP32 side

Wiring, pin numbers and the four rules that stop the demo from breaking
(flyback diode, common ground, pump off the ESP32 5V pin, tube outlet above the
water line) are documented at the top of `firmware/esp32_irrigation.ino`.

Safety is on the device, not in Python: max 60 s burst, min 45 min gap, cutoff
when the probe reads <5% or >95%, and after 3 failed requests it waters 30 s
locally if soil is under 20%. Laptop dies → the plant still survives, and the
pump never runs unattended.

---

## Honest limitations

1. The dataset is synthetic; the accuracy does not transfer to a real field.
2. `confidence` sits near 0.52 on mid-range inputs — the model is decisive only
   on clear cases. Report the probability, not just the label.
3. No time dimension, so no forecasting. If that is the project goal, this file
   is the wrong input and you need a per-minute sensor log.
4. 8 categorical + 11 numeric features is far more than an ESP32 can measure;
   the defaults file is what bridges the gap, and it is a compromise, not data.
5. The exported forest is 6.1 MB — it runs in Python, **not** on the ESP32
   (4 MB flash). The device only calls `/sensor`. Edge inference would need a
   retrained ~15-tree forest, measured against this model before replacing it.
