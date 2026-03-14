/**
 * main.js — 3D View entry point
 * Sets up Three.js scene, camera, lights, grid, and connects
 * to the tracking server WebSocket for real-time vehicle updates.
 */

import "./style.css";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { VehicleManager3D } from "./vehicles.js";

// --- Configuration ---
const WS_URL = `ws://${window.location.hostname || "localhost"}:8765`;
const RECONNECT_MS = 2000;

// --- Three.js Setup ---
const canvas = document.getElementById("scene");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.2;

// Scene
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0e17);
scene.fog = new THREE.Fog(0x0a0e17, 80, 250);

// Camera — positioned above and to the side, looking at center
const camera = new THREE.PerspectiveCamera(
  60,
  window.innerWidth / window.innerHeight,
  0.5,
  500,
);
camera.position.set(30, 40, 50);
camera.lookAt(0, 0, 0);

// Orbit Controls
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.maxPolarAngle = Math.PI / 2.1; // Don't let camera go below ground
controls.minDistance = 5;
controls.maxDistance = 200;
controls.target.set(0, 0, 0);

// --- Lighting ---
// Ambient
const ambient = new THREE.AmbientLight(0x4466aa, 0.6);
scene.add(ambient);

// Hemisphere (sky + ground bounce)
const hemi = new THREE.HemisphereLight(0x88aacc, 0x444422, 0.5);
scene.add(hemi);

// Directional (sun — casts shadows)
const sun = new THREE.DirectionalLight(0xffeedd, 1.2);
sun.position.set(40, 60, 30);
sun.castShadow = true;
sun.shadow.mapSize.width = 2048;
sun.shadow.mapSize.height = 2048;
sun.shadow.camera.near = 1;
sun.shadow.camera.far = 200;
sun.shadow.camera.left = -100;
sun.shadow.camera.right = 100;
sun.shadow.camera.top = 100;
sun.shadow.camera.bottom = -100;
scene.add(sun);

// --- Ground Plane ---
const groundGeo = new THREE.PlaneGeometry(200, 200);
const groundMat = new THREE.MeshStandardMaterial({
  color: 0x111820,
  roughness: 0.95,
  metalness: 0.0,
});
const ground = new THREE.Mesh(groundGeo, groundMat);
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.01; // Slightly below 0 to avoid z-fighting
ground.receiveShadow = true;
scene.add(ground);

// --- Grid ---
const gridHelper = new THREE.GridHelper(200, 40, 0x1a2540, 0x111c30);
scene.add(gridHelper);

// Axis indicators (subtle)
const axisSize = 5;
const axisX = new THREE.Line(
  new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0.05, 0),
    new THREE.Vector3(axisSize, 0.05, 0),
  ]),
  new THREE.LineBasicMaterial({
    color: 0xff4444,
    opacity: 0.4,
    transparent: true,
  }),
);
const axisZ = new THREE.Line(
  new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0.05, 0),
    new THREE.Vector3(0, 0.05, axisSize),
  ]),
  new THREE.LineBasicMaterial({
    color: 0x4444ff,
    opacity: 0.4,
    transparent: true,
  }),
);
scene.add(axisX, axisZ);

// --- Vehicle Manager ---
const vehicleManager = new VehicleManager3D(scene);

// --- HUD Elements ---
const hudDot = document.getElementById("connectionDot");
const hudConn = document.getElementById("connectionText");
const hudVehicles = document.getElementById("vehicleCount");
const hudGlobalIds = document.getElementById("globalIdCount");
const hudTime = document.getElementById("currentTime");

function setConnected(connected) {
  if (connected) {
    hudDot.classList.add("connected");
    hudConn.textContent = "Connected";
  } else {
    hudDot.classList.remove("connected");
    hudConn.textContent = "Reconnecting…";
  }
}

// --- WebSocket ---
let ws = null;
let shouldReconnect = true;
let totalGlobalIds = 0;

function connectWS() {
  try {
    ws = new WebSocket(WS_URL);
  } catch (e) {
    console.error("[WS] Failed:", e);
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    console.log("[WS] Connected");
    setConnected(true);
  };

  ws.onclose = () => {
    console.log("[WS] Disconnected");
    setConnected(false);
    scheduleReconnect();
  };

  ws.onerror = (e) => console.warn("[WS] Error:", e);

  ws.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);

      if (msg.type === "tracking_update") {
        vehicleManager.update(msg);

        // Update HUD
        hudVehicles.textContent = vehicleManager.count;
        totalGlobalIds = msg.stats?.num_global_ids || totalGlobalIds;
        hudGlobalIds.textContent = totalGlobalIds;
        hudTime.textContent = msg.timestamp.toFixed(1) + "s";
      }

      if (msg.type === "system_status") {
        totalGlobalIds = msg.total_global_ids || totalGlobalIds;
        hudGlobalIds.textContent = totalGlobalIds;
      }
    } catch (e) {
      console.warn("[WS] Parse error:", e);
    }
  };
}

function scheduleReconnect() {
  if (!shouldReconnect) return;
  setTimeout(() => connectWS(), RECONNECT_MS);
}

// --- Animation Loop ---
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

// --- Window Resize ---
window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// --- Boot ---
console.log("[3D View] Starting...");
connectWS();
animate();
