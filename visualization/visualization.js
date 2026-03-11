// Showcase Page JavaScript - Ground Plane Visualization
// With localStorage integration for statistics page

let trajectoryData = null;
let currentTime = 0;
let isPlaying = false;
let playbackSpeed = 1;
let animationFrame = null;
let selectedVehicleId = null;
let showcaseVehicles = [];
let showcaseIndex = 0;
let showcaseMode = false;
let plotInitialized = false;
let switchTraceCurveNumber = null;
let allVehicleIds = [];
const transitionCache = {};
const SWITCH_MIN_CONSECUTIVE = 2;
const SWITCH_MIN_DURATION = 0.25;
const CAMERA_IDS = ["c001", "c002", "c003", "c004", "c005"];
const UI_STATE_KEY = "showcase_ui_state_v2";
let activeCameraFilters = new Set(CAMERA_IDS);

async function init() {
  try {
    const response = await fetch("trajectory_data_optimized.json");
    trajectoryData = await response.json();
    allVehicleIds = Object.keys(trajectoryData.trajectories).sort(
      (a, b) => Number(a) - Number(b)
    );

    const slider = document.getElementById("timeSlider");
    slider.min = Math.floor(trajectoryData.time_range.min * 10);
    slider.max = Math.floor(trajectoryData.time_range.max * 10);
    slider.value = slider.min;

    currentTime = trajectoryData.time_range.min;
    document.getElementById("currentTime").textContent =
      currentTime.toFixed(1) + "s";

    setupEventListeners();
    populateGlobalIdOptions();
    restoreUiState();
    syncCameraFilterUI();
    clearCameraTransitionsPanel();
    renderGroundPlane(currentTime);
    updateCameraTransitionsPanel(selectedVehicleId, currentTime);
    renderTimelineTicks(selectedVehicleId, currentTime);
    updateCurrentCameraBadge(selectedVehicleId, currentTime);

    console.log("Loaded:", trajectoryData.statistics);
  } catch (error) {
    console.error("Error loading data:", error);
    alert("Error loading visualization data.");
  }
}

function setupEventListeners() {
  document.getElementById("timeSlider").addEventListener("input", (e) => {
    currentTime = parseFloat(e.target.value) / 10;
    document.getElementById("currentTime").textContent =
      currentTime.toFixed(1) + "s";
    renderGroundPlane(currentTime);
    persistUiState();
  });

  document
    .getElementById("playPauseBtn")
    .addEventListener("click", togglePlayPause);
  document.getElementById("resetBtn").addEventListener("click", reset);
  document.getElementById("speedSelect").addEventListener("change", (e) => {
    playbackSpeed = parseFloat(e.target.value);
    persistUiState();
  });

  document
    .getElementById("searchBtn")
    .addEventListener("click", searchGlobalId);
  document
    .getElementById("searchGlobalId")
    .addEventListener("keypress", (e) => {
      if (e.key === "Enter") searchGlobalId();
    });
  document
    .getElementById("showcaseBtn")
    .addEventListener("click", startShowcase);
  document
    .getElementById("nextExampleBtn")
    .addEventListener("click", nextShowcaseExample);
  document
    .getElementById("exitShowcaseBtn")
    .addEventListener("click", exitShowcase);

  document
    .getElementById("prevVehicleBtn")
    .addEventListener("click", () => jumpToAdjacentVehicle(-1));
  document
    .getElementById("nextVehicleBtn")
    .addEventListener("click", () => jumpToAdjacentVehicle(1));
  document
    .getElementById("prevSwitchBtn")
    .addEventListener("click", () => jumpToSwitch(-1));
  document
    .getElementById("nextSwitchBtn")
    .addEventListener("click", () => jumpToSwitch(1));
  document
    .getElementById("selectAllCamerasBtn")
    .addEventListener("click", () => setAllCameraFilters(true));
  document
    .getElementById("clearCameraFiltersBtn")
    .addEventListener("click", () => setAllCameraFilters(false));

  document.querySelectorAll("#cameraFilterGroup input[type='checkbox']").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      updateCameraFiltersFromUI();
      renderGroundPlane(currentTime);
      updateCameraTransitionsPanel(selectedVehicleId, currentTime);
      renderTimelineTicks(selectedVehicleId, currentTime);
      updateCurrentCameraBadge(selectedVehicleId, currentTime);
      persistUiState();
    });
  });
}

function populateGlobalIdOptions() {
  const datalist = document.getElementById("globalIdOptions");
  if (!datalist) return;

  datalist.innerHTML = allVehicleIds
    .map((id) => `<option value="${id}"></option>`)
    .join("");
}

function syncCameraFilterUI() {
  document.querySelectorAll("#cameraFilterGroup input[type='checkbox']").forEach((checkbox) => {
    checkbox.checked = activeCameraFilters.has(checkbox.value);
  });
}

function updateCameraFiltersFromUI() {
  activeCameraFilters = new Set();
  document.querySelectorAll("#cameraFilterGroup input[type='checkbox']").forEach((checkbox) => {
    if (checkbox.checked) activeCameraFilters.add(checkbox.value);
  });
}

function setAllCameraFilters(enabled) {
  activeCameraFilters = enabled ? new Set(CAMERA_IDS) : new Set();
  syncCameraFilterUI();
  renderGroundPlane(currentTime);
  updateCameraTransitionsPanel(selectedVehicleId, currentTime);
  renderTimelineTicks(selectedVehicleId, currentTime);
  updateCurrentCameraBadge(selectedVehicleId, currentTime);
  persistUiState();
}

function persistUiState() {
  try {
    localStorage.setItem(
      UI_STATE_KEY,
      JSON.stringify({
        selectedVehicleId: selectedVehicleId || "",
        currentTime,
        playbackSpeed,
        cameraFilters: Array.from(activeCameraFilters),
      })
    );
  } catch (error) {
    console.warn("Failed to persist UI state", error);
  }
}

function restoreUiState() {
  try {
    const raw = localStorage.getItem(UI_STATE_KEY);
    if (!raw) return;

    const state = JSON.parse(raw);
    if (typeof state.playbackSpeed === "number") {
      playbackSpeed = state.playbackSpeed;
      const speedSelect = document.getElementById("speedSelect");
      if (speedSelect) speedSelect.value = String(playbackSpeed);
    }

    if (Array.isArray(state.cameraFilters)) {
      activeCameraFilters = new Set(
        state.cameraFilters.filter((camera) => CAMERA_IDS.includes(camera))
      );
    }

    if (typeof state.currentTime === "number") {
      const minTime = trajectoryData.time_range.min;
      const maxTime = trajectoryData.time_range.max;
      currentTime = Math.min(Math.max(state.currentTime, minTime), maxTime);
      document.getElementById("timeSlider").value = Math.floor(currentTime * 10);
      document.getElementById("currentTime").textContent = `${currentTime.toFixed(1)}s`;
    }

    if (
      state.selectedVehicleId &&
      trajectoryData.trajectories[state.selectedVehicleId]
    ) {
      selectedVehicleId = String(state.selectedVehicleId);
      document.getElementById("searchGlobalId").value = selectedVehicleId;
      getTransitionData(selectedVehicleId);
    }
  } catch (error) {
    console.warn("Failed to restore UI state", error);
  }
}

function getFootprintCentroid(footprint) {
  return {
    x: (footprint[0] + footprint[2] + footprint[4] + footprint[6]) / 4,
    y: (footprint[1] + footprint[3] + footprint[5] + footprint[7]) / 4,
  };
}

function buildRunsFromLabels(detections, labels) {
  const runs = [];
  if (!detections.length) return runs;

  let startIndex = 0;
  let currentCamera = labels[0];

  for (let i = 1; i < labels.length; i++) {
    if (labels[i] !== currentCamera) {
      const endIndex = i - 1;
      runs.push({
        camera: currentCamera,
        startIndex,
        endIndex,
        length: endIndex - startIndex + 1,
        startTime: detections[startIndex].timestamp,
        endTime: detections[endIndex].timestamp,
        duration:
          detections[endIndex].timestamp - detections[startIndex].timestamp,
      });
      startIndex = i;
      currentCamera = labels[i];
    }
  }

  const finalEnd = labels.length - 1;
  runs.push({
    camera: currentCamera,
    startIndex,
    endIndex: finalEnd,
    length: finalEnd - startIndex + 1,
    startTime: detections[startIndex].timestamp,
    endTime: detections[finalEnd].timestamp,
    duration: detections[finalEnd].timestamp - detections[startIndex].timestamp,
  });

  return runs;
}

function isTinyRun(run) {
  return (
    run.length < SWITCH_MIN_CONSECUTIVE && run.duration < SWITCH_MIN_DURATION
  );
}

function pickReplacementCamera(runs, runIndex) {
  if (runIndex <= 0) return runs[1].camera;
  if (runIndex >= runs.length - 1) return runs[runs.length - 2].camera;

  const left = runs[runIndex - 1];
  const right = runs[runIndex + 1];

  if (left.length !== right.length) {
    return left.length > right.length ? left.camera : right.camera;
  }

  if (left.duration !== right.duration) {
    return left.duration > right.duration ? left.camera : right.camera;
  }

  return left.camera;
}

function stabilizeCameraLabels(detections) {
  const labels = detections.map((det) => det.camera);
  if (labels.length < 3) return labels;

  let changed = true;
  let guard = 0;

  while (changed && guard < 20) {
    changed = false;
    guard += 1;

    const runs = buildRunsFromLabels(detections, labels);
    if (runs.length <= 1) break;

    for (let runIndex = 0; runIndex < runs.length; runIndex++) {
      const run = runs[runIndex];
      if (!isTinyRun(run)) continue;

      const replacementCamera = pickReplacementCamera(runs, runIndex);
      if (!replacementCamera || replacementCamera === run.camera) continue;

      for (let i = run.startIndex; i <= run.endIndex; i++) {
        labels[i] = replacementCamera;
      }

      changed = true;
    }
  }

  return labels;
}

function buildTransitionData(globalId) {
  const trajectory = trajectoryData?.trajectories?.[globalId];
  if (!trajectory || !trajectory.detections || !trajectory.detections.length) {
    return null;
  }

  const detections = [...trajectory.detections].sort(
    (a, b) => a.timestamp - b.timestamp
  );
  const stableLabels = stabilizeCameraLabels(detections);
  const runs = buildRunsFromLabels(detections, stableLabels);

  const transitions = [];
  for (let i = 1; i < runs.length; i++) {
    const previousRun = runs[i - 1];
    const currentRun = runs[i];

    if (previousRun.camera === currentRun.camera) continue;

    const previousDet = detections[previousRun.endIndex];
    const currentDet = detections[currentRun.startIndex];
    const previousCenter = getFootprintCentroid(previousDet.footprint);
    const currentCenter = getFootprintCentroid(currentDet.footprint);

    transitions.push({
      fromCamera: previousRun.camera,
      toCamera: currentRun.camera,
      switchTime: (previousRun.endTime + currentRun.startTime) / 2,
      x: (previousCenter.x + currentCenter.x) / 2,
      y: (previousCenter.y + currentCenter.y) / 2,
      fromTime: previousRun.endTime,
      toTime: currentRun.startTime,
      quality: getSwitchQuality(previousRun, currentRun),
      evidencePoints: Math.min(previousRun.length, currentRun.length),
      evidenceDuration: Math.min(previousRun.duration, currentRun.duration),
    });
  }

  const cameraPath = runs.map((run) => run.camera);

  return { detections, runs, transitions, cameraPath };
}

function getSwitchQuality(previousRun, currentRun) {
  const points = Math.min(previousRun.length, currentRun.length);
  const duration = Math.min(previousRun.duration, currentRun.duration);

  if (points >= 4 && duration >= 0.6) return "high";
  if (points >= 2 && duration >= 0.25) return "medium";
  return "low";
}

function getTransitionData(globalId) {
  if (!globalId) return null;
  if (!transitionCache[globalId]) {
    transitionCache[globalId] = buildTransitionData(globalId);
  }
  return transitionCache[globalId];
}

function clearCameraTransitionsPanel() {
  const summaryEl = document.getElementById("cameraTransitionsSummary");
  const listEl = document.getElementById("cameraTransitionsList");
  if (!summaryEl || !listEl) return;

  summaryEl.textContent = "Select a Global ID to see confirmed camera switches.";
  listEl.innerHTML =
    '<div class="camera-transitions-empty">No vehicle selected</div>';
}

function getActiveStableCamera(transitionData, time) {
  if (!transitionData || !transitionData.runs?.length) return null;

  let activeCamera = transitionData.runs[0].camera;
  for (const run of transitionData.runs) {
    if (time >= run.startTime) {
      activeCamera = run.camera;
    } else {
      break;
    }
  }

  return activeCamera;
}

function getFilteredTransitions(transitionData) {
  if (!transitionData) return [];
  if (!activeCameraFilters.size) return [];
  return transitionData.transitions.filter(
    (transition) =>
      activeCameraFilters.has(transition.fromCamera) ||
      activeCameraFilters.has(transition.toCamera)
  );
}

function bindTransitionHoverSync(filteredTransitions) {
  const listEl = document.getElementById("cameraTransitionsList");
  const plotDiv = document.getElementById("groundPlane");
  if (!listEl || !plotDiv || switchTraceCurveNumber === null) return;

  listEl
    .querySelectorAll(".camera-transition-item[data-switch-index]")
    .forEach((item) => {
      const itemIndex = Number(item.getAttribute("data-switch-index"));
      item.addEventListener("mouseenter", () => {
        if (Number.isNaN(itemIndex)) return;
        try {
          Plotly.Fx.hover(plotDiv, [
            { curveNumber: switchTraceCurveNumber, pointNumber: itemIndex },
          ]);
        } catch (error) {
          // no-op
        }
      });
      item.addEventListener("mouseleave", () => {
        try {
          Plotly.Fx.unhover(plotDiv);
        } catch (error) {
          // no-op
        }
      });
    });
}

function updateCameraTransitionsPanel(globalId, time) {
  const summaryEl = document.getElementById("cameraTransitionsSummary");
  const listEl = document.getElementById("cameraTransitionsList");
  if (!summaryEl || !listEl) return;

  if (!globalId) {
    clearCameraTransitionsPanel();
    return;
  }

  const transitionData = getTransitionData(globalId);
  if (!transitionData) {
    summaryEl.textContent = "No trajectory data available for this Global ID.";
    listEl.innerHTML =
      '<div class="camera-transitions-empty">Unable to build transition information</div>';
    return;
  }

  const activeCamera = getActiveStableCamera(transitionData, time);
  const pathText = transitionData.cameraPath.join(" -> ");
  const filteredTransitions = getFilteredTransitions(transitionData);

  if (!activeCameraFilters.size) {
    summaryEl.textContent =
      "No cameras selected in filter. Enable at least one camera.";
    listEl.innerHTML =
      '<div class="camera-transitions-empty">Camera filter is empty</div>';
    return;
  }

  if (transitionData.transitions.length === 0) {
    summaryEl.textContent = `No camera change detected. Path: ${pathText}`;
    listEl.innerHTML = `
      <div class="camera-transition-item">
        <div>
          <div class="camera-transition-route">${pathText}</div>
          <div class="camera-transition-time">Vehicle remained in one camera for this trajectory</div>
        </div>
        <span class="camera-transition-status stable">stable</span>
      </div>
      <div class="camera-transition-item">
        <div>
          <div class="camera-transition-route">Current camera</div>
          <div class="camera-transition-time">t=${time.toFixed(2)}s</div>
        </div>
        <span class="camera-transition-status past">${activeCamera || "n/a"}</span>
      </div>
    `;
    return;
  }

  summaryEl.textContent = `${filteredTransitions.length} visible switch${
    filteredTransitions.length === 1 ? "" : "es"
  } of ${transitionData.transitions.length} total | Path: ${pathText} | Current: ${
    activeCamera || "n/a"
  }`;

  if (!filteredTransitions.length) {
    listEl.innerHTML =
      '<div class="camera-transitions-empty">No switches visible under current camera filter</div>';
    return;
  }

  listEl.innerHTML = filteredTransitions
    .map((transition, index) => {
      const statusClass = transition.switchTime <= time ? "past" : "upcoming";
      const statusLabel =
        transition.switchTime <= time ? "completed" : "upcoming";

      return `
        <div class="camera-transition-item" data-switch-index="${index}">
          <div>
            <div class="camera-transition-route">${transition.fromCamera} \u2192 ${transition.toCamera}</div>
            <div class="camera-transition-time">switch @ t=${transition.switchTime.toFixed(
              2
            )}s • quality: ${transition.quality}</div>
          </div>
          <span class="camera-transition-status ${statusClass}">${statusLabel}</span>
        </div>
      `;
    })
    .join("");

  bindTransitionHoverSync(filteredTransitions);
}

function renderTimelineTicks(globalId, time) {
  const ticksContainer = document.getElementById("timelineTicks");
  if (!ticksContainer) return;

  ticksContainer.innerHTML = "";
  if (!globalId) return;

  const transitionData = getTransitionData(globalId);
  if (!transitionData) return;

  const transitions = getFilteredTransitions(transitionData);
  if (!transitions.length) return;

  const minTime = trajectoryData.time_range.min;
  const maxTime = trajectoryData.time_range.max;
  const span = maxTime - minTime;
  if (span <= 0) return;

  transitions.forEach((transition) => {
    const tick = document.createElement("span");
    tick.className = "timeline-tick";
    if (transition.switchTime > time) tick.classList.add("upcoming");
    const pct = ((transition.switchTime - minTime) / span) * 100;
    tick.style.left = `${Math.min(100, Math.max(0, pct))}%`;
    tick.title = `${transition.fromCamera} -> ${transition.toCamera} @ ${transition.switchTime.toFixed(
      2
    )}s`;
    ticksContainer.appendChild(tick);
  });
}

function updateCurrentCameraBadge(globalId, time) {
  const badge = document.getElementById("currentCameraBadge");
  if (!badge) return;

  if (!globalId) {
    badge.textContent = "Current camera: -";
    return;
  }

  const transitionData = getTransitionData(globalId);
  if (!transitionData) {
    badge.textContent = "Current camera: n/a";
    return;
  }

  const activeCamera = getActiveStableCamera(transitionData, time);
  if (!activeCamera) {
    badge.textContent = "Current camera: n/a";
    return;
  }

  if (!activeCameraFilters.has(activeCamera)) {
    badge.textContent = `Current camera: ${activeCamera} (filtered)`;
    return;
  }

  badge.textContent = `Current camera: ${activeCamera}`;
}

function jumpToAdjacentVehicle(direction) {
  if (!allVehicleIds.length) return;

  let currentIndex = allVehicleIds.indexOf(selectedVehicleId || "");
  if (currentIndex === -1) currentIndex = direction > 0 ? -1 : 0;

  const nextIndex =
    (currentIndex + direction + allVehicleIds.length) % allVehicleIds.length;
  const nextId = allVehicleIds[nextIndex];

  const input = document.getElementById("searchGlobalId");
  if (input) input.value = nextId;
  searchGlobalId();
}

function jumpToSwitch(direction) {
  if (!selectedVehicleId) return;
  const transitionData = getTransitionData(selectedVehicleId);
  if (!transitionData) return;

  const transitions = getFilteredTransitions(transitionData);
  if (!transitions.length) return;

  if (isPlaying) togglePlayPause();

  if (direction > 0) {
    const next = transitions.find((transition) => transition.switchTime > currentTime + 1e-6);
    currentTime = (next || transitions[0]).switchTime;
  } else {
    const previous = [...transitions]
      .reverse()
      .find((transition) => transition.switchTime < currentTime - 1e-6);
    currentTime = (previous || transitions[transitions.length - 1]).switchTime;
  }

  document.getElementById("timeSlider").value = Math.floor(currentTime * 10);
  document.getElementById("currentTime").textContent = `${currentTime.toFixed(1)}s`;
  renderGroundPlane(currentTime);
  updateCameraTransitionsPanel(selectedVehicleId, currentTime);
  renderTimelineTicks(selectedVehicleId, currentTime);
  updateCurrentCameraBadge(selectedVehicleId, currentTime);
  persistUiState();
}

function togglePlayPause() {
  isPlaying = !isPlaying;
  const btn = document.getElementById("playPauseBtn");

  if (isPlaying) {
    btn.textContent = "Pause";
    startAnimation();
  } else {
    btn.textContent = "Play";
    stopAnimation();
  }
}

function startAnimation() {
  const animate = () => {
    if (!isPlaying) return;

    currentTime += 0.1 * playbackSpeed;

    if (currentTime > trajectoryData.time_range.max) {
      currentTime = trajectoryData.time_range.min;
    }

    document.getElementById("timeSlider").value = Math.floor(currentTime * 10);
    document.getElementById("currentTime").textContent =
      currentTime.toFixed(1) + "s";

    renderGroundPlane(currentTime);

    animationFrame = requestAnimationFrame(animate);
  };

  animate();
}

function stopAnimation() {
  if (animationFrame) {
    cancelAnimationFrame(animationFrame);
    animationFrame = null;
  }
}

function reset() {
  stopAnimation();
  isPlaying = false;
  document.getElementById("playPauseBtn").textContent = "Play";
  currentTime = trajectoryData.time_range.min;
  document.getElementById("timeSlider").value = Math.floor(currentTime * 10);
  document.getElementById("currentTime").textContent =
    currentTime.toFixed(1) + "s";
  selectedVehicleId = null;
  clearCameraTransitionsPanel();
  renderGroundPlane(currentTime);
  exitShowcase();
  persistUiState();
}

function renderGroundPlane(time) {
  const frameKey = time.toFixed(1);
  const frameData = trajectoryData.frames[frameKey] || [];
  const visibleFrameVehicles = frameData.filter((vehicle) =>
    activeCameraFilters.has(vehicle.camera)
  ).length;

  const traces = [];
  const layoutAnnotations = [];
  switchTraceCurveNumber = null;

  for (const vehicle of frameData) {
    if (!activeCameraFilters.has(vehicle.camera)) {
      continue;
    }

    if (
      selectedVehicleId &&
      vehicle.global_id.toString() !== selectedVehicleId
    ) {
      continue;
    }

    const footprint = vehicle.footprint;
    const x = [
      footprint[0],
      footprint[2],
      footprint[4],
      footprint[6],
      footprint[0],
    ];
    const y = [
      footprint[1],
      footprint[3],
      footprint[5],
      footprint[7],
      footprint[1],
    ];

    const isSelected = selectedVehicleId === vehicle.global_id.toString();

    const trace = {
      x: x,
      y: y,
      mode: "lines+text",
      fill: "toself",
      fillcolor: vehicle.color,
      line: {
        color: vehicle.color,
        width: isSelected ? 4 : 2,
      },
      opacity: isSelected ? 1.0 : 0.7,
      text: [`G${vehicle.global_id}`],
      textposition: "middle center",
      textfont: {
        size: 12,
        color: "white",
        family: "Arial Black, sans-serif",
      },
      name: `Global ID ${vehicle.global_id}`,
      customdata: [[vehicle.global_id]],
      hovertemplate:
        `<b>Global ID ${vehicle.global_id}</b><br>` +
        `Camera: ${vehicle.camera}<br>` +
        `Track: ${vehicle.track_id}<br>` +
        `Class: ${vehicle.class}<br>` +
        `<extra></extra>`,
    };

    traces.push(trace);
  }

  if (selectedVehicleId) {
    const transitionData = getTransitionData(selectedVehicleId);
    if (transitionData) {
      const segmentedTraces = [];
      const legendCameras = new Set();

      for (const run of transitionData.runs) {
        if (!activeCameraFilters.has(run.camera)) {
          continue;
        }

        const segmentX = [];
        const segmentY = [];
        const runDetections = [];

        for (let i = run.startIndex; i <= run.endIndex; i++) {
          const det = transitionData.detections[i];
          if (det.timestamp > time) break;
          runDetections.push(det);
          const centroid = getFootprintCentroid(det.footprint);
          segmentX.push(centroid.x);
          segmentY.push(centroid.y);
        }

        if (!runDetections.length) continue;

        const cameraColor =
          trajectoryData.camera_colors?.[run.camera] ||
          runDetections[0].color ||
          "#ffffff";
        const startTime = runDetections[0].timestamp;
        const endTime = runDetections[runDetections.length - 1].timestamp;

        segmentedTraces.push({
          x: segmentX,
          y: segmentY,
          mode: segmentX.length > 1 ? "lines+markers" : "markers",
          line: { color: cameraColor, width: 3 },
          marker: {
            size: 7,
            color: cameraColor,
            line: { color: "white", width: 1 },
          },
          hovertemplate:
            `<b>${run.camera}</b><br>` +
            `Segment window: ${startTime.toFixed(2)}s - ${endTime.toFixed(
              2
            )}s<extra></extra>`,
          name: run.camera,
          legendgroup: run.camera,
          showlegend: !legendCameras.has(run.camera),
        });

        legendCameras.add(run.camera);
      }

      if (segmentedTraces.length) {
        traces.unshift(...segmentedTraces);
      }

      const filteredTransitions = getFilteredTransitions(transitionData);
      if (filteredTransitions.length) {
        const transitionColors = filteredTransitions.map((transition) =>
          transition.switchTime <= time ? "#ffd166" : "#36506d"
        );
        switchTraceCurveNumber = traces.length;
        traces.push({
          x: filteredTransitions.map((transition) => transition.x),
          y: filteredTransitions.map((transition) => transition.y),
          mode: "markers+text",
          marker: {
            size: 13,
            color: transitionColors,
            symbol: "diamond",
            line: { color: "#ffffff", width: 1.5 },
          },
          text: filteredTransitions.map(
            (transition) =>
              `${transition.fromCamera} \u2192 ${transition.toCamera}`
          ),
          textposition: "top center",
          textfont: {
            size: 11,
            color: "#ffffff",
            family: "Arial, sans-serif",
          },
          hovertemplate:
            "<b>Camera Switch</b><br>" +
            "%{text}<br>" +
            "t=%{customdata:.2f}s<extra></extra>",
          customdata: filteredTransitions.map(
            (transition) => transition.switchTime
          ),
          name: "Camera switches",
          legendgroup: "switches",
          showlegend: true,
        });
      } else if (transitionData.cameraPath.length === 1) {
        layoutAnnotations.push({
          xref: "paper",
          yref: "paper",
          x: 0.01,
          y: 1.08,
          xanchor: "left",
          yanchor: "bottom",
          showarrow: false,
          text: `No camera switch (stayed in ${transitionData.cameraPath[0]})`,
          font: { size: 12, color: "#98D8C8" },
          bgcolor: "rgba(10,25,41,0.9)",
          bordercolor: "rgba(152,216,200,0.6)",
          borderwidth: 1,
          borderpad: 5,
        });
      }

      const activeCamera = getActiveStableCamera(transitionData, time);
      if (activeCamera) {
        layoutAnnotations.push({
          xref: "paper",
          yref: "paper",
          x: 0.99,
          y: 1.08,
          xanchor: "right",
          yanchor: "bottom",
          showarrow: false,
          text: `Active camera @ ${time.toFixed(1)}s: ${activeCamera}`,
          font: { size: 12, color: "#ffffff" },
          bgcolor: "rgba(10,25,41,0.9)",
          bordercolor: "rgba(0,113,227,0.7)",
          borderwidth: 1,
          borderpad: 5,
        });
      }
    }

    updateCameraTransitionsPanel(selectedVehicleId, time);
  }

  renderTimelineTicks(selectedVehicleId, time);
  updateCurrentCameraBadge(selectedVehicleId, time);

  const titleText = selectedVehicleId
    ? `Ground Plane View - Global ID ${selectedVehicleId}`
    : `Ground Plane View - ${visibleFrameVehicles} vehicles`;

  const layout = {
    title: {
      text: titleText,
      font: { size: 20, color: "#ffffff" },
    },
    xaxis: {
      title: "X (meters)",
      scaleanchor: "y",
      scaleratio: 1,
      gridcolor: "#1e3a5f",
      color: "#ffffff",
    },
    yaxis: {
      title: "Y (meters)",
      gridcolor: "#1e3a5f",
      color: "#ffffff",
    },
    hovermode: "closest",
    showlegend: !!selectedVehicleId,
    legend: {
      orientation: "h",
      yanchor: "top",
      y: -0.12,
      xanchor: "left",
      x: 0,
      bgcolor: "rgba(10,25,41,0.4)",
      bordercolor: "rgba(30,58,95,0.8)",
      borderwidth: 1,
      font: { color: "#ffffff", size: 11 },
    },
    plot_bgcolor: "#0a1929",
    paper_bgcolor: "#0a1929",
    font: { color: "#ffffff" },
    margin: { l: 60, r: 40, t: 60, b: 90 },
    annotations: layoutAnnotations,
  };

  const config = { responsive: true, displayModeBar: false };

  Plotly.react("groundPlane", traces, layout, config).then(() => {
    if (!plotInitialized) {
      const plotDiv = document.getElementById("groundPlane");
      plotDiv.on("plotly_click", handleVehicleClick);
      plotInitialized = true;
    }
  });
}

function handleVehicleClick(data) {
  if (!data || !data.points || data.points.length === 0) return;

  const point = data.points[0];
  let globalId = null;

  if (point.customdata && point.customdata.length > 0) {
    globalId = point.customdata[0];
  } else if (
    point.data &&
    point.data.customdata &&
    point.data.customdata.length > 0
  ) {
    globalId = point.data.customdata[0][0];
  } else if (point.data && point.data.name) {
    const match = point.data.name.match(/ID (\d+)/);
    if (match) {
      globalId = match[1];
    }
  }

  if (!globalId) return;

  if (isPlaying) togglePlayPause();
  selectedVehicleId = globalId.toString();

  // Save to localStorage for statistics page
  localStorage.setItem("lastViewedGlobalId", globalId.toString());

  // Navigate to statistics page
  window.location.href = `statistics.html`;
}

function searchGlobalId() {
  const input = document.getElementById("searchGlobalId");
  const globalId = input.value.trim();

  if (!globalId) {
    alert("Please enter a Global ID");
    return;
  }

  const traj = trajectoryData.trajectories[globalId];
  if (!traj) {
    alert(`Global ID ${globalId} not found`);
    return;
  }

  if (traj.detections.length > 0) {
    const firstTime = traj.detections[0].timestamp;
    currentTime = firstTime;
    document.getElementById("timeSlider").value = Math.floor(firstTime * 10);
    document.getElementById("currentTime").textContent =
      firstTime.toFixed(1) + "s";

    if (isPlaying) togglePlayPause();
    selectedVehicleId = globalId.toString();
    getTransitionData(selectedVehicleId);
    updateCameraTransitionsPanel(selectedVehicleId, currentTime);

    // Save to localStorage for statistics page
    localStorage.setItem("lastViewedGlobalId", selectedVehicleId);

    renderGroundPlane(currentTime);
    persistUiState();
  }
}

function startShowcase() {
  showcaseVehicles = [];

  for (const [globalId, traj] of Object.entries(trajectoryData.trajectories)) {
    const cameraCount = traj.cameras.length;
    if (cameraCount >= 3) {
      showcaseVehicles.push({
        globalId: globalId,
        cameras: cameraCount,
        detections: traj.detections.length,
        firstTime: traj.detections[0].timestamp,
      });
    }
  }

  showcaseVehicles.sort((a, b) => {
    if (b.cameras !== a.cameras) return b.cameras - a.cameras;
    return b.detections - a.detections;
  });

  if (showcaseVehicles.length === 0) {
    alert("No multi-camera vehicles found");
    return;
  }

  showcaseMode = true;
  showcaseIndex = 0;
  document.getElementById("showcaseInfo").style.display = "block";
  document.getElementById("showcaseTotal").textContent =
    showcaseVehicles.length;

  console.log(
    `Showcase mode: Found ${showcaseVehicles.length} multi-camera vehicles`
  );
  showShowcaseExample();
}

function nextShowcaseExample() {
  if (!showcaseMode || showcaseVehicles.length === 0) return;

  showcaseIndex = (showcaseIndex + 1) % showcaseVehicles.length;
  showShowcaseExample();
}

function showShowcaseExample() {
  const example = showcaseVehicles[showcaseIndex];
  document.getElementById("showcaseIndex").textContent = showcaseIndex + 1;

  currentTime = example.firstTime;
  document.getElementById("timeSlider").value = Math.floor(currentTime * 10);
  document.getElementById("currentTime").textContent =
    currentTime.toFixed(1) + "s";

  if (isPlaying) togglePlayPause();
  selectedVehicleId = example.globalId.toString();
  getTransitionData(selectedVehicleId);
  updateCameraTransitionsPanel(selectedVehicleId, currentTime);

  // Save to localStorage for statistics page
  localStorage.setItem("lastViewedGlobalId", selectedVehicleId);

  renderGroundPlane(currentTime);
  persistUiState();

  console.log(
    `Showcase ${showcaseIndex + 1}/${showcaseVehicles.length}: Global ID ${
      example.globalId
    } - ${example.cameras} cameras, ${example.detections} detections`
  );
}

function exitShowcase() {
  showcaseMode = false;
  showcaseVehicles = [];
  showcaseIndex = 0;
  document.getElementById("showcaseInfo").style.display = "none";
  persistUiState();
}

window.addEventListener("DOMContentLoaded", init);
