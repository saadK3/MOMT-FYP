/**
 * main.js — Dashboard entry point
 * Wires together: WebSocket client → Vehicle Manager → Ground Plane + Stats
 */

import "./style.css";
import { WebSocketClient } from "./websocket-client.js";
import { VehicleManager } from "./vehicle-manager.js";
import { initPlot, render, setTrails, setLabels } from "./ground-plane.js";
import {
  updateStats,
  updateCameras,
  updateConnectionStatus,
  updateVehicleList,
} from "./stats-panel.js";

// --- Configuration ---
const WS_URL = `ws://${window.location.hostname || "localhost"}:8765`;
const PLOT_CONTAINER = "groundPlane";

// --- State ---
const wsClient = new WebSocketClient(WS_URL);
const vehicleManager = new VehicleManager();
let latestTimestamp = 0;
let uptime = 0;

// --- Initialize ---
function init() {
  console.log("[Dashboard] Initializing...");

  // Plotly ground plane
  initPlot(PLOT_CONTAINER);

  // Wire up UI toggles
  document.getElementById("trailToggle")?.addEventListener("change", (e) => {
    setTrails(e.target.checked);
    render(PLOT_CONTAINER, vehicleManager, latestTimestamp);
  });
  document.getElementById("labelsToggle")?.addEventListener("change", (e) => {
    setLabels(e.target.checked);
    render(PLOT_CONTAINER, vehicleManager, latestTimestamp);
  });

  // --- WebSocket event handlers ---

  wsClient.on("open", () => {
    updateConnectionStatus(true);
  });

  wsClient.on("close", () => {
    updateConnectionStatus(false);
  });

  wsClient.on("connection_ack", (msg) => {
    console.log("[Dashboard] Server says:", msg.message);
  });

  wsClient.on("tracking_update", (msg) => {
    latestTimestamp = msg.timestamp;

    // Update vehicle manager
    vehicleManager.update(msg);

    // Update ground plane
    render(PLOT_CONTAINER, vehicleManager, latestTimestamp);

    // Update stats sidebar
    const stats = msg.stats || {};
    updateStats({
      activeVehicles: vehicleManager.count,
      totalGlobalIds: stats.num_global_ids || 0,
      timestamp: latestTimestamp,
      uptime,
    });

    // Update camera indicators
    updateCameras(stats.arrived_cameras || []);

    // Update vehicle list
    updateVehicleList(vehicleManager.getActive());
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

  // Start connection
  wsClient.connect();
  console.log("[Dashboard] Connecting to", WS_URL);
}

// --- Boot ---
document.addEventListener("DOMContentLoaded", init);
