---
name: The Quiet Field Instrument
description: A calm, plant-centered irrigation dashboard with traceable live decisions.
colors:
  paper: "#fbfcf9"
  ground: "#f1f4ef"
  ground-deep: "#e8eee7"
  ink: "#20342a"
  ink-soft: "#44574b"
  muted-ink: "#59695f"
  rule: "#d7dfd7"
  rule-strong: "#b7c5b8"
  measured-green: "#527b53"
  forest-green: "#315b3c"
  measured-tint: "#e7efe4"
  forecast-amber: "#8c571f"
  forecast-tint: "#f4ecdf"
  warning-coral: "#a84c3d"
  warning-tint: "#f6e8e4"
typography:
  display:
    fontFamily: "Georgia, Times New Roman, serif"
    fontSize: "2.3rem"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Georgia, Times New Roman, serif"
    fontSize: "1.35rem"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 650
    lineHeight: 1.4
rounded:
  square: "0"
  workspace: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  burst-button:
    backgroundColor: "{colors.forest-green}"
    textColor: "{colors.paper}"
    rounded: "{rounded.square}"
    padding: "9px 12px"
    height: "39px"
  mode-control:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.square}"
    padding: "6px 8px 6px 11px"
  central-workspace:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.workspace}"
    padding: "24px 29px 20px"
---

# Design System: The Quiet Field Instrument

## Overview

**Creative North Star: "The Quiet Field Instrument"**

This dashboard presents irrigation telemetry as a composed field instrument: quiet enough to scan in a lab, precise enough to explain to an examiner. The measured probe and +15-minute forecast flank a centered plant; the chart directly beneath them grounds that living focal point in actual values. A small editorial serif gives the system a human voice, while clear sans-serif labels keep controls and readings practical.

One central workspace carries a soft, diffuse lift. The pipeline rail, decision controls, and evidence footer stay flat and orderly. Color and motion clarify data rather than decorate it. Stale readings, simulated history, firmware safety, and device-reported pump state remain explicit.

**Key Characteristics:**
- A centered plant that responds gently to measured moisture.
- One softly lifted workspace; supporting surfaces stay quiet.
- Measured green, forecast amber, and warning coral have distinct jobs.
- Freshness, provenance, decisions, and safety remain readable at a glance.

**The Plant-as-Proof Rule.** The plant is centered evidence of the measured moisture, not an ornamental mascot.

## Colors

Mineral paper and botanical ink create a calm field; green marks measured data, amber marks the forecast, and coral is reserved for warnings.

### Primary
- **Deep Forest Green** (`#315b3c`): Primary actions and the measured trace.
- **Measured Leaf** (`#527b53`): Moisture-responsive plant color and measured-data marks.

### Secondary
- **Forecast Amber** (`#8c571f`): Forecast values, horizon markers, and model output.

### Tertiary
- **Warning Coral** (`#a84c3d`): Critical and stale warnings, and the threshold line.

### Neutral
- **Mineral Paper** (`#fbfcf9`): Main working surface and text-on-action contrast.
- **Field Ground** (`#f1f4ef`): Page background, rail, and evidence footer.
- **Botanical Ink** (`#20342a`): Primary text and measured values.
- **Muted Ink** (`#59695f`): Secondary labels, notes, and timestamps.
- **Quiet Rule** (`#d7dfd7`): Panel dividers and chart gridlines.

**The Signal-Color Rule.** Green is measured, amber is forecast, coral is warning; never exchange these meanings.

## Typography

- **Display Font:** Georgia (with Times New Roman fallback)
- **Body Font:** Segoe UI (with Helvetica Neue and Arial fallbacks)
- **Label/Mono Font:** Body sans; telemetry uses tabular numerals rather than a decorative monospace.

**Character:** Georgia adds a restrained, human note to the product name, workspace title, and decision. The interface remains sans-serif and numerically stable everywhere the visitor scans or acts.

### Hierarchy
- **Display** (500, `2.3rem`, `1` line-height): Decision outcome.
- **Headline** (500, `1.35rem`, `1.2` line-height): Workspace title.
- **Title** (700, `1rem`): Rail, control, and footer headings.
- **Body** (400, `14px`, `1.5` line-height): Explanations, notes, and event messages.
- **Label** (650–700, `12px` minimum): Readout labels, freshness, chart keys, and metadata.

Use tabular numerals for readings, timestamps, ages, and metrics. Keep explanatory copy comfortably wrapped and avoid shrinking functional labels to preserve density.

**The Stable-Reading Rule.** Live numbers change in place; tabular figures keep adjacent labels from shifting.

## Layout

The desktop board uses a compact header above a three-column instrument: a 220px pipeline and conditions rail, a flexible centered workspace, and a 286px decision/device column. A four-part evidence footer spans the board. The central plant sits between current and forecast values, with the historical trace below.

At widths below `1180px`, the rail and workspace occupy two columns, the controls move into a three-part row, and the footer becomes two columns. Below `760px`, the page stacks; the plant remains centered between the values, and the footer becomes a single column. At `420px`, labels and chart ticks simplify without hiding the state or values. Short desktop viewports use a tighter header, rail, chart, and footer so the evidence remains in the first screen.

Use a 4–24px spacing rhythm inside panels, with generous separation between the primary workspace and supporting evidence. The body scrolls naturally on mobile; there is no demo-blocking navigation.

## Elevation & Depth

Depth is reserved for one surface: the central irrigation workspace uses `0 8px 26px rgba(32, 52, 42, 0.09)` over the field ground. The rail, controls, and footer use flat tonal surfaces and thin rules. Do not layer a border and a shadow on the same container.

### Shadow Vocabulary
- **Central workspace** (`0 8px 26px rgba(32, 52, 42, 0.09)`): Separates the plant, readouts, and chart as one working surface.

**The One-Lift Rule.** Lift the central work surface only; never turn each section into a floating card.

## Shapes

The central workspace alone has a `12px` radius. Buttons, toggle, warning labels, chart, and support panels stay square-edged. Dividers are quiet 1px rules; the chart uses a measured grid and dashed forecast/threshold lines. The plant is a crisp, data-responsive SVG diagram with no gradients or glow.

## Components

### Buttons
- **Shape:** Square corners (`0` radius).
- **Primary:** Forest green with paper text; the manual burst button spans its available width and is `39px` tall.
- **Hover / Focus:** Hover inverts to paper with a forest outline. Keyboard focus uses a visible 3px amber outline.
- **Disabled:** Muted ground treatment and a disabled cursor; never imply a burst can be issued.

### Chips
- **Style:** Compact square labels with a pale tone and readable state text.
- **State:** Nominal uses measured green; caution uses amber; critical/stale uses coral.

### Cards / Containers
- **Central workspace:** Paper surface, `12px` radius, single soft shadow, approximately `24px` internal padding.
- **Supporting areas:** Flat rail, control column, and footer separated by rules or tonal ground; no nested cards.

### Signature Component: Plant Readout

The plant sits between measured and forecast values. Its leaf color and posture, plus the water level inside its pot, respond to the latest probe value. The caption repeats the moisture and condition in words. A slow sway is the only ambient animation; watering drops appear only with a burst recommendation. `prefers-reduced-motion` disables the loops and transitions.

### Signature Component: Moisture Trace

The measured series is a forest-green line. The amber dashed bridge leads to the +15-minute forecast. The 30% safety threshold is separately labeled; axes, legend, spread, and holdout error remain explicit.

## Do's and Don'ts

### Do:
- **Do** keep the measured and forecast values on opposite sides of the centered plant.
- **Do** show sensor age, server connectivity, source, and stale warnings as text.
- **Do** preserve the single softly lifted workspace and keep secondary areas flat.
- **Do** honor reduced-motion preferences and keep all state readable without color.
- **Do** label simulated history and distinguish device-reported pump state from a queued command.

### Don't:
- **Don't** add gradients, glass, glow, emoji, or decorative motion.
- **Don't** turn the rail, controls, or footer into a repeated grid of floating cards.
- **Don't** imply that software overrides firmware safety or that stale data is fresh.
- **Don't** invent confidence; show model spread and held-out metrics instead.
