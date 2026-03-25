import * as THREE from "./vendor/three.module.js";
import { OrbitControls } from "./vendor/OrbitControls.js";
import { MAP_SIZE, mapPointToWorld } from "./coordinates-3d.js";
import {
  VehicleManager3D,
  createJourneyObjects,
} from "./vehicle-manager-3d.js";

let rootEl = null;
let canvasEl = null;
let messageEl = null;
let renderer = null;
let scene = null;
let camera = null;
let controls = null;
let raycaster = null;
let pointer = null;
let vehicleManager = null;
let groundMesh = null;
let gridLines = null;
let journeyObjects = [];
let selectedCallback = null;
let animationFrameId = null;
let hoveredGlobalId = null;
let lastFocusedGlobalId = null;

export function initScene(containerId, { onSelectGlobalId } = {}) {
  if (renderer) {
    selectedCallback = onSelectGlobalId;
    return;
  }

  rootEl = document.getElementById(containerId);
  selectedCallback = onSelectGlobalId;

  canvasEl = document.createElement("canvas");
  canvasEl.className = "ground-plane-3d-canvas";
  rootEl.appendChild(canvasEl);

  messageEl = document.createElement("div");
  messageEl.className = "ground-plane-3d-message hidden";
  rootEl.appendChild(messageEl);

  renderer = new THREE.WebGLRenderer({
    canvas: canvasEl,
    antialias: true,
    alpha: true,
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x050505);
  scene.fog = new THREE.Fog(0x050505, 90, 260);

  camera = new THREE.PerspectiveCamera(50, 1, 0.1, 1000);
  camera.position.set(0, 120, 115);

  controls = new OrbitControls(camera, canvasEl);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.maxPolarAngle = Math.PI / 2.05;
  controls.minDistance = 18;
  controls.maxDistance = 220;
  controls.target.set(0, 0, 0);

  raycaster = new THREE.Raycaster();
  pointer = new THREE.Vector2();
  vehicleManager = new VehicleManager3D(scene);

  addLights();
  addGround();
  attachEvents();
  resize();
  animate();
}

export function setActive(active) {
  if (!rootEl) {
    return;
  }

  rootEl.classList.toggle("active", Boolean(active));
  if (active) {
    resize();
  }
}

export function renderLiveScene(message, options = {}) {
  ensureInitialized();
  clearJourneyObjects();
  hideMessage();
  if (groundMesh) {
    groundMesh.visible = true;
  }

  vehicleManager.update(message || { vehicles: [], timestamp: 0 }, options);
  maybeFocus(options.selectedGlobalId);
}

export function renderJourneyScene(journey, options = {}) {
  ensureInitialized();
  clearJourneyObjects();
  hideMessage();
  vehicleManager.dispose();
  groundMesh.visible = true;

  journeyObjects = createJourneyObjects(scene, journey, options);

  const focusPoint = computeJourneyFocus(journey);
  if (focusPoint) {
    controls.target.lerp(new THREE.Vector3(focusPoint.x, 0, focusPoint.z), 1);
    camera.position.set(focusPoint.x, 90, focusPoint.z + 85);
  }
}

export function renderSceneMessage(title, message) {
  ensureInitialized();
  clearJourneyObjects();
  vehicleManager.dispose();
  if (groundMesh) {
    groundMesh.visible = true;
  }

  messageEl.innerHTML = `
    <div class="ground-plane-3d-message-title">${title}</div>
    <div class="ground-plane-3d-message-body">${message}</div>
  `;
  messageEl.classList.remove("hidden");
}

function ensureInitialized() {
  if (!renderer) {
    throw new Error("3D scene has not been initialized");
  }
}

function addLights() {
  scene.add(new THREE.AmbientLight(0xffffff, 0.75));

  const hemi = new THREE.HemisphereLight(0xb8ddff, 0x0f172a, 0.55);
  hemi.position.set(0, 120, 0);
  scene.add(hemi);

  const sun = new THREE.DirectionalLight(0xfff4de, 1.25);
  sun.position.set(48, 105, 55);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -140;
  sun.shadow.camera.right = 140;
  sun.shadow.camera.top = 140;
  sun.shadow.camera.bottom = -140;
  scene.add(sun);
}

function addGround() {
  const texture = new THREE.TextureLoader().load("clean_mosaic_3_feathered.png");
  texture.colorSpace = THREE.SRGBColorSpace;

  const geometry = new THREE.PlaneGeometry(MAP_SIZE.width, MAP_SIZE.depth);
  const material = new THREE.MeshStandardMaterial({
    map: texture,
    transparent: true,
    opacity: 0.92,
    roughness: 0.95,
    metalness: 0.0,
  });

  groundMesh = new THREE.Mesh(geometry, material);
  groundMesh.rotation.x = -Math.PI / 2;
  groundMesh.receiveShadow = true;
  scene.add(groundMesh);

  gridLines = createAlignedGrid(MAP_SIZE.width, MAP_SIZE.depth, 16, 20);
  gridLines.position.y = 0.04;
  scene.add(gridLines);
}

function attachEvents() {
  canvasEl.addEventListener("pointermove", onPointerMove);
  canvasEl.addEventListener("click", onClick);
  window.addEventListener("resize", resize);
}

function onPointerMove(event) {
  const rect = canvasEl.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

  if (!vehicleManager) {
    return;
  }

  raycaster.setFromCamera(pointer, camera);
  const intersections = raycaster.intersectObjects(scene.children, true);
  const hitGlobalId = vehicleManager.pick(intersections);

  if (hitGlobalId !== hoveredGlobalId) {
    hoveredGlobalId = hitGlobalId;
    canvasEl.style.cursor = hoveredGlobalId == null ? "grab" : "pointer";
  }
}

function onClick() {
  if (hoveredGlobalId == null || !selectedCallback) {
    return;
  }

  selectedCallback(hoveredGlobalId);
}

function resize() {
  if (!renderer || !rootEl) {
    return;
  }

  const width = Math.max(rootEl.clientWidth, 10);
  const height = Math.max(rootEl.clientHeight, 10);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate() {
  animationFrameId = requestAnimationFrame(animate);
  if (!renderer) {
    return;
  }

  controls.update();
  renderer.render(scene, camera);
}

function maybeFocus(globalId) {
  vehicleManager.setSelectedGlobalId(globalId);
  if (globalId == null || globalId === lastFocusedGlobalId) {
    return;
  }

  const target = vehicleManager.focusTarget(globalId);
  if (!target) {
    return;
  }

  lastFocusedGlobalId = globalId;
  controls.target.lerp(new THREE.Vector3(target.x, 0, target.z), 1);
}

function computeJourneyFocus(journey) {
  const bounds = journey?.bounds;
  if (!bounds) {
    return null;
  }

  return mapPointToWorld([
    (bounds.xmin + bounds.xmax) / 2,
    (bounds.ymin + bounds.ymax) / 2,
  ]);
}

function clearJourneyObjects() {
  for (const object of journeyObjects) {
    if (object.geometry) {
      object.geometry.dispose();
    }
    if (object.material) {
      if (object.material.map) {
        object.material.map.dispose();
      }
      object.material.dispose();
    }
    scene.remove(object);
  }
  journeyObjects = [];
}

function hideMessage() {
  messageEl.classList.add("hidden");
  messageEl.innerHTML = "";
}

function createAlignedGrid(width, depth, xDivisions, zDivisions) {
  const positions = [];
  const colors = [];
  const alphas = [];
  const group = new THREE.Group();
  const majorXDivisions = Math.max(6, Math.floor(xDivisions / 2));
  const majorZDivisions = Math.max(8, Math.floor(zDivisions / 2));
  const xStep = width / majorXDivisions;
  const zStep = depth / majorZDivisions;
  const xStart = -width / 2;
  const zStart = -depth / 2;
  const borderColor = new THREE.Color(0x31445f);
  const majorColor = new THREE.Color(0x1b2a3f);

  for (let index = 0; index <= majorXDivisions; index += 1) {
    const x = xStart + index * xStep;
    const isBorder = index === 0 || index === majorXDivisions;
    const color = isBorder ? borderColor : majorColor;
    const alpha = isBorder ? 0.36 : edgeFade(index / majorXDivisions, 0.05, 0.11);
    positions.push(x, 0, zStart, x, 0, zStart + depth);
    colors.push(color.r, color.g, color.b, color.r, color.g, color.b);
    alphas.push(alpha, alpha);
  }

  for (let index = 0; index <= majorZDivisions; index += 1) {
    const z = zStart + index * zStep;
    const isBorder = index === 0 || index === majorZDivisions;
    const color = isBorder ? borderColor : majorColor;
    const alpha = isBorder ? 0.36 : edgeFade(index / majorZDivisions, 0.05, 0.11);
    positions.push(xStart, 0, z, xStart + width, 0, z);
    colors.push(color.r, color.g, color.b, color.r, color.g, color.b);
    alphas.push(alpha, alpha);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(positions, 3),
  );
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.setAttribute("alpha", new THREE.Float32BufferAttribute(alphas, 1));

  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    vertexColors: true,
    uniforms: {},
    vertexShader: `
      attribute float alpha;
      varying vec3 vColor;
      varying float vAlpha;

      void main() {
        vColor = color;
        vAlpha = alpha;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      varying vec3 vColor;
      varying float vAlpha;

      void main() {
        gl_FragColor = vec4(vColor, vAlpha);
      }
    `,
  });

  const lines = new THREE.LineSegments(geometry, material);
  group.add(lines);
  return group;
}

function edgeFade(ratio, edgeAlpha, centerAlpha) {
  const distanceFromCenter = Math.abs(ratio - 0.5) / 0.5;
  const eased = 1 - Math.pow(distanceFromCenter, 1.35);
  return edgeAlpha + (centerAlpha - edgeAlpha) * Math.max(eased, 0);
}
