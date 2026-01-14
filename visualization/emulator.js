// Emulator Playground - WebSocket Client and Visualization Logic

let ws = null;
let isConnected = false;
let frameHistory = [];
const MAX_HISTORY = 20;

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  initializeWebSocket();
  initializeControls();
});

// WebSocket Connection
function initializeWebSocket() {
  const wsUrl = "ws://localhost:8765";

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("WebSocket connected");
      isConnected = true;
      updateConnectionStatus(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (error) {
        console.error("Error parsing message:", error);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      updateConnectionStatus(false);
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      isConnected = false;
      updateConnectionStatus(false);

      // Attempt to reconnect after 3 seconds
      setTimeout(initializeWebSocket, 3000);
    };
  } catch (error) {
    console.error("Failed to create WebSocket:", error);
    updateConnectionStatus(false);
  }
}

// Handle incoming messages
function handleMessage(data) {
  if (data.type === "decision") {
    updateVisualization(data);
    addToHistory(data);
  }
}

// Update connection status indicator
function updateConnectionStatus(connected) {
  const statusElement = document.getElementById("connectionStatus");
  const statusDot = statusElement.querySelector(".status-dot");
  const statusText = statusElement.querySelector(".status-text");

  if (connected) {
    statusDot.classList.add("connected");
    statusText.textContent = "Connected";
  } else {
    statusDot.classList.remove("connected");
    statusText.textContent = "Disconnected";
  }
}

// Update visualization with decision event
function updateVisualization(decision) {
  // Update timestamp
  document.getElementById(
    "currentTimestamp"
  ).textContent = `Frame @ t=${decision.timestamp.toFixed(1)}s`;

  // Update camera columns and sentence words
  const sentenceStatus = decision.sentence_status;

  for (const [cameraId, status] of Object.entries(sentenceStatus)) {
    updateCameraColumn(cameraId, status);
    updateSentenceWord(cameraId, status);
  }

  // Update decision status
  updateDecisionStatus(decision);
}

// Update individual camera column
function updateCameraColumn(cameraId, status) {
  const wordElement = document.getElementById(`word-${cameraId}`);
  const statusElement = document.getElementById(`status-${cameraId}`);
  const delayElement = document.getElementById(`delay-${cameraId}`);
  const columnElement = document.getElementById(`camera-${cameraId}`);

  if (status.arrived) {
    wordElement.textContent = status.word;
    statusElement.textContent = "✓ Arrived";
    delayElement.textContent = `${status.delay_ms}ms`;
    columnElement.classList.add("arrived");
    columnElement.classList.remove("waiting");
  } else {
    wordElement.textContent = "...";
    statusElement.textContent = "⏳ Waiting";
    delayElement.textContent = "-";
    columnElement.classList.add("waiting");
    columnElement.classList.remove("arrived");
  }
}

// Update sentence word display
function updateSentenceWord(cameraId, status) {
  const sentenceElement = document.getElementById(`sentence-${cameraId}`);

  if (status.arrived) {
    sentenceElement.textContent = status.word;
    sentenceElement.classList.remove("waiting");
    sentenceElement.classList.add("arrived");
  } else {
    sentenceElement.textContent = "...";
    sentenceElement.classList.add("waiting");
    sentenceElement.classList.remove("arrived");
  }
}

// Update decision status badge
function updateDecisionStatus(decision) {
  const statusElement = document.getElementById("decisionStatus");
  const badgeElement = statusElement.querySelector(".decision-badge");
  const infoElement = document.getElementById("decisionInfo");

  const arrivedCount = decision.arrived_cameras.length;
  const totalCount = arrivedCount + decision.missing_cameras.length;

  // Remove all decision classes
  badgeElement.classList.remove("complete", "partial", "drop");

  // Update based on decision type
  if (decision.decision === "complete") {
    badgeElement.textContent = "✅ COMPLETE";
    badgeElement.classList.add("complete");
  } else if (decision.decision === "partial") {
    badgeElement.textContent = "⚠️ PARTIAL";
    badgeElement.classList.add("partial");
  } else {
    badgeElement.textContent = "❌ DROP";
    badgeElement.classList.add("drop");
  }

  infoElement.textContent = `${arrivedCount}/${totalCount} cameras • ${decision.latency_ms}ms`;
}

// Add decision to history
function addToHistory(decision) {
  frameHistory.unshift(decision);

  // Keep only last MAX_HISTORY items
  if (frameHistory.length > MAX_HISTORY) {
    frameHistory = frameHistory.slice(0, MAX_HISTORY);
  }

  renderHistory();
}

// Render history list
function renderHistory() {
  const historyList = document.getElementById("historyList");

  if (frameHistory.length === 0) {
    historyList.innerHTML =
      '<div class="history-empty">Waiting for decisions...</div>';
    return;
  }

  historyList.innerHTML = frameHistory
    .map((decision) => {
      const arrivedCount = decision.arrived_cameras.length;
      const totalCount = arrivedCount + decision.missing_cameras.length;

      let statusClass = "";
      let statusIcon = "";

      if (decision.decision === "complete") {
        statusClass = "complete";
        statusIcon = "✅";
      } else if (decision.decision === "partial") {
        statusClass = "partial";
        statusIcon = "⚠️";
      } else {
        statusClass = "drop";
        statusIcon = "❌";
      }

      return `
      <div class="history-item ${statusClass}">
        <span class="history-time">t=${decision.timestamp.toFixed(1)}s</span>
        <span class="history-status">${statusIcon} ${decision.decision.toUpperCase()}</span>
        <span class="history-info">(${arrivedCount}/${totalCount}) • ${
        decision.latency_ms
      }ms</span>
      </div>
    `;
    })
    .join("");
}

// Initialize control sliders
function initializeControls() {
  const jitterSlider = document.getElementById("jitterSlider");
  const latencySlider = document.getElementById("latencySlider");
  const lossSlider = document.getElementById("lossSlider");

  const jitterValue = document.getElementById("jitterValue");
  const latencyValue = document.getElementById("latencyValue");
  const lossValue = document.getElementById("lossValue");

  jitterSlider.addEventListener("input", (e) => {
    const value = parseInt(e.target.value);
    jitterValue.textContent = `${value}ms`;
    sendConfigUpdate({ jitter_ms: value });
  });

  latencySlider.addEventListener("input", (e) => {
    const value = parseInt(e.target.value);
    latencyValue.textContent = `${value}ms`;
    sendConfigUpdate({ base_latency_ms: value });
  });

  lossSlider.addEventListener("input", (e) => {
    const value = parseFloat(e.target.value);
    lossValue.textContent = `${value}%`;
    sendConfigUpdate({ packet_loss_prob: value / 100 });
  });
}

// Send configuration update to backend
function sendConfigUpdate(config) {
  if (!isConnected || !ws) {
    console.warn("WebSocket not connected, cannot send config update");
    return;
  }

  const message = {
    type: "config_update",
    ...config,
  };

  try {
    ws.send(JSON.stringify(message));
    console.log("Config update sent:", config);
  } catch (error) {
    console.error("Failed to send config update:", error);
  }
}
