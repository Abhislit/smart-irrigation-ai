---
version: 1
slug: "src-dashboard-index-html"
primary_target: "src/dashboard/index.html"
related_targets: []
---

Scope: web dashboard at `src/dashboard/index.html`, Operate mode. Audience: a student presenting to examiners on a projector; success is a live AI loop legible in ten seconds.

Audience, job, action, proof, constraints: the presenter needs a fresh timestamp, the AI state chain, a 15-minute forecast, an explained decision, device-reported pump state and safety status. The one action is a manual 40 s burst. Proof is live data changing without a reload. No CDN, no extra sensors, 3 s polling, simulated history labelled as such.

Chosen direction: canal gauge. Memorable moment: the downstream +15 MIN marker moves as live readings arrive.

## Direction contract

THESIS: A live water-routing board rather than a KPI card grid — the sensor reading is a gauge level and the forecast is a downstream marker, while every control stays a standard web control.

OWN-WORLD: Deep indigo enamel `#102f3f` shell, teal `#0f6e7b` measured trace, amber `#d98324` forecast, porcelain `#f4f7f5` ground, soil green `#5b7a3a` for confirmed states. One-pixel measured rules, channel bends at 45 and 90 degrees, humanist system sans with tabular numerals, dense but breathable grid.

STORY: Freshness is seen first; the eye then follows channel, forecast, decision and pump in one pass. Warnings sit beside the state chain and never replace it.

FIRST VIEWPORT: Top live bar with timestamp and AUTO toggle; left column five AI states as stations; centre one large channel gauge with NOW and +15 MIN markers; right decision and pump cards; bottom strip carrying safety, metrics and history provenance. The manual burst button lives in the pump card.

FORM: Canal gauge, candidate 5 of the grounded list. seed:b7d190e555da5e50

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
