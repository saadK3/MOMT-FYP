/**
 * Coordinate Mapper — converts swapped EPSG:3857 coords to Three.js world.
 *
 * The data stores det_birdeye as [Y_merc, X_merc, Y_merc, X_merc, ...]
 * i.e. [northing, easting, northing, easting, ...]
 *
 * Three.js uses Y-up:
 *   Three X = easting  (data odd indices: 1, 3, 5, 7)
 *   Three Z = northing (data even indices: 0, 2, 4, 6)  — negated for correct orientation
 *   Three Y = height   (above ground)
 */

// Origin: center of the mosaic bounds (EPSG:3857)
const ORIGIN_EASTING = (-9072438.675959857 + -9072289.704694824) / 2; // data Y-values
const ORIGIN_NORTHING = (4252523.5462492965 + 4252623.142834548) / 2; // data X-values

// Vehicle heights by class (meters)
const CLASS_HEIGHTS = {
  Sedan: 1.5,
  "SUV / Hatchback": 1.8,
  "Pickup / Minitruck": 2.2,
  Truck: 3.0,
  Bus: 3.2,
  Motorcycle: 1.2,
  unknown: 1.5,
};

/**
 * Convert a det_birdeye array [n0,e0, n1,e1, n2,e2, n3,e3] to local 3D corners.
 * Returns array of 4 {x, z} objects (y is up, handled separately).
 */
export function footprintToCorners(birdeye) {
  const corners = [];
  for (let i = 0; i < 8; i += 2) {
    corners.push({
      x: birdeye[i + 1] - ORIGIN_EASTING, // easting → X
      z: -(birdeye[i] - ORIGIN_NORTHING), // northing → -Z (Three.js Z points "into screen")
    });
  }
  return corners;
}

/**
 * Convert a centroid [northing, easting] to Three.js {x, z}.
 */
export function centroidToLocal(centroid) {
  return {
    x: centroid[1] - ORIGIN_EASTING,
    z: -(centroid[0] - ORIGIN_NORTHING),
  };
}

/**
 * Compute vehicle dimensions and heading from 4 corners.
 */
export function computeVehicleGeometry(corners) {
  // Distances between consecutive corners
  const d01 = dist(corners[0], corners[1]);
  const d12 = dist(corners[1], corners[2]);

  // Width = shorter side, Length = longer side
  const width = Math.min(d01, d12);
  const length = Math.max(d01, d12);

  // Heading angle: direction of the longest edge
  let edge;
  if (d12 > d01) {
    edge = { dx: corners[2].x - corners[1].x, dz: corners[2].z - corners[1].z };
  } else {
    edge = { dx: corners[1].x - corners[0].x, dz: corners[1].z - corners[0].z };
  }
  const heading = Math.atan2(edge.dx, edge.dz);

  return { width, length, heading };
}

/**
 * Get vehicle height from class name (meters).
 */
export function getVehicleHeight(className) {
  return CLASS_HEIGHTS[className] || CLASS_HEIGHTS["unknown"];
}

function dist(a, b) {
  return Math.sqrt((b.x - a.x) ** 2 + (b.z - a.z) ** 2);
}
