/**
 * Dashboard entry point.
 * Keeps the existing 2D dashboard flow intact while adding
 * Unity-powered 3D live and per-vehicle journey modes.
 */

import "./style.css";
import { WebSocketClient } from "./websocket-client.js";
import { PlaybackClient } from "./playback-client.js";
import { VehicleManager } from "./vehicle-manager.js";
import { UnityEmbed } from "./unity-embed.js";
import {
  initPlot,
  render as renderLiveMap,
  setVehicleClickHandler,
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
import { updateVideoPanels } from "./video-panels.js";

const WS_URL = `ws://${window.location.hostname || "localhost"}:8765`;
const PLOT_CONTAINER = "groundPlane";
const UNITY_CONTAINER = "unityViewport";
const MAX_CAMERA_EVENTS = 50;
const URL_PARAMS = new URLSearchParams(window.location.search);
const APP_MODE = (URL_PARAMS.get("mode") || "offline").toLowerCase();
const IS_OFFLINE_MODE = APP_MODE === "offline";
const VIEW_MODES = {
  LIVE_2D: "2d-live",
  JOURNEY_2D: "2d-journey",
  LIVE_3D: "3d-live",
  JOURNEY_3D: "3d-journey",
};

const dataClient = createDataClient();
const playbackClient =
  IS_OFFLINE_MODE && dataClient?.isPlaybackClient ? dataClient : null;
const vehicleManager = new VehicleManager();
const unityEmbed = new UnityEmbed(UNITY_CONTAINER);
const cameraJourneys = new Map();
const journeyViewCache = new Map();
const seenCameraEventIds = new Set();

let latestTimestamp = 0;
let uptime = 0;
let selectedGlobalId = null;
let cameraChangeEvents = [];
let hasArchiveSnapshot = false;
let viewMode = VIEW_MODES.LIVE_2D;
let pendingJourneyGlobalId = null;
let latestArrivedCameras = [];

function init() {
  initPlot(PLOT_CONTAINER);
  setVehicleClickHandler((globalId) => {
    selectGlobalId(globalId);
  });
  bindControls();
  configureOfflinePlaybackControls();
  bindSearch();
  bindUnityEvents();

  dataClient.on("open", () => {
    updateConnectionStatus(true);
  });

  dataClient.on("close", () => {
    updateConnectionStatus(false);
  });

  dataClient.on("connection_ack", (msg) => {
    console.log("[Dashboard] Server says:", msg.message);
  });

  dataClient.on("camera_journey_snapshot", (msg) => {
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

  dataClient.on("tracking_update", (msg) => {
    latestTimestamp = msg.timestamp;
    latestArrivedCameras = msg.stats?.arrived_cameras || [];

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

    updateCameras(latestArrivedCameras);
    renderSidebarState();
    renderMainView();
  });

  dataClient.on("journey_view_data", (msg) => {
    if (msg.journey) {
      journeyViewCache.set(String(msg.global_id), msg.journey);
    } else if (msg.global_id != null) {
      journeyViewCache.delete(String(msg.global_id));
    }

    if (pendingJourneyGlobalId === msg.global_id) {
      pendingJourneyGlobalId = null;
    }

    syncViewButtons();
    renderMainView();
  });

  dataClient.on("system_status", (msg) => {
    uptime = msg.uptime_s || 0;
    updateStats({
      activeVehicles: vehicleManager.count,
      totalGlobalIds: msg.total_global_ids || 0,
      timestamp: latestTimestamp,
      uptime,
    });
  });

  dataClient.on("playback_state", (msg) => {
    syncOfflinePlaybackUi(msg);
  });

  dataClient.connect();
  if (IS_OFFLINE_MODE) {
    console.log("[Dashboard] Starting in offline playback mode");
  } else {
    console.log("[Dashboard] Connecting to", WS_URL);
  }
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
    ?.addEventListener("click", () => openJourneyView(VIEW_MODES.JOURNEY_2D));

  document
    .getElementById("journey3dViewBtn")
    ?.addEventListener("click", () => openJourneyView(VIEW_MODES.JOURNEY_3D));

  document.getElementById("view3dLiveBtn")?.addEventListener("click", () => {
    viewMode = VIEW_MODES.LIVE_3D;
    renderMainView();
  });

  document.getElementById("backToLiveBtn")?.addEventListener("click", () => {
    viewMode = VIEW_MODES.LIVE_2D;
    renderMainView();
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
      if (document.getElementById(PLOT_CONTAINER)) {
        Plotly.Plots.resize(PLOT_CONTAINER);
      }
    });

    document.addEventListener("mouseup", () => {
      if (isResizing) {
        isResizing = false;
        document.body.style.cursor = "";
        resizer.classList.remove("is-resizing");
        // One final resize to ensure it snapped correctly
        if (document.getElementById(PLOT_CONTAINER)) {
          Plotly.Plots.resize(PLOT_CONTAINER);
        }
      }
    });
  }
}

function configureOfflinePlaybackControls() {
  const panel = document.getElementById("offlinePlaybackControls");
  if (!panel) return;

  if (!playbackClient) {
    panel.classList.add("hidden");
    return;
  }

  panel.classList.remove("hidden");

  const playPauseBtn = document.getElementById("playPauseBtn");
  const restartBtn = document.getElementById("restartPlaybackBtn");
  const speedSelect = document.getElementById("playbackSpeedSelect");
  const loopToggle = document.getElementById("loopPlaybackToggle");
  const seekBar = document.getElementById("playbackSeek");

  playPauseBtn?.addEventListener("click", () => {
    const state = playbackClient.getPlaybackState();
    if (state.isPlaying) playbackClient.pause();
    else playbackClient.play();
  });

  restartBtn?.addEventListener("click", () => {
    playbackClient.restart();
  });

  speedSelect?.addEventListener("change", (event) => {
    playbackClient.setSpeed(event.target.value);
  });

  loopToggle?.addEventListener("change", (event) => {
    playbackClient.setLoop(event.target.checked);
  });

  seekBar?.addEventListener("input", (event) => {
    const progress = Number(event.target.value) / 1000;
    playbackClient.seekToProgress(progress);
  });

  syncOfflinePlaybackUi(playbackClient.getPlaybackState());
}

function syncOfflinePlaybackUi(state) {
  if (!playbackClient || !state) return;

  const playPauseBtn = document.getElementById("playPauseBtn");
  const speedSelect = document.getElementById("playbackSpeedSelect");
  const loopToggle = document.getElementById("loopPlaybackToggle");
  const seekBar = document.getElementById("playbackSeek");
  const timeLabel = document.getElementById("playbackTimeLabel");

  if (playPauseBtn) {
    playPauseBtn.textContent = state.isPlaying ? "Pause" : "Play";
    playPauseBtn.classList.toggle("active", state.isPlaying);
  }

  if (speedSelect) {
    const normalizedSpeed = String(Number(state.speed));
    if (speedSelect.value !== normalizedSpeed) {
      speedSelect.value = normalizedSpeed;
    }
  }

  if (loopToggle) {
    loopToggle.checked = Boolean(state.loop);
  }

  if (seekBar) {
    seekBar.value = String(Math.round((state.progress || 0) * 1000));
  }

  if (timeLabel) {
    const now = Number(state.currentTimestamp) || 0;
    const total = Number(state.endTimestamp) || 0;
    timeLabel.textContent = `${formatSeconds(now)} / ${formatSeconds(total)}`;
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

function bindUnityEvents() {
  unityEmbed.onVehicleClick = (globalId) => {
    selectGlobalId(globalId);
    requestJourneyView(globalId);
    viewMode = VIEW_MODES.JOURNEY_3D;
    renderMainView();
  };
}

function handleSearch(rawValue) {
  selectGlobalId(parseGlobalId(rawValue));
}

function selectGlobalId(globalId) {
  selectedGlobalId = globalId;

  const searchInput = document.getElementById("globalIdSearch");
  if (searchInput) {
    searchInput.value =
      globalId == null ? "" : `G${Number(globalId).toString()}`;
  }

  if (selectedGlobalId != null) {
    requestJourneyView(selectedGlobalId);
  }

  renderSidebarState();

  if (isJourneyMode(viewMode) || is3DMode(viewMode)) {
    renderMainView();
  }
}

function openJourneyView(nextMode) {
  if (!canOpenSelectedJourney()) return;

  viewMode = nextMode;
  requestJourneyView(selectedGlobalId);
  renderMainView();
}

function requestJourneyView(globalId) {
  if (globalId == null) return;
  if (journeyViewCache.has(String(globalId))) return;
  if (pendingJourneyGlobalId === globalId) return;

  const sent = dataClient.send({
    type: "journey_view_request",
    global_id: globalId,
  });

  if (sent) {
    pendingJourneyGlobalId = globalId;
    syncViewButtons();
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
  updateVideoPanels({
    latestTimestamp,
    arrivedCameras: latestArrivedCameras,
    selectedGlobalId,
    journeySummary: journey,
    activeVehicle,
  });
  syncViewButtons();
}

function renderMainView() {
  syncViewButtons();

  switch (viewMode) {
    case VIEW_MODES.JOURNEY_2D:
      render2DJourneyView();
      return;
    case VIEW_MODES.LIVE_3D:
      render3DView("Unity 3D - Live All Vehicles");
      return;
    case VIEW_MODES.JOURNEY_3D:
      render3DJourneyView();
      return;
    case VIEW_MODES.LIVE_2D:
    default:
      render2DLiveView();
  }
}

function render2DLiveView() {
  showPlotContainer();
  setVizTitle("Ground Plane - Real-Time");
  renderLiveMap(PLOT_CONTAINER, vehicleManager, latestTimestamp);
}

function render2DJourneyView() {
  showPlotContainer();

  if (selectedGlobalId == null) {
    setVizTitle("Journey View");
    renderJourneyUnavailable(
      PLOT_CONTAINER,
      "Journey View - No Global ID selected",
      "Search for a Global ID, then open the 2D Journey View.",
    );
    return;
  }

  const summary = cameraJourneys.get(String(selectedGlobalId));
  if (!summary) {
    setVizTitle(`Journey View - G${selectedGlobalId}`);
    renderJourneyUnavailable(
      PLOT_CONTAINER,
      `Journey View - G${selectedGlobalId}`,
      "No archived journey is available for this Global ID.",
    );
    return;
  }

  setVizTitle(`Journey View - G${selectedGlobalId}`);

  const journey = journeyViewCache.get(String(selectedGlobalId));
  if (!journey) {
    requestJourneyView(selectedGlobalId);
    renderJourneyLoading(PLOT_CONTAINER, selectedGlobalId);
    return;
  }

  renderJourneyView(PLOT_CONTAINER, journey, {
    currentTimestamp: latestTimestamp,
    activeVehicle: vehicleManager.getByGlobalId(selectedGlobalId),
    showTrails: document.getElementById("trailToggle")?.checked ?? true,
    showLabels: document.getElementById("labelsToggle")?.checked ?? true,
  });
}

function render3DView(title) {
  showUnityContainer();
  setVizTitle(title);
  unityEmbed.setState(buildUnityStatePayload());
}

function render3DJourneyView() {
  const title =
    selectedGlobalId == null
      ? "Unity 3D - Vehicle Journey"
      : `Unity 3D - G${selectedGlobalId} Journey`;

  if (selectedGlobalId != null) {
    requestJourneyView(selectedGlobalId);
  }

  render3DView(title);
}

function showPlotContainer() {
  document.getElementById(PLOT_CONTAINER)?.classList.remove("hidden");
  document.getElementById(UNITY_CONTAINER)?.classList.add("hidden");
  document.getElementById("vizControls")?.classList.remove("hidden");
  unityEmbed.hide();
}

function showUnityContainer() {
  document.getElementById(PLOT_CONTAINER)?.classList.add("hidden");
  document.getElementById(UNITY_CONTAINER)?.classList.remove("hidden");
  document.getElementById("vizControls")?.classList.add("hidden");
  unityEmbed.show();
}

function syncViewButtons() {
  const journey2dBtn = document.getElementById("journeyViewBtn");
  const journey3dBtn = document.getElementById("journey3dViewBtn");
  const view3dLiveBtn = document.getElementById("view3dLiveBtn");
  const backButton = document.getElementById("backToLiveBtn");

  const hasJourneySelection = canOpenSelectedJourney();
  const isJourneyLoading =
    selectedGlobalId != null && pendingJourneyGlobalId === selectedGlobalId;

  if (journey2dBtn) {
    journey2dBtn.disabled = !hasJourneySelection;
    journey2dBtn.classList.toggle(
      "active",
      viewMode === VIEW_MODES.JOURNEY_2D,
    );
    journey2dBtn.textContent = !hasJourneySelection
      ? "Open Selected Vehicle in 2D"
      : viewMode === VIEW_MODES.JOURNEY_2D
        ? `2D Vehicle View Open for G${selectedGlobalId}`
        : isJourneyLoading
          ? `Loading selected vehicle...`
          : `Open G${selectedGlobalId} in 2D`;
  }

  if (journey3dBtn) {
    journey3dBtn.disabled = !hasJourneySelection;
    journey3dBtn.classList.toggle(
      "active",
      viewMode === VIEW_MODES.JOURNEY_3D,
    );
    journey3dBtn.textContent = !hasJourneySelection
      ? "Open Selected Vehicle in 3D"
      : viewMode === VIEW_MODES.JOURNEY_3D
        ? `3D Vehicle View Open for G${selectedGlobalId}`
        : isJourneyLoading
          ? `Loading selected vehicle...`
          : `Open G${selectedGlobalId} in 3D`;
  }

  if (view3dLiveBtn) {
    view3dLiveBtn.classList.toggle("active", viewMode === VIEW_MODES.LIVE_3D);
    view3dLiveBtn.textContent =
      viewMode === VIEW_MODES.LIVE_3D
        ? "3D Live Map Open"
        : "Open 3D Live Map";
  }

  backButton?.classList.toggle("hidden", viewMode === VIEW_MODES.LIVE_2D);
}

function canOpenSelectedJourney() {
  return (
    selectedGlobalId != null && cameraJourneys.has(String(selectedGlobalId))
  );
}

function setVizTitle(title) {
  const vizTitle = document.getElementById("vizTitle");
  if (vizTitle) {
    vizTitle.textContent = title;
  }
}

function isJourneyMode(mode) {
  return mode === VIEW_MODES.JOURNEY_2D || mode === VIEW_MODES.JOURNEY_3D;
}

function is3DMode(mode) {
  return mode === VIEW_MODES.LIVE_3D || mode === VIEW_MODES.JOURNEY_3D;
}

function buildUnityStatePayload() {
  const activeVehicles = vehicleManager.getActive();
  const liveJourneySummaries = activeVehicles
    .map((vehicle) => {
      const summary = cameraJourneys.get(String(vehicle.global_id));
      return serializeSummaryForUnity(summary, vehicle);
    })
    .filter(Boolean);

  const summary =
    selectedGlobalId == null
      ? null
      : cameraJourneys.get(String(selectedGlobalId)) || null;
  const selectedJourney =
    selectedGlobalId == null
      ? null
      : journeyViewCache.get(String(selectedGlobalId)) || null;

  return {
    viewMode,
    timestamp: latestTimestamp,
    selectedGlobalId: selectedGlobalId ?? 0,
    mapTextureUrl: new URL(
      "/clean_mosaic_3_feathered.png",
      window.location.origin,
    ).toString(),
    liveVehicles: activeVehicles.map((vehicle) => ({
      globalId: vehicle.global_id,
      className: vehicle.class,
      footprint: vehicle.footprint,
      centroid: vehicle.centroid,
      camera: vehicle.camera,
      cameraStateLabel: vehicle.cameraStateLabel,
      hasCameraChanged: Boolean(vehicle.hasCameraChanged),
    })),
    liveJourneySummaries,
    selectedJourneySummary: serializeSummaryForUnity(
      summary,
      vehicleManager.getByGlobalId(selectedGlobalId),
    ),
    selectedJourney: serializeJourneyForUnity(selectedJourney),
  };
}

function serializeSummaryForUnity(summary, activeVehicle = null) {
  if (!summary && !activeVehicle) return null;

  const currentCameraLabel =
    activeVehicle?.cameraStateLabel ||
    summary?.current_camera_label ||
    "Unknown";
  const hasCameraChanged = Boolean(
    activeVehicle?.hasCameraChanged ?? summary?.has_camera_changed,
  );

  return {
    globalId: summary?.global_id ?? activeVehicle?.global_id ?? 0,
    vehicleClass: activeVehicle?.class || summary?.vehicle_class || "unknown",
    currentCameraLabel,
    hasCameraChanged,
    transitionCount: summary?.transition_count ?? 0,
    journeyText: summary ? buildJourneySummaryText(summary) : `${currentCameraLabel} only`,
    lastTransitionText: summary
      ? buildLastTransitionText(summary)
      : "No camera changes recorded",
  };
}

function serializeJourneyForUnity(journey) {
  if (!journey) return null;

  return {
    globalId: journey.global_id,
    currentCameraLabel: journey.summary?.current_camera_label || "Unknown",
    transitionCount: journey.summary?.transition_count || 0,
    hasCameraChanged: Boolean(journey.summary?.has_camera_changed),
    pathPoints: (journey.path_points || []).map((point) => ({
      timestamp: point.timestamp,
      centroid: point.centroid,
      footprint: point.footprint || null,
      headingDeg: point.heading_deg ?? null,
      cameraLabel: point.camera_label,
      className: point.class,
    })),
    segments: (journey.segments || []).map((segment) => ({
      cameraLabel: segment.camera_label,
      points: (segment.points || []).map((point) => ({
        timestamp: point.timestamp,
        centroid: point.centroid,
        footprint: point.footprint || null,
        headingDeg: point.heading_deg ?? null,
        cameraLabel: point.camera_label,
        className: point.class,
      })),
    })),
    transitions: (journey.transitions || []).map((transition) => ({
      timestamp: transition.timestamp,
      centroid: transition.centroid,
      fromCameraLabel: transition.from_camera_label,
      toCameraLabel: transition.to_camera_label,
    })),
  };
}

function buildJourneySummaryText(journey) {
  const segments = journey?.journey || [];
  if (!segments.length) return "Unknown";
  if (segments.length === 1) return `${segments[0].camera_label} only`;
  return segments.map((segment) => segment.camera_label).join(" -> ");
}

function buildLastTransitionText(journey) {
  if (!journey?.last_transition) {
    return "No camera changes recorded";
  }
  const transition = journey.last_transition;
  return `${transition.from_camera_label} -> ${transition.to_camera_label} @ ${Number(
    transition.timestamp,
  ).toFixed(1)}s`;
}

function parseGlobalId(value) {
  const match = String(value).trim().match(/\d+/);
  if (!match) return null;

  const parsed = Number(match[0]);
  if (!Number.isInteger(parsed)) return null;
  return parsed;
}

function formatSeconds(value) {
  return `${Number(value || 0).toFixed(1)}s`;
}

function createDataClient() {
  if (!IS_OFFLINE_MODE) {
    return new WebSocketClient(WS_URL);
  }

  const playbackFile = URL_PARAMS.get("file") || "/offline_playback_demo.json";
  const playbackSpeed = Number(URL_PARAMS.get("speed") || "1");
  const playbackStartTimestamp = Number(URL_PARAMS.get("start") || "12");
  const playbackLoopParam = (URL_PARAMS.get("loop") || "1").toLowerCase();
  const playbackLoop = !(playbackLoopParam === "0" || playbackLoopParam === "false");

  return new PlaybackClient({
    fileUrl: playbackFile,
    speed: playbackSpeed,
    startTimestamp: playbackStartTimestamp,
    loop: playbackLoop,
  });
}

document.addEventListener("DOMContentLoaded", init);
