import { MOSAIC_BOUNDS } from "./ground-plane.js";

export const MAP_CENTER = {
  x: (MOSAIC_BOUNDS.xmin + MOSAIC_BOUNDS.xmax) / 2,
  y: (MOSAIC_BOUNDS.ymin + MOSAIC_BOUNDS.ymax) / 2,
};

export const MAP_SIZE = {
  width: MOSAIC_BOUNDS.xmax - MOSAIC_BOUNDS.xmin,
  depth: MOSAIC_BOUNDS.ymax - MOSAIC_BOUNDS.ymin,
};

const CLASS_HEIGHTS = {
  Sedan: 1.5,
  "SUV / Hatchback": 1.8,
  "Pickup / Minitruck": 2.2,
  Truck: 3.1,
  Bus: 3.2,
  Motorcycle: 1.2,
  unknown: 1.6,
};

export function mapPointToWorld(point) {
  if (!point || point.length < 2) {
    return { x: 0, z: 0 };
  }

  return {
    x: point[0] - MAP_CENTER.x,
    z: point[1] - MAP_CENTER.y,
  };
}

export function footprintToWorldCorners(footprint) {
  if (!footprint || footprint.length !== 8) {
    return [];
  }

  const corners = [];
  for (let index = 0; index < 8; index += 2) {
    corners.push(mapPointToWorld([footprint[index], footprint[index + 1]]));
  }
  return corners;
}

export function centroidToWorld(centroid) {
  return mapPointToWorld(centroid);
}

export function computeVehicleTransform(footprint) {
  const corners = footprintToWorldCorners(footprint);

  if (corners.length !== 4) {
    return {
      corners: [],
      width: 1.8,
      length: 4.2,
      heading: 0,
      centroid: { x: 0, z: 0 },
    };
  }

  const centroid = {
    x: corners.reduce((sum, point) => sum + point.x, 0) / 4,
    z: corners.reduce((sum, point) => sum + point.z, 0) / 4,
  };

  const d01 = distance(corners[0], corners[1]);
  const d12 = distance(corners[1], corners[2]);
  const width = Math.max(Math.min(d01, d12), 0.9);
  const length = Math.max(Math.max(d01, d12), width + 0.2);

  const edge =
    d12 > d01
      ? {
          dx: corners[2].x - corners[1].x,
          dz: corners[2].z - corners[1].z,
        }
      : {
          dx: corners[1].x - corners[0].x,
          dz: corners[1].z - corners[0].z,
        };

  const heading = Math.atan2(edge.dx, edge.dz);

  return {
    corners,
    width,
    length,
    heading,
    centroid,
  };
}

export function getVehicleHeight(vehicleClass) {
  return CLASS_HEIGHTS[vehicleClass] || CLASS_HEIGHTS.unknown;
}

function distance(first, second) {
  const dx = second.x - first.x;
  const dz = second.z - first.z;
  return Math.sqrt(dx * dx + dz * dz);
}
