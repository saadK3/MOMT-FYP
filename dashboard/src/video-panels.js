const CAMERA_IDS = ["c001", "c002", "c003", "c004", "c005"];
const CAMERA_OFFSETS = {
  c001: 0.0,
  c002: 1.64,
  c003: 2.049,
  c004: 2.177,
  c005: 2.235,
};
const FPS = 5;
const FRAME_SERVER_BASE = `http://${window.location.hostname || "localhost"}:5000`;
const HEALTH_CHECK_MS = 10000;
const OBS_INDEX_URL = "/offline_observations_index.json";
const FOOTPRINT_INDICES = [12, 13, 14, 15];

let frameServerStatus = "unknown";
let lastHealthCheckAt = 0;
let healthCheckPromise = null;
let observationsLoadPromise = null;
let observationsByGid = null;
let lastArgs = null;
let lastRenderSignature = "";
const PREFETCHED_FRAME_URLS = new Set();
const PREFETCH_INFLIGHT = new Set();
const prefetchedUrls = new Set();
const inFlightPrefetch = new Map();

const cardElements = new Map();

export function updateVideoPanels(args, { force = false } = {}) {
  lastArgs = args;
  ensureFrameServerHealth();
  ensureObservationIndexLoaded();

  const model = buildVideoModel(args);
  if (!model) return;

  prefetchCardImages(model.cards);

  if (!force && model.renderSignature === lastRenderSignature) {
    return;
  }
  lastRenderSignature = model.renderSignature;
  renderVideoModel(model);
}

function ensureFrameServerHealth() {
  if (healthCheckPromise) return;
  if (Date.now() - lastHealthCheckAt < HEALTH_CHECK_MS) return;

  lastHealthCheckAt = Date.now();
  healthCheckPromise = fetch(`${FRAME_SERVER_BASE}/health`, { cache: "no-store" })
    .then((response) => {
      frameServerStatus = response.ok ? "ready" : "unavailable";
    })
    .catch(() => {
      frameServerStatus = "unavailable";
    })
    .finally(() => {
      healthCheckPromise = null;
      if (lastArgs) updateVideoPanels(lastArgs, { force: true });
    });
}

function ensureObservationIndexLoaded() {
  if (observationsByGid || observationsLoadPromise) return;

  observationsLoadPromise = fetch(OBS_INDEX_URL, { cache: "no-store" })
    .then((response) => (response.ok ? response.json() : null))
    .then((payload) => {
      observationsByGid = payload?.by_gid || {};
    })
    .catch(() => {
      observationsByGid = {};
    })
    .finally(() => {
      observationsLoadPromise = null;
      if (lastArgs) updateVideoPanels(lastArgs, { force: true });
    });
}

function buildVideoModel({
  latestTimestamp = 0,
  arrivedCameras = [],
  selectedGlobalId = null,
}) {
  const selectedMode = selectedGlobalId != null;
  const cards = selectedMode
    ? buildSelectedCards({ selectedGlobalId })
    : buildLiveCards({ latestTimestamp, arrivedCameras });

  const title = selectedMode
    ? `G${selectedGlobalId} Camera Frames`
    : "Live Camera Frames";
  const subtitle = selectedMode
    ? "One representative frame per camera where the selected vehicle appears."
    : "Synchronized frame previews aligned to the shared global timeline.";
  const info = buildInfoMessage(selectedMode, cards.length > 0);

  const renderSignature = JSON.stringify({
    selectedGlobalId,
    frameServerStatus,
    cards: cards.map((card) => ({
      key: card.key,
      frame: card.frameNumber,
      obsTs: card.observation?.global_ts ?? null,
    })),
  });

  return {
    title,
    subtitle,
    info,
    cards,
    renderSignature,
  };
}

function buildInfoMessage(selectedMode, hasCards) {
  if (frameServerStatus === "unavailable") {
    return "Frame previews are unavailable. Start tools/frame_server.py to enable frame panels.";
  }
  if (selectedMode && observationsByGid == null) {
    return "Loading observation index for footprint overlays...";
  }
  if (selectedMode && !hasCards) {
    return "Selected GID is not visible in any camera at this moment.";
  }
  return selectedMode
    ? "Panels show one representative frame for each camera that observed the selected vehicle."
    : "Select a Global ID to show synchronized camera frames with overlays.";
}

function buildSelectedCards({ selectedGlobalId }) {
  if (!observationsByGid) return [];
  const gidKey = String(selectedGlobalId);
  const byCamera = observationsByGid[gidKey];
  if (!byCamera) return [];

  const cards = [];
  for (const [camera, observations] of Object.entries(byCamera)) {
    const observation = pickRepresentativeObservation(observations);
    if (!observation) continue;

    cards.push({
      key: `gid${selectedGlobalId}:${camera}`,
      camera,
      cameraLabel: camera.toUpperCase(),
      badge: "Seen",
      badgeTone: "archive",
      title: `G${selectedGlobalId} in ${camera.toUpperCase()}`,
      meta: `Representative frame ${observation.frame_number} • t=${formatSeconds(observation.global_ts)}`,
      detail: `Track ${observation.track_id} in ${camera.toUpperCase()}`,
      frameNumber: observation.frame_number,
      imageUrl: buildFrameUrl(camera, observation.frame_number),
      observation,
      selectedGlobalId,
      emphasis: true,
    });
  }

  return cards.sort((left, right) => left.camera.localeCompare(right.camera));
}

function buildLiveCards({ latestTimestamp, arrivedCameras }) {
  const arrivedSet = new Set(arrivedCameras || []);
  return CAMERA_IDS.map((camera) => {
    const frameNumber = frameForTimestamp(camera, latestTimestamp);
    return {
      key: `live:${camera}`,
      camera,
      cameraLabel: camera.toUpperCase(),
      badge: arrivedSet.has(camera) ? "Live" : "Idle",
      badgeTone: arrivedSet.has(camera) ? "live" : "idle",
      title: "Synchronized camera frame",
      meta: `global ${formatSeconds(latestTimestamp)} • frame ${frameNumber}`,
      detail: "Select a Global ID to enable vehicle overlay.",
      frameNumber,
      imageUrl: buildFrameUrl(camera, frameNumber),
      observation: null,
      selectedGlobalId: null,
      emphasis: false,
    };
  });
}

function frameForTimestamp(camera, globalTimestamp) {
  const localTime = Math.max(0, globalTimestamp - (CAMERA_OFFSETS[camera] || 0));
  return Math.max(0, Math.floor(localTime * FPS));
}

function buildFrameUrl(camera, frameNumber) {
  return `${FRAME_SERVER_BASE}/frame/${camera}/${frameNumber}`;
}

function findNearestObservation(observations, timestamp, toleranceSeconds) {
  if (!Array.isArray(observations) || observations.length === 0) return null;

  let lo = 0;
  let hi = observations.length - 1;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (observations[mid].global_ts < timestamp) lo = mid + 1;
    else hi = mid;
  }

  const candidates = [observations[lo], observations[lo - 1], observations[lo + 1]].filter(Boolean);
  let best = null;
  let bestDiff = Infinity;
  for (const candidate of candidates) {
    const diff = Math.abs(candidate.global_ts - timestamp);
    if (diff < bestDiff) {
      bestDiff = diff;
      best = candidate;
    }
  }
  if (!best || bestDiff > toleranceSeconds) return null;
  return best;
}

function pickRepresentativeObservation(observations) {
  if (!Array.isArray(observations) || observations.length === 0) return null;
  const mid = Math.floor(observations.length / 2);
  return observations[mid] || observations[0];
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
        <div class="video-empty-title">No synchronized frames</div>
        <div class="video-empty-copy">
          Select a Global ID and move playback to a timestamp where it is visible.
        </div>
      </div>
    `;
    cardElements.clear();
    return;
  }

  prefetchCardFrames(model.cards);
  reconcileCards(gridEl, model.cards);
}

function reconcileCards(gridEl, cards) {
  const wantedKeys = new Set(cards.map((card) => card.key));

  for (const [key, cardEl] of cardElements.entries()) {
    if (wantedKeys.has(key)) continue;
    cardEl.root.remove();
    cardElements.delete(key);
  }

  cards.forEach((card) => {
    let cardEl = cardElements.get(card.key);
    if (!cardEl) {
      cardEl = createCardElement(card);
      cardElements.set(card.key, cardEl);
      gridEl.appendChild(cardEl.root);
    }
    updateCard(cardEl, card);
  });
}

function createCardElement(card) {
  const root = document.createElement("article");
  root.className = `video-panel-card ${card.emphasis ? "emphasis" : ""}`;

  const media = document.createElement("div");
  media.className = "video-panel-media";

  const image = document.createElement("img");
  image.className = "video-panel-image";
  image.alt = `${card.cameraLabel} frame preview`;
  image.loading = "eager";
  image.decoding = "async";
  image.fetchPriority = "high";

  const canvas = document.createElement("canvas");
  canvas.className = "video-panel-overlay-canvas";

  const overlay = document.createElement("div");
  overlay.className = "video-panel-overlay";
  const cameraLabel = document.createElement("span");
  cameraLabel.className = "video-panel-camera";
  const badge = document.createElement("span");
  badge.className = "video-panel-badge";
  overlay.appendChild(cameraLabel);
  overlay.appendChild(badge);

  media.appendChild(image);
  media.appendChild(canvas);
  media.appendChild(overlay);

  const body = document.createElement("div");
  body.className = "video-panel-body";
  const title = document.createElement("div");
  title.className = "video-panel-title";
  const meta = document.createElement("div");
  meta.className = "video-panel-meta";
  const detail = document.createElement("div");
  detail.className = "video-panel-detail";
  body.appendChild(title);
  body.appendChild(meta);
  body.appendChild(detail);

  root.appendChild(media);
  root.appendChild(body);

  return {
    root,
    image,
    canvas,
    cameraLabel,
    badge,
    title,
    meta,
    detail,
    lastImageUrl: "",
  };
}

function updateCard(cardEl, card) {
  cardEl.root.classList.toggle("emphasis", card.emphasis);
  cardEl.cameraLabel.textContent = card.cameraLabel;
  cardEl.badge.className = `video-panel-badge ${card.badgeTone}`;
  cardEl.badge.textContent = card.badge;
  cardEl.title.textContent = card.title;
  cardEl.meta.textContent = card.meta;
  cardEl.detail.textContent = card.detail;

  if (cardEl.lastImageUrl !== card.imageUrl) {
    cardEl.image.src = card.imageUrl;
    cardEl.lastImageUrl = card.imageUrl;
  }

  cardEl.image.onload = () => drawOverlay(cardEl, card);
  if (cardEl.image.complete && cardEl.image.naturalWidth > 0) {
    drawOverlay(cardEl, card);
  }
}

function prefetchCardFrames(cards) {
  for (const card of cards) {
    const url = card.imageUrl;
    if (!url) continue;
    if (PREFETCHED_FRAME_URLS.has(url) || PREFETCH_INFLIGHT.has(url)) continue;
    PREFETCH_INFLIGHT.add(url);
    fetch(url, { cache: "force-cache" })
      .then((response) => {
        if (!response.ok) return null;
        return response.arrayBuffer();
      })
      .finally(() => {
        PREFETCH_INFLIGHT.delete(url);
        PREFETCHED_FRAME_URLS.add(url);
      });
  }
}

function drawOverlay(cardEl, card) {
  const observation = card.observation;
  const image = cardEl.image;
  const canvas = cardEl.canvas;

  const width = Math.max(1, image.clientWidth || image.naturalWidth || 1);
  const height = Math.max(1, image.clientHeight || image.naturalHeight || 1);
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }

  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.clearRect(0, 0, width, height);
  if (!observation) return;

  const points = footprintFromKeypoints(observation.det_keypoints, width, height);
  if (!points) return;

  ctx.lineWidth = 4;
  ctx.strokeStyle = "rgba(34, 197, 94, 0.98)";
  ctx.fillStyle = "rgba(34, 197, 94, 0.14)";
  ctx.beginPath();
  ctx.moveTo(points[0][0], points[0][1]);
  for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
}

function footprintFromKeypoints(keypoints, width, height) {
  if (!Array.isArray(keypoints) || keypoints.length < 32) return null;
  const points = [];
  for (const idx of FOOTPRINT_INDICES) {
    const x = Number(keypoints[idx * 2]);
    const y = Number(keypoints[idx * 2 + 1]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    points.push([x * width, y * height]);
  }
  return points;
}

function formatSeconds(value) {
  return `${Number(value || 0).toFixed(1)}s`;
}

function prefetchCardImages(cards) {
  for (const card of cards) {
    const url = card.imageUrl;
    if (!url || prefetchedUrls.has(url) || inFlightPrefetch.has(url)) continue;
    const promise = fetch(url, { cache: "force-cache" })
      .then((response) => {
        if (response.ok) {
          prefetchedUrls.add(url);
        }
      })
      .catch(() => {})
      .finally(() => {
        inFlightPrefetch.delete(url);
      });
    inFlightPrefetch.set(url, promise);
  }
}
