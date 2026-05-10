/**
 * PlaybackClient - offline data source compatible with WebSocketClient API.
 * Loads a precomputed playback file and emits dashboard events over time.
 */

const DEFAULT_FILE = "/offline_playback.json";
const DEFAULT_SPEED = 1.0;
const DEFAULT_LOOP = true;
const DEFAULT_START_TIMESTAMP = 12.0;
const MIN_SPEED = 0.1;
const MAX_SPEED = 8.0;

export class PlaybackClient {
  constructor({
    fileUrl = DEFAULT_FILE,
    speed = DEFAULT_SPEED,
    loop = DEFAULT_LOOP,
    startTimestamp = DEFAULT_START_TIMESTAMP,
  } = {}) {
    this.fileUrl = fileUrl;
    this.speed = Number.isFinite(speed) && speed > 0 ? speed : DEFAULT_SPEED;
    this.loop = Boolean(loop);
    this.startTimestamp = Number.isFinite(startTimestamp)
      ? Number(startTimestamp)
      : DEFAULT_START_TIMESTAMP;

    this.isConnected = false;
    this.isPlaybackClient = true;
    this._listeners = {};
    this._frames = [];
    this._timer = null;
    this._shouldRun = false;
    this._isPlaying = false;
    this._frameIndex = 0;
    this._startFrameIndex = 0;
    this._startedAt = Date.now();
    this._fullJourneys = new Map();
    this._snapshotJourneys = {};
    this._snapshotEvents = [];
  }

  connect() {
    this._shouldRun = true;
    this._loadAndStart().catch((error) => {
      console.error("[Playback] Failed to initialize:", error);
      this._emit("close");
    });
  }

  disconnect() {
    this._shouldRun = false;
    this._isPlaying = false;
    this._clearTimer();
    if (this.isConnected) {
      this.isConnected = false;
      this._emit("close");
    }
  }

  on(event, callback) {
    if (!this._listeners[event]) this._listeners[event] = [];
    this._listeners[event].push(callback);
  }

  send(payload) {
    if (!payload || payload.type !== "journey_view_request") return false;

    const gid = Number(payload.global_id);
    const journey = Number.isInteger(gid) ? this._fullJourneys.get(gid) || null : null;
    this._emit("journey_view_data", {
      type: "journey_view_data",
      global_id: Number.isInteger(gid) ? gid : null,
      journey,
      error: journey ? null : `Journey not found for Global ID ${gid}`,
    });
    return true;
  }

  play() {
    if (!this.isConnected || !this._frames.length) return;
    if (this._isPlaying) return;
    this._isPlaying = true;
    this._emitPlaybackState("play");
    this._scheduleNext();
  }

  pause() {
    if (!this.isConnected) return;
    if (!this._isPlaying) return;
    this._isPlaying = false;
    this._clearTimer();
    this._emitPlaybackState("pause");
  }

  restart() {
    if (!this.isConnected || !this._frames.length) return;
    this.seekToFrame(this._startFrameIndex);
  }

  seekToFrame(frameIndex) {
    if (!this.isConnected || !this._frames.length) return;
    const bounded = clamp(Math.round(frameIndex), 0, this._frames.length - 1);
    this._frameIndex = bounded;
    this._emitCurrentFrame();
    this._emitPlaybackState("seek");
    if (this._isPlaying) {
      this._scheduleNext();
    }
  }

  seekToProgress(progress) {
    if (!this._frames.length) return;
    const bounded = clamp(Number(progress), 0, 1);
    const frameIndex = Math.round(bounded * (this._frames.length - 1));
    this.seekToFrame(frameIndex);
  }

  setSpeed(nextSpeed) {
    const value = Number(nextSpeed);
    if (!Number.isFinite(value)) return;
    this.speed = clamp(value, MIN_SPEED, MAX_SPEED);
    this._emitPlaybackState("speed");
    if (this._isPlaying) {
      this._scheduleNext();
    }
  }

  setLoop(nextLoop) {
    this.loop = Boolean(nextLoop);
    this._emitPlaybackState("loop");
  }

  getPlaybackState() {
    const totalFrames = this._frames.length;
    const currentFrame = this._frames[this._frameIndex] || null;
    const startTs = this._frames[0]?.timestamp || 0;
    const endTs = this._frames[totalFrames - 1]?.timestamp || startTs;
    const duration = Math.max(0, endTs - startTs);
    const currentTs = Number(currentFrame?.timestamp) || startTs;
    const progress = duration > 0 ? clamp((currentTs - startTs) / duration, 0, 1) : 0;

    return {
      fileUrl: this.fileUrl,
      isConnected: this.isConnected,
      isPlaying: this._isPlaying,
      speed: this.speed,
      loop: this.loop,
      currentFrameIndex: this._frameIndex,
      totalFrames,
      currentTimestamp: currentTs,
      startTimestamp: startTs,
      endTimestamp: endTs,
      progress,
    };
  }

  async _loadAndStart() {
    const response = await fetch(this.fileUrl, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} while loading ${this.fileUrl}`);
    }

    const rawText = await response.text();
    this._frames = parsePlaybackFrames(rawText);
    if (this._frames.length === 0) {
      throw new Error(`No frames found in ${this.fileUrl}`);
    }

    const derived = buildJourneyArtifacts(this._frames);
    this._fullJourneys = derived.fullJourneys;
    this._snapshotJourneys = derived.snapshotJourneys;
    this._snapshotEvents = derived.recentEvents;

    this._startedAt = Date.now();
    this.isConnected = true;
    this._isPlaying = true;
    this._emit("open");
    this._emit("connection_ack", {
      type: "connection_ack",
      message: `Connected to offline playback (${this.fileUrl})`,
    });
    this._emit("camera_journey_snapshot", {
      type: "camera_journey_snapshot",
      journeys: this._snapshotJourneys,
      recent_events: this._snapshotEvents,
    });

    this._startFrameIndex = this._findStartFrameIndex();
    this._frameIndex = this._startFrameIndex;
    this._emitCurrentFrame();
    this._emitPlaybackState("ready");
    this._scheduleNext();
  }

  _emitCurrentFrame() {
    if (!this._shouldRun || this._frames.length === 0) return;
    const frame = this._frames[this._frameIndex];
    this._emit("tracking_update", frame);
    this._emit("system_status", {
      type: "system_status",
      uptime_s: Math.max(0, (Date.now() - this._startedAt) / 1000),
      total_global_ids: frame?.stats?.num_global_ids || 0,
    });
  }

  _scheduleNext() {
    if (!this._shouldRun || !this._isPlaying) return;
    this._clearTimer();

    const nextIndex = this._frameIndex + 1;
    if (nextIndex >= this._frames.length) {
      if (!this.loop) {
        this._isPlaying = false;
        this._emitPlaybackState("ended");
        return;
      }
      this._frameIndex = this._startFrameIndex;
      this._timer = setTimeout(() => {
        this._emitCurrentFrame();
        this._emitPlaybackState("loop");
        this._scheduleNext();
      }, 250);
      return;
    }

    const currentTs = this._frames[this._frameIndex]?.timestamp || 0;
    const nextTs = this._frames[nextIndex]?.timestamp || currentTs;
    const dtMs = Math.max(16, ((nextTs - currentTs) * 1000) / this.speed);

    this._timer = setTimeout(() => {
      if (!this._shouldRun) return;
      this._frameIndex = nextIndex;
      this._emitCurrentFrame();
      this._emitPlaybackState("tick");
      this._scheduleNext();
    }, dtMs);
  }

  _clearTimer() {
    if (this._timer) {
      clearTimeout(this._timer);
      this._timer = null;
    }
  }

  _emit(event, data) {
    const cbs = this._listeners[event];
    if (cbs) cbs.forEach((cb) => cb(data));
  }

  _emitPlaybackState(reason) {
    this._emit("playback_state", {
      type: "playback_state",
      reason,
      ...this.getPlaybackState(),
    });
  }

  _findStartFrameIndex() {
    if (!this._frames.length) return 0;
    const target = this.startTimestamp;
    if (!Number.isFinite(target)) return 0;

    const index = this._frames.findIndex(
      (frame) => Number(frame?.timestamp) >= target,
    );
    return index >= 0 ? index : this._frames.length - 1;
  }
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function parsePlaybackFrames(rawText) {
  const trimmed = rawText.trim();
  if (!trimmed) return [];

  if (trimmed.startsWith("{")) {
    const payload = JSON.parse(trimmed);
    if (Array.isArray(payload?.frames)) return payload.frames;
    return [];
  }

  // JSONL fallback
  return trimmed
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function cameraStateLabel(cameraState) {
  if (!cameraState || cameraState.length === 0) return "Unknown";
  return cameraState.map((camera) => camera.toUpperCase()).join(" + ");
}

function buildJourneyArtifacts(frames) {
  const fullJourneys = new Map();
  const latestSummaries = new Map();
  const recentEvents = [];
  const seenEventIds = new Set();

  const pointsByGid = new Map();

  for (const frame of frames) {
    const ts = Number(frame.timestamp) || 0;
    const grouped = new Map();

    for (const vehicle of frame.vehicles || []) {
      const gid = Number(vehicle.global_id);
      if (!Number.isInteger(gid)) continue;
      if (!grouped.has(gid)) grouped.set(gid, []);
      grouped.get(gid).push(vehicle);
    }

    for (const [gid, group] of grouped.entries()) {
      const primary = group[group.length - 1];
      const cameraState = primary.camera_state || [...new Set(group.map((v) => v.camera))].sort();
      const point = {
        timestamp: ts,
        centroid: primary.centroid || [0, 0],
        footprint: primary.footprint || [],
        heading_deg: 0,
        camera_state: cameraState,
        camera_label: cameraStateLabel(cameraState),
        class: primary.class || "unknown",
      };
      if (!pointsByGid.has(gid)) pointsByGid.set(gid, []);
      pointsByGid.get(gid).push(point);
    }

    for (const [gid, summary] of Object.entries(frame.journey_updates || {})) {
      latestSummaries.set(Number(gid), summary);
    }

    for (const event of frame.camera_change_events || []) {
      if (!event?.event_id || seenEventIds.has(event.event_id)) continue;
      seenEventIds.add(event.event_id);
      recentEvents.push(event);
    }
  }

  for (const [gid, points] of pointsByGid.entries()) {
    if (!points.length) continue;
    const summary = latestSummaries.get(gid);
    const segments = buildSegments(points);
    const transitions = buildTransitions(segments, gid);

    const xs = points.map((p) => p.centroid[0]);
    const ys = points.map((p) => p.centroid[1]);
    const padX = Math.max((Math.max(...xs) - Math.min(...xs)) * 0.2, 8);
    const padY = Math.max((Math.max(...ys) - Math.min(...ys)) * 0.2, 8);

    fullJourneys.set(gid, {
      global_id: gid,
      summary:
        summary ||
        {
          global_id: gid,
          current_camera_state: points[points.length - 1].camera_state,
          current_camera_label: points[points.length - 1].camera_label,
          previous_camera_state: null,
          previous_camera_label: null,
          unique_cameras: [...new Set(points.flatMap((p) => p.camera_state))].sort(),
          transition_count: transitions.length,
          has_camera_changed: transitions.length > 0,
          last_seen_at: points[points.length - 1].timestamp,
          journey: segments.map((seg) => ({
            camera_state: seg.camera_state,
            camera_label: seg.camera_label,
            entered_at: seg.start_time,
            last_seen_at: seg.end_time,
          })),
          last_transition: transitions[transitions.length - 1] || null,
        },
      path_points: points,
      segments,
      transitions,
      bounds: {
        xmin: Math.min(...xs) - padX,
        xmax: Math.max(...xs) + padX,
        ymin: Math.min(...ys) - padY,
        ymax: Math.max(...ys) + padY,
      },
    });
  }

  const snapshotJourneys = {};
  for (const [gid, summary] of latestSummaries.entries()) {
    snapshotJourneys[String(gid)] = summary;
  }

  return {
    fullJourneys,
    snapshotJourneys,
    recentEvents: recentEvents.slice(-50),
  };
}

function buildSegments(points) {
  const segments = [];
  let current = null;

  for (const point of points) {
    const key = point.camera_label;
    if (!current || current.camera_label !== key) {
      current = {
        camera_state: point.camera_state,
        camera_label: point.camera_label,
        start_time: point.timestamp,
        end_time: point.timestamp,
        points: [point],
      };
      segments.push(current);
      continue;
    }
    current.end_time = point.timestamp;
    current.points.push(point);
  }
  return segments;
}

function buildTransitions(segments, globalId) {
  const transitions = [];
  for (let i = 1; i < segments.length; i++) {
    const from = segments[i - 1];
    const to = segments[i];
    const point = to.points[0];
    transitions.push({
      event_id: `${globalId}:${point.timestamp.toFixed(2)}:${from.camera_label}>${to.camera_label}`,
      global_id: globalId,
      timestamp: point.timestamp,
      centroid: point.centroid,
      from_camera_state: from.camera_state,
      from_camera_label: from.camera_label,
      to_camera_state: to.camera_state,
      to_camera_label: to.camera_label,
      transition_index: i,
    });
  }
  return transitions;
}
