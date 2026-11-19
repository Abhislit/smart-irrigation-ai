---
name: Smart Irrigation Realtime
description: A live water-routing board for a one-probe, one-pump irrigation node.
colors:
  ink: "#102f3f"
  teal: "#0f6e7b"
  amber: "#d98324"
  amber-ink: "#9a4f0c"
  green: "#5b7a3a"
  red: "#a5352a"
  paper: "#f4f7f5"
  muted: "#566a62"
  line: "#c6d5ce"
  white: "#ffffff"
typography:
  headline:
    fontFamily: "Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "1.15rem"
    fontWeight: 650
    letterSpacing: "0.01em"
  numeric:
    fontFamily: "Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "2.6rem"
    fontWeight: 600
    letterSpacing: "-0.03em"
    fontFeature: "tabular-nums"
  body:
    fontFamily: "Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tabular-nums"
  label:
    fontFamily: "Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    letterSpacing: "0.12em"
rounded:
  none: "0"
spacing:
  hair: "1px"
  xs: "6px"
  sm: "8px"
  lg: "22px"
  xl: "28px"
components:
  button-primary:
    backgroundColor: "{colors.teal}"
    textColor: "{colors.white}"
    rounded: "{rounded.none}"
    padding: "11px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "8px 14px"
  panel:
    backgroundColor: "{colors.white}"
    rounded: "{rounded.none}"
    padding: "22px 20px"
  chip-warning:
    backgroundColor: "#fff2e1"
    textColor: "{colors.amber-ink}"
    rounded: "{rounded.none}"
    padding: "4px 8px"
---

# Design System: Smart Irrigation Realtime

## Overview

**Creative North Star: "The Canal Gauge"**

The dashboard is a water-routing board, not a card grid. A single channel carries the measured trace from the left edge to a NOW station, then an amber bridge reaches a fixed +15 MIN station. Everything around that channel is an instrument readout: pipeline stations down the left, decision and pump state on the right, safety and provenance along the foot. The plant is the channel's living face — its leaves, colour and soil water table read the same measured value the numerals report. The metaphor stops at the gauge; buttons, chips and lists are ordinary web controls a presenter can use without decoding a theme.

Legibility beats decoration. The lecture-hall context means one screen must survive a projector and a skeptical examiner: freshness first, then state, then forecast, then decision, then the device's own pump report. One humanist system sans carries every role, and every number is tabular so live updates never shift the grid. Nothing loads from a CDN. The plant's response to moisture is the one authored moment; the forecast dot's 320 ms move is the only other continuous motion.

Direction seed: `b7d190e555da5e50` (canal gauge, candidate 5, code-led).

**Key Characteristics:**

- One stretched channel with a measured trace, an amber forecast bridge and two labelled stations.
- A living plant beside the measured figure: leaves lift and green as soil wets, droop and amber as it dries, with water rising in the pot and drops falling on a burst recommendation.
- A five-station state chain that writes every state out in words.
- Flat enamel panels separated by single hairlines, never rounded cards or soft shadows.
- Live age, weather source, model quality and safety limits visible without navigation.

**The One Gauge Rule.** The canal metaphor lives only in the channel and its stations. Controls stay standard; no pump button becomes a sluice lever.

**The Freshness Rule.** The last-reading age and clock sit in the top bar before the forecast is read. A stale sensor is named, never implied.

**The Motion Rule.** The plant reacts to data, never to attention: a 700 ms posture and colour transition on each new reading, a slow near-imperceptible sway, and falling drops only while a burst is advised. State is also written in the caption and the numerals, so reduced motion removes the loops without losing the reading.

## Colors

A deep water-indigo shell carries teal measurements and amber forecasts; neutral porcelain keeps the numbers quiet.

### Primary
- **Deep Enamel Indigo** (`#102f3f`): top bar, channel labels, decision numerals and the primary text role. It is the material of the board, not an accent.

### Secondary
- **Measured Teal** (`#0f6e7b`): the measured trace, confirmed pipeline stations, primary button fill and focus rings. This is the colour of something the probe actually reported.

### Tertiary
- **Forecast Amber** (`#d98324`): the +15 MIN station, forecast bridge, forecast band and BURST state. Its ink companion **Burnt Amber** (`#9a4f0c`) keeps small amber text readable on light surfaces.
- **Critical Red** (`#a5352a`): critical warning pills and command errors only.
- **Soil Green** (`#5b7a3a`): the device-reported pump-on lamp.

### Neutral
- **Porcelain** (`#f4f7f5`): page ground and top-bar text.
- **Paper White** (`#ffffff`): panel faces.
- **Hairline** (`#c6d5ce`): one-pixel panel divisions and grid.
- **Muted Slate** (`#566a62`): captions, secondary readings, axis labels and empty states.

**The Measured Rule.** Colour never carries state alone. Every state, warning and pump condition is written out in words, so the board remains readable without colour vision.

## Typography

**Display Font:** Segoe UI, with system-ui and -apple-system fallbacks.
**Body Font:** the same family; no second face.
**Label/Mono Font:** none. Numerals use the body face with `tabular-nums`.

**Character:** One humanist voice throughout. The instrument speaks plainly; it does not switch to a display face for a big number or a monospace face for telemetry.

### Hierarchy
- **Headline** (650, 1.15rem, 1.45 line-height): product name in the top bar.
- **Numeric display** (600, 2.6rem, 1 line-height, -0.03em tracking): measured and forecast moisture; shrinks to 1.9rem under 720px.
- **Decision** (400, 1.8rem, -0.02em tracking): HOLD or BURST, amber when a burst is recommended.
- **Body** (400, 15px, 1.45 line-height): explanations and notes, capped near 46ch in the foot strip.
- **Label** (700, 0.75rem, 0.12em tracking, uppercase): panel headings and the mode toggle. Micro labels drop to 0.68–0.72rem for warnings and log lines.

**The Numbers Rule.** All telemetry uses tabular numerals. A live reading must change its digits without moving the label beside it.

## Layout

The top bar is 72px tall. Below it a one-pixel-gapped grid runs `212px | minmax(0,1fr) | 286px`, with a `minmax(520px,1fr)` content row and an auto footer row; the board fills at least `calc(100vh - 72px)`. Panels use 22px 20px padding, the channel uses 22px 26px, and the footer is a four-cell strip (`1.4fr | 1fr | 1fr | 1.1fr`). The rhythm is tight inside a group (6–14px) and generous between groups (22–30px).

The channel uses a fixed `0 0 1000 320` SVG viewBox with `preserveAspectRatio="none"` so the trace stretches with the panel. Text is deliberately not drawn in that non-uniform space: four y-axis numbers and the NOW / +15 MIN labels sit in an HTML overlay inside `.gauge-frame`, so they render at device resolution at every width.

At 1100px the board drops to two columns and the right-hand cards flow into a wrapping row; at 720px everything stacks into one column, the top bar wraps, forecast numerals shrink, and the two chart labels tighten so they never collide.

## Elevation & Depth

The system is flat by default. Depth comes from one-pixel hairlines, the indigo top bar against porcelain ground, and tonal panel fills such as the `#eaf0ec` footer and `#fff2e1` warning chips. There are no structural shadows. The two `box-shadow` declarations are zero-offset attention rings on the active station and the live pip; they mark state and are not depth.

**The Flat Rule.** No card floats. If a surface needs emphasis, change its tone or its one-pixel border, never its shadow.

## Shapes

Square corners throughout: no `border-radius` is declared anywhere. Stations are 9px diamonds rotated 45 degrees; the live pip is an 8px square with a soft ring; chart strokes are hairlines with a dashed amber bridge and round-ended teal trace. The recurring silhouette is a ruled panel with a straight top edge and a single hairline division.

## Components

### Buttons
- **Shape:** square corners, no radius, no shadow.
- **Primary:** teal fill, white text, 11px padding, full width in the pump card; hover darkens to `#0b5863`.
- **Ghost:** the mode toggle is transparent with a 1px `#7fa7a0` border; manual mode swaps the border and text to amber.
- **Disabled:** `#b9cbc4` fill with `#5f726b` text.
- **Focus:** a 2px teal outline with 3px offset.

### Warning chips
- **Style:** 4px 8px padding, 0.68rem bold uppercase text, `#fff2e1` fill with `#e6c79c` border.
- **State:** critical warnings switch to `#fbe9e7`, `#e3b6b1` and red text. State names are literal (`SENSOR_STALE`, `MANUAL_OVERRIDE`).

### Panels
- **Corner style:** square, separated by 1px hairlines rather than gaps.
- **Background:** paper white; the footer uses a tonal green-grey fill.
- **Internal padding:** 22px 20px (channel 22px 26px).
- **Heading:** 0.75rem uppercase muted label with 12px space below.

### Station list
- **Style:** hairline-separated rows, 10px vertical padding, 9px diamond marker.
- **State:** past stations fill teal, the active station fills amber with a 4px attention ring, and future stations stay outlined. Every row names its state.

### Channel gauge (signature)
- **Geometry:** fixed 1000×320 viewBox stretched to the panel; gridlines at 50, 40, 30 and 20 %.
- **Measured:** a 3px teal trace ending in an indigo dot at NOW.
- **Forecast:** a tinted amber band, a dashed amber bridge and an amber dot at +15 MIN, with a single 320ms `cubic-bezier(.2,.8,.2,1)` transition on the dot's vertical position.
- **Labels:** HTML overlay, never SVG text, so they stay crisp on mobile.
- **Caption:** forest spread and holdout MAE are printed under the legend; no fabricated confidence score.

### Event log
- **Style:** hairline rows with a muted timestamp, capped at eight entries, newest first.
- **Voice:** short factual lines (`Mode switched to MANUAL`, `Burst <id> queued for 40 s`).

## Do's and Don'ts

### Do:
- **Do** keep the amber +15 MIN station on the gauge and its label in the HTML overlay.
- **Do** show the last-reading age and clock before the forecast value.
- **Do** use tabular numerals and 1px rules at every breakpoint.
- **Do** keep `prefers-reduced-motion` honoured by removing the forecast-dot transition.
- **Do** print `SENSOR_STALE`, `WEATHER_STALE` and `MANUAL_OVERRIDE` as words beside the station chain.

### Don't:
- **Don't** add rounded cards, soft drop shadows, gradients or CDN fonts.
- **Don't** put SVG text inside the stretched gauge; it distorts at mobile widths.
- **Don't** carry the canal metaphor into buttons, chips or lists.
- **Don't** encode pump or AI state in colour alone.
- **Don't** invent a confidence percentage; show spread and holdout error.
