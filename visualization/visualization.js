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

async function init() {
  try {
    const response = await fetch("trajectory_data_optimized.json");
    trajectoryData = await response.json();

    const slider = document.getElementById("timeSlider");
    slider.min = Math.floor(trajectoryData.time_range.min * 10);
    slider.max = Math.floor(trajectoryData.time_range.max * 10);
    slider.value = slider.min;

    currentTime = trajectoryData.time_range.min;
    document.getElementById("currentTime").textContent =
      currentTime.toFixed(1) + "s";

    setupEventListeners();
    renderGroundPlane(trajectoryData.time_range.min);

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
  });

  document
    .getElementById("playPauseBtn")
    .addEventListener("click", togglePlayPause);
  document.getElementById("resetBtn").addEventListener("click", reset);
  document.getElementById("speedSelect").addEventListener("change", (e) => {
    playbackSpeed = parseFloat(e.target.value);
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
  renderGroundPlane(currentTime);
  selectedVehicleId = null;
  exitShowcase();
}

function renderGroundPlane(time) {
  const frameKey = time.toFixed(1);
  const frameData = trajectoryData.frames[frameKey];

  if (!frameData) return;

  const traces = [];

  for (const vehicle of frameData) {
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
    const traj = trajectoryData.trajectories[selectedVehicleId];
    if (traj) {
      const trailDetections = traj.detections.filter(
        (det) => det.timestamp <= time
      );
      if (trailDetections.length > 1) {
        const trailX = [];
        const trailY = [];
        const trailColors = [];

        for (const det of trailDetections) {
          const fp = det.footprint;
          trailX.push((fp[0] + fp[2] + fp[4] + fp[6]) / 4);
          trailY.push((fp[1] + fp[3] + fp[5] + fp[7]) / 4);
          trailColors.push(det.color);
        }

        traces.unshift({
          x: trailX,
          y: trailY,
          mode: "lines+markers",
          line: { color: "rgba(255,255,255,0.5)", width: 3, dash: "dot" },
          marker: {
            size: 6,
            color: trailColors,
            line: { color: "white", width: 1 },
          },
          showlegend: false,
          hoverinfo: "skip",
        });
      }
    }
  }

  const titleText = selectedVehicleId
    ? `Ground Plane View - Global ID ${selectedVehicleId}`
    : `Ground Plane View - ${frameData.length} vehicles`;

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
    showlegend: false,
    plot_bgcolor: "#0a1929",
    paper_bgcolor: "#0a1929",
    font: { color: "#ffffff" },
    margin: { l: 60, r: 40, t: 60, b: 60 },
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
    selectedVehicleId = globalId;

    // Save to localStorage for statistics page
    localStorage.setItem("lastViewedGlobalId", globalId);

    renderGroundPlane(currentTime);
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
  selectedVehicleId = example.globalId;

  // Save to localStorage for statistics page
  localStorage.setItem("lastViewedGlobalId", example.globalId);

  renderGroundPlane(currentTime);

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
}

window.addEventListener("DOMContentLoaded", init);
