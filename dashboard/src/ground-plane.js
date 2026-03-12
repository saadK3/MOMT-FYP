/**
 * Ground Plane — renders vehicles on a Plotly scatter plot
 * with the mosaic background image.
 */

// Mosaic image bounds (EPSG:3857 / Web Mercator, metres)
const MOSAIC_BOUNDS = {
  xmin: 4252523.5462492965,
  xmax: 4252623.142834548,
  ymin: -9072438.675959857,
  ymax: -9072289.704694824,
};

let plotInitialized = false;
let showTrails = true;
let showLabels = true;

/**
 * Initialize Plotly with an empty plot + mosaic background.
 * @param {string} containerId  DOM element id
 */
export function initPlot(containerId) {
  const layout = buildLayout("Ground Plane — Waiting for data…");
  const config = { responsive: true, displayModeBar: false };
  Plotly.newPlot(containerId, [], layout, config);
  plotInitialized = true;
}

/**
 * Set toggle states.
 */
export function setTrails(enabled) {
  showTrails = enabled;
}
export function setLabels(enabled) {
  showLabels = enabled;
}

/**
 * Render current vehicle state on the ground plane.
 * @param {string} containerId
 * @param {import("./vehicle-manager").VehicleManager} vehicleManager
 * @param {number} timestamp  current simulation time
 */
export function render(containerId, vehicleManager, timestamp) {
  if (!plotInitialized) return;

  const vehicles = vehicleManager.getActive();
  const traces = [];

  // --- Trail traces (rendered first so they appear below) --------
  if (showTrails) {
    for (const v of vehicles) {
      if (v.trail.length < 2) continue;
      const trailX = v.trail.map((c) => c[0]);
      const trailY = v.trail.map((c) => c[1]);

      // Fading opacity: old positions more transparent
      const n = trailX.length;
      const opacities = trailX.map((_, i) => 0.15 + 0.6 * (i / (n - 1)));

      traces.push({
        x: trailX,
        y: trailY,
        mode: "lines+markers",
        line: { color: "rgba(255,255,255,0.18)", width: 2, dash: "dot" },
        marker: {
          size: 4,
          color: opacities.map((o) => v.color.replace(/[\d.]+\)$/, `${o})`)),
          line: { color: "rgba(255,255,255,0.15)", width: 0.5 },
        },
        showlegend: false,
        hoverinfo: "skip",
      });
    }
  }

  // --- Vehicle footprint traces ----------------------------------
  for (const v of vehicles) {
    const fp = v.footprint;
    if (!fp || fp.length !== 8) continue;

    const x = [fp[0], fp[2], fp[4], fp[6], fp[0]];
    const y = [fp[1], fp[3], fp[5], fp[7], fp[1]];

    traces.push({
      x,
      y,
      mode: showLabels ? "lines+text" : "lines",
      fill: "toself",
      fillcolor: v.color,
      line: { color: v.color, width: 2 },
      opacity: 0.85,
      text: showLabels ? [`G${v.global_id}`] : undefined,
      textposition: "middle center",
      textfont: {
        size: 11,
        color: "white",
        family: "Inter, Arial Black, sans-serif",
      },
      name: `GID ${v.global_id}`,
      customdata: [[v.global_id, v.camera, v.track_id, v.class]],
      hovertemplate:
        `<b>Global ID ${v.global_id}</b><br>` +
        `Camera: ${v.camera}<br>` +
        `Track: ${v.track_id}<br>` +
        `Class: ${v.class}` +
        `<extra></extra>`,
    });
  }

  // --- Update title ---
  const title =
    vehicles.length > 0
      ? `Ground Plane — ${vehicles.length} vehicles @ t=${timestamp.toFixed(1)}s`
      : `Ground Plane — Waiting for data…`;

  const layout = buildLayout(title);
  const config = { responsive: true, displayModeBar: false };

  Plotly.react(containerId, traces, layout, config);
}

/* ---- helpers ---- */

function buildLayout(titleText) {
  return {
    title: {
      text: titleText,
      font: { size: 16, color: "#8899b3", family: "Inter, sans-serif" },
      x: 0.01,
      xanchor: "left",
    },
    xaxis: {
      title: "",
      gridcolor: "rgba(255,255,255,0.04)",
      zerolinecolor: "rgba(255,255,255,0.04)",
      color: "#5a6d87",
      range: [MOSAIC_BOUNDS.xmin, MOSAIC_BOUNDS.xmax],
      constrain: "range",
      showticklabels: false,
    },
    yaxis: {
      title: "",
      gridcolor: "rgba(255,255,255,0.04)",
      zerolinecolor: "rgba(255,255,255,0.04)",
      color: "#5a6d87",
      range: [MOSAIC_BOUNDS.ymin, MOSAIC_BOUNDS.ymax],
      constrain: "range",
      scaleanchor: "x",
      showticklabels: false,
    },
    images: [
      {
        source: "clean_mosaic_3_feathered.png",
        x: MOSAIC_BOUNDS.xmin,
        y: MOSAIC_BOUNDS.ymax,
        sizex: MOSAIC_BOUNDS.xmax - MOSAIC_BOUNDS.xmin,
        sizey: MOSAIC_BOUNDS.ymax - MOSAIC_BOUNDS.ymin,
        xanchor: "left",
        yanchor: "top",
        xref: "x",
        yref: "y",
        layer: "below",
        sizing: "stretch",
        opacity: 0.8,
      },
    ],
    hovermode: "closest",
    showlegend: false,
    plot_bgcolor: "rgba(0,0,0,0)",
    paper_bgcolor: "#060d18",
    font: { color: "#e8edf5" },
    margin: { l: 10, r: 10, t: 40, b: 10 },
  };
}
