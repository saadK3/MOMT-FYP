/**
 * Journey View renders one selected Global ID across the full dataset.
 */

import { MOSAIC_BOUNDS, createBaseLayout } from "./ground-plane.js";

const CAMERA_COLORS = {
  c001: "#4ade80",
  c002: "#38bdf8",
  c003: "#f472b6",
  c004: "#f59e0b",
  c005: "#a78bfa",
};

const TRANSITION_COLOR = "#f8fafc";

export function renderJourneyLoading(containerId, globalId) {
  renderMessage(
    containerId,
    `Journey View - Loading G${globalId || "?"}...`,
    "Preparing the full vehicle journey from the archive.",
  );
}

export function renderJourneyUnavailable(containerId, title, message) {
  renderMessage(containerId, title, message);
}

export function renderJourneyView(
  containerId,
  journey,
  { currentTimestamp = 0, activeVehicle = null, showTrails = true, showLabels = true } = {},
) {
  const summary = journey?.summary;
  const pathPoints = journey?.path_points || [];

  if (!summary || pathPoints.length === 0) {
    renderJourneyUnavailable(
      containerId,
      "Journey View - No data",
      "No archived path points are available for this Global ID.",
    );
    return;
  }

  const traces = [];
  const legendSeen = new Set();

  for (const segment of journey.segments || []) {
    const color = getCameraColor(segment.camera_state);
    const x = segment.points.map((point) => point.centroid[0]);
    const y = segment.points.map((point) => point.centroid[1]);
    const customdata = segment.points.map((point) => [
      point.timestamp,
      point.camera_label,
      point.class,
    ]);

    traces.push({
      x,
      y,
      mode: showTrails ? "lines+markers" : "lines",
      name: segment.camera_label,
      showlegend: !legendSeen.has(segment.camera_label),
      line: {
        color,
        width: 4,
        dash: segment.camera_state.length > 1 ? "dash" : "solid",
      },
      marker: showTrails
        ? {
            size: 5,
            color,
            line: { color: "rgba(255,255,255,0.35)", width: 0.7 },
          }
        : undefined,
      customdata,
      hovertemplate:
        `<b>G${summary.global_id}</b><br>` +
        `Camera: %{customdata[1]}<br>` +
        `Class: %{customdata[2]}<br>` +
        `t=%{customdata[0]:.1f}s` +
        `<extra></extra>`,
    });

    legendSeen.add(segment.camera_label);
  }

  const startPoint = pathPoints[0];
  const endPoint = pathPoints[pathPoints.length - 1];
  traces.push(buildEndpointTrace("Start", startPoint, "#22c55e", showLabels));
  traces.push(buildEndpointTrace("End", endPoint, "#ef4444", showLabels));

  if (activeVehicle?.centroid) {
    traces.push({
      x: [activeVehicle.centroid[0]],
      y: [activeVehicle.centroid[1]],
      mode: showLabels ? "markers+text" : "markers",
      name: "Current Position",
      showlegend: true,
      marker: {
        size: 16,
        color: "#ffffff",
        symbol: "circle-open-dot",
        line: { color: "#3b82f6", width: 2 },
      },
      text: showLabels ? [`Now @ ${currentTimestamp.toFixed(1)}s`] : undefined,
      textposition: "top center",
      hovertemplate:
        `<b>Current replay position</b><br>` +
        `Camera State: ${activeVehicle.cameraStateLabel}<br>` +
        `t=${currentTimestamp.toFixed(1)}s` +
        `<extra></extra>`,
    });
  }

  const transitions = journey.transitions || [];
  if (transitions.length > 0) {
    traces.push({
      x: transitions.map((transition) => transition.centroid[0]),
      y: transitions.map((transition) => transition.centroid[1]),
      mode: showLabels ? "markers+text" : "markers",
      name: "Camera Change",
      showlegend: true,
      marker: {
        size: 14,
        color: TRANSITION_COLOR,
        symbol: "diamond",
        line: { color: "#0f172a", width: 2 },
      },
      text: showLabels
        ? transitions.map(
            (transition) =>
              `${transition.from_camera_label} -> ${transition.to_camera_label}<br>${transition.timestamp.toFixed(1)}s`,
          )
        : undefined,
      textposition: "top center",
      customdata: transitions.map((transition) => [
        transition.timestamp,
        transition.from_camera_label,
        transition.to_camera_label,
      ]),
      hovertemplate:
        `<b>Camera change</b><br>` +
        `%{customdata[1]} -> %{customdata[2]}<br>` +
        `t=%{customdata[0]:.1f}s` +
        `<extra></extra>`,
    });
  }

  const ranges = computeRanges(journey.bounds || null, pathPoints);
  const title = buildTitle(summary, activeVehicle);
  const annotations = [];

  if (transitions.length === 0) {
    annotations.push({
      xref: "paper",
      yref: "paper",
      x: 0.01,
      y: 0.99,
      xanchor: "left",
      yanchor: "top",
      text: `Camera unchanged: ${summary.current_camera_label} only`,
      showarrow: false,
      font: { size: 12, color: "#f6c56d", family: "Inter, sans-serif" },
      bgcolor: "rgba(12,26,46,0.78)",
      bordercolor: "rgba(245,158,11,0.35)",
      borderwidth: 1,
      borderpad: 6,
    });
  }

  const layout = createBaseLayout(title, {
    xRange: ranges.xRange,
    yRange: ranges.yRange,
    showLegend: true,
    annotations,
    margin: { l: 10, r: 10, t: 56, b: 10 },
  });

  Plotly.react(
    containerId,
    traces,
    layout,
    { responsive: true, displayModeBar: false },
  );
}

function renderMessage(containerId, title, message) {
  const layout = createBaseLayout(title, {
    annotations: [
      {
        xref: "paper",
        yref: "paper",
        x: 0.5,
        y: 0.5,
        xanchor: "center",
        yanchor: "middle",
        text: message,
        showarrow: false,
        font: { size: 15, color: "#c8d3e3", family: "Inter, sans-serif" },
        bgcolor: "rgba(12,26,46,0.8)",
        bordercolor: "rgba(255,255,255,0.08)",
        borderwidth: 1,
        borderpad: 12,
      },
    ],
  });

  Plotly.react(
    containerId,
    [],
    layout,
    { responsive: true, displayModeBar: false },
  );
}

function buildEndpointTrace(label, point, color, showLabels) {
  return {
    x: [point.centroid[0]],
    y: [point.centroid[1]],
    mode: showLabels ? "markers+text" : "markers",
    name: label,
    showlegend: true,
    marker: {
      size: 14,
      color,
      symbol: label === "Start" ? "triangle-up" : "square",
      line: { color: "#0f172a", width: 2 },
    },
    text: showLabels ? [`${label} ${point.timestamp.toFixed(1)}s`] : undefined,
    textposition: label === "Start" ? "bottom center" : "top center",
    hovertemplate:
      `<b>${label}</b><br>` +
      `Camera: ${point.camera_label}<br>` +
      `t=${point.timestamp.toFixed(1)}s` +
      `<extra></extra>`,
  };
}

function getCameraColor(cameraState) {
  if (!cameraState || cameraState.length === 0) return "#94a3b8";
  if (cameraState.length > 1) return "#f59e0b";
  return CAMERA_COLORS[cameraState[0]] || "#94a3b8";
}

function computeRanges(bounds, pathPoints) {
  if (bounds) {
    return {
      xRange: [
        clamp(bounds.xmin, MOSAIC_BOUNDS.xmin, MOSAIC_BOUNDS.xmax),
        clamp(bounds.xmax, MOSAIC_BOUNDS.xmin, MOSAIC_BOUNDS.xmax),
      ],
      yRange: [
        clamp(bounds.ymin, MOSAIC_BOUNDS.ymin, MOSAIC_BOUNDS.ymax),
        clamp(bounds.ymax, MOSAIC_BOUNDS.ymin, MOSAIC_BOUNDS.ymax),
      ],
    };
  }

  const xs = pathPoints.map((point) => point.centroid[0]);
  const ys = pathPoints.map((point) => point.centroid[1]);
  const padX = Math.max((Math.max(...xs) - Math.min(...xs)) * 0.2, 8);
  const padY = Math.max((Math.max(...ys) - Math.min(...ys)) * 0.2, 8);

  return {
    xRange: [
      clamp(Math.min(...xs) - padX, MOSAIC_BOUNDS.xmin, MOSAIC_BOUNDS.xmax),
      clamp(Math.max(...xs) + padX, MOSAIC_BOUNDS.xmin, MOSAIC_BOUNDS.xmax),
    ],
    yRange: [
      clamp(Math.min(...ys) - padY, MOSAIC_BOUNDS.ymin, MOSAIC_BOUNDS.ymax),
      clamp(Math.max(...ys) + padY, MOSAIC_BOUNDS.ymin, MOSAIC_BOUNDS.ymax),
    ],
  };
}

function buildTitle(summary, activeVehicle) {
  const suffix = activeVehicle
    ? ` - live replay now in ${activeVehicle.cameraStateLabel}`
    : "";
  return `Journey View - G${summary.global_id} - ${summary.journey.length} segment(s), ${summary.transition_count} camera change(s)${suffix}`;
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}
