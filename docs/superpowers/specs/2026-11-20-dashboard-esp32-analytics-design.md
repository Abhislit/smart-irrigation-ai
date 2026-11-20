# Dashboard ESP32 analytics — design

Date: 2026-11-20
Status: proposed

## Intent

Show the data the ESP32 actually sends, analytically, on the existing
dashboard: a dedicated ESP32 live panel (option A) plus a fuller analytics
section (option B).

**When the ESP32 is connected, show only real ESP32 readings.** The
simulated history is a fallback for when the ESP32 is offline, never mixed
into the live view.

## Goals

- ESP32-only live chart with stats: reading count, min / max / average
  moisture, sample interval, gap count.
- Analytics section: moisture over time, a distribution histogram, and a
  pump ON/OFF event timeline — all from ESP32 rows while the device is live.
- A small data-source badge: "ESP32 live" or "Simulated fallback".
- Works with the current stdlib server and vanilla JS + SVG. No new
  dependencies, no CDN, no cloud.

## Non-goals

- No change to ingestion, firmware, or the trained model.
- No authentication, no retention policy, no database migration.
- No new sensor fields.
- Not retraining the model on ESP32-only data (35 rows is far too little).

## Definitions

- **ESP32 live**: the newest `source='esp32'` reading is under 5 minutes old.
- **Fallback**: no ESP32 reading in the last 5 minutes; use simulated rows.

## Constraint

While the probe reads 0 %, every chart is flat at zero. That is the sensor
wire issue, not the dashboard. The panel must still render correctly.

The AI state machine needs ≥ 200 rows to leave COLLECTING, so `snapshot()`
and the model keep reading the full stored window internally. Only the
**displayed** series and analytics switch to ESP32-only. This keeps the
forecast working while the screen shows real data.

## Approach

Add one read-only endpoint, `GET /api/analytics`, computed in SQL from the
existing `readings` table (no schema change), and render it in a new
dashboard section.

When ESP32 is live, the endpoint returns ESP32 rows only and sets
`"live": true`. When it is not, it returns simulated rows and
`"live": false`.

Response shape:

```json
{
  "live": true,
  "source": "esp32",
  "counts": {"esp32": 35, "simulated": 20160},
  "esp32": {
    "count": 35, "min": 0.0, "max": 0.0, "avg": 0.0,
    "first": "2026-11-20T12:25:32", "last": "2026-11-20T13:12:57",
    "interval_s": 60, "gaps": 0
  },
  "series": [{"ts": "...", "moisture": 0.0, "pump": 0}],
  "histogram": [
    {"bucket": "0-10", "rows": 35}
  ],
  "pump_events": [
    {"start": "...", "end": "...", "duration_s": 40}
  ]
}
```

- `series`: the last 120 rows of the active source.
- `interval_s`: median gap between consecutive readings of the active source.
- `gaps`: intervals longer than 2.5 x the median (missed samples).
- `histogram`: 10 buckets of 10 percentage points, active source only.
- `pump_events`: pump 0→1 and 1→0 transitions, paired; open event has null end.
- `counts`: both totals, for the badge only, never plotted.

## UI

New section below the existing chart, same visual system (cards, monospace
numbers, accent colour):

1. **ESP32 live** — line chart of `series` + four stat tiles
   (count, min, max, average) and a line for interval / gaps.
2. **Distribution** — histogram bars for the active source.
3. **Pump events** — horizontal timeline, one bar per pump-on window.
4. **Source badge** — "ESP32 live" (green) or "Simulated fallback" (muted).

No mixed ESP32/simulated chart. When live, no simulated series is drawn
anywhere. The existing top chart also switches to the active source, so it
never mixes the two.

Rendered with inline SVG, same 1000-unit viewBox convention as the current
chart. Polled with the existing 3 s `poll()`.

## Files

- `src/server.py` — `/api/analytics` route + `analytics()` helper; make
  `/api/history` return the active source only.
- `src/dashboard/index.html` — new section markup.
- `src/dashboard/app.js` — fetch + render functions.
- `src/dashboard/styles.css` — section styles.
- `src/test_project.py` — analytics helper assertions.

## Testing

- Unit: analytics over a seeded temp DB — counts, min/max/avg, histogram
  totals, pump event pairing, gap detection, live vs fallback selection.
- Route: `GET /api/analytics` returns 200 and the expected keys.
- Browser: dashboard renders with no JS errors at 1440 and 390; with ESP32
  live, no simulated points are in the chart.

## Risk

Flat 0 % lines until the probe wiring is fixed. With fewer than ~31 ESP32
rows the forecast cannot be computed; the dashboard must degrade to "collecting"
rather than error.
