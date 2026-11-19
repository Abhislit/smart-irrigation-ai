---
version: 1
slug: "src-dashboard-index-html"
primary_target: "src/dashboard/index.html"
related_targets: []
---

Scope: web dashboard at `src/dashboard/index.html`, Operate mode. Audience: a student presenting a live irrigation-AI loop to examiners on a laptop/projector. Keep the existing telemetry, forecast, decision, safety, provenance, event log, and 40-second manual burst behavior; no CDN or new frontend dependencies.

Chosen direction: user-pinned, modern and calm plant-centered dashboard. Success is a clearly live, attractive presentation that feels deliberately crafted rather than generated from dashboard defaults. The user's visual requirements are minimal and calm, a plant centered in the main view, subtle purposeful animation, a softly lifted central surface, and a modern finish.

## Direction contract

THESIS: The plant is the visual center of a real irrigation inference loop; measured soil, forecast, decision, and device state prove what the system is doing.

OWN-WORLD: Mineral-white ground, deep botanical ink, restrained leaf green for measured data, warm amber for forecast, and coral only for warnings. System sans with tabular telemetry, generous whitespace, and quiet rules. Lift only the central irrigation workspace with a soft, diffuse shadow; keep the supporting rail and footer flat. No gradients, glass, generic nested cards, emoji, or decorative glow.

STORY: Freshness and link status come first. The eye then reads current and +15-minute moisture around the centered plant, follows the actual trace, and finds the decision, device-reported pump state, and manual action. Safety, model quality, and simulated/live provenance remain visible.

FIRST VIEWPORT: Compact live header; left pipeline and conditions; center plant flanked by measured and forecast values, with the wide chart directly beneath; right decision, pump state, and burst control; bottom strip for firmware safety, holdout metrics, feature importance, and provenance. On mobile, stack without clipping the plant or controls.

FORM: User-pinned calm, minimal, animated plant-centered composition outside the rolled options; seed:2eea014ed2c28f5c.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
