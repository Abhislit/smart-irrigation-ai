"""Realtime irrigation server: ingest, forecast, states, commands, dashboard.

Run: ./run.sh src/server.py    ->  http://localhost:8000
     PORT=8001 ./run.sh src/server.py  ->  http://localhost:8001
"""

import json
import os
import threading
from datetime import datetime
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import joblib

from model import BUNDLE_PATH, predict
from simulator import backfill
from state import compute_state
from store import init_db, insert_reading, latest, read_window
from weather import current_weather

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "irrigation.db"
DASHBOARD = Path(__file__).resolve().parent / "dashboard"
PORT = int(os.environ.get("PORT", "8000"))

LOCK = threading.Lock()
MODE = "AUTO"
PENDING = None          # command waiting for the device to fetch it
LAST_COMMAND_ID = None
ACK_COMMAND_ID = None
BUNDLE = None

if not DB_PATH.exists():
    backfill(str(DB_PATH), days=14)
init_db(str(DB_PATH))
if BUNDLE_PATH.exists():
    BUNDLE = joblib.load(BUNDLE_PATH)


def minutes_since_irrigation(rows) -> float:
    for row in reversed(rows):
        if row["pump"]:
            delta = datetime.now() - datetime.fromisoformat(row["ts"])
            return max(0.0, delta.total_seconds() / 60.0)
    return 1440.0


def snapshot() -> dict:
    # The state machine needs >=200 rows; 120 would pin it at COLLECTING forever.
    rows = read_window(str(DB_PATH), 240)
    weather = current_weather()
    ctx = {
        "rows": rows,
        "has_model": BUNDLE is not None,
        "has_prediction": BUNDLE is not None and len(rows) >= 30,
        "weather": weather,
        "mode": MODE,
        "last_command_id": LAST_COMMAND_ID,
        "ack_command_id": ACK_COMMAND_ID,
        "reported_pump": rows[-1]["pump"] if rows else 0,
    }
    state = compute_state(ctx)
    prediction = predict(BUNDLE, rows, MODE) if BUNDLE and len(rows) >= 30 else None
    return {
        "state": state,
        "prediction": prediction,
        "mode": MODE,
        "weather": {k: weather[k] for k in ("temperature", "humidity", "stale")},
        "latest": rows[-1] if rows else None,
    }


def maybe_auto_command(snap: dict) -> None:
    """AUTO mode turns a BURST recommendation into one queued, one-shot command."""
    global LAST_COMMAND_ID, PENDING
    if MODE != "AUTO" or "SAFETY_LOCK" in snap["state"]["warnings"]:
        return
    if snap["state"]["primary"] in ("NO_DATA", "COLLECTING", "TRAINING"):
        return
    if snap["state"]["pump_state"] == "ON":
        return
    if LAST_COMMAND_ID and ACK_COMMAND_ID != LAST_COMMAND_ID:
        return  # previous command not acknowledged yet
    prediction = snap["prediction"]
    if not prediction or prediction["decision"] != "BURST":
        return
    with LOCK:
        if PENDING is None:
            LAST_COMMAND_ID = uuid.uuid4().hex[:10]
            PENDING = {"id": LAST_COMMAND_ID, "duration_s": prediction["duration_s"]}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, payload):
        self._send(code, json.dumps(payload).encode())

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        global PENDING
        path = self.path.split("?")[0]
        if path == "/":
            path = "/index.html"
        if path in ("/index.html", "/styles.css", "/app.js"):
            file = DASHBOARD / path.lstrip("/")
            if file.exists():
                ctype = {".css": "text/css", ".js": "text/javascript"}.get(file.suffix, "text/html")
                return self._send(200, file.read_bytes(), f"{ctype}; charset=utf-8")
            return self._send(404, b"not found", "text/plain")
        if path == "/api/state":
            snap = snapshot()
            maybe_auto_command(snap)
            return self._json(200, snap)
        if path == "/api/history":
            return self._json(200, {"rows": read_window(str(DB_PATH), 240)})
        if path == "/api/metrics":
            if not BUNDLE:
                return self._json(200, {"ready": False})
            return self._json(
                200,
                {
                    "ready": True,
                    "mae": BUNDLE["mae"],
                    "r2": BUNDLE["r2"],
                    "persistence_mae": BUNDLE["persistence_mae"],
                    "ridge_mae": BUNDLE["ridge_mae"],
                    "importances": BUNDLE["importances"],
                    "trained_rows": BUNDLE["trained_rows"],
                },
            )
        if path == "/api/health":
            return self._json(200, {"status": "ok"})
        if path == "/command":
            with LOCK:
                command, PENDING = PENDING, None
            return self._json(200, command or {"id": None, "duration_s": 0})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        global MODE, LAST_COMMAND_ID, PENDING, ACK_COMMAND_ID, BUNDLE
        path = self.path.split("?")[0]
        try:
            body = self._body()
        except (ValueError, TypeError) as exc:
            return self._json(400, {"error": str(exc)})

        if path == "/ingest":
            with LOCK:
                rows = read_window(str(DB_PATH), 120)
                weather = current_weather()
                msi = minutes_since_irrigation(rows)
                if body.get("last_command_id"):
                    ACK_COMMAND_ID = body["last_command_id"]
                row = {
                    "ts": body.get("ts") or datetime.now().isoformat(timespec="seconds"),
                    "moisture": float(body["moisture"]),
                    "temp": weather["temperature"],
                    "humidity": weather["humidity"],
                    "pump": int(bool(body.get("pump_state", 0))),
                    "minutes_since_irrigation": msi,
                    "source": "esp32",
                }
                insert_reading(str(DB_PATH), row)
            return self._json(200, {"ok": True, "ts": row["ts"]})

        if path == "/command":
            duration = min(60, max(1, int(body.get("duration_s", 40))))
            snap = snapshot()
            if snap["state"]["primary"] in ("NO_DATA", "COLLECTING", "TRAINING"):
                return self._json(409, {"error": "model not ready"})
            if "SENSOR_STALE" in snap["state"]["warnings"]:
                return self._json(409, {"error": "sensor data stale"})
            if snap["state"]["pump_state"] == "ON":
                return self._json(409, {"error": "pump already commanded"})
            with LOCK:
                LAST_COMMAND_ID = uuid.uuid4().hex[:10]
                PENDING = {"id": LAST_COMMAND_ID, "duration_s": duration}
            return self._json(200, PENDING)

        if path == "/api/mode":
            MODE = "AUTO" if body.get("mode") == "AUTO" else "MANUAL"
            return self._json(200, {"mode": MODE})

        if path == "/api/train":
            rows = read_window(str(DB_PATH), 5000)
            if len(rows) < 200:
                return self._json(409, {"error": "not enough rows"})
            from model import train

            BUNDLE = train(rows)
            return self._json(200, {"ready": True, "rows": BUNDLE["trained_rows"]})

        self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}")


if __name__ == "__main__":
    print(f"serving on http://localhost:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
