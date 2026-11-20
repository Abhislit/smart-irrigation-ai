# Smart Irrigation Realtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old classifier with a live moisture-only IoT system that logs readings, forecasts moisture 15 minutes ahead with a Random Forest Regressor, shows every AI state on a realtime dashboard, and controls the pump safely over WiFi.

**Architecture:** ESP32 POSTs moisture to a stdlib Python server every 60 s and polls a one-shot command endpoint. The server stores readings in SQLite, fetches temperature/humidity from Open-Meteo (no extra sensors), trains and serves the regressor, computes a visible state machine and decision, and serves a polling dashboard. All pump safety is enforced in firmware.

**Tech Stack:** Python 3.14 (stdlib `http.server`, `sqlite3`), pandas 3, scikit-learn 1.9, existing `.deps` folder; Arduino C++ on ESP32; plain HTML/CSS/JS.

**Spec:** `docs/superpowers/specs/2026-11-20-smart-irrigation-forecast-design.md`

## Global Constraints

- Only sensor hardware: one capacitive soil-moisture probe and one pump. No DHT, no extra hardware.
- Temperature/humidity come from Open-Meteo, fetched by the server, cached, no API key.
- Forecast horizon is exactly **15 rows** at 60 s sampling.
- Chronological split only. Target must never appear in features.
- Pump safety in firmware: 60 s max burst, 45 min min gap, moisture sanity 5–95 %, 30 s local fallback after 3 failed server contacts.
- Commands are one-shot `{id, duration_s<=60}`, acknowledged once by the device.
- Device-reported pump state only; server never assumes the pump executed.
- No new Python dependencies beyond `pandas`, `scikit-learn`, `matplotlib`, `joblib`.
- All dashboard panels update live (3 s polling), including AI states and pump state.

## Review Focus

- Gap or stale reading → `SENSOR_STALE`, no prediction shown. Test in Task 3.
- No trained model yet → `NO_DATA`/`COLLECTING`, no pump command issued. Test in Task 3.
- Duplicate command id → firmware drives the pump once, not twice. Test in Task 5.
- Pump state reported by device, never inferred from issued commands. Test in Task 3.
- Open-Meteo unreachable → `WEATHER_STALE`, last known value used, no crash. Test in Task 3.
- AUTO mode still obeys 45 min gap and 15 % moisture floor. Test in Task 4.

---

### Task 1: Storage and simulated history

**Files:** Create `src/store.py`, `src/simulator.py`, `src/test_project.py` (start of suite)

**Interfaces:**
- Produces: `init_db(db_path)`, `insert_reading(db_path, row)`, `latest(db_path) -> dict | None`, `read_window(db_path, n) -> list[dict]`, `count(db_path) -> int`; `backfill(db_path, days=14) -> int`.

- [ ] **Step 1: Write failing tests** in `src/test_project.py` for: init creates the `readings` table; `insert_reading` + `latest` round-trips moisture/temp/humidity/pump/source; `read_window(5)` returns at most 5 rows newest-last; `backfill` inserts ~20 160 rows and every row has a timestamp.
- [ ] **Step 2:** Run `./run.sh -m unittest discover -s src -p test_project.py` — expect failures for missing modules.
- [ ] **Step 3:** Implement `src/store.py` with SQLite schema `readings(ts TEXT PRIMARY KEY, moisture REAL, temp REAL, humidity REAL, pump INTEGER, minutes_since_irrigation REAL, source TEXT)` and `src/simulator.py`: per-minute water balance — moisture decays by temp/humidity-driven evapotranspiration, irrigation jumps it by 20–30 points every 1–2 days, pump flag set on those minutes, `source='simulated'`, ending at the current minute.
- [ ] **Step 4:** Run the tests — expect PASS.
- [ ] **Step 5:** Commit `feat: sqlite store and water-balance history simulator`.

### Task 2: Random Forest regressor

**Files:** Create `src/model.py`; extend `src/test_project.py`

**Interfaces:**
- Consumes: `read_window` from Task 1.
- Produces: `build_features(rows) -> (X: DataFrame, y: Series)`, `train(rows) -> dict` (pickleable model bundle with `model`, `mae`, `r2`, `persistence_mae`, `ridge_mae`, `importances`), `predict(bundle, rows) -> dict` with keys `moisture_15min`, `spread`, `mae`, `r2`, `decision`, `why`.

- [ ] **Step 1:** Write failing tests: `build_features` never contains `target`; shifting is exactly 15 rows (construct rows where moisture rises linearly and assert target equals row i+15); `train` returns `mae < persistence_mae`; `predict` on a dry-down window returns `moisture_15min < current moisture` and a non-negative `spread`.
- [ ] **Step 2:** Run tests — expect FAIL (module missing).
- [ ] **Step 3:** Implement `src/model.py`: features = moisture lags 0/5/10/15/30, 15/30 min slopes, temp, humidity, hour sin/cos, minutes since irrigation, pump; target = moisture shifted −15; chronological 70/30 split; `RandomForestRegressor(n_estimators=300, min_samples_leaf=5, random_state=42)`; baselines persistence and Ridge; `spread` = standard deviation of per-tree predictions.
- [ ] **Step 4:** Save trained bundle to `models/forecast.joblib`; run tests — expect PASS.
- [ ] **Step 5:** Commit `feat: 15-minute soil moisture random forest regressor`.

### Task 3: Server, weather, state machine, command queue

**Files:** Create `src/weather.py`, `src/state.py`, `src/server.py`; extend tests

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: `current_weather() -> dict` (temperature, humidity, stale flag); `compute_state(ctx) -> dict` with `primary` and `warnings`; HTTP `GET /`, `/api/state`, `/api/history`, `/api/metrics`, `/command`, `POST /ingest`, `/command`.

- [ ] **Step 1:** Write failing tests: `compute_state` with no rows → `NO_DATA`; with <200 rows → `COLLECTING`; with a 10-minute-old last reading → warning `SENSOR_STALE`; with stale weather → warning `WEATHER_STALE` and primary unchanged; with an issued-but-unacknowledged command → pump state is `UNKNOWN`, not `ON`.
- [ ] **Step 2:** Run tests — expect FAIL.
- [ ] **Step 3:** Implement `src/weather.py` (Open-Meteo fetch with 15 min cache in `data/weather.json`, returns last cached values + `stale=True` on failure) and `src/state.py` (primary chain `NO_DATA → COLLECTING → TRAINING → READY → PREDICTING`; warning pills as per spec).
- [ ] **Step 4:** Implement `src/server.py` on port 8000: `/ingest` writes a reading (source `esp32`), `/command` GET returns one pending command with `{id, duration_s}` and POST from the dashboard queues one, `/api/state` returns primary + warnings + prediction + decision + reported pump state + mode (AUTO/MANUAL), `/api/history` returns last 240 rows, `/api/metrics` returns MAE/R²/baselines/importances. Serve `src/dashboard/` statically. No command is queued when model is untrained or data stale.
- [ ] **Step 5:** Run tests and live smoke: `curl localhost:8000/api/state`, POST a fake `/ingest`, confirm state changes — expect PASS.
- [ ] **Step 6:** Commit `feat: realtime API, weather cache, visible AI state machine`.

### Task 4: Decision engine and AUTO/MANUAL

**Files:** Modify `src/server.py`, `src/state.py`; extend tests

**Interfaces:**
- Consumes: `predict()` from Task 2, `compute_state()` from Task 3.
- Produces: `decide(prediction, ctx) -> dict` with `action` (`BURST`/`HOLD`), `duration_s`, `why`.

- [ ] **Step 1:** Write failing tests: prediction 28.5 with current 31 and 60 min since irrigation → `BURST`; current moisture 12 → `HOLD` (floor); 20 min since last irrigation → `HOLD` (gap); MANUAL mode → no auto command; SAFETY_LOCK warning → no auto command.
- [ ] **Step 2:** Run tests — expect FAIL.
- [ ] **Step 3:** Implement `decide()` with the spec thresholds (<30 predicted, >15 current, >45 min gap, 40 s burst) and wire it into `/api/state` and AUTO command queueing in `src/server.py`.
- [ ] **Step 4:** Run tests — expect PASS.
- [ ] **Step 5:** Commit `feat: explainable irrigation decision with auto/manual modes`.

### Task 5: ESP32 firmware

**Files:** Create `firmware/esp32_realtime.ino` (keep existing sketch for reference)

**Interfaces:**
- Consumes: `/ingest` and `/command` from Task 3.

- [ ] **Step 1:** Write a host-side test in `src/test_project.py` that parses the sketch source and asserts the presence of `MAX_BURST_MS = 60000`, `MIN_GAP_MS = 45UL * 60000UL`, `pumpStopAt`, `lastCommandId`, and a check that rejects `duration_s > 60`.
- [ ] **Step 2:** Run test — expect FAIL (file missing).
- [ ] **Step 3:** Implement the sketch: read GPIO34 every 60 s with GPIO25 power gating, POST `{moisture, pump_state, last_command_id}`, poll `GET /command`, execute each id once, drive GPIO26, enforce all safety limits locally, 30 s fallback after 3 failed contacts, serial `o`/`f` override.
- [ ] **Step 4:** Run test — expect PASS; compile with Arduino IDE if available.
- [ ] **Step 5:** Commit `feat: ESP32 realtime ingest and one-shot pump commands`.

### Task 6: Realtime dashboard (impeccable skill)

**Files:** Create `src/dashboard/index.html`, `styles.css`, `app.js`

**Interfaces:**
- Consumes: `/api/state`, `/api/history`, `/api/metrics` from Tasks 3–4.

- [ ] **Step 1:** Invoke the `impeccable` skill and design a single-page dashboard: header with live connection + mode; primary state chain + warning pills; live moisture chart with the 15-minute prediction marker; decision card with plain-English `why`; pump card with device-reported state and a manual burst button; metrics/feature-importance panel; event log.
- [ ] **Step 2:** Implement static files with 3 s polling, no CDN dependencies (draw the chart with inline SVG or canvas).
- [ ] **Step 3:** Verify in browser: `./run.sh src/server.py`, open `localhost:8000`, confirm values change after POSTing `/ingest`, manual burst queues a command, warning pills appear on stale data.
- [ ] **Step 4:** Commit `feat: realtime AI dashboard`.

### Task 7: End-to-end verification and docs

**Files:** Modify `README.md`; extend `src/test_project.py`

- [ ] **Step 1:** Add one end-to-end test: backfill → train → serve state → POST reading → decision → command → acknowledge, asserting no target leakage and no command inside the 45 min gap.
- [ ] **Step 2:** Run full suite, API smoke and dashboard check; fix anything failing.
- [ ] **Step 3:** Rewrite `README.md` for the new project: run steps, architecture, AI states, safety, measured MAE/R², and the honest note that temp/humidity are API-sourced and history is simulated until real logging starts.
- [ ] **Step 4:** Commit `docs: realtime irrigation project README`, push to GitHub.
