const CAMERA_IDS = ["c001", "c002", "c003", "c004", "c005"];
const CAMERA_OFFSETS = {
  c001: 0.0,
  c002: 1.64,
  c003: 2.049,
  c004: 2.177,
  c005: 2.235,
};
const FPS = 10;
const FRAME_SERVER_BASE = `http://${window.location.hostname || "localhost"}:5000`;
const HEALTH_CHECK_MS = 10000;
const VIDEO_REFRESH_MS = 400;

let lastContextKey = "";
let lastFrameSignature = "";
let lastRenderedAt = 0;
let frameServerStatus = "unknown";
let lastHealthCheckAt = 0;
let healthCheckPromise = null;
let lastArgs = null;

export function updateVideoPanels(args, { force = false } = {}) {
  lastArgs = args;
  ensureFrameServerHealth();

  const model = buildVideoModel(args);
  if (!model) return;

  const now = Date.now();
  if (
    !force &&
    model.contextKey === lastContextKey &&
    now - lastRenderedAt < VIDEO_REFRESH_MS
  ) {
    return;
  }

  if (
    !force &&
    model.contextKey === lastContextKey &&
    model.frameSignature === lastFrameSignature
  ) {
    return;
  }

  lastContextKey = model.contextKey;
  lastFrameSignature = model.frameSignature;
  lastRenderedAt = now;

  renderVideoModel(model);
}

function ensureFrameServerHealth() {
  if (healthCheckPromise) return;
  if (Date.now() - lastHealthCheckAt < HEALTH_CHECK_MS) return;

  lastHealthCheckAt = Date.now();
  healthCheckPromise = fetch(`${FRAME_SERVER_BASE}/health`, {
    cache: "no-store",
  })
    .then((response) => {
      frameServerStatus = response.ok ? "ready" : "unavailable";
    })
    .catch(() => {
      frameServerStatus = "unavailable";
    })
    .finally(() => {
      healthCheckPromise = null;
      if (lastArgs) {
        updateVideoPanels(lastArgs, { force: true });
      }
    });
}

function buildVideoModel({
  latestTimestamp = 0,
  arrivedCameras = [],
  selectedGlobalId = null,
  journeySummary = null,
  activeVehicle = null,
}) {
  const selectedMode = selectedGlobalId != null && (journeySummary || activeVehicle);
  const cards = selectedMode
    ? buildSelectedCards({
        latestTimestamp,
        selectedGlobalId,
        journeySummary,
        activeVehicle,
      })
    : buildLiveCards({ latestTimestamp, arrivedCameras });

  const title = selectedMode
    ? `G${selectedGlobalId} Video Streams`
    : "Live Camera Streams";
  const subtitle = selectedMode
    ? "Representative camera previews for the selected Global ID across its journey."
    : "Synchronized frame previews aligned to the shared global timeline.";

  const info = buildInfoMessage(selectedMode, cards.length > 0);
  const contextKey = JSON.stringify({
    mode: selectedMode ? "selected" : "live",
    globalId: selectedGlobalId,
    cameras: cards.map((card) => card.key),
    status: frameServerStatus,
  });
  const frameSignature = cards
    .map((card) => `${card.key}:${card.frame ?? "na"}`)
    .join("|");

  return {
    title,
    subtitle,
    info,
    cards,
    contextKey,
    frameSignature,
  };
}

function buildInfoMessage(selectedMode, hasCards) {
  if (frameServerStatus === "unavailable") {
    return "Frame previews are unavailable. Start tools/frame_server.py to enable the video panels.";
  }

  if (!hasCards && selectedMode) {
    return "No camera segments are available yet for the selected Global ID.";
  }

  return selectedMode
    ? "Current cameras are highlighted first. Past cameras use representative archive frames."
    : "Each card shows the latest frame from its synchronized camera stream.";
}

function buildLiveCards({ latestTimestamp, arrivedCameras }) {
  const arrivedSet = new Set(arrivedCameras || []);

  return CAMERA_IDS.map((camera) => {
    const frameInfo = getFrameInfo(camera, latestTimestamp);
    const inLatestDecision = arrivedSet.has(camera);
    const localTime = frameInfo?.localTime ?? null;

    return {
      key: `live:${camera}`,
      camera,
      cameraLabel: camera.toUpperCase(),
      badge: inLatestDecision ? "Live" : "Idle",
      badgeTone: inLatestDecision ? "live" : "idle",
      title: inLatestDecision
        ? "Latest synchronized frame"
        : "No packet in latest decision",
      meta:
        frameInfo == null
          ? "Camera is outside the current synchronized window."
          : `Frame ${frameInfo.frame} • global ${formatSeconds(latestTimestamp)} • local ${formatSeconds(localTime)}`,
      detail: inLatestDecision
        ? "Aligned to the same shared replay timestamp as the map."
        : "This camera did not contribute detections in the latest hub decision.",
      frame: frameInfo?.frame ?? null,
      imageUrl:
        frameInfo == null || frameServerStatus === "unavailable"
          ? null
          : buildFrameUrl(camera, frameInfo.frame),
      emphasis: false,
    };
  });
}

function buildSelectedCards({
  latestTimestamp,
  selectedGlobalId,
  journeySummary,
  activeVehicle,
}) {
  const cardsByCamera = new Map();
  const journeySegments = journeySummary?.journey || [];
  const currentState = new Set(
    activeVehicle?.cameraState ||
      journeySummary?.current_camera_state ||
      [],
  );

  if (journeySegments.length > 0) {
    for (const segment of journeySegments) {
      const segmentTimestamp = pickSegmentTimestamp(
        segment,
        latestTimestamp,
        currentState,
      );

      for (const camera of segment.camera_state || []) {
        const frameInfo = getFrameInfo(camera, segmentTimestamp);
        const existing = cardsByCamera.get(camera);
        const candidate = {
          key: `selected:${camera}`,
          camera,
          cameraLabel: camera.toUpperCase(),
          badge: currentState.has(camera)
            ? "Current"
            : segment.camera_state.length > 1
              ? "Overlap"
              : "Archive",
          badgeTone: currentState.has(camera)
            ? "current"
            : segment.camera_state.length > 1
              ? "overlap"
              : "archive",
          title: currentState.has(camera)
            ? `G${selectedGlobalId} currently visible`
            : `Representative view for G${selectedGlobalId}`,
          meta:
            frameInfo == null
              ? `Segment ${formatSeconds(segment.entered_at)} - ${formatSeconds(segment.last_seen_at)}`
              : `Frame ${frameInfo.frame} • global ${formatSeconds(segmentTimestamp)} • local ${formatSeconds(frameInfo.localTime)}`,
          detail: currentState.has(camera)
            ? `Selected vehicle is currently associated with ${segment.camera_label}.`
            : `Representative frame from ${segment.camera_label} during ${formatSeconds(segment.entered_at)} - ${formatSeconds(segment.last_seen_at)}.`,
          frame: frameInfo?.frame ?? null,
          imageUrl:
            frameInfo == null || frameServerStatus === "unavailable"
              ? null
              : buildFrameUrl(camera, frameInfo.frame),
          emphasis: currentState.has(camera),
          sortTimestamp: segment.last_seen_at,
        };

        if (!existing || candidate.sortTimestamp >= existing.sortTimestamp) {
          cardsByCamera.set(camera, candidate);
        }
      }
    }
  } else if (activeVehicle?.cameraState?.length) {
    for (const camera of activeVehicle.cameraState) {
      const frameInfo = getFrameInfo(camera, latestTimestamp);
      cardsByCamera.set(camera, {
        key: `selected:${camera}`,
        camera,
        cameraLabel: camera.toUpperCase(),
        badge: "Current",
        badgeTone: "current",
        title: `G${selectedGlobalId} currently visible`,
        meta:
          frameInfo == null
            ? "Current frame unavailable for this camera."
            : `Frame ${frameInfo.frame} • global ${formatSeconds(latestTimestamp)} • local ${formatSeconds(frameInfo.localTime)}`,
        detail: "Selected vehicle is active in this camera state right now.",
        frame: frameInfo?.frame ?? null,
        imageUrl:
          frameInfo == null || frameServerStatus === "unavailable"
            ? null
            : buildFrameUrl(camera, frameInfo.frame),
        emphasis: true,
        sortTimestamp: latestTimestamp,
      });
    }
  }

  return [...cardsByCamera.values()].sort((left, right) => {
    if (left.emphasis !== right.emphasis) {
      return left.emphasis ? -1 : 1;
    }
    return right.sortTimestamp - left.sortTimestamp;
  });
}

function pickSegmentTimestamp(segment, latestTimestamp, currentState) {
  const cameras = segment.camera_state || [];
  const isCurrent = cameras.some((camera) => currentState.has(camera));
  if (isCurrent) {
    return Math.max(segment.entered_at, Math.min(latestTimestamp, segment.last_seen_at));
  }

  return (segment.entered_at + segment.last_seen_at) / 2;
}

function getFrameInfo(camera, globalTimestamp) {
  const offset = CAMERA_OFFSETS[camera];
  if (offset == null) return null;

  const localTime = globalTimestamp - offset;
  if (!Number.isFinite(localTime) || localTime < 0) return null;

  return {
    localTime,
    frame: Math.max(0, Math.floor(localTime * FPS + 1e-6)),
  };
}

function buildFrameUrl(camera, frame) {
  return `${FRAME_SERVER_BASE}/frame/${camera}/${frame}?t=${frame}`;
}

function renderVideoModel(model) {
  const titleEl = document.getElementById("videoRailTitle");
  const subtitleEl = document.getElementById("videoRailSubtitle");
  const infoEl = document.getElementById("videoRailInfo");
  const gridEl = document.getElementById("videoPanelGrid");

  if (!titleEl || !subtitleEl || !infoEl || !gridEl) return;

  titleEl.textContent = model.title;
  subtitleEl.textContent = model.subtitle;
  infoEl.textContent = model.info;
  infoEl.classList.toggle("warning", frameServerStatus === "unavailable");

  if (model.cards.length === 0) {
    gridEl.innerHTML = `
      <div class="video-empty-state">
        <div class="video-empty-title">No video previews available</div>
        <div class="video-empty-copy">
          Select a vehicle with journey history or wait for synchronized live frames.
        </div>
      </div>
    `;
    return;
  }

  gridEl.innerHTML = model.cards
    .map((card) => {
      const imageHtml = card.imageUrl
        ? `
          <img
            class="video-panel-image"
            src="${card.imageUrl}"
            alt="${card.cameraLabel} frame preview"
            loading="lazy"
            data-camera="${card.camera}"
            data-frame="${card.frame}"
          />
        `
        : `
          <div class="video-panel-placeholder">
            <span>${frameServerStatus === "unavailable" ? "Frame preview unavailable" : "No frame available"}</span>
          </div>
        `;

      return `
        <article class="video-panel-card ${card.emphasis ? "emphasis" : ""}">
          <div class="video-panel-media">
            ${imageHtml}
            <div class="video-panel-overlay">
              <span class="video-panel-camera">${card.cameraLabel}</span>
              <span class="video-panel-badge ${card.badgeTone}">${card.badge}</span>
            </div>
          </div>
          <div class="video-panel-body">
            <div class="video-panel-title">${card.title}</div>
            <div class="video-panel-meta">${card.meta}</div>
            <div class="video-panel-detail">${card.detail}</div>
          </div>
        </article>
      `;
    })
    .join("");

  for (const image of gridEl.querySelectorAll(".video-panel-image")) {
    image.addEventListener("error", handleImageError, { once: true });
  }
}

function handleImageError() {
  if (frameServerStatus !== "unavailable") {
    frameServerStatus = "unavailable";
    if (lastArgs) {
      updateVideoPanels(lastArgs, { force: true });
    }
  }
}

function formatSeconds(value) {
  return `${Number(value || 0).toFixed(1)}s`;
}
