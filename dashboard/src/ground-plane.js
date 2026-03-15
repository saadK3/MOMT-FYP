/**
 * Ground Plane renders active vehicles on the shared mosaic map.
 */

export const MOSAIC_BOUNDS = {
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
 * @param {string} containerId
 */
export function initPlot(containerId) {
  const layout = createBaseLayout("Ground Plane - Waiting for data...");
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
 * @param {number} timestamp
 */
export function render(containerId, vehicleManager, timestamp) {
  if (!plotInitialized) return;

  const vehicles = vehicleManager.getActive();
  const traces = [];

  if (showTrails) {
    for (const vehicle of vehicles) {
      if (vehicle.trail.length < 2) continue;
      const trailX = vehicle.trail.map((centroid) => centroid[0]);
      const trailY = vehicle.trail.map((centroid) => centroid[1]);
      const count = trailX.length;
      const opacities = trailX.map((_, index) => 0.15 + 0.6 * (index / (count - 1)));

      traces.push({
        x: trailX,
        y: trailY,
        mode: "lines+markers",
        line: { color: "rgba(255,255,255,0.18)", width: 2, dash: "dot" },
        marker: {
          size: 4,
          color: opacities.map((opacity) =>
            vehicle.color.replace(/[\d.]+\)$/, `${opacity})`),
          ),
          line: { color: "rgba(255,255,255,0.15)", width: 0.5 },
        },
        showlegend: false,
        hoverinfo: "skip",
      });
    }
  }

  for (const vehicle of vehicles) {
    const footprint = vehicle.footprint;
    if (!footprint || footprint.length !== 8) continue;

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

    traces.push({
      x,
      y,
      mode: showLabels ? "lines+text" : "lines",
      fill: "toself",
      fillcolor: vehicle.color,
      line: { color: vehicle.color, width: 2 },
      opacity: 0.85,
      text: showLabels ? [`G${vehicle.global_id}`] : undefined,
      textposition: "middle center",
      textfont: {
        size: 11,
        color: "white",
        family: "Inter, Arial Black, sans-serif",
      },
      name: `GID ${vehicle.global_id}`,
      customdata: [[
        vehicle.global_id,
        vehicle.cameraStateLabel || vehicle.camera.toUpperCase(),
        vehicle.track_id,
        vehicle.class,
        vehicle.hasCameraChanged ? "Yes" : "No",
      ]],
      hovertemplate:
        `<b>Global ID ${vehicle.global_id}</b><br>` +
        `Camera State: %{customdata[1]}<br>` +
        `Track: ${vehicle.track_id}<br>` +
        `Class: ${vehicle.class}<br>` +
        `Camera Changed: %{customdata[4]}` +
        `<extra></extra>`,
      showlegend: false,
    });
  }

  const title =
    vehicles.length > 0
      ? `Ground Plane - ${vehicles.length} vehicles @ t=${timestamp.toFixed(1)}s`
      : "Ground Plane - Waiting for data...";

  const layout = createBaseLayout(title);
  const config = { responsive: true, displayModeBar: false };
  Plotly.react(containerId, traces, layout, config);
}

/**
 * Shared base layout used by both live map and journey view.
 * @param {string} titleText
 * @param {object} options
 * @returns {object}
 */
export function createBaseLayout(titleText, options = {}) {
  const xRange = options.xRange || [MOSAIC_BOUNDS.xmin, MOSAIC_BOUNDS.xmax];
  const yRange = options.yRange || [MOSAIC_BOUNDS.ymin, MOSAIC_BOUNDS.ymax];
  const showLegend = Boolean(options.showLegend);

  const layout = {
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
      range: xRange,
      constrain: "range",
      showticklabels: false,
    },
    yaxis: {
      title: "",
      gridcolor: "rgba(255,255,255,0.04)",
      zerolinecolor: "rgba(255,255,255,0.04)",
      color: "#5a6d87",
      range: yRange,
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
    annotations: options.annotations || [],
    hovermode: "closest",
    showlegend: showLegend,
    plot_bgcolor: "rgba(0,0,0,0)",
    paper_bgcolor: "#060d18",
    font: { color: "#e8edf5" },
    margin: options.margin || { l: 10, r: 10, t: 40, b: 10 },
  };

  if (showLegend) {
    layout.legend = {
      orientation: "h",
      x: 0.01,
      y: 1.02,
      xanchor: "left",
      yanchor: "bottom",
      bgcolor: "rgba(6,13,24,0.78)",
      bordercolor: "rgba(255,255,255,0.08)",
      borderwidth: 1,
      font: { size: 11, color: "#c8d3e3", family: "Inter, sans-serif" },
    };
  }

  return layout;
}
