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
const PLOT_CONTAINER = "groundPlane";
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

function init() {
  initPlot(PLOT_CONTAINER);
  bindControls();
  bindSearch();

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

  document
    .getElementById("journeyViewBtn")
    ?.addEventListener("click", openJourneyView);

  document.getElementById("backToLiveBtn")?.addEventListener("click", () => {
    journeyViewMode = false;
    pendingJourneyGlobalId = null;
    renderMainView();
    syncJourneyViewButton();
  });
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

  if (journeyViewMode) {
    renderMainView();
  }
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
      vizTitle.textContent = "Ground Plane - Real-Time";
    }
    backButton?.classList.add("hidden");
    renderLiveMap(PLOT_CONTAINER, vehicleManager, latestTimestamp);
    return;
  }

  backButton?.classList.remove("hidden");

  if (selectedGlobalId == null) {
    if (vizTitle) {
      vizTitle.textContent = "Journey View";
    }
    renderJourneyUnavailable(
      PLOT_CONTAINER,
      "Journey View - No Global ID selected",
      "Search for a Global ID, then open Journey View.",
    );
    return;
  }

  const summary = cameraJourneys.get(String(selectedGlobalId));
  if (!summary) {
    if (vizTitle) {
      vizTitle.textContent = `Journey View - G${selectedGlobalId}`;
    }
    renderJourneyUnavailable(
      PLOT_CONTAINER,
      `Journey View - G${selectedGlobalId}`,
      "No archived journey is available for this Global ID.",
    );
    return;
  }

  if (vizTitle) {
    vizTitle.textContent = `Journey View - G${selectedGlobalId}`;
  }

  const journey = journeyViewCache.get(String(selectedGlobalId));
  if (!journey) {
    requestJourneyView(selectedGlobalId);
    renderJourneyLoading(PLOT_CONTAINER, selectedGlobalId);
    return;
  }

  renderJourneyView(PLOT_CONTAINER, journey, {
    currentTimestamp: latestTimestamp,
    activeVehicle,
    showTrails: document.getElementById("trailToggle")?.checked ?? true,
    showLabels: document.getElementById("labelsToggle")?.checked ?? true,
  });
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

document.addEventListener("DOMContentLoaded", init);
