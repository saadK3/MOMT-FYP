// Statistics Page JavaScript
// Auto-loads last viewed vehicle from showcase mode

let trajectoryData = null;

const CAMERA_COLORS = {
  c001: "rgb(255, 107, 107)",
  c002: "rgb(78, 205, 196)",
  c003: "rgb(69, 183, 209)",
  c004: "rgb(255, 160, 122)",
  c005: "rgb(152, 216, 200)",
};

async function init() {
  try {
    const response = await fetch("trajectory_data_optimized.json");
    trajectoryData = await response.json();

    setupEventListeners();

    // Auto-load last viewed Global ID from showcase
    const lastViewedId = localStorage.getItem("lastViewedGlobalId");
    if (lastViewedId && trajectoryData.trajectories[lastViewedId]) {
      document.getElementById("statsSearchGlobalId").value = lastViewedId;
      loadVehicleStatistics();
    }

    console.log("Statistics page loaded");
  } catch (error) {
    console.error("Error loading data:", error);
    alert("Error loading visualization data.");
  }
}

function setupEventListeners() {
  document
    .getElementById("statsSearchBtn")
    .addEventListener("click", loadVehicleStatistics);
  document
    .getElementById("statsSearchGlobalId")
    .addEventListener("keypress", (e) => {
      if (e.key === "Enter") loadVehicleStatistics();
    });
}

function loadVehicleStatistics() {
  const input = document.getElementById("statsSearchGlobalId");
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

  document.getElementById("vehicleInfo").style.display = "block";
  document.getElementById("infoGlobalId").textContent = globalId;

  const cameraSet = new Set();
  let vehicleClass = "";

  for (const det of traj.detections) {
    cameraSet.add(det.camera);
    if (!vehicleClass) vehicleClass = det.class;
  }

  document.getElementById("infoClass").textContent = vehicleClass;
  document.getElementById("infoCameras").textContent = cameraSet.size;
  document.getElementById("infoDetections").textContent =
    traj.detections.length;

  loadCameraFrames(globalId);
  renderCameraCoverageChart(globalId);
  renderTemporalChart(globalId);
}

async function loadCameraFrames(globalId) {
  const framesContainer = document.getElementById("cameraFrames");
  framesContainer.innerHTML =
    '<div class="loading">Loading camera frames...</div>';

  const traj = trajectoryData.trajectories[globalId];

  const cameraDetections = {};
  for (const det of traj.detections) {
    if (!cameraDetections[det.camera]) {
      cameraDetections[det.camera] = [];
    }
    cameraDetections[det.camera].push(det);
  }

  for (const camera in cameraDetections) {
    cameraDetections[camera].sort((a, b) => a.timestamp - b.timestamp);
  }

  const selectedFrames = [];
  for (const camera in cameraDetections) {
    const dets = cameraDetections[camera];
    const selectedDet = dets.length >= 2 ? dets[1] : dets[0];
    selectedFrames.push(selectedDet);
  }

  selectedFrames.sort((a, b) => a.camera.localeCompare(b.camera));

  framesContainer.innerHTML = "";

  for (const det of selectedFrames) {
    const frameDiv = document.createElement("div");
    frameDiv.className = "camera-frame";
    frameDiv.style.borderLeft = `4px solid ${det.color}`;

    const keypointsStr = det.keypoints ? det.keypoints.join(",") : "";
    const frameUrl = keypointsStr
      ? `http://localhost:5000/frame_with_footprint/${det.camera}/${det.frame_number}/${det.track_id}/${keypointsStr}`
      : `http://localhost:5000/frame/${det.camera}/${det.frame_number}`;

    const instanceNum = cameraDetections[det.camera].indexOf(det) + 1;
    const totalInstances = cameraDetections[det.camera].length;

    frameDiv.innerHTML = `
            <h4 style="color: ${det.color}">${det.camera}</h4>
            <p style="color: var(--text-secondary); font-size: 0.9em; margin: 5px 0;">
                Instance ${instanceNum} of ${totalInstances} | Frame ${det.frame_number}
            </p>
            <img src="${frameUrl}"
                 alt="Frame ${det.frame_number}"
                 style="width: 100%; border-radius: 8px; margin-top: 0.5rem;"
                 onerror="this.parentElement.innerHTML='<div style=\\'background: var(--bg-tertiary); height: 200px; display: flex; align-items: center; justify-content: center; border-radius: 8px;\\' ><p style=\\'color: var(--text-secondary);\\'>Frame server not running</p></div>'">
        `;

    framesContainer.appendChild(frameDiv);
  }
}

function renderCameraCoverageChart(globalId) {
  const traj = trajectoryData.trajectories[globalId];

  const cameraDetections = {};
  for (const det of traj.detections) {
    if (!cameraDetections[det.camera]) {
      cameraDetections[det.camera] = [];
    }
    cameraDetections[det.camera].push(det);
  }

  const cameras = Object.keys(cameraDetections).sort();
  const detectionCounts = cameras.map((cam) => cameraDetections[cam].length);
  const colors = cameras.map((cam) => CAMERA_COLORS[cam] || "#667eea");

  const data = [
    {
      x: cameras,
      y: detectionCounts,
      type: "bar",
      marker: {
        color: colors,
        line: {
          color: "rgba(255,255,255,0.2)",
          width: 2,
        },
      },
      text: detectionCounts.map((count) => `${count}`),
      textposition: "outside",
      textfont: { color: "#ffffff" },
      hovertemplate: "<b>%{x}</b><br>Detections: %{y}<extra></extra>",
    },
  ];

  const layout = {
    plot_bgcolor: "#0a1929",
    paper_bgcolor: "#0a1929",
    font: { color: "#ffffff" },
    xaxis: {
      title: "Camera",
      gridcolor: "#1e3a5f",
    },
    yaxis: {
      title: "Detections",
      gridcolor: "#1e3a5f",
    },
    margin: { l: 60, r: 40, t: 40, b: 60 },
    height: 300,
  };

  const config = { responsive: true, displayModeBar: false };

  Plotly.newPlot("cameraCoverageChart", data, layout, config);
}

function renderTemporalChart(globalId) {
  const traj = trajectoryData.trajectories[globalId];

  const timestamps = traj.detections.map((det) => det.timestamp);
  const cameras = traj.detections.map((det) => det.camera);
  const colors = traj.detections.map((det) => CAMERA_COLORS[det.camera]);

  const data = [
    {
      x: timestamps,
      y: cameras,
      mode: "markers",
      marker: {
        size: 12,
        color: colors,
        line: {
          color: "rgba(255,255,255,0.3)",
          width: 2,
        },
      },
      hovertemplate: "<b>%{y}</b><br>Time: %{x:.1f}s<extra></extra>",
    },
  ];

  const layout = {
    plot_bgcolor: "#0a1929",
    paper_bgcolor: "#0a1929",
    font: { color: "#ffffff" },
    xaxis: {
      title: "Time (seconds)",
      gridcolor: "#1e3a5f",
    },
    yaxis: {
      title: "Camera",
      gridcolor: "#1e3a5f",
    },
    margin: { l: 60, r: 40, t: 40, b: 60 },
    height: 300,
  };

  const config = { responsive: true, displayModeBar: false };

  Plotly.newPlot("temporalChart", data, layout, config);
}

window.addEventListener("DOMContentLoaded", init);
