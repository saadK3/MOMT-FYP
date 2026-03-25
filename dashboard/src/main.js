/**
 * Dashboard entry point.
 * Wires together live tracking updates, search, sidebar summaries,
 * camera-change events, and the archive-backed Journey View.
 */

import "./style.css";
import { WebSocketClient } from "./websocket-client.js";
import { VehicleManager } from "./vehicle-manager.js";
import {
  initPlot,
  render as renderLiveMap,
  setTrails,
  setLabels,
} from "./ground-plane.js";
import {
  initScene as initGroundPlane3D,
  renderJourneyScene,
  renderLiveScene,
  renderSceneMessage,
  setActive as setGroundPlane3DActive,
} from "./ground-plane-3d.js";
import {
  renderJourneyLoading,
  renderJourneyUnavailable,
  renderJourneyView,
} from "./journey-view.js";
import {
  updateStats,
  updateCameras,
  updateConnectionStatus,
  updateVehicleList,
  updateJourneyDetails,
  updateCameraChangeLog,
} from "./stats-panel.js";

const WS_URL = `ws://${window.location.hostname || "localhost"}:8765`;
const PLOT_CONTAINER_2D = "groundPlane2d";
const PLOT_CONTAINER_3D = "groundPlane3d";
const MAX_CAMERA_EVENTS = 50;

const wsClient = new WebSocketClient(WS_URL);
const vehicleManager = new VehicleManager();
const cameraJourneys = new Map();
const journeyViewCache = new Map();
const seenCameraEventIds = new Set();

let latestTimestamp = 0;
let uptime = 0;
let selectedGlobalId = null;
let cameraChangeEvents = [];
let hasArchiveSnapshot = false;
let journeyViewMode = false;
let pendingJourneyGlobalId = null;
let vizMode = "2d";
let latestTrackingUpdate = null;

function init() {
  initPlot(PLOT_CONTAINER_2D);
  initGroundPlane3D(PLOT_CONTAINER_3D, {
    onSelectGlobalId: selectGlobalId,
  });
  bindControls();
  bindSearch();
  syncVizMode();

  wsClient.on("open", () => {
    updateConnectionStatus(true);
  });

  wsClient.on("close", () => {
    updateConnectionStatus(false);
  });

  wsClient.on("connection_ack", (msg) => {
    console.log("[Dashboard] Server says:", msg.message);
  });

  wsClient.on("camera_journey_snapshot", (msg) => {
    cameraJourneys.clear();
    journeyViewCache.clear();
    pendingJourneyGlobalId = null;
    mergeJourneyUpdates(msg.journeys);
    hasArchiveSnapshot = Object.keys(msg.journeys || {}).length > 0;
    cameraChangeEvents = [];
    seenCameraEventIds.clear();
    pushCameraChangeEvents(msg.recent_events || []);
    renderSidebarState();
    renderMainView();
  });

  wsClient.on("tracking_update", (msg) => {
    latestTimestamp = msg.timestamp;
    latestTrackingUpdate = msg;

    if (!hasArchiveSnapshot) {
      mergeJourneyUpdates(msg.journey_updates);
    }

    pushCameraChangeEvents(msg.camera_change_events || []);
    vehicleManager.update(msg);

    const stats = msg.stats || {};
    updateStats({
      activeVehicles: vehicleManager.count,
      totalGlobalIds: stats.num_global_ids || 0,
      timestamp: latestTimestamp,
      uptime,
    });

    updateCameras(stats.arrived_cameras || []);
    renderSidebarState();
    renderMainView();
  });

  wsClient.on("journey_view_data", (msg) => {
    if (msg.journey) {
      journeyViewCache.set(String(msg.global_id), msg.journey);
    } else if (msg.global_id != null) {
      journeyViewCache.delete(String(msg.global_id));
    }

    if (pendingJourneyGlobalId === msg.global_id) {
      pendingJourneyGlobalId = null;
    }

    syncJourneyViewButton();
    renderMainView();
  });

  wsClient.on("system_status", (msg) => {
    uptime = msg.uptime_s || 0;
    updateStats({
      activeVehicles: vehicleManager.count,
      totalGlobalIds: msg.total_global_ids || 0,
      timestamp: latestTimestamp,
      uptime,
    });
  });

  wsClient.connect();
  console.log("[Dashboard] Connecting to", WS_URL);
}

function bindControls() {
  document.getElementById("trailToggle")?.addEventListener("change", (event) => {
    setTrails(event.target.checked);
    renderMainView();
  });

  document
    .getElementById("labelsToggle")
    ?.addEventListener("change", (event) => {
      setLabels(event.target.checked);
      renderMainView();
    });

  document.getElementById("mode2dBtn")?.addEventListener("click", () => {
    vizMode = "2d";
    syncVizMode();
    renderMainView();
  });

  document.getElementById("mode3dBtn")?.addEventListener("click", () => {
    vizMode = "3d";
    syncVizMode();
    renderMainView();
  });

  document
    .getElementById("journeyViewBtn")
    ?.addEventListener("click", openJourneyView);

  document.getElementById("backToLiveBtn")?.addEventListener("click", () => {
    journeyViewMode = false;
    pendingJourneyGlobalId = null;
    renderMainView();
    syncJourneyViewButton();
  });

  const resizer = document.getElementById("sidebarResizer");
  const sidebar = document.getElementById("sidebar");

  if (resizer && sidebar) {
    let isResizing = false;

    resizer.addEventListener("mousedown", (e) => {
      isResizing = true;
      document.body.style.cursor = "col-resize";
      resizer.classList.add("is-resizing");
      e.preventDefault();
    });

    document.addEventListener("mousemove", (e) => {
      if (!isResizing) return;
      const newWidth = e.clientX;
      sidebar.style.width = `${newWidth}px`;
      
      // Force plot resize during drag for a smooth effect
      if (document.getElementById(PLOT_CONTAINER_2D)) {
        Plotly.Plots.resize(PLOT_CONTAINER_2D);
      }
    });

    document.addEventListener("mouseup", () => {
      if (isResizing) {
        isResizing = false;
        document.body.style.cursor = "";
        resizer.classList.remove("is-resizing");
        // One final resize to ensure it snapped correctly
        if (document.getElementById(PLOT_CONTAINER_2D)) {
          Plotly.Plots.resize(PLOT_CONTAINER_2D);
        }
      }
    });
  }
}

function bindSearch() {
  const searchInput = document.getElementById("globalIdSearch");
  const searchButton = document.getElementById("globalIdSearchBtn");
  const vehicleList = document.getElementById("vehicleList");

  searchButton?.addEventListener("click", () => {
    handleSearch(searchInput?.value || "");
  });

  searchInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      handleSearch(searchInput.value);
    }
  });

  vehicleList?.addEventListener("click", (event) => {
    const item = event.target.closest(".vehicle-item[data-global-id]");
    if (!item) return;

    const globalId = Number(item.dataset.globalId);
    if (!Number.isFinite(globalId)) return;
    selectGlobalId(globalId);
  });
}

function handleSearch(rawValue) {
  const globalId = parseGlobalId(rawValue);
  selectGlobalId(globalId);
}

function selectGlobalId(globalId) {
  selectedGlobalId = globalId;

  const searchInput = document.getElementById("globalIdSearch");
  if (searchInput) {
    searchInput.value =
      globalId == null ? "" : `G${Number(globalId).toString()}`;
  }

  renderSidebarState();
  renderMainView();
}

function openJourneyView() {
  if (selectedGlobalId == null) return;

  const summary = cameraJourneys.get(String(selectedGlobalId));
  if (!summary) return;

  journeyViewMode = true;
  requestJourneyView(selectedGlobalId);
  syncJourneyViewButton();
  renderMainView();
}

function requestJourneyView(globalId) {
  if (globalId == null) return;
  if (journeyViewCache.has(String(globalId))) return;
  if (pendingJourneyGlobalId === globalId) return;

  const sent = wsClient.send({
    type: "journey_view_request",
    global_id: globalId,
  });

  if (sent) {
    pendingJourneyGlobalId = globalId;
  }
}

function mergeJourneyUpdates(journeys) {
  if (!journeys) return;

  for (const [globalId, journey] of Object.entries(journeys)) {
    cameraJourneys.set(String(globalId), journey);
  }
}

function pushCameraChangeEvents(events) {
  if (!events || events.length === 0) return;

  const freshEvents = [];

  for (const event of events) {
    if (!event?.event_id || seenCameraEventIds.has(event.event_id)) continue;
    seenCameraEventIds.add(event.event_id);
    freshEvents.push(event);
  }

  if (freshEvents.length === 0) return;

  cameraChangeEvents = [...freshEvents, ...cameraChangeEvents]
    .sort((left, right) => right.timestamp - left.timestamp)
    .slice(0, MAX_CAMERA_EVENTS);
}

function renderSidebarState() {
  updateVehicleList(vehicleManager.getActive(), selectedGlobalId);

  const activeVehicle =
    selectedGlobalId == null
      ? null
      : vehicleManager.getByGlobalId(selectedGlobalId);
  const journey =
    selectedGlobalId == null
      ? null
      : cameraJourneys.get(String(selectedGlobalId)) || null;

  updateJourneyDetails(selectedGlobalId, journey, activeVehicle);
  updateCameraChangeLog(cameraChangeEvents, selectedGlobalId);
  syncJourneyViewButton();
}

function renderMainView() {
  const vizTitle = document.getElementById("vizTitle");
  const backButton = document.getElementById("backToLiveBtn");
  const activeVehicle =
    selectedGlobalId == null
      ? null
      : vehicleManager.getByGlobalId(selectedGlobalId);

  if (!journeyViewMode) {
    if (vizTitle) {
      vizTitle.textContent =
        vizMode === "3d" ? "Ground Plane - Real-Time 3D" : "Ground Plane - Real-Time";
    }
    backButton?.classList.add("hidden");
    if (vizMode === "3d") {
      renderLiveScene(latestTrackingUpdate, {
        selectedGlobalId,
        showTrails: document.getElementById("trailToggle")?.checked ?? true,
        showLabels: document.getElementById("labelsToggle")?.checked ?? true,
      });
    } else {
      renderLiveMap(PLOT_CONTAINER_2D, vehicleManager, latestTimestamp);
    }
    return;
  }

  backButton?.classList.remove("hidden");

  if (selectedGlobalId == null) {
    if (vizTitle) {
      vizTitle.textContent = vizMode === "3d" ? "Journey View 3D" : "Journey View";
    }
    if (vizMode === "3d") {
      renderSceneMessage(
        "Journey View - No Global ID selected",
        "Search for a Global ID, then open Journey View.",
      );
    } else {
      renderJourneyUnavailable(
        PLOT_CONTAINER_2D,
        "Journey View - No Global ID selected",
        "Search for a Global ID, then open Journey View.",
      );
    }
    return;
  }

  const summary = cameraJourneys.get(String(selectedGlobalId));
  if (!summary) {
    if (vizTitle) {
      vizTitle.textContent =
        vizMode === "3d"
          ? `Journey View 3D - G${selectedGlobalId}`
          : `Journey View - G${selectedGlobalId}`;
    }
    if (vizMode === "3d") {
      renderSceneMessage(
        `Journey View - G${selectedGlobalId}`,
        "No archived journey is available for this Global ID.",
      );
    } else {
      renderJourneyUnavailable(
        PLOT_CONTAINER_2D,
        `Journey View - G${selectedGlobalId}`,
        "No archived journey is available for this Global ID.",
      );
    }
    return;
  }

  if (vizTitle) {
    vizTitle.textContent =
      vizMode === "3d"
        ? `Journey View 3D - G${selectedGlobalId}`
        : `Journey View - G${selectedGlobalId}`;
  }

  const journey = journeyViewCache.get(String(selectedGlobalId));
  if (!journey) {
    requestJourneyView(selectedGlobalId);
    if (vizMode === "3d") {
      renderSceneMessage(
        `Journey View - Loading G${selectedGlobalId}...`,
        "Preparing the full vehicle journey from the archive.",
      );
    } else {
      renderJourneyLoading(PLOT_CONTAINER_2D, selectedGlobalId);
    }
    return;
  }

  if (vizMode === "3d") {
    renderJourneyScene(journey, {
      currentTimestamp: latestTimestamp,
      activeVehicle,
      showTrails: document.getElementById("trailToggle")?.checked ?? true,
      showLabels: document.getElementById("labelsToggle")?.checked ?? true,
    });
  } else {
    renderJourneyView(PLOT_CONTAINER_2D, journey, {
      currentTimestamp: latestTimestamp,
      activeVehicle,
      showTrails: document.getElementById("trailToggle")?.checked ?? true,
      showLabels: document.getElementById("labelsToggle")?.checked ?? true,
    });
  }
}

function syncJourneyViewButton() {
  const button = document.getElementById("journeyViewBtn");
  if (!button) return;

  const hasSelection =
    selectedGlobalId != null && cameraJourneys.has(String(selectedGlobalId));
  button.disabled = !hasSelection;

  if (!hasSelection) {
    button.textContent = "Open Journey View";
    return;
  }

  if (journeyViewMode && selectedGlobalId != null) {
    button.textContent = `Journey View Open for G${selectedGlobalId}`;
    return;
  }

  if (pendingJourneyGlobalId === selectedGlobalId) {
    button.textContent = `Loading G${selectedGlobalId}...`;
    return;
  }

  button.textContent = `Open Journey View for G${selectedGlobalId}`;
}

function parseGlobalId(value) {
  const match = String(value).trim().match(/\d+/);
  if (!match) return null;

  const parsed = Number(match[0]);
  if (!Number.isInteger(parsed)) return null;
  return parsed;
}

function syncVizMode() {
  const mode2dButton = document.getElementById("mode2dBtn");
  const mode3dButton = document.getElementById("mode3dBtn");
  const surface2d = document.getElementById(PLOT_CONTAINER_2D);
  const surface3d = document.getElementById(PLOT_CONTAINER_3D);

  mode2dButton?.classList.toggle("active", vizMode === "2d");
  mode3dButton?.classList.toggle("active", vizMode === "3d");
  surface2d?.classList.toggle("active", vizMode === "2d");
  surface3d?.classList.toggle("active", vizMode === "3d");
  setGroundPlane3DActive(vizMode === "3d");
}

document.addEventListener("DOMContentLoaded", init);
