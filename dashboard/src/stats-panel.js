/**
 * Stats Panel - updates the sidebar statistics, vehicle list, journey panel,
 * and recent camera-change log.
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
 * @param {string[]} arrivedCameras
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
      statusEl.textContent = "OK";
    } else {
      card.classList.remove("active");
      statusEl.textContent = "-";
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
    text.textContent = "Reconnecting...";
  }
}

/**
 * Update the vehicle list in the sidebar.
 * @param {Array} vehicles
 * @param {number|null} selectedGlobalId
 */
export function updateVehicleList(vehicles, selectedGlobalId = null) {
  const container = document.getElementById("vehicleList");
  if (!container) return;

  if (vehicles.length === 0) {
    container.innerHTML =
      '<div class="vehicle-list-empty">Waiting for data...</div>';
    return;
  }

  const items = [...vehicles]
    .sort((a, b) => a.global_id - b.global_id)
    .slice(0, 30)
    .map((vehicle) => {
      const isSelected = vehicle.global_id === selectedGlobalId;
      const cameraLabel = formatCameraState(
        vehicle.cameraState || [vehicle.camera],
      );
      return `
        <div class="vehicle-item ${isSelected ? "selected" : ""}" data-global-id="${vehicle.global_id}">
          <span class="vehicle-color-dot" style="background:${vehicle.color}"></span>
          <span class="vehicle-label">G${vehicle.global_id}</span>
          <span class="vehicle-camera">${cameraLabel} - ${vehicle.class}</span>
        </div>
      `;
    })
    .join("");

  const overflow =
    vehicles.length > 30
      ? `<div class="vehicle-list-empty">+${vehicles.length - 30} more</div>`
      : "";

  container.innerHTML = items + overflow;
}

/**
 * Render the selected Global ID camera journey details.
 * @param {number|null} selectedGlobalId
 * @param {object|null} journey
 * @param {object|null} activeVehicle
 */
export function updateJourneyDetails(
  selectedGlobalId,
  journey,
  activeVehicle,
) {
  const container = document.getElementById("journeyDetails");
  if (!container) return;

  if (selectedGlobalId == null) {
    container.className = "journey-card journey-card-empty";
    container.innerHTML =
      "Search a Global ID or click a vehicle from the list to inspect its camera journey.";
    return;
  }

  if (!journey) {
    container.className = "journey-card journey-card-empty";
    container.innerHTML = `No camera journey found yet for G${selectedGlobalId}.`;
    return;
  }

  const currentState =
    activeVehicle?.cameraState || journey.current_camera_state || [];
  const currentLabel = formatCameraState(currentState);
  const isActive = Boolean(activeVehicle);
  const seenCameras = formatCameraState(journey.unique_cameras || []);
  const lastTransition = journey.last_transition
    ? `${journey.last_transition.from_camera_label} -> ${journey.last_transition.to_camera_label} @ ${formatTimestamp(journey.last_transition.timestamp)}`
    : "No camera changes recorded";

  container.className = "journey-card";
  container.innerHTML = `
    <div class="journey-header">
      <div class="journey-id">G${journey.global_id}</div>
      <div class="journey-status ${isActive ? "active" : "inactive"}">
        ${isActive ? "Active" : "Inactive"}
      </div>
    </div>
    <div class="journey-grid">
      <div class="journey-row">
        <span class="journey-key">Current Camera</span>
        <span class="journey-value">${currentLabel}</span>
      </div>
      <div class="journey-row">
        <span class="journey-key">Camera Changed</span>
        <span class="journey-value ${journey.has_camera_changed ? "changed" : "unchanged"}">
          ${journey.has_camera_changed ? "Yes" : "No"}
        </span>
      </div>
      <div class="journey-row">
        <span class="journey-key">Transitions</span>
        <span class="journey-value">${journey.transition_count}</span>
      </div>
      <div class="journey-row">
        <span class="journey-key">Seen Cameras</span>
        <span class="journey-value wrap">${seenCameras || "Unknown"}</span>
      </div>
      <div class="journey-row">
        <span class="journey-key">Journey</span>
        <span class="journey-value wrap">${buildJourneySummary(journey)}</span>
      </div>
      <div class="journey-row">
        <span class="journey-key">Last Change</span>
        <span class="journey-value wrap">${lastTransition}</span>
      </div>
    </div>
  `;
}

/**
 * Render a recent camera-change log.
 * @param {Array} events
 * @param {number|null} selectedGlobalId
 */
export function updateCameraChangeLog(events, selectedGlobalId = null) {
  const container = document.getElementById("cameraChangeLog");
  if (!container) return;

  if (!events.length) {
    container.innerHTML =
      '<div class="vehicle-list-empty">Waiting for camera changes...</div>';
    return;
  }

  container.innerHTML = [...events]
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, 25)
    .map((event) => {
      const isSelected = event.global_id === selectedGlobalId;
      return `
        <div class="event-item ${isSelected ? "selected" : ""}">
          <div class="event-meta">
            <span>G${event.global_id}</span>
            <span>${formatTimestamp(event.timestamp)}</span>
          </div>
          <div class="event-flow">${event.from_camera_label} -> ${event.to_camera_label}</div>
        </div>
      `;
    })
    .join("");
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
  if (seconds < 3600) {
    return Math.floor(seconds / 60) + "m " + (Math.floor(seconds) % 60) + "s";
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h + "h " + m + "m";
}

function formatCameraState(cameraState) {
  if (!cameraState || cameraState.length === 0) return "Unknown";
  return cameraState.map((camera) => camera.toUpperCase()).join(" + ");
}

function buildJourneySummary(journey) {
  const segments = journey.journey || [];
  if (!segments.length) return "Unknown";
  if (segments.length === 1) return `${segments[0].camera_label} only`;
  return segments.map((segment) => segment.camera_label).join(" -> ");
}

function formatTimestamp(timestamp) {
  return `${Number(timestamp).toFixed(1)}s`;
}
