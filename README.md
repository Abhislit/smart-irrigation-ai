# Smart Irrigation — live 15-minute forecast

A B.Tech major project with **one capacitive moisture probe, one submersible pump and one ESP32 on WiFi**. The laptop runs a small Python server: it logs a reading every 60 s, predicts soil moisture 15 minutes ahead with a Random Forest regressor, explains a watering decision, and serves a dashboard that updates every 3 s. The pump's hard safety limits live in firmware, not in Python.

No cloud account, no GPU, no API key, no frontend dependencies or CDN.

---

## Run it

Dependencies are already in `./.deps`; `run.sh` only puts that folder on `PYTHONPATH` (this machine has no `python3-venv`).

```sh
./run.sh -m unittest discover -s src -p test_project.py   # 23 tests
./run.sh src/server.py                                     # http://localhost:8000
PORT=8001 ./run.sh src/server.py                            # if port 8000 is in use
```

On first start the server creates `data/irrigation.db` and backfills 14 days of per-minute simulated history ending at the current minute. **Those backfill rows are simulated and are what the dashboard shows until the ESP32 starts posting.** The dashboard is at `http://localhost:8000/`. To retrain from the current database:

```sh
curl -X POST localhost:8000/api/train
```

### Connect the ESP32

The ESP32 sketch is `firmware/esp32_realtime.ino`. Before flashing, set:

- `WIFI_SSID`, `WIFI_PASS` — the same WiFi the laptop is on;
- `API_BASE` — `http://<laptop-LAN-IP>:<port>`. The server prints the exact line to paste when it starts, for example `ESP32: set API_BASE = "http://192.168.1.12:8001"`.

Laptop and ESP32 must be on the same network. The laptop firewall must allow inbound TCP on that port. The sketch posts one reading per 60 s to `/ingest` and polls `/command`.

Confirm data is arriving:

```sh
curl -s localhost:8001/api/state | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['latest']['source'], d['latest']['ts'], d['state']['age_minutes'])"
```

`source` must read `esp32` and `age_minutes` should stay under 2. If it still reads `simulated`, no ingest reached the server — check the firmware's `API_BASE`, the port, and the firewall. Wiring, ADC calibration notes and the four hardware cautions are at the top of the sketch.

---

## What is live

```
 ESP32 probe ──POST /ingest (60 s)──> SQLite ──> Random Forest ──> decision
      ^                                  │                            │
      └──── GET /command (one-shot) ──────┴── state machine ──> dashboard (3 s)
                                                    │
                                     Open-Meteo temperature/humidity (cached)
```

- **State chain:** `NO_DATA → COLLECTING → TRAINING → READY → PREDICTING`, all five stations visible at once.
- **Warnings:** `SENSOR_STALE` (last reading older than 5 min), `WEATHER_STALE`, `MODEL_STALE`, `SAFETY_LOCK`, `MANUAL_OVERRIDE`.
- **Forecast:** change in moisture over the next 15 rows (15 minutes at 60 s sampling), added to the current reading. The model predicts the *change*, not the absolute level: absolute targets regress to the mean of the wet/dry cycle and lose to persistence. Training windows that contain an irrigation event are dropped, so the model forecasts an unwatered dry-down instead of predicting its own command.
- **Decision:** `BURST` only when the forecast is below 30 %, current moisture is above 15 %, at least 45 minutes have passed since watering, and mode is `AUTO`. Otherwise `HOLD`, with the reason printed in plain English. A burst is 40 s by default.
- **Pump state:** only what the device reports. An issued but unacknowledged command shows `UNKNOWN`, never `ON`.
- **No fabricated confidence:** the dashboard shows per-tree spread and held-out MAE/R², not a probability invented for a regressor.

### Dashboard demo in ten seconds

1. Open `/` — fresh timestamp, state chain, measured and forecast numbers, decision, pump and safety limits are all in the first viewport.
2. `POST /ingest` with a dry reading and watch the forecast and decision change on the next poll:

   ```sh
   curl -X POST localhost:8000/ingest -H 'Content-Type: application/json' \
     -d '{"moisture":22.0,"pump_state":0}'
   ```

3. In `AUTO`, the BURST recommendation becomes one queued command. `GET /command` returns `{"id": "...", "duration_s": 40}` once, then an empty id until the device acknowledges with `last_command_id` on its next ingest.
4. Toggle `MANUAL` to suppress automatic commands; use the pump card's 40 s button instead.

---

## HTTP API

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/` | — | dashboard (HTML, CSS and JS are served locally) |
| GET | `/api/state` | — | state, warnings, prediction, decision, mode, weather, latest reading, pump state |
| GET | `/api/history` | — | last 240 readings |
| GET | `/api/metrics` | — | MAE, R², baselines, importances, trained row count |
| GET | `/api/health` | — | `{"status":"ok"}` |
| GET | `/command` | — | one pending `{id, duration_s}`; the queue then clears |
| POST | `/ingest` | `{"moisture": 22.0, "pump_state": 0, "last_command_id": "..."}` | stored reading with timestamp; optional `ts` |
| POST | `/command` | `{"duration_s": 40}` | queued one-shot command (capped at 60 s) |
| POST | `/api/mode` | `{"mode": "AUTO" \| "MANUAL"}` | current mode |
| POST | `/api/train` | — | retrains from the last 5000 rows |

Malformed JSON returns 400. Commands are refused when the model is not ready, data is stale, or the pump is already commanded.

---

## Measured model result

Trained on 4,865 usable windows from the simulated history, chronological 70/30 split, `RandomForestRegressor(300 trees, min_samples_leaf=5)`:

| Metric | Value |
|---|---|
| Holdout MAE | 0.011 percentage points |
| Holdout R² | 0.99 |
| Persistence MAE (predict no change) | 0.380 pp |
| Ridge MAE | 0.069 pp |

The largest feature importance is humidity, which is API-sourced rather than measured on the board. These numbers describe the simulated water-balance series, **not** a field deployment. See `DESIGN.md` for the visual system and `.impeccable/design.json` for its machine-readable sidecar.

---

## Safety, on the device

From `firmware/esp32_realtime.ino`:

- maximum 60 s burst,
- minimum 45 min gap between bursts,
- 5–95 % moisture sanity cutoff,
- after 3 failed server contacts, a local 30 s fallback if soil is under 20 %,
- each command id drives the pump once and is acknowledged on the next ingest.

The server can *recommend* a burst; it cannot make the pump ignore these rules. If the laptop dies, the plant still gets watered and the pump never runs unattended.

---

## Layout

```
README.md                    this file
PRODUCT.md / DESIGN.md       product truth and visual system
src/server.py                HTTP API, command queue, AUTO/MANUAL, dashboard host
src/model.py                 features, regressor, decision explanation
src/state.py                 visible state machine and warning pills
src/weather.py               Open-Meteo fetch with 15 min cache and stale fallback
src/store.py / simulator.py  SQLite readings and 14-day water-balance backfill
src/dashboard/               static HTML/CSS/JS dashboard, no external assets
src/test_project.py          23 tests including an end-to-end pipeline test
firmware/esp32_realtime.ino  probe, ingest, one-shot command, local safety
models/forecast.joblib       trained bundle, retrained after filtering irrigation windows
data/irrigation.db           runtime readings (generated, not committed)
docs/superpowers/            approved design spec and implementation plan
```

Old classifier files (`src/train.py`, `src/api.py`, `firmware/esp32_irrigation.ino`, `reports/`) remain for reference. That project used the synthetic Kaggle dataset, which has **no timestamp** and therefore cannot train a `t+15` regressor; its 99 % accuracy measured the data generator, not field skill. It is not part of the live system.

---

## Honest limitations

1. The 14-day history is a simulated water balance, not measured soil data. Its smooth dry-downs make the regressor look far better than a real probe will; treat the MAE/R² above as pipeline evidence only.
2. Temperature and humidity come from Open-Meteo over WiFi, not from a local sensor. When the API is unreachable the last cached values are used and `WEATHER_STALE` is shown.
3. Real rows append after the simulated backfill; gaps produce `SENSOR_STALE` and no automatic command. Let the node log for a while before trusting the forecast.
4. The forest runs on the laptop, not the ESP32. The device only reports moisture, fetches a command and enforces safety.
5. Access is over the college LAN. There is no authentication and no cloud relay; do not expose port 8000 to the internet.
6. Calibrate `ADC_DRY` and `ADC_WET` for your actual probe before the demo, or the moisture percentage will be wrong no matter how good the model is.
