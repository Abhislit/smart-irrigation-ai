/* Live irrigation dashboard. Polls the stdlib API; no external dependencies. */
const $ = (id) => document.getElementById(id);
const STATES = ["NO_DATA", "COLLECTING", "TRAINING", "READY", "PREDICTING"];
const CRITICAL = ["SENSOR_STALE", "SAFETY_LOCK"];
let lastPrimary = null;
let commandPending = false;

function log(message) {
  const li = document.createElement("li");
  const time = document.createElement("time");
  time.textContent = new Date().toLocaleTimeString([], { hour12: false });
  li.append(time, document.createTextNode(message));
  const list = $("events");
  if (list.children.length === 1 && list.textContent.includes("Waiting")) list.textContent = "";
  list.prepend(li);
  while (list.children.length > 8) list.lastChild.remove();
}

async function get(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} -> ${response.status}`);
  return response.json();
}

function connection(ok) {
  $("conn").classList.toggle("off", !ok);
  $("connText").textContent = ok ? "live" : "offline";
}

function renderState(snap) {
  const state = snap.state;
  const primary = state.primary;
  for (const li of $("stations").children) {
    const index = STATES.indexOf(li.dataset.state);
    const active = STATES.indexOf(primary);
    li.classList.toggle("active", li.dataset.state === primary);
    li.classList.toggle("past", index < active);
  }
  if (primary !== lastPrimary) {
    if (lastPrimary) log(`AI state ${lastPrimary} to ${primary}`);
    lastPrimary = primary;
  }

  const warnings = state.warnings || [];
  $("warnings").textContent = "";
  if (!warnings.length) {
    const span = document.createElement("span");
    span.className = "muted";
    span.textContent = "none";
    $("warnings").append(span);
  }
  for (const name of warnings) {
    const span = document.createElement("span");
    span.className = "warn" + (CRITICAL.includes(name) ? " critical" : "");
    span.textContent = name;
    $("warnings").append(span);
  }

  const age = state.age_minutes;
  $("age").textContent = age == null ? "…" : age < 1 ? "just now" : `${age} min ago`;
  const latest = snap.latest;
  $("clock").textContent = latest ? new Date(latest.ts).toLocaleTimeString([], { hour12: false }) : "…";
  $("temp").textContent = snap.weather ? `${snap.weather.temperature} °C` : "…";
  $("humid").textContent = snap.weather ? `${snap.weather.humidity} %` : "…";
  $("source").textContent = latest ? latest.source : "…";
  $("modeBtn").textContent = snap.mode;
  $("modeBtn").setAttribute("aria-pressed", String(snap.mode === "AUTO"));

  const p = snap.prediction;
  $("current").innerHTML = latest ? `${latest.moisture.toFixed(1)}<small>%</small>` : "…<small>%</small>";
  $("forecast").innerHTML = p ? `${p.moisture_15min.toFixed(1)}<small>%</small>` : "…<small>%</small>";
  $("spread").textContent = p ? `spread ±${p.spread.toFixed(2)} pp, holdout MAE ${p.mae.toFixed(2)} pp` : "spread …";
  $("forecastWhy").textContent = p
    ? `Random Forest: ${latest.moisture.toFixed(1)}% now, ${p.moisture_15min.toFixed(1)}% at +15 min. ${p.why}`
    : "Waiting for a trained model and a fresh reading.";

  const burst = p && p.decision === "BURST";
  $("decision").textContent = p ? p.decision : "HOLD";
  $("decision").classList.toggle("burst", !!burst);
  document.querySelector(".decision").classList.toggle("burst", !!burst);
  $("decisionWhy").textContent = p ? p.why : "No model or stale sensor: no automatic command.";
  $("burstInfo").textContent = burst ? `${p.duration_s} s burst recommended, ${snap.mode} mode` : "No command sent.";
  $("pumpState").textContent = state.pump_state;
  $("pumpState").className = `pump-state ${state.pump_state.toLowerCase()}`;
  $("pumpNote").textContent = state.pump_state === "UNKNOWN"
    ? "Command sent, awaiting the device acknowledgement."
    : state.pump_state === "ON" ? "Sluice open. Do not send a second burst." : "Sluice shut. Safety limits are enforced in firmware.";
  $("burstBtn").disabled = !p || state.pump_state !== "OFF" || commandPending || primary === "NO_DATA" || primary === "COLLECTING";
}

function renderChart(rows, prediction) {
  if (!rows || !rows.length) return;
  const values = rows.map((r) => r.moisture);
  // Fixed scale matches the gridlines: 50/40/30/20 % at y 28/104/180/256.
  const y = (v) => Math.max(16, Math.min(292, 256 - (v - 20) * 7.6));
  const x = (i) => 40 + (i / Math.max(1, rows.length - 1)) * 820;
  $("trace").setAttribute("d", values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" "));

  const nowX = x(rows.length - 1);
  const nowY = y(values[values.length - 1]);
  $("bridgeBand").setAttribute("x", nowX);
  $("bridgeBand").setAttribute("width", Math.max(0, 960 - nowX));
  $("nowDot").setAttribute("cx", nowX);
  $("nowDot").setAttribute("cy", nowY);
  if (prediction) {
    const futureY = y(prediction.moisture_15min);
    $("bridge").setAttribute("d", `M${nowX} ${nowY} L960 ${futureY}`);
    $("futureDot").style.setProperty("cy", String(futureY));
  } else {
    $("bridge").setAttribute("d", "");
  }
}

function renderMetrics(m) {
  if (!m.ready) return;
  $("mae").textContent = `${m.mae.toFixed(2)} pp`;
  $("r2").textContent = m.r2.toFixed(2);
  $("persist").textContent = `${m.persistence_mae.toFixed(2)} pp`;
  $("ridge").textContent = `${m.ridge_mae.toFixed(2)} pp`;
  $("trainedRows").textContent = m.trained_rows.toLocaleString();
  const top = Object.entries(m.importances).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const max = top[0] ? top[0][1] : 1;
  $("importances").textContent = "";
  for (const [name, value] of top) {
    const row = document.createElement("div");
    row.className = "bar";
    const label = document.createElement("span");
    const short = { minutes_since_irrigation: "since irrigation", moisture_lag0: "moisture now", hour_sin: "hour sin", hour_cos: "hour cos" };
    label.textContent = short[name] || name.replace("moisture_", "m ").replaceAll("_", " ");
    const track = document.createElement("i");
    const fill = document.createElement("b");
    fill.style.width = `${Math.max(2, (value / max) * 100)}%`;
    track.append(fill);
    const number = document.createElement("b");
    number.textContent = value.toFixed(2);
    row.append(label, track, number);
    $("importances").append(row);
  }
}

async function poll() {
  try {
    const [snap, history, metrics] = await Promise.all([get("/api/state"), get("/api/history"), get("/api/metrics")]);
    connection(true);
    renderState(snap);
    renderChart(history.rows, snap.prediction);
    renderMetrics(metrics);
  } catch (error) {
    connection(false);
    $("decisionWhy").textContent = `Server unreachable: ${error.message}`;
    log("Server unreachable. Retrying in 3 s");
  }
  setTimeout(poll, 3000);
}

$("modeBtn").addEventListener("click", async () => {
  const mode = $("modeBtn").textContent === "AUTO" ? "MANUAL" : "AUTO";
  try {
    const response = await fetch("/api/mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    if (!response.ok) throw new Error(`mode change rejected (${response.status})`);
    log(`Mode switched to ${mode}`);
    $("cmdError").hidden = true;
    poll();
  } catch (error) {
    $("cmdError").textContent = error.message;
    $("cmdError").hidden = false;
  }
});

$("burstBtn").addEventListener("click", async () => {
  commandPending = true;
  $("burstBtn").disabled = true;
  try {
    const response = await fetch("/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ duration_s: 40 }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || `command rejected (${response.status})`);
    log(`Burst ${body.id} queued for ${body.duration_s} s`);
    $("cmdError").hidden = true;
  } catch (error) {
    $("cmdError").textContent = error.message;
    $("cmdError").hidden = false;
  } finally {
    commandPending = false;
    poll();
  }
});

poll();
