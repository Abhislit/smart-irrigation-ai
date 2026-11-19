# Site and dashboard design record

What was designed and where it lives. This file is the handoff note for anyone
editing the same folder with another assistant.

## URLs

| URL | Serves |
| --- | --- |
| `http://localhost:8001/` | live dashboard (also `/index.html`) |
| `http://localhost:8001/dashboard` | live dashboard, explicit path used by the site buttons |
| `http://localhost:8001/site/` | public project site |
| `http://localhost:8001/site/demo.html` | standalone site variant; buttons use a full `localhost:8001` URL |

Start the server with `PORT=8001 ./run.sh src/server.py`. Port 8000 may already be
taken by another project on the same machine.

The two site pages are identical except for their dashboard links. `site/index.html`
uses `/dashboard`, which is correct when the Python server serves everything.
`site/demo.html` uses `http://localhost:8001/dashboard`, so the buttons still work
if the folder is opened with VS Code Live Server, `python3 -m http.server`, or as
`file://` — in those cases a root-absolute `/` points back at the site itself.

## Public site (`site/index.html`)

Static page built with the design-taste-frontend kit copied into `site/assets/`.
No build step, no framework. Palette `blue-black-cornflower`, type `Schibsted
Grotesk` with `JetBrains Mono` for figures, soft radius, tonal buttons, wordmark.

Deals used: centred hero, centre nav, close-type, footer statement, surface
pairs, word highlight. Hero and main ground use the kit's `deep` and `topglow`
backgrounds. No shader (this is a software product page, not a tech/game page).

Sections, in order:

1. Hero — "Live irrigation forecasting, 15 minutes ahead", a real snapshot of
   the dashboard's five readouts, and the primary dashboard button. The
   "Live demo / Sensor readings are simulated" pill keeps the data honest.
2. Method — "One decision, four steps": probe, forecast, decision, pump.
3. Metrics — "Model metrics": held-out MAE `0.0117`, R² `0.988`, 4,865 rows.
4. Safety — "Four limits the ESP32 keeps": 60 s burst, 45 min gap, 5–95 %
   sanity range, 30 s offline fallback after 3 failed contacts.
5. Close — "Open the live dashboard" and the repeated primary action.

The word-highlight moment runs on the safety statement. Google Fonts are loaded
from their CDN; the system-font fallback is intentional so the page still reads
offline.

Verification used the kit's gate (PASS), quick consistency at 1440/390 (0 FAIL),
and the layout checker. Full-width consistency still reports rhythm warnings at
820/768/390; they are not gate-blocking.

## Live dashboard (`src/dashboard/`)

`index.html`, `styles.css` and `app.js`, served locally by `src/server.py` with
no external assets. The canal-gauge direction shows moisture on the same scale
as the pump decision, so the user reads direction and action together.

Visible states are the real pipeline states — no data, collecting, training,
model ready, predicting — plus AUTO/MANUAL, per-tree spread and held-out
MAE/R² instead of an invented probability. Readings refresh every 3 s. Pump
state is always device-reported; commands are one-shot `{id, duration_s<=60}`
and acknowledged through `last_command_id` in `/ingest`.

The dashboard's safety limits are duplicated in firmware. Python can request a
burst; only the ESP32 can allow it.

## Editing without conflicts

Two assistants have edited this folder. Before changing a shared file, check
`git status` and `git log` first. New explanatory files belong in `docs/` so
they do not overwrite a page someone else is editing.
