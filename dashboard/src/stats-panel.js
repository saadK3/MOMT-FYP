/**
 * Stats Panel — updates the sidebar statistics and camera status indicators.
 */

/**
 * Update the four stat cards.
 * @param {object} opts
 * @param {number} opts.activeVehicles
 * @param {number} opts.totalGlobalIds
 * @param {number} opts.timestamp
 * @param {number} opts.uptime
 */
export function updateStats({
  activeVehicles,
  totalGlobalIds,
  timestamp,
  uptime,
}) {
  setText("statVehicles", activeVehicles);
  setText("statGlobalIds", totalGlobalIds);
  setText("statTimestamp", timestamp.toFixed(1) + "s");
  setText("statUptime", formatUptime(uptime));
}

/**
 * Update camera status indicators.
 * @param {string[]} arrivedCameras  list of camera IDs that arrived in the latest update
 */
export function updateCameras(arrivedCameras) {
  const grid = document.getElementById("cameraGrid");
  if (!grid) return;

  const arrivedSet = new Set(arrivedCameras);

  for (const card of grid.querySelectorAll(".camera-card")) {
    const camId = card.dataset.camera;
    const statusEl = card.querySelector(".camera-status");

    if (arrivedSet.has(camId)) {
      card.classList.add("active");
      statusEl.textContent = "✓";
    } else {
      card.classList.remove("active");
      statusEl.textContent = "—";
    }
  }
}

/**
 * Update the connection indicator in the navbar.
 * @param {boolean} connected
 */
export function updateConnectionStatus(connected) {
  const dot = document.getElementById("connectionDot");
  const text = document.getElementById("connectionText");
  if (!dot || !text) return;

  if (connected) {
    dot.classList.add("connected");
    text.textContent = "Connected";
  } else {
    dot.classList.remove("connected");
    text.textContent = "Reconnecting…";
  }
}

/**
 * Update the vehicle list in the sidebar.
 * @param {Array} vehicles  active vehicle states from VehicleManager
 */
export function updateVehicleList(vehicles) {
  const container = document.getElementById("vehicleList");
  if (!container) return;

  if (vehicles.length === 0) {
    container.innerHTML =
      '<div class="vehicle-list-empty">Waiting for data…</div>';
    return;
  }

  // Sort by global_id
  const sorted = [...vehicles].sort((a, b) => a.global_id - b.global_id);

  // Build HTML (limit to 30 to avoid DOM overload)
  const items = sorted
    .slice(0, 30)
    .map((v) => {
      return `<div class="vehicle-item">
      <span class="vehicle-color-dot" style="background:${v.color}"></span>
      <span class="vehicle-label">G${v.global_id}</span>
      <span class="vehicle-camera">${v.camera} · ${v.class}</span>
    </div>`;
    })
    .join("");

  const overflow =
    sorted.length > 30
      ? `<div class="vehicle-list-empty">+${sorted.length - 30} more</div>`
      : "";

  container.innerHTML = items + overflow;
}

/* ---- helpers ---- */

function setText(parentId, value) {
  const el = document.getElementById(parentId);
  if (!el) return;
  const valEl = el.querySelector(".stat-value");
  if (valEl) valEl.textContent = value;
}

function formatUptime(seconds) {
  if (seconds < 60) return Math.floor(seconds) + "s";
  if (seconds < 3600)
    return Math.floor(seconds / 60) + "m " + (Math.floor(seconds) % 60) + "s";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h + "h " + m + "m";
}
