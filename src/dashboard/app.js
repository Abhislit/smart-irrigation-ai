/* Live irrigation dashboard. Polls the stdlib API; no external dependencies. */
const $ = (id) => document.getElementById(id);
const STATES = ["NO_DATA", "COLLECTING", "TRAINING", "READY", "PREDICTING"];
const CRITICAL = ["SENSOR_STALE", "SAFETY_LOCK"];
let lastPrimary = null;
let commandPending = false;
let currentRows = [];
const mix = (a, b, t) => "#" + [1, 3, 5].map((i) => Math.round(parseInt(a.slice(i, i + 2), 16) * (1 - t) + parseInt(b.slice(i, i + 2), 16) * t).toString(16).padStart(2, "0")).join("");

function log(message) {
  const li = document.createElement("li");
  const time = document.createElement("time");
  time.textContent = new Date().toLocaleTimeString([], { hour12: false });
  li.append(time, document.createTextNode(message));
  const list = $("events");
  if (list && list.children.length === 1 && list.textContent.includes("Waiting")) {
    list.textContent = "";
  }
  if (list) {
    list.prepend(li);
    while (list.children.length > 8) list.lastChild.remove();
  }
}

async function get(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} -> ${response.status}`);
  return response.json();
}

function connection(ok) {
  const conn = $("conn");
  if (conn) conn.classList.toggle("off", !ok);
  const connText = $("connText");
  if (connText) connText.textContent = ok ? "online" : "offline";
}

function renderPlant(latest, watering) {
  const caption = $("plantCaption");
  if (!latest) { 
    if (caption) caption.textContent = "Waiting for sensor stream…"; 
    return; 
  }
  const m = latest.moisture;
  const t = Math.max(0, Math.min(1, (m - 12) / 28));
  const plant = $("plant");
  if (plant) {
    plant.style.setProperty("--droop", (38 * (1 - t)).toFixed(1));
    plant.style.setProperty("--water", (0.12 + 0.88 * t).toFixed(2));
    plant.style.setProperty("--leaf", mix("#a8661f", "#5b7a3a", t));
    plant.classList.toggle("watering", !!watering);
    plant.classList.toggle("dry", t < 0.4);
  }
  const mood = watering ? "Thirsty — burst advised" : t > 0.75 ? "Well watered" : t > 0.45 ? "Moist and steady" : t > 0.2 ? "Drying out" : "Deficit — needs water";
  if (caption) caption.textContent = `${mood} · ${m.toFixed(1)}% soil`;
}

function renderState(snap) {
  const state = snap.state;
  const primary = state.primary;
  const stations = $("stations");
  if (stations) {
    for (const li of stations.children) {
      const index = STATES.indexOf(li.dataset.state);
      const active = STATES.indexOf(primary);
      li.classList.toggle("active", li.dataset.state === primary);
      li.classList.toggle("past", index < active);
    }
  }
  if (primary !== lastPrimary) {
    if (lastPrimary) log(`AI state ${lastPrimary} → ${primary}`);
    lastPrimary = primary;
  }

  const warnings = state.warnings || [];
  const warnBox = $("warnings");
  if (warnBox) {
    warnBox.textContent = "";
    if (!warnings.length) {
      const span = document.createElement("span");
      span.className = "muted";
      span.textContent = "All telemetry nominal";
      warnBox.append(span);
    }
    for (const name of warnings) {
      const span = document.createElement("span");
      span.className = "warn" + (CRITICAL.includes(name) ? " critical" : "");
      span.textContent = name;
      warnBox.append(span);
    }
  }

  const age = state.age_minutes;
  if ($("age")) $("age").textContent = age == null ? "…" : age < 1 ? "just now" : `${age.toFixed(1)} min ago`;
  const latest = snap.latest;
  if ($("clock")) $("clock").textContent = latest ? new Date(latest.ts).toLocaleTimeString([], { hour12: false }) : "…";
  if ($("temp")) $("temp").textContent = snap.weather ? `${snap.weather.temperature.toFixed(1)} °C` : "…";
  if ($("humid")) $("humid").textContent = snap.weather ? `${snap.weather.humidity.toFixed(0)} %` : "…";
  if ($("source")) $("source").textContent = latest ? (latest.source === "simulated" ? "Simulated Stream" : "ESP32 Hardware") : "…";
  
  const modeBtn = $("modeBtn");
  if (modeBtn) {
    const modeText = modeBtn.querySelector(".mode-text") || modeBtn;
    modeText.textContent = snap.mode;
    modeBtn.setAttribute("aria-pressed", String(snap.mode === "AUTO"));
  }

  const p = snap.prediction;
  if ($("current")) $("current").innerHTML = latest ? `${latest.moisture.toFixed(1)}<small>%</small>` : "…<small>%</small>";
  if ($("forecast")) $("forecast").innerHTML = p ? `${p.moisture_15min.toFixed(1)}<small>%</small>` : "…<small>%</small>";
  
  if (latest && p && $("trendDelta")) {
    const diff = p.moisture_15min - latest.moisture;
    const sign = diff > 0.05 ? "▲ +" : diff < -0.05 ? "▼ " : "▲ ";
    const diffText = Math.abs(diff) < 0.05 ? "Horizon Steady (±0.0 pp)" : `${sign}${diff.toFixed(1)} pp horizon delta`;
    $("trendDelta").textContent = diffText;
  }

  if ($("spread")) {
    $("spread").textContent = p ? `Spread ±${p.spread.toFixed(2)} pp · Holdout MAE ${p.mae.toFixed(2)} pp` : "spread …";
  }
  
  if ($("forecastWhy")) {
    $("forecastWhy").textContent = p
      ? `Random Forest: Current ${latest.moisture.toFixed(1)}% → Expected ${p.moisture_15min.toFixed(1)}% at +15 min horizon. ${p.why}`
      : "Waiting for trained model and fresh telemetry packets.";
  }

  const burst = p && p.decision === "BURST";
  renderPlant(latest, burst);
  
  const decisionEl = $("decision");
  if (decisionEl) {
    decisionEl.textContent = p ? p.decision : "HOLD";
    decisionEl.classList.toggle("burst", !!burst);
  }
  const decisionCard = document.querySelector(".decision-section") || document.querySelector(".decision-card") || document.querySelector(".decision");
  if (decisionCard) decisionCard.classList.toggle("burst", !!burst);
  
  if ($("decisionWhy")) {
    $("decisionWhy").textContent = p ? p.why : "No model or stale sensor: no automatic command.";
  }
  if ($("burstInfo")) {
    $("burstInfo").textContent = burst ? `${p.duration_s} s burst recommended (${snap.mode} mode)` : "No active command dispatched.";
  }

  const pumpStateEl = $("pumpState");
  if (pumpStateEl) {
    pumpStateEl.textContent = state.pump_state;
    pumpStateEl.className = `pump-state ${state.pump_state.toLowerCase()}`;
  }

  const pumpIconWrap = $("pumpIconWrap");
  if (pumpIconWrap) {
    pumpIconWrap.classList.toggle("on", state.pump_state === "ON");
  }

  if ($("pumpNote")) {
    $("pumpNote").textContent = state.pump_state === "UNKNOWN"
      ? "Command queued, awaiting ESP32 device acknowledgement."
      : state.pump_state === "ON" ? "Valve open (irrigating). Safety limits active." : "Valve shut (idle). Safety interlocks enforced in firmware.";
  }

  const burstBtn = $("burstBtn");
  if (burstBtn) {
    burstBtn.disabled = !p || state.pump_state !== "OFF" || commandPending || primary === "NO_DATA" || primary === "COLLECTING";
  }
}

function renderChart(rows, prediction) {
  if (!rows || !rows.length) return;
  currentRows = rows;
  const values = rows.map((r) => r.moisture);
  // Fixed scale matches the gridlines: 50/40/30/20 % at y 28/104/180/256.
  const y = (v) => Math.max(16, Math.min(292, 256 - (v - 20) * 7.6));
  const x = (i) => 40 + (i / Math.max(1, rows.length - 1)) * 820;
  const path = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  
  if ($("trace")) $("trace").setAttribute("d", path);

  const nowX = x(rows.length - 1);
  if ($("traceFill")) $("traceFill").setAttribute("d", `${path} L${nowX.toFixed(1)} 292 L40 292 Z`);
  const nowY = y(values[values.length - 1]);
  
  if ($("bridgeBand")) {
    $("bridgeBand").setAttribute("x", nowX);
    $("bridgeBand").setAttribute("width", Math.max(0, 960 - nowX));
  }
  if ($("bridgePattern")) {
    $("bridgePattern").setAttribute("x", nowX);
    $("bridgePattern").setAttribute("width", Math.max(0, 960 - nowX));
  }
  if ($("nowDot")) {
    $("nowDot").setAttribute("cx", nowX);
    $("nowDot").setAttribute("cy", nowY);
  }
  if (prediction) {
    const futureY = y(prediction.moisture_15min);
    if ($("bridge")) $("bridge").setAttribute("d", `M${nowX} ${nowY} L960 ${futureY}`);
    if ($("futureDot")) $("futureDot").style.setProperty("cy", String(futureY));
  } else {
    if ($("bridge")) $("bridge").setAttribute("d", "");
  }
}

function renderMetrics(m) {
  if (!m || !m.ready) return;
  if ($("mae")) $("mae").textContent = `${m.mae.toFixed(2)} pp`;
  if ($("r2")) $("r2").textContent = m.r2.toFixed(2);
  if ($("persist")) $("persist").textContent = `${m.persistence_mae.toFixed(2)} pp`;
  if ($("ridge")) $("ridge").textContent = `${m.ridge_mae.toFixed(2)} pp`;
  if ($("trainedRows")) $("trainedRows").textContent = `${m.trained_rows.toLocaleString()} pts`;
  
  const top = Object.entries(m.importances).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const max = top[0] ? top[0][1] : 1;
  const importancesBox = $("importances");
  if (importancesBox) {
    importancesBox.textContent = "";
    for (const [name, value] of top) {
      const row = document.createElement("div");
      row.className = "bar";
      const label = document.createElement("span");
      const short = { minutes_since_irrigation: "Since irrigation", moisture_lag0: "Moisture (lag0)", hour_sin: "Diurnal sin", hour_cos: "Diurnal cos", slope15: "15m Rate" };
      label.textContent = short[name] || name.replace("moisture_", "m ").replaceAll("_", " ");
      label.title = name;
      
      const track = document.createElement("i");
      const fill = document.createElement("b");
      fill.style.width = `${Math.max(2, (value / max) * 100)}%`;
      track.append(fill);
      
      const number = document.createElement("b");
      number.className = "bar-num";
      number.textContent = `${(value * 100).toFixed(0)}%`;
      
      row.append(label, track, number);
      importancesBox.append(row);
    }
  }
}

// Chart Tooltip Tracking
const chartSvg = $("chart");
const chartTooltip = $("chartTooltip");
if (chartSvg && chartTooltip) {
  chartSvg.addEventListener("mousemove", (e) => {
    if (!currentRows || !currentRows.length) return;
    const rect = chartSvg.getBoundingClientRect();
    const relX = (e.clientX - rect.left) / rect.width;
    const svgX = relX * 1000;
    
    // Check if within the historical range [40, 860]
    if (svgX < 40 || svgX > 860) {
      chartTooltip.hidden = true;
      return;
    }
    
    const index = Math.round(((svgX - 40) / 820) * (currentRows.length - 1));
    const clamped = Math.max(0, Math.min(currentRows.length - 1, index));
    const pt = currentRows[clamped];
    if (!pt) return;
    
    chartTooltip.hidden = false;
    const ttVal = $("ttVal");
    const ttTime = $("ttTime");
    if (ttVal) ttVal.textContent = `${pt.moisture.toFixed(1)}%`;
    if (ttTime) ttTime.textContent = new Date(pt.ts).toLocaleTimeString([], { hour12: false });
    
    chartTooltip.style.left = `${e.clientX - rect.left}px`;
    chartTooltip.style.top = `${e.clientY - rect.top}px`;
  });

  chartSvg.addEventListener("mouseleave", () => {
    chartTooltip.hidden = true;
  });
}

function renderAnalytics(a) {
  if (!a) return;
  const badge = $("analyticsSource");
  if (badge) {
    badge.textContent = a.live ? "ESP32 live" : "Simulated fallback";
    badge.className = `analytics-badge ${a.live ? "live" : "fallback"}`;
  }

  const s = a.stats || {};
  const set = (id, text) => { const el = $(id); if (el) el.textContent = text; };
  set("anCount", s.count != null ? s.count.toLocaleString() : "—");
  set("anAvg", s.avg != null ? `${s.avg.toFixed(1)}%` : "—");
  set("anMin", s.min != null ? `${s.min.toFixed(1)}%` : "—");
  set("anMax", s.max != null ? `${s.max.toFixed(1)}%` : "—");
  set("anInterval", s.interval_s != null ? `${s.interval_s} s` : "—");
  set("anGaps", s.gaps != null ? String(s.gaps) : "—");

  const trace = $("anTrace");
  const series = a.series || [];
  if (trace) {
    if (series.length < 2) {
      trace.setAttribute("d", "");
    } else {
      trace.setAttribute("d", series.map((r, i) => {
        const x = 40 + (i / (series.length - 1)) * 920;
        const y = 170 - (Math.max(0, Math.min(100, r.moisture)) / 100) * 140;
        return `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
      }).join(" "));
    }
  }

  const hist = $("anHistogram");
  if (hist) {
    hist.textContent = "";
    const buckets = a.histogram || [];
    const max = Math.max(0, ...buckets.map((b) => b.rows));
    for (const b of buckets) {
      const row = document.createElement("div");
      row.className = "hist-row";
      const label = document.createElement("span");
      label.textContent = b.bucket;
      const track = document.createElement("i");
      const fill = document.createElement("b");
      fill.style.width = `${max ? Math.max(0, (b.rows / max) * 100) : 0}%`;
      track.append(fill);
      const count = document.createElement("span");
      count.textContent = b.rows;
      row.append(label, track, count);
      hist.append(row);
    }
    if (!buckets.length) {
      const note = document.createElement("div");
      note.className = "muted";
      note.textContent = "No readings yet.";
      hist.append(note);
    }
  }

  const pump = $("anPump");
  if (pump) {
    pump.textContent = "";
    const events = a.pump_events || [];
    const times = series.map((r) => new Date(r.ts).getTime());
    const start = times.length ? Math.min(...times) : 0;
    const end = times.length ? Math.max(...times) : 0;
    const span = end - start || 1;
    if (!events.length) {
      const note = document.createElement("span");
      note.className = "muted";
      note.textContent = "No pump events recorded.";
      pump.append(note);
    } else {
      for (const ev of events) {
        const seg = document.createElement("span");
        seg.className = "pump-seg";
        const from = Math.max(0, (new Date(ev.start).getTime() - start) / span);
        const to = ev.end ? Math.min(1, (new Date(ev.end).getTime() - start) / span) : 1;
        seg.style.left = `${from * 100}%`;
        seg.style.width = `${Math.max(1, (to - from) * 100)}%`;
        seg.title = ev.end ? `${ev.duration_s} s pump-on` : "Pump on (open)";
        pump.append(seg);
      }
    }
  }
}

function renderXLabels(rows) {
  const ticks = document.querySelectorAll(".x-labels .t-tick");
  if (!ticks.length || !rows || rows.length < 2) return;
  const start = new Date(rows[0].ts).getTime();
  const end = new Date(rows[rows.length - 1].ts).getTime();
  const span = end - start;
  const fmt = (ms) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  [0, 0.25, 0.5, 0.75].forEach((f, i) => {
    if (ticks[i]) ticks[i].textContent = fmt(start + span * f);
  });
}

async function poll() {
  try {
    const [snap, history, metrics, analyticsData] = await Promise.all([
      get("/api/state"), get("/api/history"), get("/api/metrics"), get("/api/analytics"),
    ]);
    connection(true);
    renderState(snap);
    renderChart(history.rows, snap.prediction);
    renderXLabels(history.rows);
    renderMetrics(metrics);
    renderAnalytics(analyticsData);
  } catch (error) {
    connection(false);
    if ($("decisionWhy")) $("decisionWhy").textContent = `Server link unreachable: ${error.message}`;
    log("Server unreachable. Retrying in 3 s");
  }
  setTimeout(poll, 3000);
}

const modeBtn = $("modeBtn");
if (modeBtn) {
  modeBtn.addEventListener("click", async () => {
    const currentMode = (modeBtn.querySelector(".mode-text") || modeBtn).textContent.trim();
    const newMode = currentMode === "AUTO" ? "MANUAL" : "AUTO";
    try {
      const response = await fetch("/api/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: newMode }),
      });
      if (!response.ok) throw new Error(`Mode change rejected (${response.status})`);
      log(`Mode switched to ${newMode}`);
      if ($("cmdError")) $("cmdError").hidden = true;
      poll();
    } catch (error) {
      if ($("cmdError")) {
        $("cmdError").textContent = error.message;
        $("cmdError").hidden = false;
      }
    }
  });
}

const burstBtn = $("burstBtn");
if (burstBtn) {
  burstBtn.addEventListener("click", async () => {
    commandPending = true;
    burstBtn.disabled = true;
    try {
      const response = await fetch("/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ duration_s: 40 }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `Command rejected (${response.status})`);
      log(`Burst #${body.id} queued for ${body.duration_s} s`);
      if ($("cmdError")) $("cmdError").hidden = true;
    } catch (error) {
      if ($("cmdError")) {
        $("cmdError").textContent = error.message;
        $("cmdError").hidden = false;
      }
    } finally {
      commandPending = false;
      poll();
    }
  });
}

poll();
