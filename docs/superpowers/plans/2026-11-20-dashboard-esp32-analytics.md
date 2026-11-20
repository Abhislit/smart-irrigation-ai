# Dashboard ESP32 Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show only real ESP32 readings, with stats and charts, on the live dashboard; simulated history is an offline fallback.

**Architecture:** One pure aggregation function in `store.py` reads the SQLite `readings` table and returns stats, series, histogram and pump events for the active source. `server.py` exposes it at `/api/analytics` and makes `/api/history` return the same active source. The dashboard renders a new analytics section with inline SVG and vanilla JS.

**Tech Stack:** Python stdlib (`sqlite3`, `statistics`, `datetime`), `ThreadingHTTPServer`, vanilla JS, inline SVG, existing CSS variables.

**Spec:** `docs/superpowers/specs/2026-11-20-dashboard-esp32-analytics-design.md`

## Global Constraints

- No new dependencies, no CDN, no cloud.
- When the newest `source='esp32'` row is ≤ 5 minutes old, the dashboard and analytics show **only** ESP32 rows. Otherwise they show simulated rows. Never mix the two in one view.
- `snapshot()` and the model keep reading the full stored window internally (≥ 200 rows needed for the state machine). Only display and analytics switch source.
- The probe currently reads `0.0 %`; every chart must still render (flat line) without errors.
- Keep the existing visual system: `--paper`, `--ground`, `--ink`, `--muted`, `--line`, `--green`, `--amber`, tabular numerals.

## Review Focus

- **ESP32 live but fewer than 31 rows:** prediction cannot be built; the analytics panel must still render and the page must not error.
- **Every reading identical (0 %):** histogram has one non-zero bucket and the chart is a flat line; no divide-by-zero.
- **Open pump event:** pump turned on with no later off; `end` is null and it must not crash.
- **One reading or none:** `interval_s` is null, `gaps` is 0, the chart hides instead of drawing a broken path.
- **Timestamps:** ISO strings with `T` must parse with `datetime.fromisoformat`; no timezone is assumed.

---

### Task 1: Analytics aggregation in `store.py`

**Files:**
- Modify: `src/store.py`
- Test: `src/test_project.py`

**Interfaces:**
- Produces:
  - `active_source(db_path: str, now: datetime | None = None, live_minutes: float = 5.0) -> tuple[str, bool]`
  - `read_source_window(db_path: str, source: str, n: int) -> list[dict]`
  - `analytics(db_path: str, now: datetime | None = None, live_minutes: float = 5.0, series_n: int = 120) -> dict`
- `analytics` returns `{"live", "source", "counts", "stats", "series", "histogram", "pump_events"}` where:
  - `stats = {"count", "min", "max", "avg", "first", "last", "interval_s", "gaps"}`
  - `series` items are `{"ts", "moisture", "pump"}`
  - `histogram` items are `{"bucket": "0-10".."90-100", "rows": int}`
  - `pump_events` items are `{"start", "end"|None, "duration_s"|None}`

- [ ] **Step 1: Write the failing tests**

Add to `src/test_project.py`, importing the new names from `store`:

```python
class AnalyticsTest(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(self.db)
        init_db(self.db)

    def tearDown(self):
        if os.path.exists(self.db):
            os.remove(self.db)

    def _row(self, ts, moisture, pump=0, source="esp32"):
        insert_reading(self.db, {
            "ts": ts, "moisture": moisture, "temp": 30.0, "humidity": 40.0,
            "pump": pump, "minutes_since_irrigation": 60.0, "source": source,
        })

    def test_active_source_prefers_fresh_esp32(self):
        self._row("2026-11-20T12:00:00", 20.0)
        now = datetime(2026, 11, 20, 12, 2, 0)
        self.assertEqual(active_source(self.db, now=now), ("esp32", True))

    def test_active_source_falls_back_when_stale(self):
        self._row("2026-11-20T12:00:00", 20.0)
        self._row("2026-11-20T11:00:00", 40.0, source="simulated")
        now = datetime(2026, 11, 20, 12, 30, 0)
        self.assertEqual(active_source(self.db, now=now), ("simulated", False))

    def test_analytics_stats_and_histogram(self):
        for i, m in enumerate([5.0, 15.0, 25.0, 35.0]):
            self._row(f"2026-11-20T12:0{i}:00", m)
        out = analytics(self.db, now=datetime(2026, 11, 20, 12, 3, 0))
        self.assertTrue(out["live"])
        self.assertEqual(out["source"], "esp32")
        self.assertEqual(out["stats"]["count"], 4)
        self.assertEqual(out["stats"]["min"], 5.0)
        self.assertEqual(out["stats"]["max"], 35.0)
        self.assertEqual(out["stats"]["avg"], 20.0)
        self.assertEqual(out["stats"]["interval_s"], 60)
        self.assertEqual(sum(b["rows"] for b in out["histogram"]), 4)

    def test_pump_events_pair_on_and_off(self):
        self._row("2026-11-20T12:00:00", 20.0, pump=0)
        self._row("2026-11-20T12:01:00", 20.0, pump=1)
        self._row("2026-11-20T12:02:00", 20.0, pump=1)
        self._row("2026-11-20T12:03:00", 20.0, pump=0)
        out = analytics(self.db, now=datetime(2026, 11, 20, 12, 4, 0))
        self.assertEqual(len(out["pump_events"]), 1)
        self.assertEqual(out["pump_events"][0]["duration_s"], 120)

    def test_open_pump_event_has_null_end(self):
        self._row("2026-11-20T12:00:00", 20.0, pump=1)
        out = analytics(self.db, now=datetime(2026, 11, 20, 12, 1, 0))
        self.assertIsNone(out["pump_events"][0]["end"])

    def test_gap_detected(self):
        self._row("2026-11-20T12:00:00", 20.0)
        self._row("2026-11-20T12:01:00", 20.0)
        self._row("2026-11-20T12:02:00", 20.0)
        self._row("2026-11-20T12:12:00", 20.0)
        out = analytics(self.db, now=datetime(2026, 11, 20, 12, 13, 0))
        self.assertEqual(out["stats"]["gaps"], 1)

    def test_single_reading_is_safe(self):
        self._row("2026-11-20T12:00:00", 20.0)
        out = analytics(self.db, now=datetime(2026, 11, 20, 12, 1, 0))
        self.assertIsNone(out["stats"]["interval_s"])
        self.assertEqual(out["stats"]["gaps"], 0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./run.sh src/test_project.py AnalyticsTest`
Expected: FAIL — `ImportError: cannot import name 'active_source'`.

- [ ] **Step 3: Implement the helpers in `src/store.py`**

Add imports `from datetime import datetime` and `from statistics import median`. Implement exactly these signatures. Details that matter:

- `active_source` returns `("esp32", True)` when the newest esp32 row is ≤ `live_minutes` old, else `("simulated", False)`.
- `read_source_window` uses `WHERE source = ?`, newest `n`, returned oldest-first.
- `analytics` computes `stats` over **all** rows of the active source, `series` over the newest `series_n`, histogram over all rows (bucket `min(9, int(m // 10))`, clamped to 0..9), `interval_s` as the median of consecutive timestamp differences in seconds (None when fewer than 2 rows), `gaps` as the count of intervals > 2.5 × median (0 when median is 0 or None). Pump events pair a 0→1 transition with the next 1→0; an unmatched start has `end=None`, `duration_s=None`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./run.sh src/test_project.py AnalyticsTest`
Expected: PASS (7 tests).

- [ ] **Step 5: Run the full suite**

Run: `./run.sh -m unittest discover -s src -p "test_*.py"`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add src/store.py src/test_project.py
git commit -m "feat: add ESP32 analytics aggregation"
```

---

### Task 2: Server routes

**Files:**
- Modify: `src/server.py`

**Interfaces:**
- Consumes: `analytics`, `active_source`, `read_source_window` from `store`.
- Produces: `GET /api/analytics` returning the `analytics()` dict; `GET /api/history` returning `{"rows": [...], "source": "esp32"|"simulated", "live": bool}`.

- [ ] **Step 1: Wire the imports and routes**

In `src/server.py`, extend the `from store import ...` line with `active_source, analytics, read_source_window`. Replace the `/api/history` branch with:

```python
if path == "/api/history":
    source, live = active_source(str(DB_PATH))
    return self._json(200, {
        "rows": read_source_window(str(DB_PATH), source, 240),
        "source": source,
        "live": live,
    })
if path == "/api/analytics":
    return self._json(200, analytics(str(DB_PATH)))
```

- [ ] **Step 2: Restart the server and verify the endpoints**

Run: `kill $(pgrep -f 'src/server.py') 2>/dev/null; PORT=8001 ./run.sh src/server.py > /tmp/opencode/irrig-live.log 2>&1 &`
Then:
`curl -s localhost:8001/api/analytics | python3 -m json.tool`
Expected: keys `live`, `source`, `counts`, `stats`, `series`, `histogram`, `pump_events`; `source` is `esp32` while the board is posting.
`curl -s localhost:8001/api/history | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['source'], d['live'], len(d['rows']), {r['source'] for r in d['rows']})"`
Expected: `esp32 True <n> {'esp32'}` — no simulated rows.

- [ ] **Step 3: Commit**

```bash
git add src/server.py
git commit -m "feat: expose analytics and source-only history"
```

---

### Task 3: Dashboard markup and styles

**Files:**
- Modify: `src/dashboard/index.html`
- Modify: `src/dashboard/styles.css`

**Interfaces:**
- Produces these element ids used by Task 4: `analyticsSource`, `anCount`, `anMin`, `anMax`, `anAvg`, `anInterval`, `anGaps`, `anChart`, `anTrace`, `anHistogram`, `anPump`.

- [ ] **Step 1: Add the section before `<footer class="footer panel">`**

```html
<section class="analytics panel" aria-labelledby="analyticsTitle">
  <div class="analytics-head">
    <h2 id="analyticsTitle">ESP32 analytics</h2>
    <span id="analyticsSource" class="analytics-badge">…</span>
  </div>
  <div class="analytics-col">
    <h3>Live readings</h3>
    <dl class="stat-grid">
      <div><dt>Readings</dt><dd id="anCount">…</dd></div>
      <div><dt>Average</dt><dd id="anAvg">…</dd></div>
      <div><dt>Minimum</dt><dd id="anMin">…</dd></div>
      <div><dt>Maximum</dt><dd id="anMax">…</dd></div>
      <div><dt>Interval</dt><dd id="anInterval">…</dd></div>
      <div><dt>Gaps</dt><dd id="anGaps">…</dd></div>
    </dl>
    <svg id="anChart" class="analytics-chart" viewBox="0 0 1000 200" preserveAspectRatio="none" role="img" aria-label="ESP32 moisture readings over time">
      <path id="anTrace" class="analytics-trace"></path>
    </svg>
  </div>
  <div class="analytics-col">
    <h3>Distribution</h3>
    <div id="anHistogram" class="hist"><div class="muted">Awaiting readings…</div></div>
  </div>
  <div class="analytics-col">
    <h3>Pump events</h3>
    <div id="anPump" class="pump-track"><span class="muted">No pump events recorded.</span></div>
  </div>
</section>
```

- [ ] **Step 2: Add styles to `src/dashboard/styles.css`**

Use the existing variables. Required classes: `.analytics` (spans `grid-column: 1 / -1`, three equal columns, top border, same padding rhythm as `.footer`), `.analytics-head` (title row, space-between), `.analytics-badge` (small uppercase), `.analytics-badge.live` (green), `.analytics-badge.fallback` (muted), `.analytics-col` (borders like `.footer-col`), `.stat-grid` (two columns, tabular numbers), `.analytics-chart` (full width, 120px high), `.analytics-trace` (no fill, green stroke), `.hist`, `.hist-row` (label / bar / count), `.hist-row i` and `.hist-row i b`, `.pump-track` and `.pump-seg` (absolute amber segments). Add a single-column rule for `.analytics` and reset the column borders inside the existing `@media (max-width: 700px)` block.

- [ ] **Step 3: Verify the page still loads**

Run: `curl -s localhost:8001/dashboard | grep -c 'ESP32 analytics'`
Expected: `1`.

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/index.html src/dashboard/styles.css
git commit -m "feat: add analytics section markup and styles"
```

---

### Task 4: Dashboard rendering

**Files:**
- Modify: `src/dashboard/app.js`

**Interfaces:**
- Consumes: `/api/analytics` response from Task 2; element ids from Task 3.
- Produces: `renderAnalytics(a)`, `renderXLabels(rows)`.

- [ ] **Step 1: Add the render functions**

Add `renderAnalytics(a)` that:
- Sets `#analyticsSource` to `ESP32 live` (class `live`) when `a.live`, else `Simulated fallback` (class `fallback`).
- Fills the six stat tiles; format moisture with `toFixed(1)`, interval as `60 s` (or `—` when null), gaps as an integer.
- Draws `#anTrace` from `a.series`: `x = 40 + (i / max(1, n - 1)) * 920`, `y = 170 - (moisture / 100) * 140`; empty path when fewer than 2 points.
- Builds histogram rows: label, a bar width relative to the largest bucket (0 width when max is 0), and the count.
- Builds pump segments over a 0–100 % track using the first and last timestamps of `a.series`; show the empty note when there are no events.

Add `renderXLabels(rows)` that sets the four `.x-labels .t-tick` time labels to `HH:MM` at 0 / 25 / 50 / 75 % of the span between the first and last row, leaving the `Now` and `+15` ticks unchanged; do nothing when there are fewer than 2 rows.

- [ ] **Step 2: Wire them into `poll()`**

Add `get("/api/analytics")` to the `Promise.all`, call `renderAnalytics(analyticsData)`, and call `renderXLabels(history.rows)` inside `renderChart` or right after it.

- [ ] **Step 3: Verify in a real browser**

Run a Playwright check at 1440×900 against `http://127.0.0.1:8001/dashboard`:
- no `pageerror`
- `#anCount` is not `…`
- `#analyticsSource` reads `ESP32 live`
- the chart path in `#anTrace` is non-empty
- no element with the text `simulated` appears inside the `.analytics` section

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/app.js
git commit -m "feat: render ESP32 analytics panel"
```

---

### Task 5: Full verification

- [ ] **Step 1: Run the suite**

Run: `./run.sh -m unittest discover -s src -p "test_*.py"`
Expected: PASS.

- [ ] **Step 2: Check every route**

`for p in / /dashboard /site/ /api/state /api/metrics /api/history /api/analytics /api/health; do printf "%s " "$p"; curl -s -o /dev/null -w "%{http_code}\n" "localhost:8001$p"; done`
Expected: all `200`.

- [ ] **Step 3: Confirm no simulated rows are served while live**

`curl -s localhost:8001/api/history | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['live']; assert {r['source'] for r in d['rows']} == {'esp32'}; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit any fixes, then push**

```bash
git add -A
git commit -m "test: verify dashboard analytics" 2>/dev/null || true
git push
```
