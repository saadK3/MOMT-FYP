const UNITY_WEBGL_BASE = "/unity-webgl/";

const statusText = document.getElementById("unityStatusText");
const hoverCard = document.getElementById("unityHoverCard");
const hoverTitle = document.getElementById("hoverTitle");
const hoverCopy = document.getElementById("hoverCopy");
const canvas = document.getElementById("unityCanvas");

let unityInstance = null;
let unityReady = false;
let latestState = null;
let hoverSummaries = new Map();

window.MomtUnityHost = {
  onReady() {
    markUnityReady();
  },
  onVehicleEvent(payloadJson) {
    let payload;
    try {
      payload = JSON.parse(payloadJson);
    } catch (error) {
      console.warn("[UnityHost] Invalid vehicle event payload", error);
      return;
    }

    handleVehicleEvent(payload);
  },
};

init().catch((error) => {
  console.error("[UnityHost] Failed to initialize", error);
  setStatus(`Failed to load Unity build: ${error.message || error}`);
});

window.addEventListener("message", (event) => {
  if (event.origin !== window.location.origin) return;
  if (event.data?.type !== "dashboard_state") return;

  latestState = event.data.payload || null;
  hoverSummaries = new Map(
    (latestState?.liveJourneySummaries || []).map((summary) => [
      summary.globalId,
      summary,
    ]),
  );
  updateStatusFromState();
  updateOverlayCards();
  flushState();
});

async function init() {
  const buildConfig = await loadBuildConfig();
  const createUnityInstance = await loadLoader(resolveBuildUrl(buildConfig.loaderUrl));

  unityInstance = await createUnityInstance(canvas, {
    dataUrl: resolveBuildUrl(buildConfig.dataUrl),
    frameworkUrl: resolveBuildUrl(buildConfig.frameworkUrl),
    codeUrl: resolveBuildUrl(buildConfig.codeUrl),
    companyName: buildConfig.companyName,
    productName: buildConfig.productName,
    productVersion: buildConfig.productVersion,
    streamingAssetsUrl: `${UNITY_WEBGL_BASE}StreamingAssets`,
  });

  markUnityReady();
}

async function loadBuildConfig() {
  const response = await fetch(`${UNITY_WEBGL_BASE}build-config.json`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Unity WebGL build not found. Build the Unity project first.");
  }
  return response.json();
}

async function loadLoader(loaderUrl) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = loaderUrl;
    script.onload = () => {
      if (typeof window.createUnityInstance !== "function") {
        reject(new Error("Unity loader did not expose createUnityInstance."));
        return;
      }
      resolve(window.createUnityInstance);
    };
    script.onerror = () =>
      reject(new Error("Failed to load Unity loader script."));
    document.head.appendChild(script);
  });
}

function resolveBuildUrl(url) {
  return new URL(url, `${window.location.origin}${UNITY_WEBGL_BASE}`).toString();
}

function flushState() {
  if (!unityReady || !unityInstance || !latestState) return;
  unityInstance.SendMessage(
    "DashboardBridge",
    "ApplyDashboardState",
    JSON.stringify(latestState),
  );
}

function updateStatusFromState() {
  if (!latestState) {
    setStatus("Waiting for dashboard state.");
    return;
  }

  if (latestState.viewMode === "3d-journey") {
    if (latestState.selectedJourneySummary) {
      setStatus(
        `Rendering 3D vehicle journey for G${latestState.selectedJourneySummary.globalId}.`,
      );
    } else if (latestState.selectedGlobalId) {
      setStatus(`Loading 3D vehicle journey for G${latestState.selectedGlobalId}.`);
    } else {
      setStatus("Select a Global ID in the dashboard to open its 3D journey.");
    }
    return;
  }

  const count = latestState.liveVehicles?.length || 0;
  setStatus(`Rendering ${count} active vehicle(s) in 3D live view.`);
}

function setStatus(text) {
  statusText.textContent = text;
}

function markUnityReady() {
  if (unityReady) return;

  unityReady = true;
  setStatus("Unity 3D ready. Waiting for dashboard state.");
  window.parent.postMessage(
    { type: "unity_ready" },
    window.location.origin,
  );
  updateStatusFromState();
  updateOverlayCards();
  flushState();
}

function handleVehicleEvent(payload) {
  if (!payload || !payload.eventType) return;

  if (payload.eventType === "leave") {
    updateOverlayCards();
    return;
  }

  const summary = hoverSummaries.get(payload.globalId) || null;
  showHoverCard(
    `G${payload.globalId}`,
    buildHoverHtml(
      payload,
      summary || latestState?.selectedJourneySummary || null,
    ),
  );

  if (payload.eventType === "click") {
    window.parent.postMessage(
      {
        type: "unity_vehicle_click",
        globalId: payload.globalId,
      },
      window.location.origin,
    );
  }
}

function updateOverlayCards() {
  if (
    latestState?.viewMode === "3d-journey" &&
    latestState?.selectedJourneySummary
  ) {
    const summary = latestState.selectedJourneySummary;
    showHoverCard(`G${summary.globalId}`, buildSummaryHtml(summary));
    return;
  }

  hoverCard.classList.add("hidden");
}

function showHoverCard(title, html) {
  hoverTitle.textContent = title;
  hoverCopy.innerHTML = html;
  hoverCard.classList.remove("hidden");
}

function buildHoverHtml(payload, summary) {
  const cameraState =
    summary?.currentCameraLabel || payload.cameraStateLabel || "Unknown";
  const hasChanged = Boolean(
    summary?.hasCameraChanged ?? payload.hasCameraChanged,
  );
  const changedClass = hasChanged ? "positive" : "warning";
  const changedText = hasChanged ? "Yes" : "No";
  const journeyText = summary?.journeyText || `${cameraState} only`;
  const lastChange =
    summary?.lastTransitionText || "No camera changes recorded";
  const transitionCount = summary?.transitionCount ?? 0;

  return [
    `<strong>${summary?.vehicleClass || payload.vehicleClass || "Vehicle"}</strong>`,
    `Camera State: ${cameraState}`,
    `Camera Changed: <span class="${changedClass}">${changedText}</span>`,
    `Transitions: ${transitionCount}`,
    `Route: ${compactJourneyText(journeyText, 52)}`,
    `Last: ${compactJourneyText(lastChange, 44)}`,
    `<span class="hint">Click to open this vehicle's 3D journey.</span>`,
  ].join("<br>");
}

function buildSummaryHtml(summary) {
  const changedClass = summary.hasCameraChanged ? "positive" : "warning";
  const changedText = summary.hasCameraChanged ? "Yes" : "No";

  return [
    `<strong>${summary.vehicleClass || "Vehicle"}</strong>`,
    `Current Camera: ${summary.currentCameraLabel || "Unknown"}`,
    `Camera Changed: <span class="${changedClass}">${changedText}</span>`,
    `Transitions: ${summary.transitionCount ?? 0}`,
    `Route: ${compactJourneyText(summary.journeyText || "Unknown", 52)}`,
    `Last: ${compactJourneyText(summary.lastTransitionText || "No camera changes recorded", 44)}`,
    `<span class="hint">Use search or click a live vehicle to switch journeys.</span>`,
  ].join("<br>");
}

function compactJourneyText(text, maxLength) {
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}
