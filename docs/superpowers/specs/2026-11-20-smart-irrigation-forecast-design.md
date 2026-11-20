# Smart Irrigation: live sensing, 15-minute forecast, visible AI states

## Intent

A B.Tech major-project demo built from the hardware actually available: one
capacitive soil-moisture probe, one 5 V submersible pump, one ESP32 on WiFi.
The system must show, on a single dashboard, the whole AI path: live sensor
data arriving, model training state, the 15-minute moisture prediction, the
decision it produces, and the pump's state — while letting a human switch the
pump remotely. The point is that every "AI state" is visible and explainable,
not hidden inside a black box.

## Goals

1. ESP32 posts moisture readings over WiFi every 60 s and accepts pump commands.
2. Server stores every reading in SQLite and enriches it with temperature and
   humidity fetched from Open-Meteo (no extra hardware, no API key).
3. A Random Forest **Regressor** predicts soil moisture 15 minutes ahead from
   the last hour of readings plus weather and irrigation history.
4. Dashboard shows live telemetry, prediction, horizon, confidence/MAE,
   baseline comparison, feature importance, decision explanation, pump state
   and the full AI state machine.
5. Pump can be switched remotely from the dashboard, but only within hard
   local safety limits enforced on the ESP32.
6. The whole thing runs today with a generated water-balance history; a real
   sensor log can be dropped in later without changing the model code.

## Non-goals

Internet/MQTT control, extra sensors, solar power, on-device inference, mobile
app, multi-node fields.

## Anti-goals

Claiming accuracy from the old synthetic Kaggle CSV (it has no timestamps and
cannot train a t+15 regressor). Letting the pump run without a physical safety
limit. Showing a prediction while the model is untrained or data is stale.

## Constraints and calls already made

- **Only one sensor.** Temperature/humidity come from the Open-Meteo API,
  fetched and cached by the server, not from hardware. Call made here.
- **Brain on the laptop**, not the ESP32. The ESP32 has no room for a forest
  and no way to display AI states. Call made here.
- **Bootstrap data generated locally.** A water-balance simulator produces
  10–14 days of per-minute moisture/temp/humidity/irrigation events so the
  regressor can be trained and the dashboard demonstrated now. Real readings
  append to the same SQLite table. Call made here.
- **LAN remote control** (dashboard and ESP32 on the same WiFi). Internet
  control needs an MQTT broker and credentials; deferred. Call made here.
- Reuse the existing stdlib HTTP server and polling updates rather than add a
  web framework; keep the dependency set to pandas/scikit-learn/matplotlib.

## Approaches considered

1. **Laptop brain + ESP32 gateway (chosen).** Full AI visibility, easy
   retraining, safe, no accounts. Cost: demo needs the laptop running.
2. **Everything on the ESP32.** Nice offline story, but a tiny model cannot
   show training states, baselines or feature importance, and retraining means
   reflashing. Rejected.
3. **Cloud MQTT control.** Real internet remote control, but adds a broker,
   credentials and a new failure mode (pump stranded when the broker drops).
   Rejected for phase one.

## Architecture

```
 moisture probe -> ESP32 --WiFi POST /ingest--> Python server
                     ^                          |-- SQLite readings
                     |-- GET /command ----------|-- Open-Meteo cache (temp/RH)
                     |                          |-- RF Regressor (t+15)
                     |                          |-- decision engine
                     |                          `-- dashboard (poll 3 s)
                     `-- local safety: 60 s max burst, 45 min min gap
```

### Data contract

`readings(ts TEXT PRIMARY KEY, moisture REAL, temp REAL, humidity REAL,
pump INTEGER, minutes_since_irrigation REAL, source TEXT)` — `source` is
`simulated` or `esp32`.

### Model

- Features: moisture at t, t−5, t−10, t−15, t−30; 15/30 min rolling slope;
  temperature; humidity; hour sin/cos; minutes since irrigation; pump state.
- Target: moisture at t+15 min.
- Chronological 70/30 split. Baselines: persistence and Ridge regression.
- Metrics: MAE (% VWC) and R². Retrain on demand or every 200 new rows.

### Visible AI states

`NO_DATA` → `COLLECTING` → `TRAINING` → `READY` → `PREDICTING`, plus
`SENSOR_STALE`, `WEATHER_STALE`, `MODEL_STALE`, `SAFETY_LOCK`,
`MANUAL_OVERRIDE`. Each state is a labelled pill in the UI with a plain-English
explanation of why it is active.

### Decision and safety

Prediction < 30 % AND current moisture > 15 % AND gap > 45 min → recommend a
40 s burst. Human may override from the dashboard. The ESP32 independently
enforces max 60 s burst, 45 min gap, sensor sanity 5–95 %, and a 30 s local
burst after 3 failed server contacts. No network path can bypass these.

## Builder-review decisions

1. **Replacement, not addition.** The new pipeline replaces the old classifier
   files in place; git history keeps the old version recoverable; README is
   rewritten. Two competing projects in one repo would confuse the viva.
2. **Simulator backfills up to "now" and stops.** Live ESP32 rows start after
   that timestamp. Feature windows require contiguous minutes; a gap produces
   `SENSOR_STALE` rather than a prediction built on mixed sources.
3. **One-shot timed commands.** Server issues `{id, duration_s <= 60}`; the
   firmware executes each id once and acknowledges it via `last_command_id` in
   `/ingest`. The dashboard's pump state comes from device reports only, never
   from the server's assumption.
4. **AUTO and MANUAL modes are both present.** AUTO applies recommendations as
   timed bursts; MANUAL requires a click. Visible as a switch in the UI. Local
   safety applies in both modes.
5. **One primary state plus concurrent warning pills.** Warnings
   (`SENSOR_STALE`, `WEATHER_STALE`, `MODEL_STALE`, `SAFETY_LOCK`,
   `MANUAL_OVERRIDE`) can coexist with `READY`/`PREDICTING` and take display
   precedence.
6. **Confidence = spread of the forest's per-tree predictions** for that one
   input, shown beside the fixed holdout MAE/R². Not a fabricated probability.

## Layout

```
src/server.py        HTTP API, SQLite, weather cache, state machine
src/model.py         feature builder, train/predict, baselines
src/simulator.py     water-balance history generator
src/dashboard/       HTML/CSS/JS served by server.py
src/test_project.py  leakage, state and safety tests
firmware/            ESP32 sketch (rewrite of existing one for /ingest + /command)
```

## Verification

- Tests: target never in features; chronological split; prediction horizon is
  exactly 15 rows; state transitions; safety limits; API endpoints.
- End-to-end: run simulator, train, open dashboard, POST a reading, issue a
  remote pump command, confirm safety blocks a second command inside 45 min.

## Left to the builder

Exact visual design (use the impeccable skill), polling interval, chart
library choice, and the specific wording of each state's explanation.
