"""Demo HTTP service: a form for humans, /sensor for the ESP32.

    ./run.sh src/api.py            # http://localhost:8000

Endpoints
    GET  /          HTML form, posts to /predict
    POST /predict   {"Soil_Moisture": 18, ...} -> need + probabilities
    POST /sensor    {"soil_moisture": 18, "temperature_c": 34} -> same, defaults fill the rest
    GET  /health    {"status": "ok"}
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import joblib

from common import CATEGORICAL, DEFAULTS_PATH, MODEL_PATH, load_raw
from predict import predict

PORT = 8000

MODEL = joblib.load(MODEL_PATH)
BASE = json.loads(DEFAULTS_PATH.read_text())
RAW = load_raw()
OPTIONS = {c: sorted(RAW[c].unique().tolist()) for c in CATEGORICAL}


def form_html() -> str:
    rows = []
    for col in CATEGORICAL:
        opts = "".join(
            f'<option {"selected" if v == BASE[col] else ""}>{v}</option>' for v in OPTIONS[col]
        )
        rows.append(f'<label>{col}<select name="{col}">{opts}</select></label>')
    for col, val in BASE.items():
        if col not in CATEGORICAL:
            rows.append(f'<label>{col}<input name="{col}" type="number" step="any" value="{val}"></label>')
    return f"""<!doctype html><meta charset="utf-8"><title>Irrigation need</title>
<style>
 body{{font:15px system-ui;max-width:720px;margin:2rem auto;padding:0 1rem}}
 form{{display:grid;grid-template-columns:1fr 1fr;gap:.6rem}}
 label{{display:flex;flex-direction:column;font-size:12px;color:#555}}
 input,select{{padding:.4rem;font-size:14px}}
 button{{grid-column:span 2;padding:.7rem;font-size:15px;cursor:pointer}}
 pre{{background:#f4f6f8;padding:1rem;border-radius:6px;overflow:auto}}
</style>
<h2>Irrigation need predictor</h2>
<form id="f">{''.join(rows)}<button>Predict</button></form>
<pre id="out">—</pre>
<script>
f.onsubmit = async e => {{
  e.preventDefault();
  const body = Object.fromEntries(new FormData(f));
  const r = await fetch('/predict', {{method:'POST', body: JSON.stringify(body)}});
  out.textContent = JSON.stringify(await r.json(), null, 2);
}};
</script>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode(), "application/json")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, form_html().encode(), "text/html; charset=utf-8")
        elif self.path == "/health":
            self._json(200, {"status": "ok"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path not in ("/predict", "/sensor"):
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._json(200, predict(payload, model=MODEL, base=BASE))
        except (ValueError, TypeError) as exc:  # bad JSON or non-numeric field
            self._json(400, {"error": str(exc)})

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}")


if __name__ == "__main__":
    print(f"serving on http://localhost:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
