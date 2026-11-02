// ---------- Health badge ----------
const badge = document.getElementById("status-badge");

async function checkHealth() {
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    if (data.status === "ok") {
      badge.textContent = "Online";
      badge.className = "badge badge-ok";
    } else {
      throw new Error("unexpected payload");
    }
  } catch (err) {
    badge.textContent = "Offline";
    badge.className = "badge badge-err";
  }
}
checkHealth();
setInterval(checkHealth, 2000);

// ---------- Clock ----------
function tickClock() {
  const el = document.getElementById("clock");
  if (el) el.textContent = new Date().toLocaleTimeString();
}
tickClock();
setInterval(tickClock, 1000);

// ---------- Shared ----------
const COUNT_LABELS = { car: "Cars", motorcycle: "Motorcycles", bus: "Buses", truck: "Trucks" };
const LANES = ["north", "south", "east", "west"];

const laneState = { north: { filename: null }, south: { filename: null }, east: { filename: null }, west: { filename: null } };

// ---------- Per-lane upload + detect ----------
document.querySelectorAll(".lane-card").forEach((card) => {
  const lane         = card.dataset.lane;
  const fileInput    = card.querySelector(".file-input");
  const uploadBtn    = card.querySelector(".upload-btn");
  const uploadStatus = card.querySelector(".upload-status");
  const detectBtn    = card.querySelector(".detect-btn");
  const detectStatus = card.querySelector(".detect-status");
  const resultWrap   = card.querySelector(".detect-result");
  const annotatedImg = card.querySelector(".annotated");
  const countsEl     = card.querySelector(".counts");

  fileInput.addEventListener("change", () => {
    uploadBtn.disabled = fileInput.files.length === 0;
    uploadStatus.textContent = "";
    uploadStatus.className = "status";
  });

  uploadBtn.addEventListener("click", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    uploadBtn.disabled = true;
    uploadStatus.textContent = "Uploading…";
    uploadStatus.className = "status";
    try {
      const form = new FormData();
      form.append("image", file);
      const res  = await fetch("/api/upload", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "HTTP " + res.status);
      uploadStatus.textContent = "Uploaded ✅";
      uploadStatus.className = "status ok";
      laneState[lane].filename = data.filename;
      detectBtn.disabled = false;
      detectStatus.textContent = "";
      detectStatus.className = "status";
      resultWrap.classList.add("hidden");
      countsEl.innerHTML = "";
    } catch (err) {
      uploadStatus.textContent = "Upload failed: " + err.message;
      uploadStatus.className = "status err";
    } finally {
      uploadBtn.disabled = false;
    }
  });

  detectBtn.addEventListener("click", async () => {
    if (!laneState[lane].filename) return;
    detectBtn.disabled = true;
    detectStatus.textContent = "Detecting…";
    detectStatus.className = "status";
    resultWrap.classList.add("hidden");
    try {
      const res = await fetch(`/api/detect/${encodeURIComponent(laneState[lane].filename)}`, { method: "POST" });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || "HTTP " + res.status);
      annotatedImg.src = data.annotated_url + "?t=" + Date.now();
      countsEl.innerHTML = "";
      for (const [key, value] of Object.entries(data.counts)) {
        const item = document.createElement("div");
        item.className = "count-item";
        item.innerHTML = `<span class="count-num">${value}</span><span class="count-label">${COUNT_LABELS[key] || key}</span>`;
        countsEl.appendChild(item);
      }
      const totalItem = document.createElement("div");
      totalItem.className = "count-item";
      totalItem.innerHTML = `<span class="count-num" style="color:#93c5fd">${data.total}</span><span class="count-label">Total</span>`;
      countsEl.appendChild(totalItem);
      detectStatus.textContent = `Detected ${data.total} vehicles ✅`;
      detectStatus.className = "status ok";
      resultWrap.classList.remove("hidden");
      document.getElementById("c-" + lane).value = data.total;
    } catch (err) {
      detectStatus.textContent = "Detection failed: " + err.message;
      detectStatus.className = "status err";
    } finally {
      detectBtn.disabled = false;
    }
  });
});

// ---------- Timing ----------
const timingBtn    = document.getElementById("timing-btn");
const timingStatus = document.getElementById("timing-status");
const timingResult = document.getElementById("timing-result");
const timingGrid   = document.getElementById("timing-grid");
const cycleTotal   = document.getElementById("cycle-total");

timingBtn.addEventListener("click", async () => {
  const counts = {};
  for (const l of LANES) counts[l] = parseInt(document.getElementById("c-" + l).value, 10) || 0;
  timingBtn.disabled = true;
  timingStatus.textContent = "Computing…";
  timingStatus.className = "status";
  timingResult.classList.add("hidden");
  try {
    const res = await fetch("/api/timing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ counts }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "HTTP " + res.status);
    timingGrid.innerHTML = "";
    for (const lane of data.lanes) {
      const t = data.timings[lane];
      const div = document.createElement("div");
      div.className = "timing-item";
      div.innerHTML =
        `<div class="timing-lane">${lane}</div>` +
        `<span class="timing-green">${t.green}s</span>` +
        `<div class="timing-sub">vehicles: ${t.count}</div>` +
        `<div class="timing-sub">yellow ${t.yellow}s · all-red ${t.all_red}s</div>`;
      timingGrid.appendChild(div);
    }
    cycleTotal.textContent = `Cycle total: ${data.cycle_total}s`;
    timingStatus.textContent = "Timings computed ✅";
    timingStatus.className = "status ok";
    timingResult.classList.remove("hidden");
  } catch (err) {
    timingStatus.textContent = "Failed: " + err.message;
    timingStatus.className = "status err";
  } finally {
    timingBtn.disabled = false;
  }
});

// ---------- Live controls ----------
const liveStart   = document.getElementById("live-start");
const liveStop    = document.getElementById("live-stop");
const liveStatus  = document.getElementById("live-status");
const liveResult  = document.getElementById("live-result");
const liveUpdated = document.getElementById("live-updated");
const liveGrid    = document.getElementById("live-grid");

liveStart.addEventListener("click", async () => {
  const urls = {};
  for (const l of LANES) urls[l] = document.getElementById("url-" + l).value.trim();
  if (!Object.values(urls).some(Boolean)) {
    liveStatus.textContent = "Set at least one URL";
    liveStatus.className = "status err";
    return;
  }
  liveStart.disabled = true;
  liveStatus.textContent = "Starting…";
  liveStatus.className = "status";
  try {
    await fetch("/api/live/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    });
    const res = await fetch("/api/live/start", { method: "POST" });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "start failed");
    liveStop.disabled = false;
    liveStatus.textContent = "Live running";
    liveStatus.className = "status ok";
    liveResult.classList.remove("hidden");
  } catch (err) {
    liveStart.disabled = false;
    liveStatus.textContent = "Start failed: " + err.message;
    liveStatus.className = "status err";
  }
});

liveStop.addEventListener("click", async () => {
  try { await fetch("/api/live/stop", { method: "POST" }); } catch (_) {}
  liveStop.disabled = true;
  liveStart.disabled = false;
  liveStatus.textContent = "Stopped";
  liveStatus.className = "status";
});

// ---------- Live frame preview + lane cards (always poll every 2s) ----------
// ---------- Live frame preview + lane cards ----------
async function pollLive() {
  try {
    const res = await fetch("/api/live");
    const data = await res.json();
    if (!data.ok) return;

    // Update the 4 live images
    let anyLive = false;
    for (const lane of LANES) {
      const L = data.lanes[lane];
      const img = document.getElementById(`img-${lane}`);
      const err = document.getElementById(`err-${lane}`);
      const ts = document.getElementById(`ts-${lane}`);

      if (L.frame_ts) {
        anyLive = true;
        img.src = `/frames/${lane}_latest.jpg?t=${Date.now()}`;
        img.classList.remove("hidden");
        err.classList.add("hidden");
        ts.textContent = L.frame_ts;
      } else {
        img.classList.add("hidden");
        err.classList.remove("hidden");
        err.textContent = L.error || "No frame yet";
        ts.textContent = "";
      }
    }

    if (anyLive) {
      frameBadge.textContent = "live";
      frameBadge.className = "phase-pill phase-green";
    } else {
      frameBadge.textContent = data.running ? "waiting" : "offline";
      frameBadge.className = "phase-pill phase-idle";
    }

    // Update lane text cards
    if (data.running) {
      liveUpdated.textContent = data.updated ? `Last update: ${data.updated}` : "Waiting for first cycle…";
      liveGrid.innerHTML = "";
      for (const lane of LANES) {
        const L = data.lanes[lane];
        const T = data.timings && data.timings.timings ? data.timings.timings[lane] : null;
        const div = document.createElement("div");
        div.className = "timing-item";
        div.innerHTML =
          `<div class="timing-lane">${lane}</div>` +
          `<span class="timing-green">${T ? T.green + "s" : "—"}</span>` +
          `<div class="timing-sub">vehicles: ${L.count}</div>` +
          (L.error ? `<div class="timing-sub" style="color:#fca5a5">${L.error}</div>` : "");
        liveGrid.appendChild(div);
      }
    }
  } catch (_) {}
}

pollLive();
setInterval(pollLive, 2000);

// ---------- History ----------
const historyStats = document.getElementById("history-stats");
const historyBody  = document.querySelector("#history-table tbody");

async function loadHistory() {
  try {
    const res = await fetch("/api/history?limit=15");
    const data = await res.json();
    if (!data.ok) return;

    const s = data.stats;
    const busiest = s.busiest_lane
      ? s.busiest_lane.charAt(0).toUpperCase() + s.busiest_lane.slice(1)
      : "—";
    const lastTs = s.last_ts ? s.last_ts.split(" ")[1] : "—";

    const items = [
      { icon: "🔄", label: "Total Cycles",  val: s.total_cycles },
      { icon: "🚗", label: "Avg Vehicles",  val: s.avg_vehicles },
      { icon: "🔥", label: "Busiest Lane",  val: busiest },
      { icon: "🕐", label: "Last Cycle",    val: lastTs },
    ];
    historyStats.innerHTML = "";
    for (const { icon, label, val } of items) {
      const el = document.createElement("div");
      el.className = "stat-item";
      el.innerHTML = `
        <div class="stat-icon">${icon}</div>
        <div class="stat-body">
          <div class="stat-label">${label}</div>
          <div class="stat-val">${val}</div>
        </div>
      `;
      historyStats.appendChild(el);
    }

    historyBody.innerHTML = "";
    for (const c of data.cycles) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${c.id}</td>
        <td>${c.ts}</td>
        <td>${c.source}</td>
        <td>${c.north_count} / ${c.north_green}s</td>
        <td>${c.south_count} / ${c.south_green}s</td>
        <td>${c.east_count} / ${c.east_green}s</td>
        <td>${c.west_count} / ${c.west_green}s</td>
        <td>${c.total_vehicles}</td>
        <td>${c.cycle_total}s</td>
      `;
      historyBody.appendChild(tr);
    }
  } catch (_) {}
}
loadHistory();
setInterval(loadHistory, 5000);

// ---------- Signal state panel ----------
const signalPhase = document.getElementById("signal-phase");

function renderDots(state) {
  const map = { RED: "red", YELLOW: "yellow", GREEN: "green" };
  return ["red", "yellow", "green"].map((c) => {
    const on = map[state] === c;
    return `<span class="signal-dot ${on ? c : ""}"></span>`;
  }).join("");
}

async function pollSignals() {
  try {
    const res = await fetch("/api/esp32/signals");
    const data = await res.json();
    if (!data.ok) return;
    document.querySelectorAll(".signal-card").forEach((card) => {
      const lane = card.dataset.lane;
      const state = data.signals[lane] || "RED";
      const rem = data.remaining[lane] || 0;
      card.querySelector(".signal-dots").innerHTML = renderDots(state);
      card.querySelector(".signal-remaining").textContent =
        state === "RED" && rem === 0 ? "—" : `${rem}s`;
    });
    const phase = data.phase || "idle";
    signalPhase.textContent = phase + (data.active ? ` · ${data.active}` : "");
    signalPhase.className = "phase-pill phase-" + phase;
  } catch (_) {}
}
pollSignals();
setInterval(pollSignals, 1000);